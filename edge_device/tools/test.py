#!/usr/bin/env python3
import minimalmodbus
import serial
import time

# --- 配置区域 ---
# 如果你是 USB 转串口，通常是 /dev/ttyUSB0
# 如果直接插在树莓派板子上，可能是 /dev/ttyACM0
PORT = "/dev/ttyACM0"

SLAVE_ADDRESS = 1       # 传感器地址 (默认通常是 1)
REGISTER = 0x0101       # 寄存器地址 (根据你之前的代码填写的)
BAUDRATE = 9600         # 波特率

def test_sensor():
    try:
        # 初始化传感器连接
        print(f"正在尝试连接端口: {PORT} ...")
        sensor = minimalmodbus.Instrument(PORT, SLAVE_ADDRESS)
        
        # 串口参数设置
        sensor.serial.baudrate = BAUDRATE
        sensor.serial.bytesize = 8
        sensor.serial.parity   = serial.PARITY_NONE
        sensor.serial.stopbits = 1
        sensor.serial.timeout  = 0.5 # 0.5秒超时
        sensor.mode = minimalmodbus.MODE_RTU
        sensor.clear_buffers_before_each_transaction = True

        print("✅ 连接成功，开始读取数据 (按 Ctrl+C 停止)...\n")

        while True:
            try:
                # 读取寄存器 (功能码 3: Read Holding Registers)
                # stored value通常是毫米(mm)
                mm = sensor.read_register(REGISTER, 0, functioncode=3)
                
                # 打印结果
                print(f"📏 读数: {mm} mm  =>  {mm/1000.0} m")
                
            except minimalmodbus.NoResponseError:
                print("❌ 错误: 传感器无响应 (检查接线 A接A, B接B)")
            except minimalmodbus.InvalidResponseError:
                print("⚠️ 错误: 收到垃圾数据 (检查波特率)")
            except Exception as e:
                print(f"❌ 读取错误: {e}")

            time.sleep(0.5)

    except serial.SerialException:
        print(f"🚫 无法打开端口 {PORT} (可能被占用或不存在)")
    except Exception as e:
        print(f"💥 程序崩溃: {e}")

if __name__ == "__main__":
    test_sensor()