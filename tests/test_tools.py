import importlib.util
from pathlib import Path

import pytest

import macip_lib
from macip_lib import MacipError

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"


def load_tool(name):
    """Load a tool script (module names start with digits, so use importlib)."""
    spec = importlib.util.spec_from_file_location(name, TOOLS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli(monkeypatch):
    """Patch sys.argv and capture exit codes via SystemExit."""

    def _cli(module, argv):
        monkeypatch.setattr("sys.argv", [module.__file__] + argv)
        try:
            module.main()
            return 0
        except SystemExit as exc:
            return exc.code

    return _cli


# --------------------------------------------------------------------------
# 01 - manual MAC changer
# --------------------------------------------------------------------------

def test_01_success_path(cli, monkeypatch, capsys):
    tool = load_tool("01_mac_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "00:11:22:33:44:55")
    monkeypatch.setattr(macip_lib, "set_mac", lambda iface, mac: None)
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)

    code = cli(tool, ["-i", "eth0", "-m", "00:11:22:33:44:55", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "successfully changed" in out


def test_01_rejects_bad_mac(cli, monkeypatch, capsys):
    tool = load_tool("01_mac_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    code = cli(tool, ["-i", "eth0", "-m", "not-a-mac", "--dry-run"])
    assert code == 1
    assert "Invalid MAC" in capsys.readouterr().out


def test_01_rejects_unknown_interface(cli, monkeypatch, capsys):
    tool = load_tool("01_mac_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: False)
    monkeypatch.setattr(macip_lib, "list_interfaces", lambda: ["eth0", "wlan0"])
    code = cli(tool, ["-i", "nope0", "-m", "00:11:22:33:44:55", "--dry-run"])
    assert code == 1
    out = capsys.readouterr().out
    assert "does not exist" in out
    assert "eth0" in out and "wlan0" in out


def test_01_requires_args(cli, monkeypatch):
    tool = load_tool("01_mac_changer")
    code = cli(tool, ["-i", "eth0"])  # missing --mac
    assert code == 2  # argparse usage error


# --------------------------------------------------------------------------
# 02 - auto MAC changer
# --------------------------------------------------------------------------

def test_02_runs_requested_times(cli, monkeypatch, capsys):
    tool = load_tool("02_auto_mac_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    monkeypatch.setattr(macip_lib, "generate_random_mac", lambda: "02:00:00:00:00:01")
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "02:00:00:00:00:01")
    monkeypatch.setattr(macip_lib, "set_mac", lambda iface, mac: None)
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)
    monkeypatch.setattr(macip_lib, "pace", lambda s: None)

    code = cli(tool, ["-i", "eth0", "--times", "3", "--interval", "0", "--dry-run", "--no-restore"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.count("Attempt ") == 3
    assert "Done. Applied 3 MAC changes" in out


def test_02_restore_mode(cli, monkeypatch, capsys):
    tool = load_tool("02_auto_mac_changer")
    restored = []
    monkeypatch.setattr(macip_lib, "restore_config", lambda iface: restored.append(iface))
    code = cli(tool, ["-i", "eth0", "--restore", "--dry-run"])
    assert code == 0
    assert restored == ["eth0"]


def test_02_rejects_bad_times(cli, monkeypatch, capsys):
    tool = load_tool("02_auto_mac_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    code = cli(tool, ["-i", "eth0", "--times", "0", "--dry-run"])
    assert code == 1
    assert "--times" in capsys.readouterr().out


# --------------------------------------------------------------------------
# 03 - manual IP changer
# --------------------------------------------------------------------------

def test_03_success_path(cli, monkeypatch, capsys):
    tool = load_tool("03_ip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    monkeypatch.setattr(macip_lib, "get_current_ip", lambda iface: "192.168.1.50")
    monkeypatch.setattr(macip_lib, "set_ip", lambda iface, ip, prefix=24: None)
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)

    code = cli(tool, ["-i", "eth0", "-ip", "192.168.1.50", "--dry-run"])
    assert code == 0
    assert "successfully changed" in capsys.readouterr().out


def test_03_rejects_bad_ip(cli, monkeypatch, capsys):
    tool = load_tool("03_ip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    code = cli(tool, ["-i", "eth0", "-ip", "999.1.1.1", "--dry-run"])
    assert code == 1
    assert "Invalid IP" in capsys.readouterr().out


# --------------------------------------------------------------------------
# 04 - auto IP changer
# --------------------------------------------------------------------------

def test_04_uses_custom_network(cli, monkeypatch, capsys):
    tool = load_tool("04_auto_ip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    generated = []
    monkeypatch.setattr(macip_lib, "generate_random_ip", lambda net: generated.append(net) or "10.1.2.3")
    monkeypatch.setattr(macip_lib, "get_current_ip", lambda iface: "10.1.2.3")
    monkeypatch.setattr(macip_lib, "set_ip", lambda iface, ip, prefix=24: None)
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)
    monkeypatch.setattr(macip_lib, "pace", lambda s: None)

    code = cli(tool, ["-i", "eth0", "--network", "10.0.0.0/8", "--times", "1", "--interval", "0", "--dry-run"])
    assert code == 0
    assert generated == ["10.0.0.0/8"]


# --------------------------------------------------------------------------
# 05 - manual combined changer (MAC must be set before IP)
# --------------------------------------------------------------------------

def test_05_sets_mac_before_ip(cli, monkeypatch, capsys):
    tool = load_tool("05_macip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    order = []
    monkeypatch.setattr(macip_lib, "set_mac", lambda iface, mac: order.append("mac"))
    monkeypatch.setattr(macip_lib, "set_ip", lambda iface, ip, prefix=24: order.append("ip"))
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "00:11:22:33:44:55")
    monkeypatch.setattr(macip_lib, "get_current_ip", lambda iface: "192.168.1.99")
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)

    code = cli(tool, ["-i", "eth0", "-m", "00:11:22:33:44:55", "-ip", "192.168.1.99", "--dry-run"])
    assert code == 0
    assert order == ["mac", "ip"]


def test_05_rejects_invalid_inputs(cli, monkeypatch, capsys):
    tool = load_tool("05_macip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    code = cli(tool, ["-i", "eth0", "-m", "bad", "-ip", "192.168.1.99", "--dry-run"])
    assert code == 1
    assert "Invalid MAC" in capsys.readouterr().out


# --------------------------------------------------------------------------
# 06 - auto combined changer
# --------------------------------------------------------------------------

def test_06_runs_and_restores_on_failure(cli, monkeypatch, capsys):
    tool = load_tool("06_auto_macip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    monkeypatch.setattr(macip_lib, "generate_random_mac", lambda: "02:00:00:00:00:01")
    monkeypatch.setattr(macip_lib, "generate_random_ip", lambda net="192.168.0.0/16": "192.168.1.77")
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "02:00:00:00:00:01")
    monkeypatch.setattr(macip_lib, "get_current_ip", lambda iface: "192.168.1.77")
    monkeypatch.setattr(macip_lib, "set_mac", lambda iface, mac: None)
    monkeypatch.setattr(macip_lib, "set_ip", lambda iface, ip, prefix=24: None)
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)
    monkeypatch.setattr(macip_lib, "pace", lambda s: None)

    code = cli(tool, ["-i", "eth0", "--times", "2", "--interval", "0", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.count("Attempt ") == 2
    assert "MAC successfully changed" in out
    assert "IP successfully changed" in out


def test_06_unknown_interface_suggests_available(cli, monkeypatch, capsys):
    tool = load_tool("06_auto_macip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: False)
    monkeypatch.setattr(macip_lib, "list_interfaces", lambda: ["lo"])
    code = cli(tool, ["-i", "ghost0", "--dry-run"])
    assert code == 1
    assert "ghost0" in capsys.readouterr().out


# --------------------------------------------------------------------------
# restore.py and interfaces.py
# --------------------------------------------------------------------------

def test_restore_helper(cli, monkeypatch, capsys):
    tool = load_tool("restore")
    restored = []
    monkeypatch.setattr(macip_lib, "restore_config", lambda iface: restored.append(iface))
    code = cli(tool, ["-i", "eth0", "--dry-run"])
    assert code == 0
    assert restored == ["eth0"]


def test_interfaces_helper_lists_interfaces(cli, monkeypatch, capsys):
    tool = load_tool("interfaces")
    monkeypatch.setattr(macip_lib, "list_interfaces", lambda: ["eth0", "wlan0"])
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "00:11:22:33:44:55")
    monkeypatch.setattr(macip_lib, "get_current_ip", lambda iface: "192.168.1.10")
    code = cli(tool, [])
    assert code == 0
    out = capsys.readouterr().out
    assert "eth0" in out and "wlan0" in out
    assert "00:11:22:33:44:55" in out
