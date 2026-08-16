import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

import macip_lib
from macip_lib import MacipError

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"


def load_installer():
    spec = importlib.util.spec_from_file_location("install_rotation", TOOLS_DIR / "install_rotation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def installer():
    return load_installer()


@pytest.fixture
def cli(monkeypatch):
    def _cli(module, argv):
        monkeypatch.setattr("sys.argv", [module.__file__] + argv)
        try:
            module.main()
            return 0
        except SystemExit as exc:
            return exc.code
    return _cli


# --------------------------------------------------------------------------
# Unit file rendering
# --------------------------------------------------------------------------

def test_render_service_unit(installer, tmp_path):
    tool = tmp_path / "06_auto_macip_changer.py"
    unit = installer.render_service_unit("/usr/bin/python3", tool, "wlan0", 1, "")
    assert 'ExecStart="/usr/bin/python3" ' in unit
    assert str(tool) in unit
    assert "-i wlan0" in unit
    assert "--no-save" in unit
    assert "--times 1" in unit
    assert "Description=MacIP - automatic MAC/IP rotation for wlan0" in unit


def test_render_service_unit_includes_extra_flags(installer, tmp_path):
    tool = tmp_path / "04_auto_ip_changer.py"
    unit = installer.render_service_unit("/usr/bin/python3", tool, "eth0", 3, "--ipv6 --network6 fd00::/64")
    assert "--ipv6 --network6 fd00::/64" in unit
    assert "--times 3" in unit


def test_render_timer_unit(installer):
    unit = installer.render_timer_unit("wlan0", "30min", "macip-rotate")
    assert "OnUnitActiveSec=30min" in unit
    assert "Unit=macip-rotate.service" in unit
    assert "WantedBy=timers.target" in unit


# --------------------------------------------------------------------------
# Install flow
# --------------------------------------------------------------------------

def test_install_writes_units_and_enables_timer(cli, installer, tmp_path, monkeypatch, capsys):
    systemctl_calls = []

    def fake_run(cmd, check=False):
        systemctl_calls.append(list(cmd))
        return __import__("subprocess").CompletedProcess(list(cmd), 0, "", "")

    monkeypatch.setattr(macip_lib, "_run", fake_run)
    code = cli(installer, ["-i", "wlan0", "--dest", str(tmp_path)])
    assert code == 0

    service = tmp_path / "macip-rotate.service"
    timer = tmp_path / "macip-rotate.timer"
    assert service.is_file()
    assert timer.is_file()
    assert "-i wlan0 --no-save --times 1" in service.read_text()
    assert "OnUnitActiveSec=5min" in timer.read_text()

    assert systemctl_calls == [
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", "--now", "macip-rotate.timer"],
    ]
    out = capsys.readouterr().out
    assert "Scheduled rotation installed" in out


def test_install_with_changer_flags(cli, installer, tmp_path, monkeypatch):
    monkeypatch.setattr(
        macip_lib, "_run",
        lambda cmd, check=False: __import__("subprocess").CompletedProcess(list(cmd), 0, "", ""),
    )
    code = cli(installer, [
        "-i", "eth0", "--tool", "04_auto_ip_changer.py", "--ipv6",
        "--network6", "fd00::/64", "--every", "30min", "--dest", str(tmp_path),
    ])
    assert code == 0
    unit = (tmp_path / "macip-rotate.service").read_text()
    assert "04_auto_ip_changer.py" in unit
    assert "--ipv6" in unit
    assert "--network6 fd00::/64" in unit
    assert "OnUnitActiveSec=30min" in (tmp_path / "macip-rotate.timer").read_text()


def test_build_changer_flags(installer):
    args = argparse.Namespace(ipv6=True, network=None, network6="fd00::/64",
                              interval=2.5, extra="")
    assert installer._build_changer_flags(args) == "--ipv6 --network6 fd00::/64 --interval 2.5"
    args.ipv6 = False
    args.interval = None
    assert installer._build_changer_flags(args) == "--network6 fd00::/64"
    args.extra = "--times=3"
    assert installer._build_changer_flags(args) == "--network6 fd00::/64 --times=3"


def test_uninstall_removes_units(cli, installer, tmp_path, monkeypatch):
    (tmp_path / "macip-rotate.service").write_text("x")
    (tmp_path / "macip-rotate.timer").write_text("x")
    systemctl_calls = []

    def fake_run(cmd, check=False):
        systemctl_calls.append(list(cmd))
        return __import__("subprocess").CompletedProcess(list(cmd), 0, "", "")

    monkeypatch.setattr(macip_lib, "_run", fake_run)
    code = cli(installer, ["-i", "wlan0", "--uninstall", "--dest", str(tmp_path)])
    assert code == 0
    assert not (tmp_path / "macip-rotate.service").exists()
    assert not (tmp_path / "macip-rotate.timer").exists()
    assert systemctl_calls[0] == ["systemctl", "disable", "--now", "macip-rotate.timer"]


def test_dry_run_changes_nothing(cli, installer, tmp_path, monkeypatch, capsys):
    def boom(cmd, **kwargs):
        raise AssertionError("must not run any command in dry-run")

    monkeypatch.setattr(macip_lib, "_run", boom)
    code = cli(installer, ["-i", "wlan0", "--dest", str(tmp_path), "--dry-run"])
    assert code == 0
    assert not list(tmp_path.glob("macip-rotate.*"))
    out = capsys.readouterr().out
    assert "[dry-run] would run: systemctl enable --now macip-rotate.timer" in out


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def test_unknown_tool_rejected(cli, installer, tmp_path, capsys):
    code = cli(installer, ["-i", "wlan0", "--tool", "nope.py", "--dest", str(tmp_path)])
    assert code == 1
    assert "not found" in capsys.readouterr().out


def test_invalid_extra_flags_rejected(cli, installer, tmp_path, capsys):
    code = cli(installer, ["-i", "wlan0", "--extra", '--evil";rm -rf /', "--dest", str(tmp_path)])
    assert code == 1
    assert "must not contain" in capsys.readouterr().out
