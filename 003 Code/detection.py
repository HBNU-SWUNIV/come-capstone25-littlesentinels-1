import pyrealsense2 as rs
import numpy as np
import cv2
import os
import sys
import torch
import time
import math
import subprocess
import json

from util.generate_instance_mask import generate_instance_mask
from util.classify_strawberry_maturity import classify_strawberry_maturity
from util.extract_centerline_and_picking_points import extract_centerline_and_picking_points
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# -------------------- 경로 설정 --------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'dl', 'yolov5n'))
sys.path.insert(0, os.path.join(BASE_DIR, 'dl', 'MobileNetV3_UNet'))

from dl.MobileNetV3_UNet.seg_infer import load_segmentation_model, infer_segmentation_on_crop
from dl.yolov5n.yolov5_infer import YOLOv5nInfer

# -------------------- 모델 및 장치 초기화 --------------------
yolo_model_path = 'dl/yolov5n/best.pt'
seg_model_path = 'dl/MobileNetV3_UNet/checkpoints/best_model.pth'
DEVICE = 'cuda'

print("[INFO] 모델 로딩 중...")
yolo_model = YOLOv5nInfer(model_path=yolo_model_path, device=DEVICE)
seg_model = load_segmentation_model(seg_model_path)

# -------------------- RealSense 설정 --------------------
pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

ctx = rs.context()
device = ctx.query_devices()[0]
depth_sensor = device.first_depth_sensor()

preset_map = {
    'default': 1,
    'high_accuracy': 3,
    'high_density': 4,
    'medium_density': 5
}
depth_sensor.set_option(rs.option.visual_preset, preset_map['high_accuracy'])
depth_sensor.set_option(rs.option.laser_power, 240.0)
depth_sensor.set_option(rs.option.exposure, 8500.0)
depth_sensor.set_option(rs.option.gain, 16.0)

profile = pipeline.start(config)
align = rs.align(rs.stream.color)

# -------------------- DI 콜백/상태 훅 --------------------
_DI_CB = None       # 외부(main.py)에서 등록하는 콜백
_LAST_DI = None     # 마지막 Ripe 포인트의 3D 결과(dict) 저장

_DI_CB_2 = None

# -------------------- Indy mode --------------------
indy_mode = 1

def register_di_callback(func):
    """외부(main.py)에서 di(dict)를 받는 콜백을 등록"""
    global _DI_CB
    _DI_CB = func

def register_di_callback2(func):
    """외부(main.py)에서 di(dict)를 받는 콜백을 등록"""
    global _DI_CB_2
    _DI_CB_2 = func

# -------------------- 유틸 함수 --------------------
def pixel_to_meter(x, y, depth_mm, fx=615, fy=615, cx=320, cy=240):
    z = depth_mm / 1000.0
    x_m = (x - cx) * z / fx
    y_m = (y - cy) * z / fy
    return x_m, y_m, z


def get_mean_valid_depth_in_mask(depth_frame, mask, padding=6):
    depth = np.asanyarray(depth_frame.get_data())
    kernel = np.ones((padding * 2 + 1, padding * 2 + 1), np.uint8)
    eroded_mask = cv2.erode(mask.astype(np.uint8), kernel, iterations=1)
    valid_mask = (depth > 0) & np.isfinite(depth)
    masked_depth = depth[(eroded_mask == 1) & valid_mask]
    if masked_depth.size > 0:
        return float(np.mean(masked_depth))
    return None


def compute_angle(tip, midpoint):
    dx = midpoint[0] - tip[0]
    dy = tip[1] - midpoint[1]
    angle_rad = np.arctan2(dx, dy)
    return np.degrees(angle_rad)

