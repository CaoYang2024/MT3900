# src/drivers/ultrasonic.py
import minimalmodbus
import serial

class UltrasonicDriver:
    def __init__(self, cfg):
        port = cfg["interface"].get("port", "/dev/ttyUSB0")
        slave = cfg["interface"].get("slaveAddress", 1)
        baud = cfg["interface"].get("baudrate", 9600)
        register = cfg["interface"]["extra"].get("register", 0x0101)

        self.register = register

        self.instrument = minimalmodbus.Instrument(port, slave)
        self.instrument.serial.baudrate = baud
        self.instrument.serial.bytesize = 8
        self.instrument.serial.parity = serial.PARITY_NONE
        self.instrument.serial.stopbits = 1
        self.instrument.serial.timeout = 0.3
        self.instrument.mode = minimalmodbus.MODE_RTU

    def read_value(self):
        """Return m (meters)"""
        try:
            mm = self.instrument.read_register(self.register, 0)
            return mm / 1000.0
        except Exception as e:
            print(f"[Ultrasonic] Read failed: {e}")
            return None
