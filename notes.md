# Notes

## Contact

- **Email** - `chrism@lambdal.com`
- **GitHub** - `https://github.com/chrismacnaughton-lambda/`

## Writing

- dual write to two chunks of blocks
- check for write success/error by comparing returned value
- re-write blocks that error
<!--
- calculate block checksum and store with file metadata
- read single chunk of blocks
- calculate read checksum - if no errors we're good
- if errors, read other chunk of blocks
- calculate read checksum - if no errors we're good
- find corrupt blocks and write back with good data
  -->

- Divide up the blocks by the number of replicas
- So N blocks with 2 replicas, has data in block 0 and replica at N/2, etc
- Use a block_size - 1 with a trailing null 0x00 byte to indicate an uncorrupted read
- Look at base64 or base128 encoding the file tree info onto the block device, since it contains values outside the ASCII range
  - base91 exists
- Add init checks for max number of supported blocks

- Calculate needed replicas based on corruption rate?

- can we store the filesystem metadata in the block storage?

## Instructions

Resilient File Storage on Unreliable Block Device
In this question, we provide you an unreliable block storage device. Your job is to use it to implement a key-value store that will resiliently write and read ASCII text files:

```python
db = FileStore()
ret = db.put("hello.txt", "lorem ipsum dolor sit amet")
assert ret == "lorem ipsum dolor sit amet"
db.get("hello.txt")
lorem ipsum dolor sit amet
db.delete("hello.txt")
db.get("hello.txt")
ValueError: file hello.txt does not exist
```

When we say the block device is unreliable, we mean that data can be corrupted when a block is written to or read from. Once corrupted, the corruption is considered persistent, meaning the original data on the block is lost. If corruption occurs, when content is read from a block, the block will return random data, and when content is written to a block, random data will be written to the block instead.

Your task is to:

Implement the core API (put, get, delete) of FileStore, using BlockDevice as the underlying storage primitive.
Implement a strategy to recover from write-time corruption of file content
Implement a strategy to recover from read-time corruption of file content
The user should experience reliable, error-free use of your FileStore implementation, with two possible exceptions:

When the user runs out of storage space on the block device
When the file is corrupted beyond recovery, a determination we leave up to you
Keep in mind that this is a toy program and not subject to all the constraints of real-world filesystems.

You do not need to worry about efficiency, memory or otherwise. Prioritize a complete, clean, and readable implementation.

You may use any and as many auxiliary data structures as you see fit, and any metadata you need to maintain may be stored in memory exclusively; however, the content of the files themselves needs to be written only to the block device.

Class you will be implementing

```python
class FileStore:
    def put(self, file_name: str, file_content: str):
        # Creates a new file with the specified name and content.
        pass

    def get(self, file_name: str):
        # Gets the content of the ASCII file.
        pass

    def delete(self, file_name: str):
        # Deletes the specified file.
        pass
```

Block device (Python)
The database should use our prewritten BlockDevice class. This class is essentially an array of fixed-width “blocks” that store arbitrary UTF-8 strings.

```python
>>> # Create a block device with 1024 blocks that can each fit an 8 character string; every read/write has a 1% chance of corruption.
>>> block_device = BlockDevice.get_new_block_device(
            block_count=1024,
            block_size=8,
            corruption_rate=0.01
        )

>>> # Write content to block 0.
>>> block_device.write(index=0, content=”12345678”)
12345678

>>> # Read content from block 0.
>>> block_device.read(index=0)
12345678

>>> # If content length exceeds the block size, the content is truncated.
>>> block_device.write(index=0, content=”123456789”)
12345678

>>> # This read caused a corruption of block 0's content.
>>> block_device.read(index=0)
rcjutrvg

>>> # The corruption is durable (unless corrupted again).
>>> block_device.read(index=0)
rcjutrvg

>>> # This write's content is corrupted.
>>> block_device.write(index=0, content="Corrupt")
xtjuvrvr
```
