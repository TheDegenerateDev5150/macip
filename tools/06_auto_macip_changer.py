#!/usr/bin/env python3
"""Automatically change the MAC and IP (IPv4 or IPv6) of an interface."""

import argparse
import sys

import macip_lib
from macip_lib import MacipError


def get_arguments():
    parser = argparse.ArgumentParser(
        description="Repeatedly change both the MAC and IP address of an interface to random values"
    )
    parser.add_argument("-i", "--interface", required=True,
                        help="Network interface to change (e.g. wlan0, eth0)")
    parser.add_argument("--ipv6", action="store_true",
                        help="Rotate random IPv6 addresses instead of IPv4")
    parser.add_argument("--network", default="192.168.0.0/16", metavar="CIDR",
                        help="IPv4 subnet to pick random addresses from (default: 192.168.0.0/16)")
    parser.add_argument("--network6", default="fd00::/64", metavar="CIDR",
                        help="IPv6 subnet to pick random addresses from (default: fd00::/64)")
    parser.add_argument("--prefix", type=int, default=None, metavar="N",
                        help="CIDR prefix length to assign (default: 24 for IPv4, 64 for IPv6)")
    parser.add_argument("--times", type=int, default=5, metavar="N",
                        help="How many times to change MAC and IP (default: 5)")
    parser.add_argument("--interval", type=float, default=1.0, metavar="SECONDS",
                        help="Seconds between changes (default: 1.0)")
    parser.add_argument("--restore", action="store_true",
                        help="Restore the original configuration saved by a previous run, then exit")
    parser.add_argument("--no-restore", action="store_true",
                        help="Do not restore the original configuration on Ctrl+C")
    parser.add_argument("--no-save", action="store_true",
                        help="Do not overwrite the saved original configuration (for scheduled rotation)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate the changes without touching the system")
    return parser.parse_args()


def main():
    args = get_arguments()
    macip_lib.set_dry_run(args.dry_run)

    try:
        if args.restore:
            if not args.dry_run:
                macip_lib.require_root()
            macip_lib.restore_config(args.interface)
            return

        if not args.dry_run:
            macip_lib.require_root()

        if not macip_lib.interface_exists(args.interface):
            available = ", ".join(macip_lib.list_interfaces()) or "none"
            raise MacipError(
                f"Interface '{args.interface}' does not exist. "
                f"Available interfaces: {available}"
            )

        if args.times < 1:
            raise MacipError("--times must be at least 1.")
        if args.interval < 0:
            raise MacipError("--interval must be zero or positive.")

        version = 6 if args.ipv6 else 4
        network = args.network6 if args.ipv6 else args.network
        prefix = args.prefix if args.prefix is not None else (64 if args.ipv6 else 24)

        if not args.no_save:
            macip_lib.save_config(args.interface)

        with macip_lib.GracefulExit(args.interface, restore=not args.no_restore):
            for i in range(1, args.times + 1):
                new_mac = macip_lib.generate_random_mac()
                new_ip = macip_lib.generate_random_ip(network)
                macip_lib.log(
                    f"\n[*] Attempt {i}/{args.times} - changing MAC to {new_mac} "
                    f"and IPv{version} to {new_ip}"
                )

                # MAC first: its down/up cycle wipes the addresses, so the IP is set last.
                macip_lib.set_mac(args.interface, new_mac)
                macip_lib.set_ip(args.interface, new_ip, prefix)

                updated_mac = macip_lib.get_current_mac(args.interface)
                updated_ip = macip_lib.get_current_ip(args.interface, version)

                if updated_mac and macip_lib.normalize_mac(updated_mac) == new_mac:
                    macip_lib.log(f"[+] MAC successfully changed to {updated_mac}")
                else:
                    macip_lib.log("[-] Failed to change the MAC address.")
                if updated_ip and macip_lib.normalize_ip(updated_ip) == macip_lib.normalize_ip(new_ip):
                    macip_lib.log(f"[+] IP successfully changed to {updated_ip}")
                else:
                    macip_lib.log("[-] Failed to change the IP address.")
                macip_lib.pace(args.interval)

        macip_lib.log(
            f"\n[*] Done. Applied {args.times} MAC and IP changes to {args.interface}."
        )
    except MacipError as exc:
        macip_lib.log(f"[-] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
