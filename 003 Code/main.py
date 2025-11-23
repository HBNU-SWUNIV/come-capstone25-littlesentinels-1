#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from detection import main as run_detection, register_di_callback, register_di_callback2
from indy7 import indyCTL
from endeffector import MotorControl
from tof_sensor import ToF_Sensor

# --- 초기화 ---
indy = indyCTL(ip="192.168.0.6")
eff  = MotorControl()
tof  = ToF_Sensor()

# 동시 호출 방지용 락 & 상태 플래그
_seq_lock = threading.Lock()
_is_busy  = False


# ---------- ToF 유틸 ----------
def read_tof_mm(samples=5, timeout_s=2.0, method="mean"):
    """
    ToF를 여러 번 읽어 거리(mm) 반환.
    method: 'median' 또는 'mean'
    """
    if method == "median":
        d = tof.read_med_mm(samples=samples, timeout_s=timeout_s)
    else:
        d = tof.read_avg_mm(samples=samples, timeout_s=timeout_s)
    print(f"[ToF] 읽기({method}, n={samples}): {d if d is not None else 'None'} mm")
    return d


def adjust_to_target_distance_mm(target_mm=70, tol_mm=10,
                                 step_mm=60, max_iters=8,
                                 method="mean"):
    """
    현재 ToF 거리 기준으로 z축(툴 프레임)만 이동해서 target_mm ± tol_mm 범위에 수렴.
    - dist > target → 너무 멀다 → +z(접근)
    - dist < target → 너무 가깝다 → -z(후퇴)
    """
    for i in range(max_iters):
        dist = read_tof_mm(samples=4, timeout_s=1.2, method=method)
        if dist is None or dist <= 0:
            print("[ToF] 유효한 거리값이 없어 보정을 스킵합니다.")
            return False

        err = dist - target_mm
        print(f"[ToF] 현재={dist} mm, 목표={target_mm} mm, 오차={err} mm")

        if abs(err) <= tol_mm:
            print("[ToF] 목표 범위에 도달 (보정 완료)")
            return True

        # 이동량 결정 (최대 step_mm)
        if err > 0:
            # 멀다 → 접근(+z)
            z_mm = min(step_mm, err)
        else:
            # 가깝다 → 후퇴(-z)
            z_mm = -min(step_mm, -err)

        z_move_m = z_mm / 1000.0
        print(f"[ToF] z축 이동: {z_mm} mm ({z_move_m:.3f} m)")

        # 툴/작업 좌표계에서 z만 이동
        indy.indy.set_task_base(1)
        indy.indy.task_move_by([0.0, 0.0, z_move_m, 0.0, 0.0, 0.0])
        indy.indy.wait_for_move_finish()
        time.sleep(0.1)  # 관성/센서 안정화

    print("[ToF] 최대 보정 횟수 도달 (잔여 오차 허용)")
    return False


# ---------- 픽킹 시퀀스 ----------
def perform_pick_sequence(di: dict, angle: float,
                          spin_speed: int = 100,
                          t_F_reverse: float = 2.0,   # 첫 "열기"
                          t_S_reverses: float = 2.0,  # 마지막 "재열기"
                          pause: float = 1.0,
                          t_forward: float = 3.5,     # "닫기"
                          settle: float = 0.15,
                          target_mm: int = 70,
                          tol_mm: int = 10,
                          tof_method: str = "mean"):
    """
    1) 2차 접근·정렬 (indy.run)
    2) ToF 70 mm 거리 보정 (±tol)
    3) 엔드이펙터: 열기 → 닫기 → 다시 열기(마지막만 restore)
    """
    # 1) 접근·정렬
    indy.run(cam_x=di.get("X"), cam_y=di.get("Y"), cam_z=di.get("Z"), angle=angle)
    time.sleep(settle)  # 마지막 정렬 후 안정화

    # 2) ToF 거리 보정
    print("[ToF] 거리 보정 시작")
    adjust_to_target_distance_mm(target_mm=target_mm, tol_mm=tol_mm,
                                 step_mm=60, max_iters=8, method=tof_method)

    # 보정 후 최종 거리 한 번 더 출력
    _final = read_tof_mm(samples=4, timeout_s=1.2, method=tof_method)
    print(f"[ToF] 최종 거리 확인: {_final if _final is not None else 'None'} mm")

    # 3) 엔드이펙터 동작 (열기 → 닫기 → 다시 열기)
    eff.rotate_for(seconds=t_F_reverse, direction=+1, speed=spin_speed, restore_mode=False)
    time.sleep(pause)

    eff.rotate_for(seconds=t_forward, direction=-1, speed=spin_speed, restore_mode=False)
    time.sleep(pause)

    # 마지막 동작에서만 모드 복구
    eff.rotate_for(seconds=t_S_reverses, direction=+1, speed=spin_speed, restore_mode=True)
    time.sleep(1.0)


def perform_pick_sequence_async(di: dict, angle: float,
                                spin_speed: int = 100,
                                t_F_reverse: float = 2.0,
                                t_S_reverses: float = 2.0,
                                pause: float = 1.0,
                                t_forward: float = 3.5,
                                target_mm: int = 70,
                                tol_mm: int = 10,
                                tof_method: str = "mean"):
    global _is_busy

    def _worker():
        global _is_busy
        with _seq_lock:
            _is_busy = True
            try:
                perform_pick_sequence(
                    di, angle,
                    spin_speed=spin_speed,
                    t_F_reverse=t_F_reverse,
                    t_S_reverses=t_S_reverses,
                    pause=pause,
                    t_forward=t_forward,
                    settle=0.15,
                    target_mm=target_mm,
                    tol_mm=tol_mm,
                    tof_method=tof_method,
                )
            except Exception as e:
                print(f"[SEQ] error: {e}")
            finally:
                # 엔드이펙터 종료 후 항상 홈 복귀
                try:
                    time.sleep(0.15)
                    indy.indy.go_home()
                    indy.indy.wait_for_move_finish()
                except Exception as e:
                    print(f"[SEQ] home error: {e}")
                _is_busy = False

    if _is_busy:
        print("[SEQ] busy: skip this trigger")
        return
    threading.Thread(target=_worker, daemon=True).start()


# ---------- DI 콜백 ----------
def on_di(di: dict):
    print(
        "[Ripe XYZ] "
        f"X={di.get('X', float('nan')):.3f} m, "
        f"Y={di.get('Y', float('nan')):.3f} m, "
        f"Z={di.get('Z', float('nan')):.3f} m | "
        f"dist={di.get('distance_m', float('nan')):.3f} m"
    )
    indy.set_point(cam_x=di.get("X"), depth=di.get("Z"))


def on_di2(di: dict, angle):
    perform_pick_sequence_async(
        di, angle,
        spin_speed=100,
        t_F_reverse=2.0,
        t_S_reverses=2.0,
        pause=1.0,
        t_forward=3.5,
        target_mm=70,       # 70mm
        tol_mm=10,
        tof_method="mean"   # 평균값 사용
    )


# ---------- 엔트리 ----------
if __name__ == "__main__":
    register_di_callback(on_di)
    register_di_callback2(on_di2)
    try:
        run_detection()
    finally:
        try:
            eff.shutdown()
        except Exception:
            pass
        indy.close()
