#!/usr/bin/env python3
"""Manually change the MAC address of a network interface."""

import argparse
import sys

import macip_lib
from macip_lib import MacipError


def get_arguments():
    parser = argparse.ArgumentParser(
        description="Manually change the MAC address of a network interface"
    )
    parser.add_argument("-i", "--interface", required=True,
                        help="Network interface to change (e.g. wlan0, eth0)")
    parser.add_argument("-m", "--mac", required=True,
                        help="New MAC address (e.g. 00:11:22:33:44:55)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate the change without touching the system")
    parser.add_argument("--no-save", action="store_true",
                        help="Do not remember the original configuration for later restore")
    return parser.parse_args()


def main():
    args = get_arguments()
    macip_lib.set_dry_run(args.dry_run)

    try:
        if not args.dry_run:
            macip_lib.require_root()

        if not macip_lib.interface_exists(args.interface):
            available = ", ".join(macip_lib.list_interfaces()) or "none"
            raise MacipError(
                f"Interface '{args.interface}' does not exist. "
                f"Available interfaces: {available}"
            )

        if not macip_lib.validate_mac(args.mac):
            raise MacipError(
                "Invalid MAC address. Expected format XX:XX:XX:XX:XX:XX "
                "(six hexadecimal pairs)."
            )

        current = macip_lib.get_current_mac(args.interface)
        macip_lib.log(f"[*] Current MAC address of {args.interface}: {current}")

        if not args.no_save:
            macip_lib.save_config(args.interface)

        macip_lib.set_mac(args.interface, args.mac)

        updated = macip_lib.get_current_mac(args.interface)
        if updated and macip_lib.normalize_mac(updated) == macip_lib.normalize_mac(args.mac):
            macip_lib.log(f"[+] MAC address successfully changed to {updated}")
        else:
            raise MacipError("Failed to change the MAC address.")
    except MacipError as exc:
        macip_lib.log(f"[-] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
