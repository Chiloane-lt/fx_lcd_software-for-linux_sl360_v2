"""Video looping tests; never access physical USB hardware."""

import unittest
from unittest.mock import patch

import core


class FakeHIDDevice:
    def __init__(self):
        self.opened = False
        self.closed = False
        self.writes = []

    def open(self, vid, pid):
        self.opened = True

    def write(self, data):
        self.writes.append(data)

    def close(self):
        self.closed = True


class VideoLoopTests(unittest.TestCase):
    def setUp(self):
        self.device = FakeHIDDevice()

        self.patches = [
            patch("core.hid.device", return_value=self.device),
            patch(
                "core.load_config",
                return_value={"usb_vid": 0x2000, "usb_pid": 0x3002},
            ),
            patch("core.prepare_blob", side_effect=lambda data: data),
            patch("core.prepare_chunks", return_value=[b"test-chunk"]),
            patch("core.time.sleep"),
        ]

        for mocked in self.patches:
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_video_restarts_with_a_fresh_generator(self):
        factory_calls = 0
        closed_passes = []

        def frames_factory():
            nonlocal factory_calls
            factory_calls += 1

            try:
                if factory_calls == 1:
                    yield b"frame-one", 0
                    yield b"frame-two", 0
                else:
                    yield b"frame-three", 0
                    raise KeyboardInterrupt
            finally:
                closed_passes.append(factory_calls)

        with self.assertRaises(KeyboardInterrupt):
            core.send_video(frames_factory)

        self.assertEqual(factory_calls, 2)
        self.assertEqual(closed_passes, [1, 2])
        self.assertTrue(self.device.opened)
        self.assertTrue(self.device.closed)
        self.assertEqual(len(self.device.writes), 3)

    def test_empty_video_raises_and_closes_device(self):
        with self.assertRaisesRegex(RuntimeError, "contains no frames"):
            core.send_video(lambda: iter(()))

        self.assertTrue(self.device.opened)
        self.assertTrue(self.device.closed)
        self.assertEqual(self.device.writes, [])


if __name__ == "__main__":
    unittest.main()
