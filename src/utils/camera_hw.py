# src/utils/camera_hw.py
# -*- coding: utf-8 -*-

from pathlib import Path
import cv2


def find_real_camera(max_index: int = 3) -> str | None:
    """
    在 /dev/video0..video{max_index-1} 中找一个真正能出图的摄像头。
    - 只看前几个节点，避免访问 /dev/video14/15 这种虚拟接口
    - 要求名字里包含 camera/webcam/uvc 之一
    """
    for i in range(max_index):
        devnode = f"/dev/video{i}"
        dev_path = Path(devnode)
        if not dev_path.exists():
            continue

        name_path = Path(f"/sys/class/video4linux/{dev_path.name}/name")
        if name_path.exists():
            name = name_path.read_text().strip().lower()
        else:
            name = ""

        if not any(k in name for k in ["camera", "webcam", "uvc"]):
            continue

        cap = cv2.VideoCapture(devnode)
        if not cap.isOpened():
            cap.release()
            continue

        ok, _ = cap.read()
        cap.release()
        if ok:
            print(f"🎯 Selected camera: {devnode} ({name})")
            return devnode

    print("❌ No real camera found")
    return None


def get_camera_metadata(devnode: str) -> dict:
    """
    读取摄像头的基本参数：名称 / 分辨率 / FPS
    """
    dev = Path(devnode)
    name_path = Path(f"/sys/class/video4linux/{dev.name}/name")
    if name_path.exists():
        name = name_path.read_text().strip()
    else:
        name = "USB Camera"

    cap = cv2.VideoCapture(devnode)
    if cap.isOpened():
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        cap.release()
    else:
        width, height, fps = 640, 480, 30

    return {
        "name": name,
        "resolution": f"{width}x{height}",
        "fps": fps,
    }


def get_camera_hw_id(devnode: str) -> dict:
    """
    读取摄像头背后的 USB 硬件 ID：
    - vendor (idVendor)
    - product (idProduct)
    - serial (serial)
    后面会用它们拼出一个稳定的 AAS ID。
    """
    dev = Path(devnode)
    base = Path(f"/sys/class/video4linux/{dev.name}/device")

    def read_field(fname: str) -> str | None:
        p = base / fname
        return p.read_text().strip() if p.exists() else None

    return {
        "vendor": read_field("idVendor"),
        "product": read_field("idProduct"),
        "serial": read_field("serial"),
    }
