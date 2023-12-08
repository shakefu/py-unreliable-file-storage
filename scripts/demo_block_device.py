#!/usr/bin/env python3

from file_store.block_device import BlockDevice

# Create a block device with 1024 blocks that can each fit an
# character string; every read/write has a 1% chance of corruption.
block_device = BlockDevice.get_new_block_device(
    block_count=1024, block_size=8, corruption_rate=0
)

# Write content to block 0.
print(
    f"Writing '12345678' to the block device: {block_device.write(index=0, content='12345678')}"
)

# Read content from block 0.
print(f"Reading from the block device: {block_device.read(index=0)}")

# If content length exceeds the block size, the content is truncated.
print(
    f"Writing '123456789' to the block device: {block_device.write(index=0, content='123456789')}"
)

# If content length is less than the block size, the content is extended with the existing content.
print(
    f"Writing 'abcd' to the block device: {block_device.write(index=0, content='abcd')}"
)

corrupting_block_device = BlockDevice.get_new_block_device(
    block_count=1024, block_size=8, corruption_rate=1
)

# Write content to block 0.
print(
    f"Writing '12345678' to the corrupting block device: {corrupting_block_device.write(index=0, content='12345678')}"
)

# don't do this, building the next demo!

corrupting_block_device.corruption_rate = 0.0
print(
    f"Writing '1234abcd' to the corrupting block device: {corrupting_block_device.write(index=0, content='1234abcd')}"
)

# Read content from block 0.
print(f"Reading (no curruption, yay!): {corrupting_block_device.read(index=0)}")

# And then it corrupts the read
corrupting_block_device.corruption_rate = 1.0

print(f"Reading (Corrupts, oh no!): {corrupting_block_device.read(index=0)}")

corrupting_block_device.corruption_rate = 0.0

print(f"Reading (Original data lost:-( ): {corrupting_block_device.read(index=0)}")

print("Success!")
