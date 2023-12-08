from dataclasses import dataclass
import random
import string
from typing import List

# See below BlockDevice for FileStore skeleton


def get_random_string(length: int) -> str:
    return "".join(random.choice(string.ascii_lowercase) for _ in range(length))


@dataclass
class BlockDevice:
    block_size: int
    _blocks: List[str]
    corruption_rate: float

    @staticmethod
    def get_new_block_device(
        block_count: int = 1024, block_size: int = 8, corruption_rate: float = 0.01
    ) -> "BlockDevice":
        """Create a new block device with the desired parameters."""
        blocks = [get_random_string(block_size) for _ in range(block_count)]
        return BlockDevice(
            block_size=block_size, _blocks=blocks, corruption_rate=corruption_rate
        )

    @property
    def block_count(self) -> int:
        """How many blocks does this device contain."""
        return len(self._blocks)

    def read(self, index: int) -> str:
        """Read the block at the specified index.

        This method may corrupt the underlying block in a consistent
        manner, such that the original data is unretrievable in the
        future, as well.

        :param index: Index of the block to read.
        :returns: Content of the block.
        """
        uncorrupted = self._blocks[index]
        return self._maybe_corrupt(uncorrupted, index)

    def write(self, index: int, content: str) -> str:
        """Write the specified content to the specified block index.

        This method may corrupt the data before persisteng it to the
        underlying block; however, it will return the content that
        was actually written.

        :: Note: The input content will be truncated to the block_size
                 of this block device.

        :param index: Block index to write into.
        :param content: Content to be written, only uses the first block_size
            characters.

        :returns: What content was written to the block device
        """
        truncated = content[: self.block_size]
        current_content = self._blocks[index]
        new_content = truncated + current_content[len(truncated) :]
        return self._maybe_corrupt(new_content, index)

    def _maybe_corrupt(self, content: str, index: int) -> str:
        should_corrupt = random.uniform(0, 1) < self.corruption_rate
        if should_corrupt:
            maybe_corrupted = get_random_string(self.block_size)
        else:
            maybe_corrupted = content
        self._blocks[index] = maybe_corrupted
        return maybe_corrupted
