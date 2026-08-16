#!/usr/bin/env python3
"""
MacIP shared library.

Centralises every network primitive used by the MacIP tools:

  * privilege (root) checks
  * interface discovery and validation
  * reading / setting MAC and IP addresses via iproute2 (``ip``) with a
    net-tools (``ifconfig``) fallback
  * MAC / IP validation and random generation
  * backup & restore of the original interface configuration
  * dry-run mode, logging and graceful Ctrl+C handling

Everything in this module is deliberately side-effect free at import time so
the test-suite can exercise it without root privileges or a real NIC.
"""

from __future__ import annotations

import ipaddress
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence

APP_NAME = "MacIP"
VERSION = "3.0"

# Saved original configurations live here so a later `restore` can find them
# even after the process has exited. Only writable with root, which is
# required for every real (non dry-run) operation anyway.
STATE_DIR = Path("/var/tmp/macip")

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

_DRY_RUN = False
_BACKEND: Optional[str] = None


class MacipError(Exception):
    """Raised for any user-facing failure (bad input, missing tools, ...)."""


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def set_dry_run(enabled: bool = True) -> None:
    """Enable / disable dry-run mode (commands are printed, never executed)."""
    global _DRY_RUN
    _DRY_RUN = enabled


def is_dry_run() -> bool:
    return _DRY_RUN


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

def log(message: str) -> None:
    print(message)


# --------------------------------------------------------------------------
# Privilege checks
# --------------------------------------------------------------------------

def require_root() -> None:
    """Raise MacipError unless the process runs as root on a POSIX system."""
    if os.name == "nt":
        raise MacipError(
            "MacIP requires a Linux system with iproute2 (ip) or net-tools (ifconfig)."
        )
    if os.geteuid() != 0:
        raise MacipError(
            "Root privileges are required to change network settings. "
            "Re-run with sudo, e.g.: sudo python3 <tool>.py -i wlan0"
        )


# --------------------------------------------------------------------------
# Command execution
# --------------------------------------------------------------------------

def backend() -> str:
    """Return the preferred command backend: 'ip' (iproute2) or 'ifconfig'."""
    global _BACKEND
    if _BACKEND is None:
        if shutil.which("ip"):
            _BACKEND = "ip"
        elif shutil.which("ifconfig"):
            _BACKEND = "ifconfig"
        else:
            raise MacipError(
                "Neither 'ip' (iproute2) nor 'ifconfig' (net-tools) was found. "
                "Install one of them, e.g.: apt install iproute2"
            )
    return _BACKEND


def _run(cmd: Sequence[str], check: bool = False) -> subprocess.CompletedProcess:
    """
    Run a command and return the CompletedProcess.

    In dry-run mode the command is only printed. When ``check`` is True a
    non-zero exit status raises MacipError with the command's stderr.
    """
    if _DRY_RUN:
        log(f"[dry-run] would run: {' '.join(cmd)}")
        return subprocess.CompletedProcess(list(cmd), 0, "", "")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError as exc:
        raise MacipError(f"Required command '{cmd[0]}' was not found on this system.") from exc
    except subprocess.TimeoutExpired:
        raise MacipError(f"Command timed out: {' '.join(cmd)}") from None
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise MacipError(
            f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n{detail}"
        )
    return result


def pace(seconds: float) -> None:
    """Sleep between automatic changes (skipped entirely in dry-run mode)."""
    if _DRY_RUN:
        return
    time.sleep(seconds)


# --------------------------------------------------------------------------
# Interfaces
# --------------------------------------------------------------------------

def list_interfaces() -> List[str]:
    """Return the names of all network interfaces on this system."""
    if shutil.which("ip"):
        try:
            out = _run(["ip", "-o", "link", "show"]).stdout
            names = []
            for line in out.splitlines():
                if ":" in line:
                    names.append(line.split(":", 2)[1].strip())
            return names
        except MacipError:
            pass
    # Fallback used when iproute2 is missing
    sys_class_net = Path("/sys/class/net")
    if sys_class_net.is_dir():
        return sorted(entry.name for entry in sys_class_net.iterdir())
    return []


def interface_exists(interface: str) -> bool:
    """Return True if the given interface is present on this system."""
    try:
        if backend() == "ip":
            result = _run(["ip", "link", "show", "dev", interface])
        else:
            result = _run(["ifconfig", interface])
        return result.returncode == 0
    except MacipError:
        return False


# --------------------------------------------------------------------------
# MAC addresses
# --------------------------------------------------------------------------

def validate_mac(mac: str) -> bool:
    """Return True if ``mac`` looks like XX:XX:XX:XX:XX:XX (or '-' separated)."""
    return bool(_MAC_RE.match(mac))


def normalize_mac(mac: str) -> str:
    """Normalise any valid MAC to lowercase colon-separated form."""
    return ":".join(part.lower() for part in re.split(r"[:-]", mac))


def generate_random_mac() -> str:
    """
    Generate a random, locally administered, unicast MAC address.

    The first octet is always 0x02: bit 1 set (locally administered) and
    bit 0 clear (unicast). This avoids impersonating real vendor OUIs.
    """
    octets = [0x02] + [random.randint(0x00, 0xFF) for _ in range(5)]
    return ":".join(f"{o:02x}" for o in octets)


def get_current_mac(interface: str) -> Optional[str]:
    """Return the current MAC of ``interface`` or None if it cannot be read."""
    try:
        if backend() == "ip":
            out = _run(["ip", "-o", "link", "show", "dev", interface]).stdout
        else:
            out = _run(["ifconfig", interface]).stdout
    except MacipError:
        return None
    match = re.search(r"([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})", out)
    return match.group(1).lower() if match else None


