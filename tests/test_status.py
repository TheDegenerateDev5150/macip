import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import macip_lib
from macip_lib import MacipError

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"


def load_status():
    spec = importlib.util.spec_from_file_location("status", TOOLS_DIR / "status.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def status_mod():
    return load_status()


@pytest.fixture
def cli(monkeypatch):
    def _cli(module, argv):
        monkeypatch.setattr("sys.argv", [module.__file__] + argv)
        module.main()
        return 0
    return _cli


def _write_state(interface, mac="00:11:22:33:44:55", ip="192.168.1.9",
                  ip6=None, saved_at=1700000000):
    macip_lib.STATE_DIR.mkdir(parents=True, exist_ok=True)
    (macip_lib.STATE_DIR / f"{interface}.json").write_text(json.dumps({
        "interface": interface, "mac": mac, "ip": ip, "ip6": ip6,
        "saved_at": saved_at,
    }))


# --------------------------------------------------------------------------
# Saved configurations
# --------------------------------------------------------------------------

def test_saved_configs_rows():
    _write_state("eth0", ip6="fd00::1")
    _write_state("wlan0", mac="aa:bb:cc:dd:ee:ff")
    rows = {r[0]: r for r in load_status().saved_configs_rows()}
    assert set(rows) == {"eth0", "wlan0"}
    assert rows["eth0"][1] == "00:11:22:33:44:55"
    assert rows["eth0"][2] == "192.168.1.9"
    assert rows["eth0"][3] == "fd00::1"
    assert rows["wlan0"][3] == "n/a"
    assert rows["eth0"][4].startswith("2023")  # formatted timestamp


def test_fmt_saved_at():
    assert load_status()._fmt_saved_at(None) == "n/a"
    assert load_status()._fmt_saved_at("not-a-number") == "n/a"


def test_status_empty_state(cli, status_mod, monkeypatch, capsys):
    monkeypatch.setattr(macip_lib, "_run", _fake_systemctl("", {}))
    cli(status_mod, [])
    out = capsys.readouterr().out
    assert "MacIP status" in out
    assert "(no saved configurations)" in out
    assert "(no 'macip-rotate' timers found)" in out


def test_status_shows_saved_configs(cli, status_mod, monkeypatch, capsys):
    _write_state("eth0")
    monkeypatch.setattr(macip_lib, "_run", _fake_systemctl("", {}))
    cli(status_mod, [])
    out = capsys.readouterr().out
    assert "eth0" in out
    assert "00:11:22:33:44:55" in out
    assert "192.168.1.9" in out
    assert "restore.py --all" in out  # tip


# --------------------------------------------------------------------------
# Timer parsing
# --------------------------------------------------------------------------

def test_parse_timer_units():
    output = (
        "UNIT                          STATE\n"
        "macip-rotate.timer            enabled\n"
        "macip-rotate-test.timer       disabled\n"
        "systemd-tmpfiles-clean.timer  static\n"
    )
    timers = load_status().parse_timer_units(output, "macip-rotate")
    assert timers == [("macip-rotate.timer", "enabled"),
                      ("macip-rotate-test.timer", "disabled")]


def test_parse_service_interface():
    unit = 'ExecStart="/usr/bin/python3" "/opt/macip/tools/06_auto_macip_changer.py" -i wlan0 --no-save --times 1\n'
    assert load_status().parse_service_interface(unit) == "wlan0"
    assert load_status().parse_service_interface("[Unit]\nDescription=x\n") == "n/a"


def _fake_systemctl(units_output, props):
    def fake_run(cmd, check=False):
        if "list-unit-files" in cmd:
            return subprocess.CompletedProcess(list(cmd), 0, units_output, "")
        if "show" in cmd:
            prop = cmd[cmd.index("-p") + 1]
            return subprocess.CompletedProcess(list(cmd), 0, props.get(prop, ""), "")
        return subprocess.CompletedProcess(list(cmd), 0, "", "")
    return fake_run


def test_timers_rows_parses_systemctl_output(status_mod, tmp_path, monkeypatch):
    units = "macip-rotate.timer          enabled\n"
    props = {"OnUnitActiveSec": "5min", "NextElapseUSecRealtime": "Thu 2026-08-16 15:00:00 UTC"}
    monkeypatch.setattr(macip_lib, "_run", _fake_systemctl(units, props))

    (tmp_path / "macip-rotate.service").write_text(
        'ExecStart="/usr/bin/python3" "/x/06_auto_macip_changer.py" -i wlan0 --no-save\n'
    )
    rows = status_mod.timers_rows("macip-rotate", str(tmp_path))
    assert rows == [[
        "macip-rotate.timer", "wlan0", "5min",
        "Thu 2026-08-16 15:00:00 UTC", "enabled",
    ]]


def test_timers_rows_missing_service_unit(status_mod, tmp_path, monkeypatch):
    units = "macip-rotate.timer          enabled\n"
    monkeypatch.setattr(macip_lib, "_run", _fake_systemctl(units, {"OnUnitActiveSec": "5min"}))
    rows = status_mod.timers_rows("macip-rotate", str(tmp_path))
    assert rows[0][1] == "n/a"  # no service file to read the interface from


def test_timers_rows_systemd_unavailable(status_mod, monkeypatch):
    def missing(cmd, **kwargs):
        raise MacipError("Required command 'systemctl' was not found")

    monkeypatch.setattr(macip_lib, "_run", missing)
    assert status_mod.timers_rows("macip-rotate", "/etc/systemd/system") is None


def test_status_reports_systemd_unavailable(cli, status_mod, monkeypatch, capsys):
    def missing(cmd, **kwargs):
        raise MacipError("Required command 'systemctl' was not found")

    monkeypatch.setattr(macip_lib, "_run", missing)
    cli(status_mod, [])
    out = capsys.readouterr().out
    assert "(systemd not available on this system)" in out


def test_status_shows_timers(cli, status_mod, tmp_path, monkeypatch, capsys):
    units = "macip-rotate.timer          enabled\n"
    props = {"OnUnitActiveSec": "5min", "NextElapseUSecRealtime": "Thu 2026-08-16 15:00:00 UTC"}
    monkeypatch.setattr(macip_lib, "_run", _fake_systemctl(units, props))
    (tmp_path / "macip-rotate.service").write_text(
        'ExecStart="/usr/bin/python3" "/x/06_auto_macip_changer.py" -i wlan0 --no-save\n'
    )
    cli(status_mod, ["--dest", str(tmp_path)])
    out = capsys.readouterr().out
    assert "macip-rotate.timer" in out
    assert "wlan0" in out
    assert "5min" in out
    assert "enabled" in out
