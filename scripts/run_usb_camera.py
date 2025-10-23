from __future__ import annotations
import os
from pathlib import Path

from src.drivers.usb_camera import USBCameraDriver

OUT_DIR = Path(__file__).resolve().parent.parent / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    drv = USBCameraDriver(
        device_index=1,  # None=自动探测；也可写 0/1/2
        width=640,
        height=480,
        fps=10,
        jpeg_quality=85,
    )
    drv.open()
    print("✅ 摄像头已打开。开始采集 1 帧并保存到 out/ ...")

    m = drv.read()
    if m is None:
        print("❌ 读取失败")
        drv.close()
        return

    fname = OUT_DIR / "frame_0.jpg"
    with open(fname, "wb") as f:
        f.write(m.data)
    print(f"🖼️ 已保存: {fname}")
    print(f"meta: {m.meta}  timestamp: {m.timestamp}")

    # 再连续读取几帧以验证稳定性
    n = 10
    print(f"▶ 连续读取 {n} 帧（不保存）...")
    i = 0
    for frame in drv.iter_frames():
        i += 1
        if i >= n:
            break
    print("✅ 连续读取完成。")

    drv.close()
    print("🔚 已关闭摄像头。")


if __name__ == "__main__":
    main()
