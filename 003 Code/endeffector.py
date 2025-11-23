#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
End Effector (OpenCR + Dynamixel) Controller

- 프로그래매틱 제어(권장):
    from endeffector import MotorControl
    eff = MotorControl()
    eff.rotate_for(seconds=4.0, direction=-1, speed=100)  # 역방향 4초
    eff.rotate_for(seconds=4.0, direction=+1, speed=100)  # 정방향 4초
    eff.shutdown()

- 인터랙티브 모드(단독 실행 시):
    python3 endeffector.py
    키보드:
      'a' : 정방향 연속 회전 시작
      'f' : 역방향 연속 회전 시작
      'c' : 회전 정지
      'r' : 100도 위치로 리셋(포지션 모드)
      'q' : 종료
"""

import sys
import os
import time
import termios
import tty
import select
sys.path.append('/home/dfx')
from opencr.opencr_firmware.libraries.peripheral._opencr import OpenCRSerial


class MotorControl:
    def __init__(
        self,
        center_motor_id: int = 16,
        possible_device_ports=None,
        baud_rate: int = 57600,
        serial_timeout: float = 1.0,
        device_address: int = 0xF0,
    ):
        """
        :param center_motor_id: 센터 모터 ID
        :param possible_device_ports: 시도할 시리얼 포트 리스트
        :param baud_rate: 시리얼 보드레이트
        :param serial_timeout: 시리얼 타임아웃(초)
        :param device_address: OpenCR 장치 주소
        """
        if possible_device_ports is None:
            possible_device_ports = ['/dev/ttyACM0', '/dev/ttyACM1']

        self.CENTER_MOTOR_ID = center_motor_id
        self.possible_device_ports = possible_device_ports
        self.connected_device_port = None
        self.baud_rate = baud_rate
        self.serial_timeout = serial_timeout
        self.device_address = device_address
        self.opencr_serial: OpenCRSerial = None

        # 현재 모터 각도(도 단위), 0~200도 맵핑 가정(사용자 코드 기준)
        self.center_position = 0.0

        # 연결 & 초기화
        self.connect()
        self.initialize_current_position()

    # ------------------------- 연결/초기화 -------------------------

    def connect(self):
        for device_port in self.possible_device_ports:
            try:
                self.opencr_serial = OpenCRSerial(
                    device_port,
                    self.baud_rate,
                    self.serial_timeout,
                    self.device_address,
                )
                self.connected_device_port = device_port
                print(f"[OpenCR] Connected to {device_port}")

                # 모터 초기화 (사용자 코드 기준: 200도 범위, 프로토콜 0)
                self.opencr_serial.dxl_init(self.CENTER_MOTOR_ID, 200, 0)

                # 기본은 토크 온 + 포지션 모드로 시작
                self._set_position_mode()
                print("[OpenCR] Center motor initialized (Position mode, torque ON)")
                return True

            except Exception as connection_error:
                print(f"[OpenCR] Failed to connect to {device_port}: {connection_error}")
                continue

        raise RuntimeError("[OpenCR] No available /dev/ttyACM* device found.")

    def initialize_current_position(self):
        try:
            center_pos = self.opencr_serial.dxl_getPresentPositionData(self.CENTER_MOTOR_ID)
            # 사용자 코드 기준: 0~1023 -> 0~200도
            self.center_position = float(center_pos) * 200.0 / 1023.0
            print(f"[OpenCR] Initialized center position: {self.center_position:.1f}°")
        except Exception as e:
            print(f"[OpenCR] Warning: Could not read current motor position: {e}")
            print("[OpenCR] Starting from 0 degrees")
            self.center_position = 0.0

    # ------------------------- 내부 유틸 -------------------------

    def _set_velocity_mode(self):
        """Velocity 모드(1)로 전환"""
        self.opencr_serial.dxl_torqueOff(self.CENTER_MOTOR_ID)
        self.opencr_serial.dxl_setOperatingMode(self.CENTER_MOTOR_ID, 1)
        self.opencr_serial.dxl_torqueOn(self.CENTER_MOTOR_ID)

    def _set_position_mode(self):
        """Position 모드(3)로 전환"""
        self.opencr_serial.dxl_torqueOff(self.CENTER_MOTOR_ID)
        self.opencr_serial.dxl_setOperatingMode(self.CENTER_MOTOR_ID, 3)
        self.opencr_serial.dxl_torqueOn(self.CENTER_MOTOR_ID)

    # ------------------------- 프로그래매틱 제어 API -------------------------

    def rotate_for(self, seconds: float, direction: int = 1, speed: int = 100, restore_mode: bool = True):
        """
        지정 시간(seconds) 동안 연속 회전 후 정지.
        :param seconds: 회전 시간(초)
        :param direction: 1(정방향), -1(역방향)
        :param speed: 목표 속도(라이브러리 단위)
        :param restore_mode: True면 종료 후 Position 모드로 복원
        """
        seconds = max(0.0, float(seconds))
        direction = 1 if direction >= 0 else -1
        speed_val = int(abs(speed)) * direction

        try:
            self._set_velocity_mode()
            print(f"[EE] Rotate {('CW' if direction>0 else 'CCW')} for {seconds:.2f}s @ {abs(speed)}")
            self.opencr_serial.dxl_goalVelocity(self.CENTER_MOTOR_ID, speed_val)
            time.sleep(seconds)
        finally:
            # 반드시 정지
            self.opencr_serial.dxl_goalVelocity(self.CENTER_MOTOR_ID, 0)
            if restore_mode:
                self._set_position_mode()
            print("[EE] Rotation stopped")

    def stop(self):
        try:
            self.opencr_serial.dxl_goalVelocity(self.CENTER_MOTOR_ID, 0)
            print("[EE] Stop command sent")
        except Exception as e:
            print(f"[EE] Stop error: {e}")

    def shutdown(self):
        try:
            self.stop()
        finally:
            try:
                self.opencr_serial.dxl_torqueOff(self.CENTER_MOTOR_ID)
                print("[OpenCR] Torque OFF")
            except Exception:
                pass

    # ------------------------- 인터랙티브(옵션) -------------------------

    def start_center_motor_rotation(self, direction: int = 1, speed: int = 100):
        try:
            dir_text = "정방향" if direction == 1 else "역방향"
            print(f"[EE] 센터 모터 {dir_text} 연속 회전 시작")

            self._set_velocity_mode()
            self.opencr_serial.dxl_goalVelocity(self.CENTER_MOTOR_ID, int(speed) * direction)

            print(f"  Motor ID: {self.CENTER_MOTOR_ID}")
            print(f"  Rotation speed: {int(speed) * direction}")
            print(f"  Press 'c' to stop rotation")

        except Exception as e:
            print(f"  Error starting center motor rotation: {e}")

    def stop_center_motor_rotation(self):
        try:
            print("[EE] Stopping center motor rotation...")
            self.opencr_serial.dxl_goalVelocity(self.CENTER_MOTOR_ID, 0)
            time.sleep(0.3)
            self._set_position_mode()
            print(f"  Motor ID: {self.CENTER_MOTOR_ID}")
            print(f"  Rotation stopped")
        except Exception as e:
            print(f"  Error stopping center motor: {e}")

    def reset_center_motor(self, target_angle: float = 100.0):
        try:
            target_angle = float(target_angle)
            position_value = int(target_angle * 1023.0 / 200.0)  # 0~200도 맵핑 가정

            print(f"[EE] Resetting center motor to {target_angle:.1f} degrees")
            print(f"  Motor ID: {self.CENTER_MOTOR_ID}")
            print(f"  Target position value: {position_value}")

            self._set_position_mode()
            self.opencr_serial.dxl_goalPosition(self.CENTER_MOTOR_ID, position_value)
            print("  Reset command sent successfully")

            self.center_position = target_angle

        except Exception as e:
            print(f"  Error resetting center motor: {e}")

    def check_motor_status(self):
        """현재 위치/각도 출력"""
        print("\n=== Motor Status Check ===")
        try:
            center_pos = self.opencr_serial.dxl_getPresentPositionData(self.CENTER_MOTOR_ID)
            center_angle = float(center_pos) * 200.0 / 1023.0
            print(f"Center Motor (ID {self.CENTER_MOTOR_ID}): Position={center_pos}, Angle={center_angle:.1f}°")
        except Exception as e:
            print(f"Error checking motor status: {e}")
        print("========================\n")

    # ------------------------- 키보드 헬퍼(인터랙티브 전용) -------------------------

    def _get_key_nonblock(self):
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None

    def run(self):
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())

            print("\n=== 엔드이펙터 수동 제어 ===")
            print("Press 'a': Start center motor (정방향)")
            print("Press 'f': Start center motor (역방향)")
            print("Press 'c': Stop center motor rotation")
            print("Press 'r': Reset center motor to 100° position")
            print("Press 'q': Quit program")
            print("===========================\n")

            print(f"\nCurrent motor position (deg, approx): {self.center_position:.1f}°")
            self.check_motor_status()

            while True:
                key = self._get_key_nonblock()

                if key == 'a':
                    self.start_center_motor_rotation(direction=1, speed=100)
                elif key == 'f':
                    self.start_center_motor_rotation(direction=-1, speed=100)
                elif key == 'c':
                    self.stop_center_motor_rotation()
                elif key == 'r':
                    self.reset_center_motor(100.0)
                elif key == 'q':
                    print("\n[EE] Stop interactive mode")
                    break

                time.sleep(0.01)

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            self.shutdown()
            print("[EE] Motor control session closed")


if __name__ == "__main__":
    try:
        motor_control = MotorControl()
        motor_control.run()
    except KeyboardInterrupt:
        print("\n[EE] Program interrupted by user")
    except Exception as e:
        print(f"[EE] Error: {e}")
