# utils/camera_detect.py

from pathlib import Path
import cv2

def find_real_camera():
    """
    只检查前 3 个：/dev/video0 /dev/video1 /dev/video2
    完全不会尝试 video14/15/21 这种虚拟节点
    """
    for i in range(3):   # 只看前三个
        dev = f"/dev/video{i}"

        if not Path(dev).exists():
            continue

        name_path = Path(f"/sys/class/video4linux/video{i}/name")
        if name_path.exists():
            name = name_path.read_text().strip().lower()
        else:
            name = ""

        # 名字必须包含 camera/webcam/uvc
        if not any(k in name for k in ["camera", "webcam", "uvc"]):
            continue

        import cv2
        cap = cv2.VideoCapture(dev)
        if cap.isOpened():
            ok, _ = cap.read()
            cap.release()
            if ok:
                print(f"🎯 Selected real camera: {dev} ({name})")
                return dev

    print("❌ No real camera found")
    return None



def get_camera_metadata(devnode):
    """Probe resolution, fps, name"""
    cap = cv2.VideoCapture(devnode)
    if not cap.isOpened():
        return {}

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    # read name from sysfs
    name_path = f"/sys/class/video4linux/{Path(devnode).name}/name"
    if Path(name_path).exists():
        name = Path(name_path).read_text().strip()
    else:
        name = "USB Camera"

    cap.release()

    return {
        "name": name,
        "resolution": f"{width}x{height}",
        "fps": fps
    }
