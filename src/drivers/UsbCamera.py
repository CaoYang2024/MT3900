# camera_driver.py
import cv2
import threading
import time


class CameraDriver:
    def __init__(self, device="/dev/video0", width=640, height=480, fps=30):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps

        self.cap = None
        self.running = False
        self.latest_frame = None
        self.thread = None

    # ============================================================
    # 打开摄像头
    # ============================================================
    def open(self):
        self.cap = cv2.VideoCapture(self.device)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        if not self.cap.isOpened():
            raise RuntimeError(f"❌ Cannot open camera: {self.device}")

        self.running = True
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    # ============================================================
    # 后台线程：持续读取最新 frame
    # ============================================================
    def _reader(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.latest_frame = frame
            else:
                time.sleep(0.01)

    # ============================================================
    # 获取最新 frame（JPEG 格式）
    # ============================================================
    def get_jpeg_frame(self):
        if self.latest_frame is None:
            return None
        ret, jpeg = cv2.imencode(".jpg", self.latest_frame)
        return jpeg.tobytes()

    # ============================================================
    # MJPEG 生成器
    # ============================================================
    def mjpeg_stream(self):
        while self.running:
            jpg = self.get_jpeg_frame()
            if jpg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    jpg +
                    b"\r\n"
                )
            time.sleep(1 / self.fps)

    # ============================================================
    # 关闭摄像头
    # ============================================================
    def close(self):
        self.running = False
        time.sleep(0.1)
        if self.cap:
            self.cap.release()
