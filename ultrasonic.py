import minimalmodbus
import serial
import time

sensor = minimalmodbus.Instrument('/dev/ttyACM0', 1)
sensor.serial.baudrate = 9600
sensor.serial.bytesize = 8
sensor.serial.parity   = serial.PARITY_NONE
sensor.serial.stopbits = 1
sensor.serial.timeout  = 0.3
sensor.mode = minimalmodbus.MODE_RTU

def read_distance():
    try:
        return sensor.read_register(0x0101, 0)  # 实时距离
    except:
        return None

while True:
    print("📏 Distance:", read_distance(), "mm")
    time.sleep(0.2)
