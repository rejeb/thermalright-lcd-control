# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Transport layer: send an encoded payload to a display over HID or USB bulk."""
import logging
import struct
from abc import ABC, abstractmethod
from enum import Enum

from usb.core import USBError

logger = logging.getLogger(__name__)


class TransportType(str, Enum):
    HID = "hid"
    USB_BULK = "usb_bulk"
    SCSI = "scsi"
    USB_BULK_LY = "usb_bulk_ly"
    LED = "led"


class Transport(ABC):
    """Sends byte payloads to a display device."""

    @abstractmethod
    def send(self, payload: bytes) -> None:
        ...

    @staticmethod
    def create(transport_type: "TransportType | str", dev, chunk_size: int,
               ep_out: int | None = None, ep_in: int = 0x81, report_id: bytes = b"\x00",
               command: int = 0xF5, pid: int = 0) -> "Transport":
        """Build the transport matching the device interface."""
        transport_type = TransportType(transport_type)
        if transport_type == TransportType.HID:
            return HidTransport(dev, chunk_size, report_id)
        if transport_type == TransportType.USB_BULK:
            if ep_out is None:
                raise ValueError("usb_bulk transport requires ep_out")
            return UsbBulkTransport(dev, ep_out, chunk_size)
        if transport_type == TransportType.SCSI:
            if ep_out is None:
                raise ValueError("scsi transport requires ep_out")
            return ScsiTransport(dev, ep_out, ep_in, chunk_size, command)
        if transport_type == TransportType.USB_BULK_LY:
            if ep_out is None:
                raise ValueError("usb_bulk_ly transport requires ep_out")
            return LyTransport(dev, ep_out, ep_in, pid)
        raise ValueError(f"Unsupported transport: {transport_type}")


class HidTransport(Transport):
    """HID write: split payload into report_id-prefixed, zero-padded chunks."""

    def __init__(self, dev, chunk_size: int, report_id: bytes = b"\x00"):
        self.dev = dev
        self.chunk_size = chunk_size
        self.report_id = report_id

    def send(self, payload: bytes) -> None:
        for i in range(0, len(payload), self.chunk_size):
            chunk = payload[i:i + self.chunk_size]
            if len(chunk) < self.chunk_size:
                chunk += b"\x00" * (self.chunk_size - len(chunk))
            self.dev.write(self.report_id + chunk)


class UsbBulkTransport(Transport):
    """USB BULK OUT write in chunks + conditional zero-length packet (512-byte aligned)."""

    def __init__(self, dev, ep_out: int, chunk_size: int, timeout_ms: int = 5000):
        self.dev = dev
        self.ep_out = ep_out
        self.chunk_size = chunk_size
        self.timeout_ms = timeout_ms

    def send(self, payload: bytes) -> None:
        for offset in range(0, len(payload), self.chunk_size):
            self.dev.write(self.ep_out, payload[offset:offset + self.chunk_size],
                           timeout=self.timeout_ms)
        if len(payload) % 512 == 0:
            self.dev.write(self.ep_out, b"", timeout=self.timeout_ms)


class ScsiTransport(Transport):
    """USB Mass Storage / SCSI BOT: per-chunk CBW (USBC) -> data -> CSW (USBS) handshake."""

    def __init__(self, dev, ep_out: int, ep_in: int, chunk_size: int, command: int = 0xF5):
        self.dev = dev
        self.ep_out = ep_out
        self.ep_in = ep_in
        self.chunk_size = chunk_size
        self.command = command
        self.tag = 0

    def _next_tag(self) -> int:
        self.tag += 1
        return self.tag

    def _gen_cbw(self, cdb: bytearray, size: int, flag: int = 0x00) -> bytearray:
        cbw = bytearray(31)
        cbw[0:4] = b"USBC"
        cbw[4:8] = self._next_tag().to_bytes(4, "little")
        cbw[8:12] = size.to_bytes(4, "little")
        cbw[12] = flag
        cbw[13] = 0  # LUN
        cbw[14] = len(cdb)
        cbw[15:15 + len(cdb)] = cdb
        return cbw

    def _xfer(self, cdb: bytearray, data: bytes) -> bytes:
        cbw = self._gen_cbw(cdb, len(data))
        if self.dev.write(self.ep_out, cbw, timeout=1000) != len(cbw):
            raise USBError("Failed to send CBW")
        if data:
            self.dev.write(self.ep_out, data, timeout=2000)
        csw = bytes(self.dev.read(self.ep_in, 13, timeout=1000))
        if len(csw) != 13 or csw[0:4] != b"USBS":
            raise USBError("Invalid CSW received")
        return csw

    def send(self, payload: bytes) -> None:
        offset = 0
        idx = 0
        total = len(payload)
        while offset < total:
            n = min(self.chunk_size, total - offset)
            chunk = payload[offset:offset + n]
            cdb = bytearray(16)
            cdb[0] = self.command
            cdb[1] = 0x01
            cdb[2] = 0x01
            cdb[3] = idx
            cdb[12:16] = len(chunk).to_bytes(4, "little")
            csw = self._xfer(cdb, chunk)
            if csw[12] != 0x00:
                raise USBError("Failed to send data")
            offset += n
            idx += 1


