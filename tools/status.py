#!/usr/bin/env python3
"""Show MacIP state: saved configurations and active rotation timers."""

import argparse
import datetime
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import macip_lib
from macip_lib import MacipError

DEFAULT_DEST = "/etc/systemd/system"


def get_arguments():
    parser = argparse.ArgumentParser(
        description="Show MacIP state: saved configurations and rotation timers"
    )
    parser.add_argument("--prefix", default="macip-rotate",
                        help="Timer prefix to report (default: macip-rotate)")
    parser.add_argument("--dest", default=DEFAULT_DEST,
                        help=f"Directory containing the unit files (default: {DEFAULT_DEST})")
    return parser.parse_args()


# --------------------------------------------------------------------------
# Saved configurations
# --------------------------------------------------------------------------

def _fmt_saved_at(epoch) -> str:
    if not epoch:
        return "n/a"
    try:
        return datetime.datetime.fromtimestamp(int(epoch)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return "n/a"


def saved_configs_rows() -> List[List[str]]:
    rows = []
    for interface in macip_lib.list_saved_configs():
        data = macip_lib.get_saved_config(interface) or {}
        rows.append([
            interface,
            data.get("mac") or "n/a",
            data.get("ip") or "n/a",
            data.get("ip6") or "n/a",
            _fmt_saved_at(data.get("saved_at")),
        ])
    return rows


# --------------------------------------------------------------------------
# Rotation timers
# --------------------------------------------------------------------------

def parse_timer_units(output: str, prefix: str) -> List[Tuple[str, str]]:
    """Return [(unit_name, state)] for timer units whose name starts with prefix."""
    timers = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(".timer") and parts[0].startswith(prefix):
            timers.append((parts[0], parts[1]))
    return timers


def parse_service_interface(unit_text: str) -> str:
    """Extract the interface from a service unit's ExecStart line (-i <iface>)."""
    match = re.search(r"ExecStart=.*?-i\s+(\S+)", unit_text)
    return match.group(1) if match else "n/a"


def _systemctl(args_cmd: Sequence[str]):
    """Run a systemctl command, returning None if systemd is unavailable."""
    try:
        return macip_lib._run(args_cmd)
    except MacipError:
        return None


def _show_prop(unit: str, prop: str) -> str:
    result = _systemctl(["systemctl", "show", unit, "-p", prop, "--value"])
    if result is None or result.returncode != 0:
        return "n/a"
    value = result.stdout.strip()
    return value or "n/a"


def timers_rows(prefix: str, dest: str) -> Optional[List[List[str]]]:
    """Return per-timer rows, or None if systemd is not available."""
    result = _systemctl(["systemctl", "list-unit-files", "--type=timer", "--no-pager", "--plain"])
    if result is None:
        return None
    dest_dir = Path(dest)
    rows = []
    for unit, state in parse_timer_units(result.stdout, prefix):
        service_unit = dest_dir / (unit[: -len(".timer")] + ".service")
        iface = (
            parse_service_interface(service_unit.read_text())
            if service_unit.is_file() else "n/a"
        )
        rows.append([
            unit,
            iface,
            _show_prop(unit, "OnUnitActiveSec"),
            _show_prop(unit, "NextElapseUSecRealtime"),
            state,
        ])
    return rows


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    args = get_arguments()
    macip_lib.log("MacIP status")
    macip_lib.log("============")
    macip_lib.log("")

    macip_lib.log("Saved configurations (revertible with 'restore'):")
    saved = saved_configs_rows()
    if saved:
        macip_lib.print_table(["Interface", "MAC", "IPv4", "IPv6", "Saved at"], saved)
    else:
        macip_lib.log("  (no saved configurations)")
    macip_lib.log("")

    macip_lib.log("Active rotation timers:")
    timers = timers_rows(args.prefix, args.dest)
    if timers is None:
        macip_lib.log("  (systemd not available on this system)")
    elif not timers:
        macip_lib.log(f"  (no '{args.prefix}' timers found)")
    else:
        macip_lib.print_table(
            ["Timer", "Interface", "Every", "Next fire", "Enabled"], timers
        )
    macip_lib.log("")

    macip_lib.log("Tip: sudo python3 tools/restore.py --all reverts every saved interface.")


if __name__ == "__main__":
    main()
