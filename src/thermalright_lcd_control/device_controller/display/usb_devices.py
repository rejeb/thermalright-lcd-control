# usb_devices.py
import time
from abc import ABC

import pyvips
import usb.core
import usb.util

from thermalright_lcd_control.device_controller.display.display_device import DisplayDevice
from thermalright_lcd_control.device_controller.display.image_encoder import (
    encode_jpeg,
    encode_rgb565_be,
)


def _find_bulk_out_ep(dev: usb.core.Device) -> tuple[int, int]:
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
    mode = "USB BULK"

    def __init__(self, vid, pid, chunk_size, width, height, config_dir: str, *args,
                 config_file: str = None, **kwargs):
        # chunk_size here is the *application* chunk we split payload into
        super().__init__(vid, pid, chunk_size, width, height, config_dir, *args,
                         config_file=config_file, **kwargs)
        self.vid = vid
        self.pid = pid
        self.width = width
        self.height = height
        self.config_dir = config_dir

        self.dev: usb.core.Device | None = usb.core.find(idVendor=vid, idProduct=pid)
        if self.dev is None:
            raise RuntimeError(f"USB device {vid:04x}:{pid:04x} not found")

        # Try detach all kernel drivers
        try:
            cfg = self.dev.get_active_configuration()
            for intf in cfg:
                if self.dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    self.dev.detach_kernel_driver(intf.bInterfaceNumber)
        except (NotImplementedError, usb.core.USBError):
            pass

        # Claim interface and discover BULK OUT endpoint
        self.iface, self.ep_out = _find_bulk_out_ep(self.dev)

        usb.util.claim_interface(self.dev, self.iface)

        # Device-specific header (subclass provides)
        self.header = self.get_header()

    def close(self) -> None:
        """Release the USB interface and dispose resources. Idempotent."""
        dev = getattr(self, "dev", None)
        if dev is not None:
            usb.util.release_interface(dev, self.iface)
            usb.util.dispose_resources(dev)
            self.dev = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __del__(self):
        # Best-effort safety net only; explicit close() is the contract.
        try:
            self.close()
        except Exception:
            pass

    # --- Encoding ---

    def _encode_image(self, img: pyvips.Image) -> bytes:
        return super()._encode_image(img)

    # --- USB transfer ---

    def send_packet(self, packet: bytes):
        """
        Send a buffer to the device via BULK OUT, chunking to avoid huge single writes.
        NOTE: PyUSB write signature is (endpoint, data, timeout=None).
        """
        if not self.dev:
            raise RuntimeError("USB device not open")

        CHUNK = self.chunk_size

        offset = 0
        total = len(packet)
        while offset < total:
            n = min(CHUNK, total - offset)
            written = self.dev.write(self.ep_out, packet[offset:offset + n], timeout=5000)
            if written != n:
                raise OSError(f"Short write {written}/{n} at offset {offset}")
            offset += n

    def _zlp(self, timeout_ms: int = 1000):
        """Send a zero-length packet on OUT (commit marker)."""
        self.dev.write(self.ep_out, b"", timeout=timeout_ms)

    _BULK_CHUNK = 16 * 1024  # 16 KiB — a single large transfer can reset the device

    def _bulk_send(self, frame: bytes, timeout_ms: int = 5000) -> None:
        """Send frame in 16 KiB chunks + conditional ZLP (only when 512-byte aligned)."""
        for offset in range(0, len(frame), self._BULK_CHUNK):
            self.dev.write(self.ep_out, frame[offset:offset + self._BULK_CHUNK], timeout=timeout_ms)
        if len(frame) % 512 == 0:
            self._zlp(timeout_ms)

    @classmethod
    def info(cls) -> dict:
        return {
            "class_name": f"{cls.__module__}.{cls.__name__}",
            "width": cls.W,
            "height": cls.H,
            "vid": cls.VID,
            "pid": cls.PID,
        }


# -----------------------------
# ChiZhu Tech 87AD:70DB devices
# -----------------------------

