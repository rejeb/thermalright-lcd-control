import threading
import time

import numpy as np
import usb
from PIL import Image
from usb.core import USBError

from thermalright_lcd_control.device_controller.display.usb_devices import UsbDevice


class DisplayDevice04023922(UsbDevice):
    """
        Base Display Device Controller for 0402:3922 ALi Corp. USBLCD
    """
    VID, PID = 0x0402, 0x3922
    COMMAND = 0xF5
    TAG = 0
    FLAG_IN = 0x80
    FLAG_OUT = 0x00

    def __init__(self, config_dir: str, bulk_size: int, width: int = 320, heigh: int = 320):
        super().__init__(self.VID,  # device vid
                         self.PID,  # device pid
                         bulk_size,
                         # the size in bytes, in wireshark it corresponds to the value of the property usb.data_len.
                         width,  # the width of the screen
                         heigh,  # the height of the screen
                         config_dir  # just keep as it
                         )

    def reset(self):
        self.dev.reset()
        self.logger.info("Display device reinitialised via USB reset")

    def _get_tag(self):
        self.TAG += 1
        return self.TAG

    # TODO: implement proper handshake
    def _handshake(self):
        tur_cdb = bytearray(6)
        data = self._write(cdb=tur_cdb, data=b'')
        if data[12] == 0x00:
            print(f"Handshake successful")
            return
        elif data[12] == 0x02:
            print(f"Check condition received during handshake")
            return
        else:
            raise USBError("Handshake failed")

    def _gen_cbw(self, cdb: bytearray, size: int, flag: int, tag: int):
        """
            Generate SCSI Command Block Wrapper (CBW)
            :param cdb: SCSI Command Descriptor Block
            :param size: Data transfer length
            :param flag: Direction flag (0x80 for IN, 0x00 for OUT)
            :param tag: Unique tag for the command
            :return: CBW as bytearray
        """
        cbw = bytearray(31)
        cbw[0:4] = b'USBC'  # CBW Signature
        if tag == 0:
            tag = self._get_tag()
        cbw[4:8] = tag.to_bytes(4, byteorder='little')
        cbw[8:12] = size.to_bytes(4, byteorder='little')
        cbw[12] = flag  # FLAG
        cbw[13] = 0  # LUN
        cbw[14] = len(cdb)
        cbw[15:15 + len(cdb)] = cdb
        return cbw

    def _write(self, cdb: bytearray, data: bytes, tag: int = 0) -> bytes:
        cbw = self._gen_cbw(cdb=cdb, size=len(data), flag=self.FLAG_OUT, tag=tag)
        rc = self.dev.write(self.ep_out, cbw, timeout=1000)
        if rc != len(cbw):
            raise USBError("Failed to send CBW")

        if len(data) > 0:
            self.dev.write(self.ep_out, data, timeout=2000)

        csw = bytes(self.dev.read(0x81, 13, timeout=1000))
        if len(csw) != 13 or csw[0:4] != b'USBS':
            raise USBError("Invalid CSW received")
        return csw

    def get_header(self) -> bytes:
        return bytes.fromhex("")

    def start(self):
        # start = time.time()
        # while time.time() - start < 30:
        #     try:
        #         self._handshake()
        #         break
        #     except USBError as e:
        #         print(f"Handshake failed, retrying... {e}")
        #         time.sleep(0.5)

        self.logger.info(
            f"Display device ({self.vid}:{self.pid}-{self.width}x{self.height}) running ({self.mode} mode)")
        self._run()

    # --- encoding: RGB565 big-endian, row-major, no per-row separators ---
    def _encode_image(self, img: Image) -> bytes:
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height), Image.LANCZOS)
        rgb = img.convert("RGB")
        arr = np.array(rgb, dtype=np.uint8)
        r = arr[..., 0].astype(np.uint16)
        g = arr[..., 1].astype(np.uint16)
        b = arr[..., 2].astype(np.uint16)
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        hi = (v >> 8).astype(np.uint8)
        lo = (v & 0xFF).astype(np.uint8)
        out = np.empty((self.height, self.width * 2), dtype=np.uint8)
        out[..., 0::2] = hi  # BE
        out[..., 1::2] = lo
        return out.tobytes()

    def _run(self):
        img, delay_time = self._get_generator().get_frame_with_duration()
        image_data = self._encode_image(img)
        off = 0
        total = len(image_data)
        idx = 0
        while off < total:
            n = min(self.chunk_size, total - off)
            chunk = image_data[off:off + n]
            cdb = bytearray(16)
            cdb[0] = self.COMMAND  # command
            cdb[1] = 0x01
            cdb[2] = 0x01
            cdb[3] = idx
            cdb[12:16] = len(chunk).to_bytes(4, byteorder='little')  # data length
            data = self._write(cdb=cdb, data=chunk)
            if data[12] != 0x00:
                raise USBError("Failed to send data")
            off += n
            idx += 1
        threading.Timer(interval=delay_time, function=self._run).start()


class DisplayDevice04023922320320(DisplayDevice04023922):
    """
        Display Device Controller for 0402:3922 ALi Corp. USBLCD with 320x320 resolution
    """
    W, H = 320, 320
    CHUNK_SIZE = 1024 * 64

    def __init__(self, config_dir: str):
        super().__init__(config_dir, self.CHUNK_SIZE, self.W, self.H)

    @staticmethod
    def info() -> dict:
        return {
            "class_name": f"{DisplayDevice04023922320320.__module__}.{DisplayDevice04023922320320.__name__}",
            "width": DisplayDevice04023922320320.W,
            "height": DisplayDevice04023922320320.H,
            "vid": DisplayDevice04023922320320.VID,
            "pid": DisplayDevice04023922320320.PID,
        }
