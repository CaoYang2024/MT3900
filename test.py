from pyudev import Context
ctx = Context()

dev = ctx.device_from_device_file('/dev/video0')
usb = dev.find_parent('usb', 'usb_device')

print("Vendor:", usb.get('ID_VENDOR'))
print("Model:", usb.get('ID_MODEL'))
print("Serial:", usb.get('ID_SERIAL'))
