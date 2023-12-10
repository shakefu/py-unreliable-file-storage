"""This package provides the FileStore class for storing ASCII text files.

This is a toy project, don't ever use it if you find it.

"""
import sys
import math
import functools
from collections import namedtuple
from typing import Iterator, Optional, Callable

import pytool

from . import block_device


class FileStoreError(Exception):
    """Raised for errors related to the FileStore class.

    This is a parent class to all specific exceptions such as `NotFoundError` and `OutOfSpaceError`.
    """


class ParameterError(FileStoreError, ValueError):
    """Raised when an invalid parameter is passed to a `FileStore`.

    This indicates the parameter name and value that were invalid in its error message.
    """


class NotFoundError(FileStoreError, RuntimeError, ValueError):
    """Raised when attempting to access a file that does not exist.

    This should indicate the file name that was not found in its error message.
    """


class OutOfSpaceError(FileStoreError, RuntimeError):
    """Raised when there are no more unwritten blocks available in the `FileStore`.

    If this is raised, the `FileStore` should be considered full, and no more files written until files are deleted.

    """


class TimeoutError(FileStoreError, RuntimeError):
    """Raised when a write times out.

    If this is raised, a write can be retried if desired.

    """


class FileStore:
    """File storage for reading and writing ASCII text files.

    Args:
        replicas (int, optional): The number of replicas to write for each file.
        timeout (float, optional): The timeout for a write to succeed.
        block_count (int, optional): The number of blocks to use for storage.
        block_size (int, optional): The size of each block.
        corruption_rate (float, optional): The rate at which blocks will be corrupted.

    **Example:**

    ```python
    import file_store

    # Create a new file store with 2 replicas, a 1 second timeout, 1024 blocks,
    store = file_store.FileStore(replicas=2, timeout=1.0, block_count=1024)
    store.put("myfile.txt", "This is the content of myfile.txt")
    content = store.get("myfile.txt")
    store.delete("myfile.txt")
    ```

    """

    FileMetadata = namedtuple("FileMetadata", ["length", "blocks"])

    store: block_device.BlockDevice
    block_count: int
    block_size: int
    corruption_rate: float
    timeout: float
    file_index: dict[str, FileMetadata]
    free_blocks: list[int]

    def __init__(
        self,
        replicas: int = 1,
        timeout: float = 1.0,
        block_count: int = 1024,
        block_size: int = 8,
        corruption_rate: float = 0.0,
    ):
        # Check params for validity, with a locals hack
        _check_filestore_params(**locals())

        # Tuning params for our FileStore behavior
        # Replicas lets us have durability
        self.replicas = replicas
        # Timeout limits how long we will wait for a write to succeed
        self.timeout = timeout

        # Handy reference to the BlockDevice params
        self.block_count = block_count
        self.block_size = block_size
        self.corruption_rate = corruption_rate
        self.store = block_device.BlockDevice.get_new_block_device(
            block_count, block_size, corruption_rate
        )

        # In a more sane implementation, we would write the index itself to the
        # block device... but the extremely unreliable reads make that
        # difficult, so we'll just keep it in memory
        self.file_index = {}

        # This is not a great implementation, but it will do for now
        self.free_blocks = [k for k in range(int(block_count / replicas))]

    def free(self) -> int:
        """Return the number of free bytes in the `FileStore`.

        Returns:
            int: The number of free bytes in the `FileStore`.

        """
        return len(self.free_blocks) * self.block_size

    def put(self, file_name: str, file_content: str) -> str:
        """Creates a new file with the specified name and content.

        Arguments:
            file_name: Name of the new file to create
            file_content (str): String content for the new file

        Returns:
            str: Contents actually written to block device

        Raises:
            OutOfSpaceError: If there is not enough space to write the file.
            TimeoutError: If the write times out.

        """
        # If the file already exists, delete it
        try:
            self.delete(file_name)
        except NotFoundError:
            # This is expected if the file doesn't exist
            pass

        # Calculate the length of the file content when each block has an
        # additional byte attached
        block_count = calculate_blocks_needed(file_content, self.block_size)

        # Check if we have free space available
        if len(self.free_blocks) < block_count:
            raise OutOfSpaceError(
                f"Not enough space for {file_name}, need {block_count} blocks, "
                f"have {len(self.free_blocks)} free blocks"
            )

        # Split the content into chunks sized one byte smaller than a block, so we can add a null byte to use as a check for corruption
        # NOTE(shakefu): This is a total cheat, because we know the random
        # corruption will not generate null bytes. A more sophisticated
        # algorithm would use a checksum for segments of blocks and check that,
        # or maintain a parity check, or both. This is a solved problem.
        chunks = list(chunkstring(file_content, self.block_size - 1))

        # Mutate the chunks to add null bytes out to the block_size (effectively
        # 1 per chunk, except the final chunks)
        chunks = [chunk + "\x00" * (self.block_size - len(chunk)) for chunk in chunks]

        # All the blocks we're going to write to
        replica_blocks = self._get_replica_blocks(block_count)

        # Write out all of our chunks to our replica blocks
        for blocks in replica_blocks:
            for i in range(len(chunks)):
                self._put(blocks[i], chunks[i])

        # We need to save the length so we can truncate the final block after we
        # regurgitate it, and we only need to save the first list of replica
        # blocks because all the rest are a fixed offset
        metadata = self.FileMetadata(
            length=len(file_content),
            blocks=replica_blocks[0],
        )

        # "Save" our metadata by storing it in the memory index
        self.file_index[file_name] = metadata

        # Claim the blocks we used, so they can't be reused
        self.free_blocks = self.free_blocks[block_count:]

        # Return the content we wrote, by cheating
        return file_content

    def _get_replica_blocks(
        self, block_count: int, blocks: Optional[list[int]] = None
    ) -> list[list[int]]:
        """Return a list of lists of the free blocks to write to.

        The outer list is the replicas, and the inner list is the blocks to be
        written within each replica.

        Args:
            block_count (int): The number of blocks to write.

        Returns:
            list[list[int]]: A list of lists of the free blocks to write to.

        """
        if blocks is None:
            blocks = self.free_blocks[:block_count]
        # Floored offset representing the space available for each set of replicas
        offset = int(self.block_count / self.replicas)
        # Make a 2D array of the blocks that are in the replica set
        return [
            [block + (offset * i) for block in blocks] for i in range(self.replicas)
        ]

    def _put(self, block: int, chunk: str) -> None:
        """Strongly put a chunk to a block, handling failures transparently.

        This will retry the write until it's successful or until it times out.

        Args:
            block (int): The block to write to.
            chunk (str): The chunk to write.

        Raises:
            TimeoutError: If the chunk cannot be written to the block.

        """
        nulls = "\x00" * self.block_size
        timer = pytool.time.Timer()
        # Loop to ensure the chunk gets written faithfully
        while True:
            # Extend the chunk to the full block size with null bytes
            data = chunk + nulls[len(chunk) :]
            # Iterate over the chunks, write each one to a free block
            val = self.store.write(block, data)
            # Make sure our write was successful
            if data == val:
                break

            # Don't let this loop forever in highly corrupt environments
            if timer.elapsed.total_seconds() > self.timeout:
                raise TimeoutError("Failed to write chunk to block: timeout")

    def get(self, file_name: str) -> str:
        """Return the contents of `file_name` in our file storage.

        If the file is corrupted, it will be deleted, and a `StorageCorrupt` will
        be returned. This will contain whatever data could be recovered from the
        block device, with null bytes in place of corrupted blocks. See the
        documentation for `StorageCorrupt` for more information.

        Args:
            file_name (str): The name of the file to retrieve.

        Returns:
            str: The contents of the file.

        Raises:
            NotFoundError: If the file does not exist.

        """
        # Get the metadata for the file
        metadata = self.file_index.get(file_name, None)
        if metadata is None:
            raise NotFoundError(f"{file_name} is not found")

        # Get all the replicas we're going to read from for this file
        replica_blocks = self._get_replica_blocks(len(metadata.blocks), metadata.blocks)

        # Corruption flag
        corrupted = False
        # Chunked data for our eventual file
        chunks = []

        # Loop over the first replica, reading data
        for i in range(len(replica_blocks[0])):
            # Read our block and check for corruption
            chunk = self.store.read(replica_blocks[0][i])
            if chunk[-1] == "\x00":
                chunks.append(chunk[:-1])
                continue

            # If we get here, we have a corrupted block, so we need to read the
            # next replica and correct our bad blocks
            bad_blocks = [replica_blocks[0][i]]
            for j in range(1, len(replica_blocks)):
                # Read the next replica's block
                chunk = self.store.read(replica_blocks[j][i])

                # If it's not corrupted, we can use it, and correct our bad block(s)
                if chunk[-1] == "\x00":
                    chunks.append(chunk[:-1])
                    for block in bad_blocks:
                        self.store.write(block, chunk)
                    bad_blocks = []
                    break

            # If we still have bad blocks, we're in trouble
            if bad_blocks:
                # Set the corruption flag so we can handle this sanely
                corrupted = True
                # Append a null chunk
                chunks.append("\x00" * (self.block_size - 1))
                # Reset the bad blocks to continue reading the remaining file
                bad_blocks = []

        # A corrupted file is unrecoverable, so we just delete it
        if corrupted:
            self.delete(file_name)

        # Return the truncated chunks to match the original file length
        content = "".join(chunks)[: metadata.length]

        if corrupted:
            return StorageCorrupt(content)

        return content

    def delete(self, file_name: str) -> None:
        """Deletes the specified file.

        Args:
            file_name (str): Name of the file to delete.

        Raises:
            NotFoundError: If the file does not exist.

        """
        metadata = self.file_index.pop(file_name, None)
        if not metadata:
            raise NotFoundError(f"{file_name} is not found")

        # We only return the 1st replica's blocks back to the list, effectively
        # unclaiming all the blocks
        self.free_blocks.extend(metadata.blocks)

    def is_corrupted(self, content: str) -> bool:
        """Returns True if the content is corrupted, False otherwise.

        Args:
            content (str): The content to check.

        Returns:
            bool: True if the content is corrupted, False otherwise.

        """
        return isinstance(content, StorageCorrupt)


