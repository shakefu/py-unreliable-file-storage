import unittest

from file_store.block_device import BlockDevice


class BlockDeviceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.block_device = BlockDevice.get_new_block_device(
            block_count=32, block_size=8, corruption_rate=0.01
        )

    def test_write(self):
        self.assertEqual(self.block_device.write(0, "1234abcd"), "1234abcd")

    def test_read(self):
        self.assertEqual(len(self.block_device.read(1)), 8)
