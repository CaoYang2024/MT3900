# src/drivers/csi_camera.py
import subprocess
import threading
import time

class CSICamera:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        self.buffer = b""  # 存最新 jpeg 帧

    def start(self):
        """启动 rpicam-vid，只启动一次"""
        if self.process:
            return

        self.process = subprocess.Popen(
            [
                "rpicam-vid",
                "--codec", "mjpeg",
                "--inline",
                "--timeout", "0",
                "--framerate", "30",
                "--width", "1280",
                "--height", "720",
                "-o", "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0
        )

        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        """后台读取 mjpeg，并保存最新 frame"""
        while True:
            chunk = self.process.stdout.read(4096)
            if not chunk:
                break
            self.buffer += chunk
            start = self.buffer.find(b"\xff\xd8")      # JPEG 开头
            end = self.buffer.find(b"\xff\xd9")        # JPEG 结尾

            if start != -1 and end != -1:
                with self.lock:
                    self.last_frame = self.buffer[start:end + 2]  # 保存最新图片
                self.buffer = self.buffer[end + 2:]  # 移除已处理数据

    def get_frame(self):
        """返回最新 JPEG 帧"""
        with self.lock:
            return getattr(self, "last_frame", None)


camera = CSICamera()
camera.start()
