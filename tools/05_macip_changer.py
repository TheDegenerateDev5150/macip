#!/usr/bin/env python3
"""Manually change the MAC and IP (IPv4 and/or IPv6) of a network interface."""

import argparse
import sys

import macip_lib
from macip_lib import MacipError


def get_arguments():
    parser = argparse.ArgumentParser(
        description="Manually change the MAC and IP address of a network interface"
    )
    parser.add_argument("-i", "--interface", required=True,
                        help="Network interface to change (e.g. wlan0, eth0)")
    parser.add_argument("-m", "--mac", required=True,
                        help="New MAC address (e.g. 00:11:22:33:44:55)")
    parser.add_argument("-ip", "--ipaddress", dest="new_ip", required=True,
                        help="New IP address - IPv4 (e.g. 192.168.1.100) or IPv6 (e.g. fd00::1)")
    parser.add_argument("--ip6", dest="new_ip6", default=None,
                        help="Additional IP address of the other family (dual-stack), "
                             "e.g. fd00::1 when -ip is IPv4")
    parser.add_argument("--prefix", type=int, default=None, metavar="N",
                        help="CIDR prefix for -ip (default: 24 for IPv4, 64 for IPv6)")
    parser.add_argument("--prefix6", type=int, default=None, metavar="N",
                        help="CIDR prefix for --ip6 (default: 24 for IPv4, 64 for IPv6)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate the changes without touching the system")
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
        if not macip_lib.validate_ip(args.new_ip):
            raise MacipError(
                "Invalid IP address. Expected a valid IPv4 (e.g. 192.168.1.100) "
                "or IPv6 (e.g. fd00::1) address."
            )

        version = macip_lib.ip_version(args.new_ip)

        # Optional second address (dual-stack): must be the other family.
        if args.new_ip6:
            if not macip_lib.validate_ip(args.new_ip6):
                raise MacipError("Invalid --ip6 address. Expected a valid IPv4 or IPv6 address.")
            if macip_lib.ip_version(args.new_ip6) == version:
                raise MacipError(
                    f"--ip6 must be a different address family than -ip "
                    f"(got IPv{version} for both)."
                )
            version6 = macip_lib.ip_version(args.new_ip6)
            prefix6 = args.prefix6 if args.prefix6 is not None else (64 if version6 == 6 else 24)
        else:
            version6 = None
            prefix6 = None

        prefix = args.prefix if args.prefix is not None else (64 if version == 6 else 24)

        current_mac = macip_lib.get_current_mac(args.interface)
        current_ip = macip_lib.get_current_ip(args.interface, version)
        current_ip6 = macip_lib.get_current_ip(args.interface, version6) if version6 else None
        macip_lib.log(f"[*] Current MAC address of {args.interface}: {current_mac}")
        macip_lib.log(f"[*] Current IPv{version} address of {args.interface}: {current_ip}")
        if version6:
            macip_lib.log(f"[*] Current IPv{version6} address of {args.interface}: {current_ip6}")

        if not args.no_save:
            macip_lib.save_config(args.interface)

        # MAC first: its down/up cycle wipes the addresses, so IPs are set last.
        macip_lib.set_mac(args.interface, args.mac)
        macip_lib.set_ip(args.interface, args.new_ip, prefix)
        if args.new_ip6:
            macip_lib.set_ip(args.interface, args.new_ip6, prefix6)

        updated_mac = macip_lib.get_current_mac(args.interface)
        updated_ip = macip_lib.get_current_ip(args.interface, version)
        updated_ip6 = macip_lib.get_current_ip(args.interface, version6) if version6 else None

        if updated_ip and macip_lib.normalize_ip(updated_ip) == macip_lib.normalize_ip(args.new_ip):
            macip_lib.log(f"[+] IPv{version} address successfully changed to {updated_ip}")
        else:
            macip_lib.log("[-] Failed to change the IP address.")

        if args.new_ip6 and updated_ip6:
            if macip_lib.normalize_ip(updated_ip6) == macip_lib.normalize_ip(args.new_ip6):
                macip_lib.log(f"[+] IPv{version6} address successfully changed to {updated_ip6}")
            else:
                macip_lib.log("[-] Failed to change the IPv6 address.")

        if updated_mac and macip_lib.normalize_mac(updated_mac) == macip_lib.normalize_mac(args.mac):
            macip_lib.log(f"[+] MAC address successfully changed to {updated_mac}")
        else:
            macip_lib.log("[-] Failed to change the MAC address.")
    except MacipError as exc:
        macip_lib.log(f"[-] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
