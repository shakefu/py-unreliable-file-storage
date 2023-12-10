# py-unreliable-file-storage

![CI](https://github.com/shakefu/py-unreliable-file-storage/actions/workflows/ci.yaml/badge.svg)

What if we wanted really unreliable file storage?

## Installation

This package can be installed using `pip` and a git URL:

```bash
pip install git+https://github.com/shakefu/py-unreliable-file-storage.git
```

## Usage

The main class is `file_store.FileStore` and it can be used like this:

```python
import file_store

# Create a FileStore with defaults
store = file_store.FileStore()

# Store some data in a file
store.put("parrot.txt", "It's a norwegian blue!")

# Read that file back
content = store.get("parrot.txt")

# Check if your file was corrupted
if store.is_corrupted(content):
    print("Oh no! The file is corrupted!")

# Delete your file
store.delete("parrot.txt")

# Check your remaining free space
print(f"Free space: {store.free_space()} bytes"

```

## Reference

The API reference documentation is provided by `mkdocs`. To build the docs and view them, run:

```bash
git clone https://github.com/shakefu/py-unreliable-file-storage.git
cd py-unreliable-file-storage
pip install poetry
poetry install
poetry run mkdocs serve
```

> [!NOTE]
> These should be built and hosted, but since this is a private project that
> shouldn't get out there publicly, we're not going to do that.

## Development

This project uses `poetry` for dependency management and packaging. To get started, run:

```bash
git clone https://github.com/shakefu/py-unreliable-file-storage.git
cd py-unreliable-file-storage
pip install poetry
poetry install
poetry shell
```

This will put you in a virtualenv shell where you can interact with the project
environment safely.

### Testing

All tests are located in the `tests/` directory and can be run with `pytest`:

```bash
poetry run pytest -vv
```
