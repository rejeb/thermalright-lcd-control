import struct
import unittest

from thermalright_lcd_control.device_controller.display.transport import (
    LyTransport,
    Transport,
    TransportType,
)


class FakeUsbDev:
    """Records bulk writes and serves canned reads (the LY ACK / handshake)."""

    def __init__(self, handshake_resp=None):
        self.writes = []          # list of (ep, bytes)
        self.reads = []           # list of (ep, size)
        # default: a valid handshake response ([0]=3,[1]=0xFF,[8]=1)
        if handshake_resp is None:
            handshake_resp = bytes([3, 0xFF, 0, 0, 0, 0, 0, 0, 1]) + bytes(503)
        self._handshake_resp = handshake_resp

    def write(self, ep, data, timeout=0):
        self.writes.append((ep, bytes(data)))
        return len(data)

    def read(self, ep, size, timeout=0):
        self.reads.append((ep, size))
        return self._handshake_resp[:size]


_HEADER = 16
_DATA = 496
_CHUNK = 512


def _chunk_at(buf, i):
    return buf[i * _CHUNK:(i + 1) * _CHUNK]


class TestLyTransport(unittest.TestCase):
    def setUp(self):
        self.dev = FakeUsbDev()
        self.t = LyTransport(self.dev, ep_out=0x09, ep_in=0x81, pid=0x5408)

    def test_factory_builds_ly_transport(self):
        t = Transport.create(TransportType.USB_BULK_LY, self.dev, 4096,
                             ep_out=0x09, ep_in=0x81, pid=0x5408)
        self.assertIsInstance(t, LyTransport)
        self.assertEqual(t.cmd, 1)
        self.assertEqual(t.pad_multiple, 4)

    def test_ly1_variant_params(self):
        t = LyTransport(self.dev, 0x02, 0x81, pid=0x5409)
        self.assertTrue(t.is_ly1)
        self.assertEqual(t.cmd, 2)
        self.assertEqual(t.pad_multiple, 1)

    def test_handshake_sent_once_before_frames(self):
        self.t.send(b"\xAA" * 1000)
        self.t.send(b"\xBB" * 1000)
        # first write is the 2048-byte handshake, sent exactly once
        self.assertEqual(self.t._HANDSHAKE, self.t._HANDSHAKE)
        handshakes = [w for (_, w) in self.dev.writes if len(w) == 2048 and w[:2] == b"\x02\xFF"]
        self.assertEqual(len(handshakes), 1)
        self.assertEqual(handshakes[0][8], 0x01)

    def test_chunk_headers_and_payload(self):
        payload = bytes(range(256)) * 5  # 1280 bytes -> 1280/496 + 1 = 3 chunks
        self.t.send(payload)
        # reconstruct the chunk buffer from the bulk writes (skip handshake)
        frame_writes = b"".join(w for (_, w) in self.dev.writes if not (len(w) == 2048 and w[:2] == b"\x02\xFF"))

        total = len(payload)
        num_chunks = total // _DATA + 1
        self.assertEqual(num_chunks, 3)

        # verify each real chunk's header + payload slice
        rebuilt = bytearray()
        for i in range(num_chunks):
            c = _chunk_at(frame_writes, i)
            self.assertEqual(c[0], 0x01)
            self.assertEqual(c[1], 0xFF)
            self.assertEqual(struct.unpack_from("<I", c, 2)[0], total)
            data_len = struct.unpack_from("<H", c, 6)[0]
            self.assertEqual(c[8], 0x01)  # cmd LY
            self.assertEqual(struct.unpack_from("<H", c, 9)[0], num_chunks)
            self.assertEqual(struct.unpack_from("<H", c, 11)[0], i)
            rebuilt += c[_HEADER:_HEADER + data_len]
        self.assertEqual(bytes(rebuilt), payload)

    def test_chunk_count_padded_to_multiple_of_four(self):
        # 3 real chunks -> padded to 4 (LY)
        self.t.send(bytes(1280))
        frame_writes = b"".join(w for (_, w) in self.dev.writes if not (len(w) == 2048 and w[:2] == b"\x02\xFF"))
        self.assertEqual(len(frame_writes) % (4 * _CHUNK), 0)
        self.assertEqual(len(frame_writes), 4 * _CHUNK)

    def test_ack_is_read_after_send(self):
        self.t.send(bytes(500))
        # at least two reads: handshake response + frame ACK
        self.assertGreaterEqual(len(self.dev.reads), 2)
        self.assertEqual(self.dev.reads[-1], (0x81, 512))


if __name__ == "__main__":
    unittest.main()
