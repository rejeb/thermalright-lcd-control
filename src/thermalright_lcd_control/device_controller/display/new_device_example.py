from PIL import Image


class DisplayDeviceVIDPID(#UsbDevice if you want to use usb device
                           #HidDevice if you want to use hid device
                           ):
    def __init__(self, config_dir: str):
        super().__init__(0x0000,# device vid
                         0x0000,# device pid
                         0x0000,# the size in bytes, in wireshark it corresponds to the value of the property usb.data_len.
                         320, # the width of the screen
                         240, # the height of the screen
                         config_dir # just keep as it
                         )
        # Change report_id value if different from bytes([0x00]), this byte is appended to every packet.
        # self.report_id = "new value"

    def get_header(self) -> bytes:
        # Implement your own logic here to get header bytes.
        # If nothing is shown on the screen that means that the header is not correct.
        # If you are sure that the header is correct, but nothing is shown, try remove report id.
        # If this works it means that the report id is not correct.
        return bytes.fromhex("your hexadecimal header")

    def _encode_image(self, img: Image) -> bytearray:
        # If encoding is not good, the screen will display a blurry image.
        # Try to find the correct encoding. and implement it here.
        return super()._encode_image(img)
