import importlib.util
import sys
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


def test_02_no_save_skips_save_config(cli, monkeypatch, capsys):
    tool = load_tool("02_auto_mac_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    monkeypatch.setattr(macip_lib, "generate_random_mac", lambda: "02:00:00:00:00:01")
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "02:00:00:00:00:01")
    monkeypatch.setattr(macip_lib, "set_mac", lambda iface, mac: None)
    monkeypatch.setattr(macip_lib, "save_config",
                        lambda iface: pytest.fail("save_config must not run with --no-save"))
    monkeypatch.setattr(macip_lib, "pace", lambda s: None)
    code = cli(tool, ["-i", "eth0", "--times", "1", "--interval", "0", "--dry-run", "--no-save"])
    assert code == 0


# --------------------------------------------------------------------------
# 03 - manual IP changer
# --------------------------------------------------------------------------

def test_03_success_path(cli, monkeypatch, capsys):
    tool = load_tool("03_ip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: "192.168.1.50" if version == 4 else None,
    )
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
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: "10.1.2.3" if version == 4 else None,
    )
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
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: "192.168.1.99" if version == 4 else None,
    )
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
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: "192.168.1.77" if version == 4 else None,
    )
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


def _interactive_session(monkeypatch):
    """Make stdin look interactive (prompt active) and skip the root check."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(macip_lib, "require_root", lambda: None)


_OK_RESULTS = [
    {"interface": "eth0", "mac": "00:11:22:33:44:55", "ip": "192.168.1.9",
     "ip6": None, "status": "restored"},
    {"interface": "wlan0", "mac": "aa:bb:cc:dd:ee:ff", "ip": None,
     "ip6": "fd00::1", "status": "restored"},
]


def test_restore_helper_all_flag(cli, monkeypatch, capsys):
    tool = load_tool("restore")
    monkeypatch.setattr(macip_lib, "list_saved_configs", lambda: ["eth0", "wlan0"])
    monkeypatch.setattr(macip_lib, "restore_all_configs", lambda: _OK_RESULTS)
    code = cli(tool, ["--all", "--dry-run"])  # dry-run: never prompts
    assert code == 0
    out = capsys.readouterr().out
    assert "Restored 2 interface(s)" in out
    # per-interface summary table
    assert "Interface" in out and "Status" in out
    assert "00:11:22:33:44:55" in out and "fd00::1" in out
    assert out.count("restored") >= 2


def test_restore_helper_all_aborts_on_no(cli, monkeypatch, capsys):
    import builtins
    tool = load_tool("restore")
    _interactive_session(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda prompt: "n")
    monkeypatch.setattr(macip_lib, "list_saved_configs", lambda: ["eth0", "wlan0"])
    monkeypatch.setattr(macip_lib, "restore_all_configs", lambda: pytest.fail("must not run"))
    code = cli(tool, ["--all"])
    assert code == 1
    out = capsys.readouterr().out
    assert "Aborted" in out
    assert "Found saved configurations for: eth0, wlan0" in out


def test_restore_helper_all_proceeds_on_yes(cli, monkeypatch, capsys):
    import builtins
    tool = load_tool("restore")
    _interactive_session(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda prompt: "y")
    monkeypatch.setattr(macip_lib, "list_saved_configs", lambda: ["eth0", "wlan0"])
    monkeypatch.setattr(macip_lib, "restore_all_configs", lambda: _OK_RESULTS)
    code = cli(tool, ["--all"])
    assert code == 0
    assert "Restored 2 interface(s)" in capsys.readouterr().out


def test_restore_helper_all_yes_flag_skips_prompt(cli, monkeypatch, capsys):
    tool = load_tool("restore")
    _interactive_session(monkeypatch)
    # input() would hang or error if it were ever called
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("prompt must be skipped"))
    monkeypatch.setattr(macip_lib, "list_saved_configs", lambda: ["eth0", "wlan0"])
    monkeypatch.setattr(macip_lib, "restore_all_configs", lambda: _OK_RESULTS)
    code = cli(tool, ["--all", "--yes"])
    assert code == 0
    assert "Restored 2 interface(s)" in capsys.readouterr().out


def test_restore_helper_all_no_prompt_when_not_tty(cli, monkeypatch, capsys):
    tool = load_tool("restore")
    monkeypatch.setattr(macip_lib, "require_root", lambda: None)
    # stdin stays non-interactive (default in tests) -> no prompt, just proceed
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("prompt must be skipped"))
    monkeypatch.setattr(macip_lib, "list_saved_configs", lambda: ["eth0", "wlan0"])
    monkeypatch.setattr(macip_lib, "restore_all_configs", lambda: _OK_RESULTS)
    code = cli(tool, ["--all"])
    assert code == 0
    assert "Restored 2 interface(s)" in capsys.readouterr().out


def test_restore_helper_all_reports_failures_and_exits_nonzero(cli, monkeypatch, capsys):
    tool = load_tool("restore")
    _interactive_session(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    monkeypatch.setattr(macip_lib, "list_saved_configs", lambda: ["eth0", "wlan0"])
    monkeypatch.setattr(macip_lib, "restore_all_configs", lambda: [
        {"interface": "eth0", "mac": "00:11:22:33:44:55", "ip": "192.168.1.9",
         "ip6": None, "status": "restored"},
        {"interface": "wlan0", "mac": None, "ip": None, "ip6": None,
         "status": "failed", "error": "boom"},
    ])
    code = cli(tool, ["--all"])
    assert code == 1  # partial failure -> non-zero exit
    out = capsys.readouterr().out
    assert "FAILED" in out
    assert "1 interface(s) failed to restore" in out


def test_restore_helper_all_no_configs_errors_before_prompt(cli, monkeypatch, capsys):
    tool = load_tool("restore")
    _interactive_session(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("prompt must be skipped"))
    monkeypatch.setattr(macip_lib, "list_saved_configs", lambda: [])
    code = cli(tool, ["--all"])
    assert code == 1
    assert "No saved configurations" in capsys.readouterr().out


def test_restore_helper_requires_target(cli, monkeypatch):
    tool = load_tool("restore")
    code = cli(tool, ["--dry-run"])  # neither -i nor --all
    assert code == 2  # argparse: one of -i/--all is required


def test_restore_helper_rejects_interface_with_all(cli, monkeypatch):
    tool = load_tool("restore")
    code = cli(tool, ["-i", "eth0", "--all", "--dry-run"])  # mutually exclusive
    assert code == 2


def test_interfaces_helper_lists_interfaces(cli, monkeypatch, capsys):
    tool = load_tool("interfaces")
    monkeypatch.setattr(macip_lib, "list_interfaces", lambda: ["eth0", "wlan0"])
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "00:11:22:33:44:55")
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: ("192.168.1.10" if version == 4 else "fd00::1"),
    )
    code = cli(tool, [])
    assert code == 0
    out = capsys.readouterr().out
    assert "eth0" in out and "wlan0" in out
    assert "00:11:22:33:44:55" in out
    assert "fd00::1" in out


# --------------------------------------------------------------------------
# IPv6 tool behaviour
# --------------------------------------------------------------------------

def test_03_ipv6_success_path(cli, monkeypatch, capsys):
    tool = load_tool("03_ip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    calls = []
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: "fd00::1" if version == 6 else None,
    )
    monkeypatch.setattr(
        macip_lib, "set_ip", lambda iface, ip, prefix=None: calls.append((ip, prefix)),
    )
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)

    code = cli(tool, ["-i", "eth0", "-ip", "fd00::1", "--dry-run"])
    assert code == 0
    assert calls == [("fd00::1", 64)]  # IPv6 defaults to /64
    assert "successfully changed" in capsys.readouterr().out


def test_04_no_save_skips_save_config(cli, monkeypatch, capsys):
    tool = load_tool("04_auto_ip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    monkeypatch.setattr(macip_lib, "generate_random_ip", lambda net="192.168.0.0/16": "10.1.2.3")
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: "10.1.2.3" if version == 4 else None,
    )
    monkeypatch.setattr(macip_lib, "set_ip", lambda iface, ip, prefix=None: None)
    monkeypatch.setattr(macip_lib, "save_config",
                        lambda iface: pytest.fail("save_config must not run with --no-save"))
    monkeypatch.setattr(macip_lib, "pace", lambda s: None)
    code = cli(tool, ["-i", "eth0", "--times", "1", "--interval", "0", "--dry-run", "--no-save"])
    assert code == 0


def test_04_ipv6_uses_network6(cli, monkeypatch, capsys):
    tool = load_tool("04_auto_ip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    generated = []
    monkeypatch.setattr(
        macip_lib, "generate_random_ip", lambda net: generated.append(net) or "fd00::42",
    )
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: "fd00::42" if version == 6 else None,
    )
    calls = []
    monkeypatch.setattr(
        macip_lib, "set_ip", lambda iface, ip, prefix=None: calls.append((ip, prefix)),
    )
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)
    monkeypatch.setattr(macip_lib, "pace", lambda s: None)

    code = cli(tool, ["-i", "eth0", "--ipv6", "--network6", "2001:db8::/32",
                      "--times", "1", "--interval", "0", "--dry-run"])
    assert code == 0
    assert generated == ["2001:db8::/32"]
    assert calls == [("fd00::42", 64)]


def test_05_dual_stack_sets_both(cli, monkeypatch, capsys):
    tool = load_tool("05_macip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    order = []
    monkeypatch.setattr(macip_lib, "set_mac", lambda iface, mac: order.append("mac"))
    monkeypatch.setattr(
        macip_lib, "set_ip", lambda iface, ip, prefix=None: order.append(("ip", ip)),
    )
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "00:11:22:33:44:55")
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: ("192.168.1.99" if version == 4 else "fd00::1"),
    )
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)

    code = cli(tool, ["-i", "eth0", "-m", "00:11:22:33:44:55", "-ip", "192.168.1.99",
                      "--ip6", "fd00::1", "--dry-run"])
    assert code == 0
    assert order == ["mac", ("ip", "192.168.1.99"), ("ip", "fd00::1")]


def test_05_rejects_same_family_ip6(cli, monkeypatch, capsys):
    tool = load_tool("05_macip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    code = cli(tool, ["-i", "eth0", "-m", "00:11:22:33:44:55", "-ip", "fd00::1",
                      "--ip6", "2001:db8::1", "--dry-run"])
    assert code == 1
    assert "different address family" in capsys.readouterr().out


def test_06_ipv6_rotation(cli, monkeypatch, capsys):
    tool = load_tool("06_auto_macip_changer")
    monkeypatch.setattr(macip_lib, "interface_exists", lambda iface: True)
    monkeypatch.setattr(macip_lib, "generate_random_mac", lambda: "02:00:00:00:00:01")
    monkeypatch.setattr(
        macip_lib, "generate_random_ip", lambda net="192.168.0.0/16": "fd00::77",
    )
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "02:00:00:00:00:01")
    monkeypatch.setattr(
        macip_lib, "get_current_ip",
        lambda iface, version=4: "fd00::77" if version == 6 else None,
    )
    calls = []
    monkeypatch.setattr(
        macip_lib, "set_ip", lambda iface, ip, prefix=None: calls.append((ip, prefix)),
    )
    monkeypatch.setattr(macip_lib, "set_mac", lambda iface, mac: None)
    monkeypatch.setattr(macip_lib, "save_config", lambda iface: None)
    monkeypatch.setattr(macip_lib, "pace", lambda s: None)

    code = cli(tool, ["-i", "eth0", "--ipv6", "--times", "1", "--interval", "0", "--dry-run"])
    assert code == 0
    assert calls == [("fd00::77", 64)]
    assert "IPv6" in capsys.readouterr().out
