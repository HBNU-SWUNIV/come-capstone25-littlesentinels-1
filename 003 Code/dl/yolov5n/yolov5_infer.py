# yolov5_infer.py
import torch
import cv2
import numpy as np
import os
import sys

from models.common import DetectMultiBackend
from utils.general import non_max_suppression, scale_boxes
from utils.dataloaders import letterbox 

class YOLOv5nInfer:
    def __init__(self, model_path='best.pt', device='cpu'):
        self.device = torch.device(device)
        self.model = DetectMultiBackend(model_path, device=self.device)
        self.model.eval()

    def __call__(self, image_np, frame_idx=None):
        img0 = image_np.copy()
        img = letterbox(img0, new_shape=640)[0]
        img = img.transpose((2, 0, 1))[::-1]  # HWC to CHW, BGR to RGB
        img = np.ascontiguousarray(img)

        img_tensor = torch.from_numpy(img).to(self.device).float() / 255.0
        img_tensor = img_tensor.unsqueeze(0)

        with torch.no_grad():
            pred = self.model(img_tensor)[0]
            pred = non_max_suppression(pred, 0.25, 0.45)[0]

        if pred is not None and len(pred):
            pred[:, :4] = scale_boxes(img_tensor.shape[2:], pred[:, :4], img0.shape).round()

            # for *xyxy, conf, cls in pred:
            #     print(f"[Frame {frame_idx}] Detected: {xyxy} | Confidence: {conf:.2f}")

        return pred