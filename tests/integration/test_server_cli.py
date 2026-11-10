"""Integration tests for `magang-log ui` and `magang-log setup` CLI entry points."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from magang_log.cli import main


def test_cli_ui_invokes_lifecycle_with_dashboard_view() -> None:
    with patch("magang_log.server.lifecycle.launch_server_and_desktop", return_value=0) as mock_launch:
        code = main(["ui", "--port", "8123", "--host", "127.0.0.1"])
        assert code == 0
        mock_launch.assert_called_once_with(
            view="dashboard",
            host="127.0.0.1",
            port=8123,
            exe_path=None,
            server_only=False,
        )


def test_cli_setup_invokes_lifecycle_with_setup_view() -> None:
    with patch("magang_log.server.lifecycle.launch_server_and_desktop", return_value=0) as mock_launch:
        code = main(["setup", "--port", "8456", "--exe", "custom/app.exe", "--server-only"])
        assert code == 0
        mock_launch.assert_called_once_with(
            view="setup",
            host="127.0.0.1",
            port=8456,
            exe_path="custom/app.exe",
            server_only=True,
        )


def test_cli_ui_rejects_non_loopback_host() -> None:
    # When non-loopback host is passed, launch_server_and_desktop raises ValueError
    code = main(["ui", "--host", "0.0.0.0"])
    # CLI catches unhandled exception and exits with error code
    assert code != 0


def test_cli_ui_end_to_end_orchestration(tmp_path: Path) -> None:
    fake_exe = tmp_path / "MagangLogPortal.exe"
    fake_exe.touch()

    mock_proc = MagicMock()
    mock_proc.wait.return_value = 42

    with (
        patch("magang_log.server.lifecycle.ServerRunner") as mock_runner_cls,
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        mock_runner = MagicMock()
        mock_runner.url = "http://127.0.0.1:8100"
        mock_runner_cls.return_value = mock_runner

        code = main(["ui", "--port", "8100", "--exe", str(fake_exe)])
        assert code == 42
        mock_runner.start.assert_called_once()
        mock_popen.assert_called_once_with(
            [str(fake_exe), "--view=dashboard", "--api-url=http://127.0.0.1:8100"]
        )
        mock_runner.stop.assert_called_once()


def test_cli_setup_end_to_end_orchestration(tmp_path: Path) -> None:
    fake_exe = tmp_path / "MagangLogPortal.exe"
    fake_exe.touch()

    mock_proc = MagicMock()
    mock_proc.wait.return_value = 0

    with (
        patch("magang_log.server.lifecycle.ServerRunner") as mock_runner_cls,
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        mock_runner = MagicMock()
        mock_runner.url = "http://127.0.0.1:8200"
        mock_runner_cls.return_value = mock_runner

        code = main(["setup", "--port", "8200", "--exe", str(fake_exe)])
        assert code == 0
        mock_runner.start.assert_called_once()
        mock_popen.assert_called_once_with(
            [str(fake_exe), "--view=setup", "--api-url=http://127.0.0.1:8200"]
        )
        mock_runner.stop.assert_called_once()
