"""
Test demo script to ensure it never breaks in the future.
"""
import sys
import importlib

import pytest


@pytest.fixture
# def mock_sys_path_scripts(mocker: pytest_mock.plugin.MockerFixture) -> unittest.mock.MagicMock:
def mock_sys_path_scripts(mocker):
    """Adds the scripts directory to the sys.path."""
    return mocker.patch("sys.path", ["scripts"] + sys.path)


def test_demo_block_device(mock_sys_path_scripts, capsys):
    importlib.import_module("demo_block_device")
    captured = capsys.readouterr()
    # This is a super soft assert because the output can change run to run, but
    # we can make a stronger assert later if we want. Probably not worth it.
    assert captured.out.endswith("Success!\n")
