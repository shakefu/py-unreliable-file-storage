import pytest
import unittest

from file_store import file_store


class FileStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.file_store = file_store.FileStore()

    @pytest.mark.skip("Comment this line to start working on it")
    def test_put(self):
        self.assertEqual(
            self.file_store.put("hello.txt", "lorem ipsum dolor sit amet"),
            "lorem ipsum dolor sit amet",
        )

    @pytest.mark.skip("Comment this line to start working on it")
    def test_get(self):
        self.file_store.put("hello.txt", "lorem ipsum dolor sit amet again")
        self.assertEqual(
            self.file_store.get("hello.txt"), "lorem ipsum dolor sit amet again"
        )

    @pytest.mark.skip("Comment this line to start working on it")
    def test_delete(self):
        self.file_store.put("hello.txt", "and again, lorem ipsum dolor sit amet")
        self.assertEqual(
            self.file_store.get("hello.txt"), "and again, lorem ipsum dolor sit amet"
        )
        self.file_store.delete("hello.txt")
        with self.assertRaises(ValueError):
            self.file_store.get("hello.txt")


def test_chunkstring_stolen_from_the_internet():
    val = "foobaryou"
    res = list(file_store.chunkstring(val, 3))
    assert res == ["foo", "bar", "you"]


def test_filestore_returns_the_data_written_on_put():
    store = file_store.FileStore(corruption_rate=0)
    expected = "foobaryou"
    val = store.put("test_file", expected)
    assert val == expected


def test_filestore_returns_the_data_written_on_put_with_longer_data():
    store = file_store.FileStore(corruption_rate=0)
    expected = "foobaryou123456789wertyuiosdfghjklcvbhijuyt5r4ewsdfghyu1"
    val = store.put("test_file", expected)
    assert val == expected


def test_filestore_stores_the_blocks_we_expected():
    store = file_store.FileStore(corruption_rate=0)
    content = "foobaryou"
    fname = "test_file"
    store.put(fname, content)
    entry = file_store.FileStore.FileMetadata(length=len(content), blocks=[0, 1])
    index = {fname: entry}
    assert store.file_index == index


def test_filestore_is_full_of_stuff():
    store = file_store.FileStore(block_count=1, corruption_rate=0)
    expected = "foobaryou"
    with pytest.raises(file_store.OutOfSpaceError):
        val = store.put("test_file", expected)
        assert val == expected


def test_file_store_raises_error_when_we_dont_have_the_file():
    store = file_store.FileStore(block_count=1, corruption_rate=0)
    with pytest.raises(file_store.NotFoundError):
        store.get("file_not_found")


@pytest.mark.parametrize(
    "expected",
    [
        (
            "This is an excessively long single line of text that should be "
            "split into multiple blocks."
        ),
        (
            """
        AI generated content:
        Testing is crucial in software development as it ensures the correctness,
        reliability, and performance of the software. It helps to identify and fix
        bugs and errors before the software becomes operational. Without proper
        testing, users may encounter problems like system crashes, data loss, or
        even security breaches. Furthermore, testing provides feedback on software
        features and helps developers understand if the software meets the business
        needs and requirements. It also improves the quality of the software,
        thereby enhancing user satisfaction.
        """
        ),
        (""),
    ],
)
def test_file_store_writes_consistently(expected):
    block_size = 8
    blocks = file_store.calculate_blocks_needed(expected, block_size)
    store = file_store.FileStore(
        block_count=blocks, block_size=block_size, corruption_rate=0.5
    )
    store.put("test_file", expected)
    # Cheating by using the internal block device
    found = "".join((b[:-1] for b in store.store._blocks[0:blocks]))
    # Trim random garbage from found because it's longer than expected
    assert expected == found[0 : len(expected)]


def test_delete_raises_error_for_bad_filename():
    store = file_store.FileStore(block_count=1, corruption_rate=0)
    with pytest.raises(file_store.NotFoundError):
        store.delete("foobar")


def test_it_will_timeout_when_writing_highly_corrupt_devices():
    store = file_store.FileStore(block_count=1, corruption_rate=1, timeout=0.01)
    with pytest.raises(file_store.FileStoreError):
        store.put("file_name", "this is a test")


@pytest.mark.parametrize("val,count", [(1, 8), (2, 16), (3, 24), (4, 32)])
def test_free_bytes(val, count):
    store = file_store.FileStore(block_count=val, corruption_rate=0)
    assert store.free() == count