def angles_from_pixel(depth_frame, u=200, v=200):
    w = depth_frame.get_width()
    h = depth_frame.get_height()
    u = int(max(0, min(w - 1, round(u))))
    v = int(max(0, min(h - 1, round(v))))
    z = depth_frame.get_distance(u, v)
    if z <= 0:
        return None

    # 반드시 "depth 프레임의" intrinsics 사용
    depth_vsp  = depth_frame.get_profile().as_video_stream_profile()
    depth_intr = depth_vsp.get_intrinsics()
    X, Y, Z = rs.rs2_deproject_pixel_to_point(depth_intr, [u, v], z)
    print(depth_intr)

    theta = math.degrees(math.atan2(math.hypot(X, Y), Z))
    yaw   = math.degrees(math.atan2(X, Z))
    pitch = math.degrees(math.atan2(-Y, math.hypot(X, Z)))
    return dict(distance_m=z, X=X, Y=Y, Z=Z,
                theta_deg=theta, yaw_deg=yaw, pitch_deg=pitch)

def put_text_bg(img, text, org, scale=0.5, thickness=1, fg=(255,255,255), bg=(0,0,0)):
    """가독성을 위해 텍스트 뒤에 배경 박스를 깔아주는 헬퍼"""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (w, h), base = cv2.getTextSize(text, font, scale, thickness)
    x, y = org
    # 배경 박스
    cv2.rectangle(img, (x, y - h - base - 4), (x + w + 6, y + 4), bg, -1)
    # 텍스트
    cv2.putText(img, text, (x + 3, y - 3), font, scale, fg, thickness, cv2.LINE_AA)

def send_data_to_subprocess(task, n_total = None, n_mature = None):    
    try:
        data = {"Task": task,
                "Total": n_total,
                "Mature": n_mature}

        json_data = json.dumps(data) + "\n"
        process.stdin.write(json_data)
        process.stdin.flush()
        print(f"[INFO] 데이터 전송 완료: {json_data.strip()}")
        
    except Exception as e:
        print(f"[ERROR] subprocess에 데이터 전송 중 오류 발생: {e}")

# subprocess로 firebase 연결
print("[INFO] subprocess 시작")
ENV_PYTHON = "" # subprocess에서 사용할 python 경로
APP_SCRIPT = "app.py" # app.py 경로

process = subprocess.Popen(
    [ENV_PYTHON, APP_SCRIPT],
    stdin=subprocess.PIPE,
    stdout=sys.stdout,
    stderr=sys.stderr,
    text=True
)