class ChiZhuDisplayDevice(UsbDevice, ABC):
    """
    ChiZhu Tech USBDISPLAY (VID=0x87AD, PID=0x70DB).

    Shared 64-byte header / framing protocol for all resolutions:
        0x00..03 : 12 34 56 78  (magic)
        0x04..07 : cmd          (LE u32 — 3 = RGB565, 2 = JPEG)
        0x08..0B : width        (LE u32)
        0x0C..0F : height       (LE u32)
        0x38..3B : mode         (LE u32 = 2)
        0x3C..3F : payload_len  (LE u32)
    Per frame: header(64) + payload, sent in 16 KiB chunks + conditional ZLP.
    EOS: header with payload_len=0 + ZLP, then a quiet wait.

    Concrete subclasses set ``W, H``; the encoding base sets ``CMD`` and
    ``_encode_image``.
    """
    VID, PID = 0x87AD, 0x70DB
    CMD: int = 0          # set by the encoding base (_ChiZhuRgb565 / _ChiZhuJpeg)
    _CHUNK_SIZE = 16384   # unused for frame writes (see _bulk_send), kept for the base

    def __init__(self, config_dir: str, start_wait: float = 2.0, stop_wait: float = 2.0,
                 config_file: str = None):
        super().__init__(self.VID, self.PID, self._CHUNK_SIZE, self.W, self.H, config_dir,
                         config_file=config_file)
        self.start_wait = start_wait
        self.stop_wait = stop_wait
        time.sleep(max(self.start_wait, 0.0))  # quiet window like the working flow

    def _make_header(self, cmd: int, payload_len: int, mode: int = 2) -> bytes:
        hdr = bytearray(64)
        hdr[0:4] = bytes.fromhex("12 34 56 78")
        hdr[4:8] = int(cmd).to_bytes(4, "little")
        hdr[8:12] = int(self.width).to_bytes(4, "little")
        hdr[12:16] = int(self.height).to_bytes(4, "little")
        hdr[0x38:0x3C] = int(mode).to_bytes(4, "little")
        hdr[0x3C:0x40] = int(payload_len).to_bytes(4, "little")
        return bytes(hdr)

    def get_header(self) -> bytes:
        # Base ctor stores this, but _run() builds its own header per frame.
        return self._make_header(self.CMD, 0)

    def _run(self) -> float:
        gen = self._get_generator()

        self._encode_cache.sync_generator(id(gen))
        # Advance timing first, then key the cache on the frame we actually
        # landed on (current_frame_index), NOT a pre-advance peek: peeking
        # before the (possibly multi-ms) sync_overlay/compose can straddle a
        # frame boundary and store the encoded frame under the wrong index,
        # poisoning the cache (mirrors RenderEngine._tick).
        base = gen.get_base_frame()
        frame_idx = gen.current_frame_index
        delay_time = gen.frame_duration
        # Refresh the overlay (metrics/clock) BEFORE reading the cache so a
        # fully-cached looping/static clip still picks up metric/clock changes.
        version = gen.sync_overlay()

        payload = self._encode_cache.get(frame_idx, version)
        if payload is None:
            payload = self._encode_image(gen.compose_device_frame(base))
            self._encode_cache.set_frame_count(gen.frame_count)
            self._encode_cache.store(frame_idx, version, payload)

        self._bulk_send(self._make_header(self.CMD, len(payload)) + payload)
        return delay_time

    def end_stream(self):
        try:
            self.dev.write(self.ep_out, self._make_header(self.CMD, 0), timeout=1000)
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


class _ChiZhuRgb565(ChiZhuDisplayDevice, ABC):
    """RGB565 big-endian raw payload (cmd = 3)."""
    CMD = 3

    def _encode_image(self, img: pyvips.Image) -> bytes:
        return encode_rgb565_be(img, self.width, self.height)


class _ChiZhuJpeg(ChiZhuDisplayDevice, ABC):
    """JPEG-compressed payload (cmd = 2)."""
    CMD = 2

    def __init__(self, config_dir: str, start_wait: float = 2.0, stop_wait: float = 2.0,
                 jpeg_quality: int = 85, config_file: str = None):
        self.jpeg_quality = jpeg_quality
        super().__init__(config_dir, start_wait, stop_wait, config_file=config_file)

    def _encode_image(self, img: pyvips.Image) -> bytes:
        return encode_jpeg(img, self.width, self.height, jpeg_quality=self.jpeg_quality)


class DisplayDevice87AD70DB320(_ChiZhuRgb565):
    """320x320 — RGB565 big-endian."""
    W, H = 320, 320


class DisplayDevice87AD70DB480(_ChiZhuJpeg):
    """480x480 — JPEG."""
    W, H = 480, 480


class DisplayDevice87AD70DB640(_ChiZhuJpeg):
    """640x480 — JPEG."""
    W, H = 640, 480
