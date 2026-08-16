import json
import re
import subprocess

import pytest

import macip_lib
from macip_lib import MacipError


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

@pytest.mark.parametrize("mac", [
    "00:11:22:33:44:55",
    "AA-BB-CC-DD-EE-FF",
    "a1:b2:c3:d4:e5:f6",
    "02:00:00:00:00:01",
])
def test_validate_mac_accepts_valid(mac):
    assert macip_lib.validate_mac(mac)


@pytest.mark.parametrize("mac", [
    "",
    "001122334455",
    "00:11:22:33:44",
    "00:11:22:33:44:55:66",
    "GG:11:22:33:44:55",
    "00:11:22:33:44:5",
    "00:11:22:33:44:55 ",
])
def test_validate_mac_rejects_invalid(mac):
    assert not macip_lib.validate_mac(mac)


@pytest.mark.parametrize("ip", [
    "192.168.1.1",
    "8.8.8.8",
    "10.0.0.1",
    "172.16.5.5",
    "255.255.255.254",
])
def test_validate_ip_accepts_valid(ip):
    assert macip_lib.validate_ip(ip)


@pytest.mark.parametrize("ip", [
    "",
    "256.1.1.1",
    "1.2.3",
    "1.2.3.4.5",
    "abc.def.ghi.jkl",
    "192.168.1.999",
    "1.2.3.4 ",
    "127.0.0.1",   # loopback is not a usable target
    "224.0.0.1",   # multicast is not a usable target
])
def test_validate_ip_rejects_invalid(ip):
    assert not macip_lib.validate_ip(ip)


# --------------------------------------------------------------------------
# Random generation
# --------------------------------------------------------------------------