# -------------------- 메인 루프 --------------------
def main():
    global _LAST_DI, indy_mode  # 함수 내에서 갱신하기 위해 global 선언

    frame_idx = 0
    prev_time = time.time()
    start_time = None
    total_frames = 0

    is_first = True
    n_mature = 0
    n_harvest = 0

    print("[INFO] 실시간 딸기 탐지 시작... 'q' 종료, '1' 현재 Ripe XYZ 출력")

    while True:
        frames = pipeline.wait_for_frames()
        frames = align.process(frames)
        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        if not color_frame or not depth_frame:
            # 공통 키 처리 (q/1)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('1'):
                if _LAST_DI is not None:
                    if _DI_CB is not None:
                        try:
                            _DI_CB(_LAST_DI)
                        except Exception as e:
                            print(f"[WARN] DI callback error: {e}")
                    else:
                        d = _LAST_DI
                        print(f"[Ripe XYZ] X={d.get('X', float('nan')):.3f} m, "
                              f"Y={d.get('Y', float('nan')):.3f} m, "
                              f"Z={d.get('Z', float('nan')):.3f} m "
                              f"(dist={d.get('distance_m', float('nan')):.3f} m)")
                else:
                    print("[INFO] 아직 Ripe 포인트가 감지되지 않았어.")
            continue

        image = np.asanyarray(color_frame.get_data())
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        binary_mask = np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)

        preds = yolo_model(image, frame_idx)
        if preds is None or len(preds) == 0:
            cv2.imshow("Strawberry Detection", image)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('1'):
                if _LAST_DI is not None:
                    if _DI_CB is not None:
                        try:
                            _DI_CB(_LAST_DI)
                        except Exception as e:
                            print(f"[WARN] DI callback error: {e}")
                    else:
                        d = _LAST_DI
                        print(f"[Ripe XYZ] X={d.get('X', float('nan')):.3f} m, "
                              f"Y={d.get('Y', float('nan')):.3f} m, "
                              f"Z={d.get('Z', float('nan')):.3f} m "
                              f"(dist={d.get('distance_m', float('nan')):.3f} m)")
                else:
                    print("[INFO] 아직 Ripe 포인트가 감지되지 않았어.")
            continue

        # ---------------- YOLO + Segmentation 시각화 ----------------
        for (*xyxy, conf, cls) in preds:
            x1 = max(int(xyxy[0].item()), 0)
            y1 = max(int(xyxy[1].item()), 0)
            x2 = min(int(xyxy[2].item()), image.shape[1])
            y2 = min(int(xyxy[3].item()), image.shape[0])

            # 바운딩 박스 표시
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)

            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            mask = infer_segmentation_on_crop(crop_rgb, seg_model, device=DEVICE)
            mask_resized = cv2.resize(mask, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)

            # 세그멘테이션 결과 시각화
            mask_overlay = np.zeros_like(crop)
            mask_overlay[mask_resized == 1] = [0, 0, 255]  # 빨간색 마스크
            blended = cv2.addWeighted(crop, 0.7, mask_overlay, 0.3, 0)
            image[y1:y2, x1:x2] = blended

            # 바이너리 마스크 통합
            binary_mask[y1:y2, x1:x2][mask_resized == 1] = 255

        # ---------------- 인스턴스 마스크, 성숙도 분석 ----------------
        instance_mask = generate_instance_mask(binary_mask)
        instance_centers = []
        for inst_id in np.unique(instance_mask):
            if inst_id == 0:
                continue
            mask = (instance_mask == inst_id)
            ys, xs = np.where(mask)
            center_x = int(np.mean(xs))
            center_y = int(np.mean(ys))
            instance_centers.append((inst_id, center_x, center_y))

        instance_centers.sort(key=lambda x: x[1])

        # 최초 1회에는 전체 숙성 딸기수 계산
        if is_first == True:
            for inst_id, cx, cy in instance_centers:
                mask = (instance_mask == inst_id)
                maturity = classify_strawberry_maturity(hsv_image, mask)

                if maturity == 'fully_ripe':
                    n_mature += 1

            # subprocess로 데이터 전송
            send_data_to_subprocess(f"init_data", len(instance_centers), n_mature)
            send_data_to_subprocess(f"init_log", len(instance_centers), n_mature)
            is_first = False
            continue

        # 수확 시작
        for inst_id, cx, cy in instance_centers:
            mask = (instance_mask == inst_id)
            maturity = classify_strawberry_maturity(hsv_image, mask)
            if maturity == 'fully_ripe':
                tip, midpoint, picking_pts = extract_centerline_and_picking_points(mask.astype(np.uint8))
                if tip is not None and midpoint is not None and len(picking_pts) == 2:
                    angle = compute_angle(tip, midpoint)
                    depth_value = get_mean_valid_depth_in_mask(depth_frame, mask.astype(np.uint8))
                    
                    if depth_value is not None:
                        left_pt, right_pt = picking_pts
                        left_xyz = pixel_to_meter(*left_pt, depth_value)
                        right_xyz = pixel_to_meter(*right_pt, depth_value)

                        # Center 픽셀 좌표 계산
                        center_x = int((left_pt[0] + right_pt[0]) / 2)
                        center_y = int((left_pt[1] + right_pt[1]) / 2)

                        message = {
                            "left": {"x": round(left_xyz[0], 3), "y": round(left_xyz[1], 3), "z": round(left_xyz[2], 3)},
                            "right": {"x": round(right_xyz[0], 3), "y": round(right_xyz[1], 3), "z": round(right_xyz[2], 3)},
                            "angle": round(angle, 2),
                            "center_pixel": {"x": center_x, "y": center_y}
                        }

                        # ---- 정보 텍스트 (좌측 상단) ----
                        text_y = 50
                        cv2.putText(image, f"Angle: {message['angle']} deg", (10, text_y),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
                        text_y += 25
                        cv2.putText(image, f"Left (x:{message['left']['x']}, y:{message['left']['y']}, z:{message['left']['z']})",
                                    (10, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
                        text_y += 25
                        cv2.putText(image, f"Right (x:{message['right']['x']}, y:{message['right']['y']}, z:{message['right']['z']})",
                                    (10, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
                        text_y += 25
                        cv2.putText(image, f"Center pixel: ({center_x}, {center_y})", (10, text_y),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2, cv2.LINE_AA)  

                        # 센터 점
                        cv2.circle(image, (center_x, center_y), 6, (0, 255, 0), -1)
                        cv2.putText(image, "Center", (center_x + 10, center_y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                        # 깊이 텍스트
                        cv2.putText(image, f"{depth_value/10:.1f} cm", (cx, cy - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                    # 중심점 및 Ripe 표시 + 3D 좌표 오버레이
                    di = angles_from_pixel(depth_frame=depth_frame, u=cx, v=cy)
                    cv2.circle(image, (cx, cy), 4, (0, 0, 255), -1)
                    cv2.putText(image, "Ripe", (cx + 10, cy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                    if di is not None:
                        # 최신 di 저장 (키 '1' 입력 시 사용)
                        _LAST_DI = di

                        # --- 화면에 X/Y/Z + dist를 선명하게 표시 (검은 배경 + 흰 글씨) ---
                        # 화면 밖으로 나가지 않도록 위치 보정
                        tx = min(cx + 12, image.shape[1] - 160)
                        ty = min(cy + 20, image.shape[0] - 10)
                        put_text_bg(image, f"X={di['X']:.3f} m", (tx, ty))
                        put_text_bg(image, f"Y={di['Y']:.3f} m", (tx, ty + 20))
                        put_text_bg(image, f"Z={di['Z']:.3f} m", (tx, ty + 40))
                        put_text_bg(image, f"d={di['distance_m']:.3f} m", (tx, ty + 60))
                    
                break
        
        # ---------------- FPS 계산 및 표시 ----------------
        if start_time is None:
            start_time = time.time()
        frame_idx += 1
        curr_time = time.time()
        elapsed = curr_time - prev_time
        fps = 1.0 / elapsed if elapsed > 0 else 0
        prev_time = curr_time
        total_frames += 1
        total_elapsed = curr_time - start_time
        avg_fps = total_frames / total_elapsed if total_elapsed > 0 else 0

        cv2.putText(image, f"FPS: {fps:.2f} (avg {avg_fps:.2f})",
                    (10, image.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 2, cv2.LINE_AA)

        # ---------------- 영상 표시 및 키 입력 ----------------
        cv2.imshow("Strawberry Detection", image)
        key = cv2.waitKey(1) & 0xFF


        # ---------------- Indy7 제어 ----------------
        if indy_mode == 2:
            if _LAST_DI is not None:
                if _DI_CB_2 is not None:
                    try:
                        _DI_CB_2(_LAST_DI, angle)
                        n_harvest += 1
                        send_data_to_subprocess("count")
                    except Exception as e:
                        print(f"[WARN] DI callback error: {e}")
                else:
                    d = _LAST_DI
                    print(f"[Ripe XYZ] X={d.get('X', float('nan')):.3f} m, "
                            f"Y={d.get('Y', float('nan')):.3f} m, "
                            f"Z={d.get('Z', float('nan')):.3f} m "
                            f"(dist={d.get('distance_m', float('nan')):.3f} m)")
            else:
                print("[INFO] 아직 Ripe 포인트가 감지되지 않았어.")

            indy_mode = 1

        if key == ord('q'):
            break
        elif key == ord('1'):
            if _LAST_DI is not None:
                if _DI_CB is not None:
                    try:
                        _DI_CB(_LAST_DI)
                        indy_mode = 2
                    except Exception as e:
                        print(f"[WARN] DI callback error: {e}")
                else:
                    d = _LAST_DI
                    print(f"[Ripe XYZ] X={d.get('X', float('nan')):.3f} m, "
                          f"Y={d.get('Y', float('nan')):.3f} m, "
                          f"Z={d.get('Z', float('nan')):.3f} m "
                          f"(dist={d.get('distance_m', float('nan')):.3f} m)")
            else:
                print("[INFO] 아직 Ripe 포인트가 감지되지 않았어.")

    pipeline.stop()
    send_data_to_subprocess("clear")
    process.terminate()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()

