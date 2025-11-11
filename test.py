#!/usr/bin/env python3

from pyudev import Context, Monitor, MonitorObserver
import subprocess, os, time, signal, glob, threading

API_PORT = 8000
PROJECT_DIR = "/home/pi/Downloads/MT3900/src/drivers"
UVICORN_CMD = [
    "python", "-m", "uvicorn", "usb_camera:app",
    "--host", "0.0.0.0", "--port", str(API_PORT),
    "--app-dir", PROJECT_DIR
]

server_proc = None
debounce_lock = threading.Lock()  # ✅ 防止重复触发


def get_first_valid_camera() -> str | None:
    """
    总是获取 /dev/video* 中编号最小且能打开的那个
    """
    devs = sorted(glob.glob("/dev/video*"), key=lambda x: int(x.replace("/dev/video", "")))
    return devs[0] if devs else None


def stop_server():
    global server_proc
    if not server_proc:
        return

    print("🛑 停止 Camera API")

    server_proc.send_signal(signal.SIGTERM)
    try:
        server_proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        print("⚠️ uvicorn 未退出，kill -9")
        server_proc.kill()

    server_proc = None
    time.sleep(0.3)  # ✅ 给内核释放端口的时间


def start_server():
    global server_proc

    cam = get_first_valid_camera()
    if not cam:
        print("⚠️ 无可用摄像头，不启动 API")
        return

    print(f"🚀 启动 Camera API (设备={cam})")

    env = os.environ.copy()
    env["CAM_DEV"] = cam  # ✅ 动态绑定当前设备

    server_proc = subprocess.Popen(UVICORN_CMD, env=env)


def handle_event(_device):
    # ✅ 使用防抖，避免多次触发
    if not debounce_lock.acquire(blocking=False):
        return

    threading.Timer(0.3, debounce_lock.release).start()

    print("🔄 发生设备变更事件，重新扫描摄像头")

    stop_server()
    start_server()


if __name__ == "__main__":
    print("🔌 热插拔监听启动...")

    # ✅ 程序启动时就检查一次
    start_server()

    # ✅ 监听热插拔事件
    context = Context()
    monitor = Monitor.from_netlink(context)
    monitor.filter_by(subsystem="video4linux")

    observer = MonitorObserver(monitor, callback=handle_event)
    observer.start()

    # ✅ 主线程阻塞
    while True:
        time.sleep(1)
