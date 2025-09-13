# usb_devices.py
from abc import ABC
from typing import Optional, Tuple
import time

import usb.core
import usb.util
import numpy as np
from PIL import Image

from .display_device import DisplayDevice


def _find_bulk_out_ep(dev: usb.core.Device) -> Tuple[int, int]:
    """
    Return (interface_number, ep_out_address) for the first interface that exposes a BULK OUT endpoint.
    Prefer vendor-specific interfaces (class 255) if present.
    """
    dev.set_configuration()
    cfg = dev.get_active_configuration()

    # Pass 1: prefer vendor-specific (255)
    for intf in cfg:
        if intf.bInterfaceClass == 255:
            for ep in intf:
                if (usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT and
                        usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK):
                    return intf.bInterfaceNumber, ep.bEndpointAddress

    # Pass 2: any BULK OUT
    for intf in cfg:
        for ep in intf:
            if (usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT and
                    usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK):
                return intf.bInterfaceNumber, ep.bEndpointAddress

    raise RuntimeError("No BULK OUT endpoint found on this USB device")


class UsbDevice(DisplayDevice, ABC):
    """
    Base class for bulk USB display devices.
    Implements endpoint discovery and a chunked write method.
    Subclasses should implement `get_header()` and (if needed) override `_encode_image`.
    """

    def __init__(self, vid, pid, chunk_size, width, height, config_dir: str, *args, **kwargs):
        # chunk_size here is the *application* chunk we split payload into
        super().__init__(vid, pid, chunk_size, width, height, config_dir, *args, **kwargs)
        self.vid = vid
        self.pid = pid
        self.width = width
        self.height = height
        self.config_dir = config_dir

        self.dev: Optional[usb.core.Device] = usb.core.find(idVendor=vid, idProduct=pid)
        if self.dev is None:
            raise RuntimeError(f"USB device {vid:04x}:{pid:04x} not found")

        # Claim interface and discover BULK OUT endpoint
        self.iface, self.ep_out = _find_bulk_out_ep(self.dev)

        # Detach kernel driver if needed, then claim
        try:
            if self.dev.is_kernel_driver_active(self.iface):
                self.dev.detach_kernel_driver(self.iface)
        except (NotImplementedError, usb.core.USBError):
            pass

        usb.util.claim_interface(self.dev, self.iface)

        # Device-specific header (subclass provides)
        self.header = self.get_header()

    def __del__(self):
        try:
            if self.dev:
                usb.util.release_interface(self.dev, self.iface)
                usb.util.dispose_resources(self.dev)
        except Exception:
            pass

    # --- Encoding ---

    def _encode_image(self, img: Image) -> bytes:
        return super()._encode_image(img)

    # --- USB transfer ---

    def send_packet(self, packet: bytes):
        """
        Send a buffer to the device via BULK OUT, chunking to avoid huge single writes.
        NOTE: PyUSB write signature is (endpoint, data, timeout=None).
        """
        if not self.dev:
            raise RuntimeError("USB device not open")

        CHUNK = self.chunk_size if getattr(self, "chunk_size", None) else 16 * 1024

        offset = 0
        total = len(packet)
        while offset < total:
            n = min(CHUNK, total - offset)
            # ✅ no iface positional arg here
            written = self.dev.write(self.ep_out, packet[offset:offset + n], timeout=5000)
            if written != n:
                raise IOError(f"Short write {written}/{n} at offset {offset}")
            offset += n

    def _zlp(self, timeout_ms: int = 1000):
        """Send a zero-length packet on OUT (commit marker)."""
        self.dev.write(self.ep_out, b"", timeout=timeout_ms)


# -----------------------------
# ChiZhu Tech 87AD:70DB device
# -----------------------------

class DisplayDevice87AD70DB(UsbDevice):
    """
    ChiZhu Tech USBDISPLAY (VID=0x87AD, PID=0x70DB), 320x320
    Protocol (confirmed):
      - Header: 64 bytes
          0x00..03 : 12 34 56 78
          0x04..07 : 03 00 00 00  (cmd = 3)
          0x08..0B : width  (LE u32) = 320
          0x0C..0F : height (LE u32) = 320
          0x38..3B : mode   (LE u32) = 2
          0x3C..3F : payload_len (LE u32) = 204800
      - Payload: 320*320*2 = 204,800 bytes, RGB565 **big-endian**
      - Transfer order per frame: header(64) → 400×(512B) → ZLP
      - EOS: single header(len=0, mode=2) + ZLP, then a short quiet wait
    """
    PKT = 512
    W, H = 320, 320
    PAYLOAD_BYTES = W * H * 2      # 204,800
    PACKETS_PER_FRAME = PAYLOAD_BYTES // PKT  # 400

    def __init__(self, config_dir: str, start_wait: float = 2.0, stop_wait: float = 2.0):
        # app-level “chunk_size” not used for the actual frame writes; we still set it
        super().__init__(0x87AD, 0x70DB, self.PKT, self.W, self.H, config_dir)
        self.start_wait = start_wait
        self.stop_wait = stop_wait
        # Build standard headers now
        self._hdr_frame = self._make_header(cmd=3, mode=2, payload_len=self.PAYLOAD_BYTES)
        self._hdr_eos   = self._make_header(cmd=3, mode=2, payload_len=0)
        time.sleep(max(self.start_wait, 0.0))  # quiet window like the working flow

    def _make_header(self, cmd: int, mode: int, payload_len: int) -> bytes:
        hdr = bytearray(64)
        hdr[0:4]   = bytes.fromhex("12 34 56 78")
        hdr[4:8]   = int(cmd).to_bytes(4, "little")
        hdr[8:12]  = int(self.width).to_bytes(4, "little")
        hdr[12:16] = int(self.height).to_bytes(4, "little")
        hdr[0x38:0x3C] = int(mode).to_bytes(4, "little")         # mode = 2
        hdr[0x3C:0x40] = int(payload_len).to_bytes(4, "little")  # bytes in payload
        return bytes(hdr)

    def get_header(self) -> bytes:
        # The base constructor calls this; make sure it returns *something* valid.
        # We’ll ignore it in run() and send our own _hdr_frame each time.
        try:
            return self._hdr_frame
        except AttributeError:
            # during super().__init__ call, build the normal frame header lazily
            return self._make_header(cmd=3, mode=2, payload_len=self.PAYLOAD_BYTES)

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

    # --- run: bulk framing (no HID report-id, no generic chunker) ---
    def run(self):
        self.logger.info("Display device (87AD:70DB) running (bulk mode)")
        while True:
            img, delay_time = self._get_generator().get_frame_with_duration()
            payload = self._encode_image(img)
            # header
            self.dev.write(self.ep_out, self._hdr_frame, timeout=2000)
            # payload in 512B slices
            off = 0
            for _ in range(self.PACKETS_PER_FRAME):
                chunk = payload[off:off + self.PKT]
                # chunks are exactly 512B by construction
                self.dev.write(self.ep_out, chunk, timeout=5000)
                off += self.PKT
            # commit (ZLP)
            self._zlp()
            time.sleep(delay_time)

    # --- graceful shutdown consistent with EOS probe ---
    def end_stream(self):
        try:
            self.dev.write(self.ep_out, self._hdr_eos, timeout=1000)
            self._zlp()
        except Exception:
            pass
        time.sleep(max(self.stop_wait, 0.0))

    def close(self):
        try:
            self.end_stream()
        finally:
            try:
                usb.util.release_interface(self.dev, self.iface)
            finally:
                usb.util.dispose_resources(self.dev)