def test_generate_random_mac_format():
    for _ in range(100):
        mac = macip_lib.generate_random_mac()
        assert re.match(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", mac)


def test_generate_random_mac_locally_administered_unicast():
    for _ in range(100):
        first = int(macip_lib.generate_random_mac().split(":")[0], 16)
        assert first & 0x02 == 0x02  # locally administered
        assert first & 0x01 == 0x00  # unicast


def test_generate_random_ip_inside_network():
    for _ in range(100):
        ip = macip_lib.generate_random_ip("192.168.0.0/16")
        parts = [int(p) for p in ip.split(".")]
        assert parts[0] == 192 and parts[1] == 168
        # never the network or broadcast address of a /24 in that space
        assert 1 <= parts[3] <= 254


def test_generate_random_ip_custom_network():
    for _ in range(50):
        ip = macip_lib.generate_random_ip("10.0.0.0/8")
        assert ip.startswith("10.")


def test_generate_random_ip_invalid_network():
    with pytest.raises(MacipError):
        macip_lib.generate_random_ip("not-a-network")


def test_normalize_mac():
    assert macip_lib.normalize_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"
    assert macip_lib.normalize_mac("00:11:22:33:44:55") == "00:11:22:33:44:55"


def test_prefix_to_netmask():
    assert macip_lib.prefix_to_netmask(24) == "255.255.255.0"
    assert macip_lib.prefix_to_netmask(16) == "255.0.0.0"
    with pytest.raises(MacipError):
        macip_lib.prefix_to_netmask(33)


# --------------------------------------------------------------------------
# Interface parsing (fake command output)
# --------------------------------------------------------------------------

def _fake_run(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, "")


def test_list_interfaces_parses_ip_output(monkeypatch):
    out = (
        "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN\n"
        "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP\n"
        "3: wlan0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN\n"
    )
    monkeypatch.setattr(macip_lib, "_run", lambda cmd, check=False: _fake_run(out))
    assert macip_lib.list_interfaces() == ["lo", "eth0", "wlan0"]


def test_interface_exists_true(monkeypatch):
    monkeypatch.setattr(macip_lib, "_run", lambda cmd, check=False: _fake_run())
    assert macip_lib.interface_exists("eth0")


def test_interface_exists_false(monkeypatch):
    monkeypatch.setattr(
        macip_lib, "_run",
        lambda cmd, check=False: _fake_run(returncode=1),
    )
    assert not macip_lib.interface_exists("nope0")


def test_get_current_mac_parses_ip_output(monkeypatch):
    out = "2: eth0: <BROADCAST,MULTICAST,UP> mtu 1500 link/ether 00:1a:2b:3c:4d:5e brd ff:ff:ff:ff:ff:ff\n"
    monkeypatch.setattr(macip_lib, "_run", lambda cmd, check=False: _fake_run(out))
    assert macip_lib.get_current_mac("eth0") == "00:1a:2b:3c:4d:5e"


def test_get_current_mac_parses_ifconfig_output(monkeypatch):
    out = "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n        ether 0a:0b:0c:0d:0e:0f  txqueuelen 1000\n"
    monkeypatch.setattr(macip_lib, "_BACKEND", "ifconfig")
    monkeypatch.setattr(macip_lib, "_run", lambda cmd, check=False: _fake_run(out))
    assert macip_lib.get_current_mac("eth0") == "0a:0b:0c:0d:0e:0f"


def test_get_current_mac_no_match(monkeypatch):
    monkeypatch.setattr(macip_lib, "_run", lambda cmd, check=False: _fake_run("no mac here"))
    assert macip_lib.get_current_mac("eth0") is None


def test_get_current_ip_parses_ip_output(monkeypatch):
    out = "2: eth0    inet 192.168.1.42/24 brd 192.168.1.255 scope global dynamic eth0\n"
    monkeypatch.setattr(macip_lib, "_run", lambda cmd, check=False: _fake_run(out))
    assert macip_lib.get_current_ip("eth0") == "192.168.1.42"


def test_get_current_ip_parses_ifconfig_output(monkeypatch):
    out = "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n        inet 10.0.0.7  netmask 255.255.255.0  broadcast 10.0.0.255\n"
    monkeypatch.setattr(macip_lib, "_BACKEND", "ifconfig")
    monkeypatch.setattr(macip_lib, "_run", lambda cmd, check=False: _fake_run(out))
    assert macip_lib.get_current_ip("eth0") == "10.0.0.7"


# --------------------------------------------------------------------------
# Command building
# --------------------------------------------------------------------------

def test_set_mac_builds_ip_commands(monkeypatch):
    calls = []

    def fake_run(cmd, check=False):
        calls.append(list(cmd))
        return _fake_run()

    monkeypatch.setattr(macip_lib, "_run", fake_run)
    macip_lib.set_mac("eth0", "AA:BB:CC:DD:EE:FF")
    assert calls == [
        ["ip", "link", "set", "dev", "eth0", "down"],
        ["ip", "link", "set", "dev", "eth0", "address", "aa:bb:cc:dd:ee:ff"],
        ["ip", "link", "set", "dev", "eth0", "up"],
    ]


def test_set_mac_builds_ifconfig_commands(monkeypatch):
    calls = []

    def fake_run(cmd, check=False):
        calls.append(list(cmd))
        return _fake_run()

    monkeypatch.setattr(macip_lib, "_BACKEND", "ifconfig")
    monkeypatch.setattr(macip_lib, "_run", fake_run)
    macip_lib.set_mac("eth0", "00:11:22:33:44:55")
    assert calls == [
        ["ifconfig", "eth0", "down"],
        ["ifconfig", "eth0", "hw", "ether", "00:11:22:33:44:55"],
        ["ifconfig", "eth0", "up"],
    ]


def test_set_ip_builds_ip_commands(monkeypatch):
    calls = []

    def fake_run(cmd, check=False):
        calls.append(list(cmd))
        return _fake_run()

    monkeypatch.setattr(macip_lib, "_run", fake_run)
    macip_lib.set_ip("eth0", "192.168.1.10", 24)
    assert calls == [
        ["ip", "addr", "replace", "192.168.1.10/24", "dev", "eth0"],
        ["ip", "link", "set", "dev", "eth0", "up"],
    ]


def test_set_ip_builds_ifconfig_commands(monkeypatch):
    calls = []

    def fake_run(cmd, check=False):
        calls.append(list(cmd))
        return _fake_run()

    monkeypatch.setattr(macip_lib, "_BACKEND", "ifconfig")
    monkeypatch.setattr(macip_lib, "_run", fake_run)
    macip_lib.set_ip("eth0", "10.0.0.5", 24)
    assert calls == [
        ["ifconfig", "eth0", "10.0.0.5", "netmask", "255.255.255.0"],
    ]


# --------------------------------------------------------------------------
# Dry-run mode
# --------------------------------------------------------------------------

def test_dry_run_never_executes_commands(monkeypatch):
    def boom(cmd, **kwargs):
        raise AssertionError("subprocess.run must not be called in dry-run mode")

    monkeypatch.setattr(subprocess, "run", boom)
    macip_lib.set_dry_run(True)
    result = macip_lib._run(["ip", "link", "show"])
    assert result.returncode == 0
    macip_lib.set_dry_run(False)


def test_dry_run_skips_state_file_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(macip_lib, "_run", lambda cmd, check=False: _fake_run(""))
    macip_lib.set_dry_run(True)
    macip_lib.save_config("eth0")
    assert not list((tmp_path / "state").glob("*"))
    macip_lib.set_dry_run(False)


# --------------------------------------------------------------------------
# Backup / restore
# --------------------------------------------------------------------------

def test_save_and_restore_config(monkeypatch):
    monkeypatch.setattr(macip_lib, "get_current_mac", lambda iface: "00:11:22:33:44:55")
    monkeypatch.setattr(macip_lib, "get_current_ip", lambda iface: "192.168.1.99")
    restored = []

    def fake_set_mac(iface, mac):
        restored.append(("mac", mac))

    def fake_set_ip(iface, ip, prefix=24):
        restored.append(("ip", ip))

    monkeypatch.setattr(macip_lib, "set_mac", fake_set_mac)
    monkeypatch.setattr(macip_lib, "set_ip", fake_set_ip)

    macip_lib.save_config("eth0")
    state_file = macip_lib.STATE_DIR / "eth0.json"
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["mac"] == "00:11:22:33:44:55"
    assert data["ip"] == "192.168.1.99"

    macip_lib.restore_config("eth0")
    # MAC restored before IP (its down/up cycle wipes the address)
    assert restored == [("mac", "00:11:22:33:44:55"), ("ip", "192.168.1.99")]
    assert not state_file.exists()


def test_restore_without_saved_config():
    with pytest.raises(MacipError, match="No saved configuration"):
        macip_lib.restore_config("eth0")


def test_restore_config_is_idempotent_when_no_mac_or_ip(monkeypatch):
    macip_lib.STATE_DIR.mkdir(parents=True, exist_ok=True)
    (macip_lib.STATE_DIR / "eth0.json").write_text(json.dumps({"mac": None, "ip": None}))
    monkeypatch.setattr(macip_lib, "set_mac", lambda iface, mac: None)
    monkeypatch.setattr(macip_lib, "set_ip", lambda iface, ip, prefix=24: None)
    macip_lib.restore_config("eth0")  # must not raise


# --------------------------------------------------------------------------
# Privileges and errors
# --------------------------------------------------------------------------

class _FakeOS:
    name = "posix"

    def __init__(self, euid):
        self._euid = euid

    def geteuid(self):
        return self._euid


def test_require_root_passes_as_root(monkeypatch):
    monkeypatch.setattr(macip_lib, "os", _FakeOS(0))
    macip_lib.require_root()  # must not raise


def test_require_root_raises_for_non_root(monkeypatch):
    monkeypatch.setattr(macip_lib, "os", _FakeOS(1000))
    with pytest.raises(MacipError, match="Root privileges"):
        macip_lib.require_root()


def test_require_root_raises_on_windows(monkeypatch):
    monkeypatch.setattr(macip_lib, "os", _FakeOS(0))
    monkeypatch.setattr(macip_lib.os, "name", "nt")
    with pytest.raises(MacipError, match="Linux"):
        macip_lib.require_root()


def test_run_reports_missing_command(monkeypatch):
    def missing(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(MacipError, match="not found"):
        macip_lib._run(["ifconfig", "eth0"])


def test_run_check_raises_on_failure(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 1, "", "boom"),
    )
    with pytest.raises(MacipError, match="boom"):
        macip_lib._run(["ip", "link", "show"], check=True)