class LyTransport(Transport):
    """USB bulk transport for LY-type LCDs (0416:5408 / 0416:5409).

    Protocol reverse-engineered from TRCC USBLCDNEW (ThreadSendDeviceDataLY /
    ThreadSendDeviceDataLY1). The payload is a JPEG image:

    1. Handshake (once): write 2048 bytes ``02 FF .. 01 ..`` + zero padding,
       read a 512-byte response, validate ``[0]==3, [1]==0xFF, [8]==1``.
    2. Frame: split the JPEG into 512-byte chunks (16-byte header + 496 data),
       pad the chunk count to a multiple of 4 (LY) / 1 (LY1), send everything
       in 4096-byte bulk writes, then read a 512-byte ACK.

    Per-chunk 16-byte header:
        [0]      0x01
        [1]      0xFF
        [2:6]    total payload size (LE32)
        [6:8]    this chunk's data length (LE16)
        [8]      cmd (1 for LY, 2 for LY1)
        [9:11]   total number of chunks (LE16)
        [11:13]  chunk index (LE16)
        [13:16]  zero padding
    """

    _PID_LY = 0x5408
    _PID_LY1 = 0x5409

    _HANDSHAKE = bytes([
        0x02, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]) + bytes(2032)

    _CHUNK_SIZE = 512
    _CHUNK_HEADER_SIZE = 16
    _CHUNK_DATA_SIZE = 496      # _CHUNK_SIZE - _CHUNK_HEADER_SIZE
    _USB_WRITE_SIZE = 4096      # bytes per USB bulk write
    _ACK_SIZE = 512

    def __init__(self, dev, ep_out: int, ep_in: int, pid: int = _PID_LY,
                 timeout_ms: int = 5000):
        self.dev = dev
        self.ep_out = ep_out
        self.ep_in = ep_in
        self.is_ly1 = (pid == self._PID_LY1)
        self.cmd = 2 if self.is_ly1 else 1
        self.pad_multiple = 1 if self.is_ly1 else 4
        self.timeout_ms = timeout_ms
        self._handshaked = False

    def _handshake(self) -> None:
        """Wake/init the panel. Best-effort: log a warning on a bad response
        but still proceed — some firmware variants differ slightly."""
        self.dev.write(self.ep_out, self._HANDSHAKE, timeout=self.timeout_ms)
        resp = bytes(self.dev.read(self.ep_in, self._ACK_SIZE, timeout=self.timeout_ms))
        ok = len(resp) >= 9 and resp[0] == 3 and resp[1] == 0xFF and resp[8] == 1
        if not ok:
            logger.warning(
                "LY handshake unexpected response (len=%d, [0]=%s [1]=%s [8]=%s)",
                len(resp),
                resp[0] if resp else None,
                resp[1] if len(resp) > 1 else None,
                resp[8] if len(resp) > 8 else None,
            )
        self._handshaked = True

    def _build_chunks(self, payload: bytes) -> bytes:
        total_size = len(payload)
        num_chunks = total_size // self._CHUNK_DATA_SIZE + 1
        last_chunk_data = total_size % self._CHUNK_DATA_SIZE

        chunks = bytearray(num_chunks * self._CHUNK_SIZE)
        for i in range(num_chunks):
            off = i * self._CHUNK_SIZE
            is_last = (i == num_chunks - 1)
            data_len = last_chunk_data if is_last else self._CHUNK_DATA_SIZE

            chunks[off] = 0x01
            chunks[off + 1] = 0xFF
            struct.pack_into("<I", chunks, off + 2, total_size)
            struct.pack_into("<H", chunks, off + 6, data_len)
            chunks[off + 8] = self.cmd
            struct.pack_into("<H", chunks, off + 9, num_chunks)
            struct.pack_into("<H", chunks, off + 11, i)
            # bytes 13-15 stay zero

            src = i * self._CHUNK_DATA_SIZE
            payload_start = off + self._CHUNK_HEADER_SIZE
            chunks[payload_start:payload_start + data_len] = payload[src:src + data_len]

        # Pad the chunk count to a multiple of pad_multiple with zero chunks.
        padded_chunks = num_chunks
        remainder = padded_chunks % self.pad_multiple
        if remainder != 0:
            padded_chunks += self.pad_multiple - remainder
        total_bytes = padded_chunks * self._CHUNK_SIZE
        return bytes(chunks) + bytes(total_bytes - len(chunks))

    def send(self, payload: bytes) -> None:
        if not self._handshaked:
            self._handshake()

        send_buf = self._build_chunks(payload)
        total_bytes = len(send_buf)

        pos = 0
        while pos < total_bytes:
            remaining = total_bytes - pos
            if remaining >= self._USB_WRITE_SIZE:
                write_size = self._USB_WRITE_SIZE
            else:
                # LY sends a 2048-byte tail; LY1 sends whatever remains.
                write_size = remaining if self.is_ly1 else min(2048, remaining)
            self.dev.write(self.ep_out, send_buf[pos:pos + write_size],
                           timeout=self.timeout_ms)
            pos += self._USB_WRITE_SIZE  # always advance by 4096

        # Read (and discard) the device ACK.
        self.dev.read(self.ep_in, self._ACK_SIZE, timeout=self.timeout_ms)