def set_mac(interface: str, mac: str) -> None:
    """Change the MAC address of ``interface`` (brings it down and back up)."""
    mac = normalize_mac(mac)
    log(f"[+] Setting MAC address of {interface} to {mac}")
    if backend() == "ip":
        _run(["ip", "link", "set", "dev", interface, "down"], check=True)
        _run(["ip", "link", "set", "dev", interface, "address", mac], check=True)
        _run(["ip", "link", "set", "dev", interface, "up"], check=True)
    else:
        _run(["ifconfig", interface, "down"], check=True)
        _run(["ifconfig", interface, "hw", "ether", mac], check=True)
        _run(["ifconfig", interface, "up"], check=True)


# --------------------------------------------------------------------------
# IP addresses
# --------------------------------------------------------------------------

def validate_ip(ip: str) -> bool:
    """Return True if ``ip`` is a valid, usable IPv4 address."""
    if not _IPV4_RE.match(ip):
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.version == 4 and not addr.is_multicast and not addr.is_loopback


def prefix_to_netmask(prefix: int) -> str:
    """Convert a CIDR prefix length to a dotted netmask (24 -> 255.255.255.0)."""
    if not 0 <= prefix <= 32:
        raise MacipError(f"Invalid prefix length: {prefix} (must be 0-32).")
    return str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask)


def generate_random_ip(network: str = "192.168.0.0/16") -> str:
    """
    Generate a random usable host IP inside ``network``.

    Network and broadcast addresses are excluded automatically.
    """
    try:
        net = ipaddress.ip_network(network, strict=False)
    except ValueError as exc:
        raise MacipError(f"Invalid network '{network}': {exc}") from exc
    hosts = list(net.hosts())
    if not hosts:
        raise MacipError(f"Network '{network}' has no usable host addresses.")
    return str(random.choice(hosts))


def get_current_ip(interface: str) -> Optional[str]:
    """Return the current IPv4 of ``interface`` or None if it cannot be read."""
    try:
        if backend() == "ip":
            out = _run(["ip", "-o", "-4", "addr", "show", "dev", interface]).stdout
        else:
            out = _run(["ifconfig", interface]).stdout
    except MacipError:
        return None
    match = re.search(r"inet\s+(\d{1,3}(?:\.\d{1,3}){3})", out)
    return match.group(1) if match else None


def set_ip(interface: str, ip: str, prefix: int = 24) -> None:
    """Assign ``ip`` (with the given CIDR prefix) to ``interface``."""
    log(f"[+] Setting IP address of {interface} to {ip}/{prefix}")
    if backend() == "ip":
        _run(["ip", "addr", "replace", f"{ip}/{prefix}", "dev", interface], check=True)
        _run(["ip", "link", "set", "dev", interface, "up"], check=True)
    else:
        netmask = prefix_to_netmask(prefix)
        _run(["ifconfig", interface, ip, "netmask", netmask], check=True)


# --------------------------------------------------------------------------
# Backup / restore
# --------------------------------------------------------------------------

def _state_path(interface: str) -> Path:
    return STATE_DIR / f"{interface}.json"


def get_saved_config(interface: str) -> Optional[dict]:
    """Return the saved original configuration for ``interface``, if any."""
    path = _state_path(interface)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save_config(interface: str) -> Optional[dict]:
    """Remember the current MAC/IP of ``interface`` so it can be restored later."""
    if _DRY_RUN:
        log(f"[dry-run] would save the original configuration of {interface}")
        return None
    mac = get_current_mac(interface)
    ip = get_current_ip(interface)
    data = {"interface": interface, "mac": mac, "ip": ip, "saved_at": int(time.time())}
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_path(interface).write_text(json.dumps(data, indent=2))
    except OSError as exc:
        raise MacipError(f"Could not save the original configuration: {exc}") from exc
    log(f"[*] Original configuration saved for {interface} (MAC: {mac}, IP: {ip}).")
    return data


def restore_config(interface: str) -> None:
    """Restore the original MAC/IP of ``interface`` and remove the saved state.

    The MAC is restored first (its down/up cycle wipes the address) and the
    IP afterwards, mirroring the order used by the changers.
    """
    data = get_saved_config(interface)
    if data is None:
        raise MacipError(
            f"No saved configuration found for interface '{interface}'. "
            "Run a changer on this interface first."
        )
    if _DRY_RUN:
        log(f"[dry-run] would restore {interface} to MAC: {data.get('mac')}, IP: {data.get('ip')}")
    else:
        if data.get("mac"):
            set_mac(interface, data["mac"])
        if data.get("ip"):
            set_ip(interface, data["ip"])
        try:
            _state_path(interface).unlink()
        except OSError:
            pass
    log(f"[+] Original configuration restored for {interface}.")


# --------------------------------------------------------------------------
# Graceful shutdown
# --------------------------------------------------------------------------

class GracefulExit:
    """
    Context manager that restores the original interface configuration when
    the user presses Ctrl+C (SIGINT) or the process receives SIGTERM.
    """

    def __init__(self, interface: str, restore: bool = True):
        self.interface = interface
        self.restore = restore
        self._handlers = {}

    def __enter__(self) -> "GracefulExit":
        if os.name != "nt":
            for sig in (signal.SIGINT, signal.SIGTERM):
                self._handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, self._handler)
        return self

    def __exit__(self, exc_type, exc, tb):
        if os.name != "nt":
            for sig, handler in self._handlers.items():
                signal.signal(sig, handler)
        return False

    def _handler(self, signum, frame):
        print("\n[!] Interrupted by user.")
        if self.restore:
            try:
                restore_config(self.interface)
            except MacipError as exc:
                print(f"[-] {exc}")
        sys.exit(128 + signum)
