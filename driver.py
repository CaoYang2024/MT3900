import time
import math
import random
from datetime import datetime, timezone
from typing import Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException


# -------------------- 配置区（按需修改） --------------------
INFLUX_URL   = "http://localhost:8086"
INFLUX_ORG   = "basyx"          # 也可用 org ID: "e7c4f04e1fc95776"
INFLUX_BUCKET= "test"
INFLUX_TOKEN = "7ycr9ML70qIlBuAQAZqyOsNcGep-AJeaSuWJztiINtm8NELN60qdTj_XbAyGFjcbt5VYeJkldcolLaHSc7rgtw=="

SENSOR_ID    = "temp-001"
LOCATION     = "lab-A"
UNIT         = "degC"

# 采样周期（秒）
PERIOD_SEC   = 1.0

# 温度模型参数
BASELINE     = 22.0   # 基线温度（平均值）
DIURNAL_AMP  = 3.0    # 日周期幅度（正弦项）
DRIFT_STD    = 0.05   # 随机游走波动强度（每步）
NOISE_STD    = 0.1    # 独立测量噪声
# -----------------------------------------------------------


class TempSensorSim:
    """简单的温度传感器模拟：基线 + 日正弦 + 随机游走 + 白噪声"""
    def __init__(self,
                 baseline: float = BASELINE,
                 diurnal_amp: float = DIURNAL_AMP,
                 drift_std: float = DRIFT_STD,
                 noise_std: float = NOISE_STD):
        self.baseline = baseline
        self.diurnal_amp = diurnal_amp
        self.drift_std = drift_std
        self.noise_std = noise_std
        self.drift = 0.0  # 累积随机游走

    def read(self, t: float) -> float:
        """
        t: 当前时间戳（秒）
        返回一个带噪声的温度读数
        """
        # 以 24 小时为周期的缓慢正弦变化（86400秒）
        diurnal = self.diurnal_amp * math.sin(2 * math.pi * (t % 86400) / 86400.0)

        # 随机游走
        self.drift += random.gauss(0.0, self.drift_std)

        # 白噪声
        noise = random.gauss(0.0, self.noise_std)

        return self.baseline + diurnal + self.drift + noise


def make_point(sensor_id: str, location: str, unit: str, value: float) -> Point:
    """
    生成 InfluxDB Point：
      measurement: sensor_temperature
      tags: sensor_id, location, unit
      fields: value
    """
    p = (
        Point("sensor_temperature")
        .tag("sensor_id", sensor_id)
        .tag("location", location)
        .tag("unit", unit)
        .field("value", float(f"{value:.3f}"))  # 保留3位小数
        .time(time.time_ns(), WritePrecision.NS)
    )
    return p


def main():
    # 建立 InfluxDB 客户端
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    sensor = TempSensorSim()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Start streaming: "
          f"org='{INFLUX_ORG}', bucket='{INFLUX_BUCKET}', sensor_id='{SENSOR_ID}'")
    print("Press Ctrl+C to stop.\n")

    backoff_sec = 1.0
    max_backoff = 30.0

    try:
        while True:
            t = time.time()
            temp_val = sensor.read(t)

            point = make_point(SENSOR_ID, LOCATION, UNIT, temp_val)

            try:
                write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
                # 成功后重置退避
                backoff_sec = 1.0
                print(f"{datetime.now(timezone.utc).isoformat()} "
                      f"-> {temp_val:.3f} {UNIT} (sensor_id={SENSOR_ID}, location={LOCATION})")
            except ApiException as e:
                # 典型：401 未授权、404 组织/桶错误、429/5xx 等
                print(f"[WARN] Write failed (HTTP {e.status}): {e.body}")
                print(f"        Backoff {backoff_sec:.1f}s and retry...")
                time.sleep(backoff_sec)
                backoff_sec = min(max_backoff, backoff_sec * 2)  # 指数退避
                continue
            except Exception as e:
                print(f"[ERROR] Unexpected exception: {repr(e)}")
                print(f"        Backoff {backoff_sec:.1f}s and retry...")
                time.sleep(backoff_sec)
                backoff_sec = min(max_backoff, backoff_sec * 2)
                continue

            # 正常采样间隔
            time.sleep(PERIOD_SEC)

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user (Ctrl+C).")
    finally:
        try:
            write_api.__del__()  # 确保刷新
        except Exception:
            pass
        client.close()
        print("[INFO] Client closed.")


if __name__ == "__main__":
    main()
