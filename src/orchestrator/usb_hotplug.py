# src/orchestrator/usb_hotplug.py

from pyudev import Context, Monitor, MonitorObserver
import subprocess, time, os, signal, glob, threading

PROJECT_DIR = "/home/pi/Downloads/MT3900/src/drivers"
API_PORT = "8000"
UVICORN_CMD = ["python", "-m", "uvicorn", "camera_driver:app",
               "--host", "0.0.0.0", "--port", API_PORT,
               "--app-dir", PROJECT_DIR]

server_proc = None
debounce_lock = threading.Lock()


def get_first_valid_camera():
    devs = sorted(glob.glob("/dev/video*"))
    return devs[0] if devs else None


def start_api():
    global server_proc
    cam = get_first_valid_camera()
    if not cam:
        print("⚠️ no camera available")
        return

    print(f"🚀 start API (device={cam})")

    env = os.environ.copy()
    env["CAM_DEV"] = cam

    server_proc = subprocess.Popen(UVICORN_CMD, env=env)


def stop_api():
    global server_proc
    if not server_proc:
        return

    print("🛑 stop API")
    server_proc.send_signal(signal.SIGTERM)

    try:
        server_proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        print("⚠️ force kill uvicorn")
        server_proc.kill()

    server_proc = None
    time.sleep(0.3)


def handle_event(_device):
    if not debounce_lock.acquire(blocking=False):
        return

    threading.Timer(0.2, debounce_lock.release).start()

    stop_api()
    start_api()


def run_hotplug():
    start_api()

    context = Context()
    monitor = Monitor.from_netlink(context)
    monitor.filter_by(subsystem="video4linux")

    observer = MonitorObserver(monitor, callback=handle_event)
    observer.start()

    while True:
        time.sleep(1)