def chunkstring(value: str, size: int) -> Iterator[str]:
    """Return `value` broken into chunks of `size` (or less).

    Args:
        value (str): The value to chunk.
        size (int): The size of each chunk.

    Returns:
        Iterator[str]: An iterator over the chunks of `value`.

    """
    return (value[0 + i : size + i] for i in range(0, len(value), size))


def _wrap_asserts(fn: Callable) -> Callable:
    """Wrap `fn` to catch `AssertionError`s and re-raise as `ParameterError`s.

    This is a bit superfluous because we're only using it in one place, but
    decorators are fun and delicious. And it saves us an indent level in the
    wrapped function for more horizontal space for cleaner error messages.

    Args:
        fn (function): The function to wrap.

    Returns:
        function: The wrapped function.

    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AssertionError:
            # This is to transparently preserve the original traceback so we can
            # see what calling code caused this, rather than just the wrapper
            _, value, traceback = sys.exc_info()
            raise ParameterError(value).with_traceback(traceback)

    return wrapper


@_wrap_asserts
def _check_filestore_params(
    replicas: int,
    timeout: float,
    block_count: int,
    block_size: int,
    corruption_rate: float,
    **kwargs,
) -> None:
    """
    Ensures all the arguments are within allowed ranges and are valid.

    This is lifted from FileStore.__init__ just for ease of reading and
    maintainence.

    Raises:
        ParameterError: If any of the parameters are invalid.

    """
    assert replicas > 0, f"'replicas' must be a positive integer: {replicas} > 0"

    assert (
        block_count >= 1
    ), f"'block_count' must be a positive integer: {block_count} >= 1"

    assert (
        replicas <= block_count
    ), f"'replicas' must be <= 'block_count': {replicas} <= {block_count}"

    # This isn't strictly necessary, it will just waste space if it's not evenly
    # divisible
    # assert block_count % replicas == 0, \
    #     (f"'block_count' must be divisible by 'replicas': {block_count} % "
    #      f"{replicas} == {block_count % replicas}")

    assert timeout > 0, f"'timeout' must be a positive float: {timeout} > 0"

    assert (
        block_size >= 2
    ), f"'block_size' must be greater than 2 bytes: {block_size} >= 2"

    assert (
        corruption_rate >= 0.0
    ), f"'corruption_rate' must be a positive float: {corruption_rate} >= 0.0"

    assert (
        corruption_rate <= 1.0
    ), f"'corruption_rate' must be less than or equal to 1: {corruption_rate} <= 1.0"

    # NOTE(shakefu): You could add asserts for the upper limits on storage,
    # replicas, etc. It might not actually break at the upper bounds of what
    # Python does, but become incredibly painfully slow. Certainly it's not
    # going to support 2^64 blocks in a device.


def calculate_blocks_needed(file_content: str, block_size: int) -> int:
    """Calculate the number of blocks needed to store `file_content`.

    The returned value is the number of blocks for a single replica.

    Args:
        file_content (str): The content to calculate the number of blocks
            needed for.

    Returns:
        int: The number of blocks needed to store `file_content`.

    """
    # Calculate the length of the file content when each block has an additional
    # byte attached
    block_count = len(file_content) / block_size
    block_count = block_count / (block_size - 1) * block_size
    block_count = math.ceil(block_count)
    return block_count or 1


class StorageCorrupt(str):
    """Represents a file that has been at least partially corrupted.

    This is a subclass of `str` so it can be used in place of a normal string,

    This subclass overrides `__bool__` so that its truthy value is always False.

    The best way to check for a corrupted file is to use the helper method `is_corrupted()` on the `FileStore` class:

    ```python
    data = StorageCorrupt("This is a corrupted file!")
    FileStore().is_corrupt(data)  # True
    ```

    It is also effective to use `isinstance`:

    ```python
    data = StorageCorrupt("This is a corrupted file!")
    if isinstance(data, StorageCorrupt):
        print("This file is corrupted!")
    ```

    Alternatively you can compare the length and truthiness, which may be faster
    in some cases:

    ```python
    data = StorageCorrupt("This is a corrupted file!")
    if len(data) and not data:
        print("This file is corrupted!")
    ```

    """

    def __bool__(self):
        return False
