#!/usr/bin/env python3
"""Restore network interface(s) to the configuration saved by previous runs."""

import argparse
import sys

import macip_lib
from macip_lib import MacipError


def get_arguments():
    parser = argparse.ArgumentParser(
        description="Restore a network interface (or every interface) to the "
                    "MAC/IP saved by a previous MacIP run"
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("-i", "--interface", default=None,
                        help="Network interface to restore (e.g. wlan0, eth0)")
    target.add_argument("--all", action="store_true",
                        help="Restore every interface MacIP has touched")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Skip the interactive confirmation prompt (for scripts)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate the restore without touching the system")
    return parser.parse_args()


def _confirm(interfaces: list) -> bool:
    """Ask the user to confirm the restore-all. No prompt in non-interactive use."""
    macip_lib.log(f"[*] Found saved configurations for: {', '.join(interfaces)}")
    try:
        answer = input("[?] Restore all of these interfaces to their original "
                       "configuration? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def _print_summary(results: list) -> None:
    """Print a per-interface table of what was restored."""
    macip_lib.log("")
    macip_lib.print_table(
        ["Interface", "MAC", "IPv4", "IPv6", "Status"],
        [
            [
                r["interface"],
                r.get("mac") or "n/a",
                r.get("ip") or "n/a",
                r.get("ip6") or "n/a",
                "FAILED" if r["status"] == "failed" else "restored",
            ]
            for r in results
        ],
    )
    macip_lib.log("")


def main():
    args = get_arguments()
    macip_lib.set_dry_run(args.dry_run)
    try:
        if not args.dry_run:
            macip_lib.require_root()

        if not args.all:
            macip_lib.restore_config(args.interface)
            return

        interfaces = macip_lib.list_saved_configs()
        if not interfaces:
            raise MacipError(
                "No saved configurations found. Run a changer on an interface first."
            )

        # Only prompt on an interactive terminal; scripts and dry-runs proceed.
        interactive = sys.stdin.isatty() and not args.dry_run
        if not args.yes and interactive and not _confirm(interfaces):
            macip_lib.log("[-] Aborted. No interfaces were changed.")
            sys.exit(1)

        results = macip_lib.restore_all_configs()
        _print_summary(results)

        restored = sum(1 for r in results if r["status"] == "restored")
        failed = sum(1 for r in results if r["status"] == "failed")
        if restored:
            macip_lib.log(f"[+] Restored {restored} interface(s).")
        if failed:
            macip_lib.log(f"[-] {failed} interface(s) failed to restore.")
            sys.exit(1)
    except MacipError as exc:
        macip_lib.log(f"[-] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
