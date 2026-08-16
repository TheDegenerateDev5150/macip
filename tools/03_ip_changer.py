#!/usr/bin/env python3
"""Manually change the IP address of a network interface."""

import argparse
import sys

import macip_lib
from macip_lib import MacipError


def get_arguments():
    parser = argparse.ArgumentParser(
        description="Manually change the IP address of a network interface"
    )
    parser.add_argument("-i", "--interface", required=True,
                        help="Network interface to change (e.g. wlan0, eth0)")
    parser.add_argument("-ip", "--ipaddress", dest="new_ip", required=True,
                        help="New IPv4 address (e.g. 192.168.1.100)")
    parser.add_argument("--prefix", type=int, default=24, metavar="N",
                        help="CIDR prefix length of the new address (default: 24)")
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

        if not macip_lib.validate_ip(args.new_ip):
            raise MacipError(
                "Invalid IP address. Expected a valid IPv4 address (e.g. 192.168.1.100)."
            )

        current = macip_lib.get_current_ip(args.interface)
        macip_lib.log(f"[*] Current IP address of {args.interface}: {current}")

        if not args.no_save:
            macip_lib.save_config(args.interface)

        macip_lib.set_ip(args.interface, args.new_ip, args.prefix)

        updated = macip_lib.get_current_ip(args.interface)
        if updated == args.new_ip:
            macip_lib.log(f"[+] IP address successfully changed to {updated}")
        else:
            raise MacipError("Failed to change the IP address.")
    except MacipError as exc:
        macip_lib.log(f"[-] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
