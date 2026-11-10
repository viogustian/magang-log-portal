"""Tests for server and desktop child process lifecycle management."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from magang_log.server.lifecycle import find_desktop_executable, launch_server_and_desktop


def test_find_desktop_executable_custom_path_exists(tmp_path: Path) -> None:
    fake_exe = tmp_path / "MagangLogPortal.exe"
    fake_exe.touch()
    found = find_desktop_executable(custom_path=str(fake_exe))
    assert found == fake_exe


def test_find_desktop_executable_not_found() -> None:
    found = find_desktop_executable(custom_path="nonexistent_folder/nonexistent.exe")
    assert found is None


def test_launch_server_and_desktop_loopback_rejection() -> None:
    with pytest.raises(ValueError, match="loopback"):
        launch_server_and_desktop(
            view="dashboard",
            host="0.0.0.0",
            port=8000,
            server_only=True,
        )


def test_launch_server_and_desktop_ui_mode(tmp_path: Path) -> None:
    fake_exe = tmp_path / "MagangLogPortal.exe"
    fake_exe.touch()

    mock_proc = MagicMock()
    mock_proc.wait.return_value = 0
    mock_proc.poll.return_value = 0

    with (
        patch("magang_log.server.lifecycle.ServerRunner") as mock_runner_cls,
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        mock_runner = MagicMock()
        mock_runner.url = "http://127.0.0.1:8000"
        mock_runner_cls.return_value = mock_runner

        ret = launch_server_and_desktop(
            view="dashboard",
            host="127.0.0.1",
            port=8000,
            exe_path=str(fake_exe),
        )

        assert ret == 0
        mock_runner.start.assert_called_once()
        mock_popen.assert_called_once_with(
            [str(fake_exe), "--view=dashboard", "--api-url=http://127.0.0.1:8000"]
        )
        mock_runner.stop.assert_called_once()


def test_launch_server_and_desktop_setup_mode(tmp_path: Path) -> None:
    fake_exe = tmp_path / "MagangLogPortal.exe"
    fake_exe.touch()

    mock_proc = MagicMock()
    mock_proc.wait.return_value = 0
    mock_proc.poll.return_value = 0

    with (
        patch("magang_log.server.lifecycle.ServerRunner") as mock_runner_cls,
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        mock_runner = MagicMock()
        mock_runner.url = "http://127.0.0.1:8000"
        mock_runner_cls.return_value = mock_runner

        ret = launch_server_and_desktop(
            view="setup",
            host="127.0.0.1",
            port=8000,
            exe_path=str(fake_exe),
        )

        assert ret == 0
        mock_runner.start.assert_called_once()
        mock_popen.assert_called_once_with(
            [str(fake_exe), "--view=setup", "--api-url=http://127.0.0.1:8000"]
        )
        mock_runner.stop.assert_called_once()


def test_launch_server_and_desktop_handles_keyboard_interrupt(tmp_path: Path) -> None:
    fake_exe = tmp_path / "MagangLogPortal.exe"
    fake_exe.touch()

    mock_proc = MagicMock()
    mock_proc.wait.side_effect = [KeyboardInterrupt, 0]
    mock_proc.poll.return_value = None

    with (
        patch("magang_log.server.lifecycle.ServerRunner") as mock_runner_cls,
        patch("subprocess.Popen", return_value=mock_proc),
    ):
        mock_runner = MagicMock()
        mock_runner.url = "http://127.0.0.1:8000"
        mock_runner_cls.return_value = mock_runner

        ret = launch_server_and_desktop(
            view="dashboard",
            host="127.0.0.1",
            port=8000,
            exe_path=str(fake_exe),
        )

        assert ret == 0
        mock_proc.terminate.assert_called_once()
        mock_runner.stop.assert_called_once()
