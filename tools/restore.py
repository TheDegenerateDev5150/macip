#!/usr/bin/env python3
"""Restore a network interface to the configuration saved by a previous run."""

import argparse
import sys

import macip_lib
from macip_lib import MacipError


def get_arguments():
    parser = argparse.ArgumentParser(
        description="Restore a network interface to the MAC/IP saved by a previous MacIP run"
    )
    parser.add_argument("-i", "--interface", required=True,
                        help="Network interface to restore (e.g. wlan0, eth0)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate the restore without touching the system")
    return parser.parse_args()


def main():
    args = get_arguments()
    macip_lib.set_dry_run(args.dry_run)
    try:
        if not args.dry_run:
            macip_lib.require_root()
        macip_lib.restore_config(args.interface)
    except MacipError as exc:
        macip_lib.log(f"[-] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