@pytest.mark.parametrize(
    "val,count",
    [
        ("1234567", 1),
        ("12345678", 2),
        ("12345678901234", 2),
        ("123456789012345", 3),
    ],
)
def test_calculate_blocks_needed(val, count):
    blocks = file_store.calculate_blocks_needed(val, 8)
    assert blocks == count


def test_get_replica_blocks():
    store = file_store.FileStore(replicas=2, block_count=64)
    blocks = store._get_replica_blocks(1)
    assert blocks == [[0], [32]]


def test_get_replica_blocks_with_leftover():
    store = file_store.FileStore(replicas=3, block_count=100)
    blocks = store._get_replica_blocks(1)
    assert blocks == [[0], [33], [66]]


def test_delete_restores_free_block_count():
    content = "That parrot is no more!"
    block_count = 16
    store = file_store.FileStore(block_count=block_count)
    free_bytes = block_count * store.block_size
    assert store.free() == free_bytes

    store.put("parrot.txt", content)
    expected = block_count - file_store.calculate_blocks_needed(
        content, store.block_size
    )
    expected *= store.block_size
    assert store.free() == expected
    assert expected < free_bytes

    store.delete("parrot.txt")
    assert store.free() == free_bytes


def test_delete_restores_free_block_count_with_replicas():
    content = "That parrot is no more!"
    block_count = 32
    replicas = 4
    store = file_store.FileStore(replicas=replicas, block_count=block_count)
    content_blocks = file_store.calculate_blocks_needed(content, store.block_size)
    assert content_blocks == 4

    free_bytes = block_count * store.block_size / replicas
    assert store.free() == free_bytes

    store.put("parrot.txt", content)
    expected = ((block_count / replicas) - content_blocks) * store.block_size
    assert store.free() == expected
    assert expected < free_bytes

    store.delete("parrot.txt")
    assert store.free() == free_bytes


def test_get_gives_us_our_file_back_with_no_corruption_or_replicas():
    content = "Sphinx of black quartz, judge my vow."
    store = file_store.FileStore(corruption_rate=0)
    val = store.put("sphinx.txt", content)
    assert val == content
    val = store.get("sphinx.txt")
    assert val == content


def test_get_gives_us_our_file_back_with_no_corruption_or_replicas_long():
    content = "Sphinx of black quartz, judge my vow. " * 100
    store = file_store.FileStore(corruption_rate=0)
    val = store.put("sphinx.txt", content)
    assert val == content
    val = store.get("sphinx.txt")
    assert val == content


def test_get_gives_us_our_file_back_with_no_corruption_longish():
    content = "Sphinx of black quartz, judge my vow. " * 50
    store = file_store.FileStore(replicas=3, corruption_rate=0)
    val = store.put("sphinx.txt", content)
    assert val == content
    val = store.get("sphinx.txt")
    assert val == content


# Don't fail the suite cause of the extremes of probability
@pytest.mark.xfail(strict=False)
def test_get_gives_us_our_file_back_with_corruption_no_replicas():
    # So this is basically a statistical test, so we want to ensure we look at
    # it that way
    content = "Sphinx of black quartz, judge my vow."
    store = file_store.FileStore(corruption_rate=0.1)

    successes = 0
    for _ in range(100):
        val = store.put("sphinx.txt", content)
        assert val == content
        val = store.get("sphinx.txt")
        if val == content:
            successes += 1
            store.delete("sphinx.txt")

    assert successes > 0

    # This is a pretty weak test because we're using such a small sample for
    # speed's sake, but it's better than nothing - we would expect a 46%
    # corruption rate for a 6 block file
    assert successes > 35 and successes < 65


@pytest.mark.xfail(strict=False)
def test_get_gives_us_our_file_back_with_corruption_with_replicas():
    content = "Sphinx of black quartz, judge my vow."
    store = file_store.FileStore(replicas=5, corruption_rate=0.1)

    successes = 0
    for _ in range(100):
        val = store.put("sphinx.txt", content)
        assert val == content
        val = store.get("sphinx.txt")
        if val == content:
            successes += 1
            store.delete("sphinx.txt")

    assert successes > 0
    # We would expect with 5 replicas, a 0.0006% corruption rate, so we should
    # see 100 successes
    assert successes == 100
