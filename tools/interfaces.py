#!/usr/bin/env python3
"""List the network interfaces visible on this system with their MAC and IP."""

import argparse
import sys

import macip_lib
from macip_lib import MacipError


def get_arguments():
    parser = argparse.ArgumentParser(
        description="List the network interfaces visible on this system with their MAC and IP"
    )
    return parser.parse_args()


def main():
    get_arguments()  # validates CLI, provides --help
    try:
        interfaces = macip_lib.list_interfaces()
    except MacipError as exc:
        macip_lib.log(f"[-] {exc}")
        sys.exit(1)

    if not interfaces:
        macip_lib.log("[-] No network interfaces found.")
        sys.exit(1)

    macip_lib.log("Available network interfaces:")
    for name in interfaces:
        mac = macip_lib.get_current_mac(name)
        ip = macip_lib.get_current_ip(name, 4)
        ip6 = macip_lib.get_current_ip(name, 6)
        macip_lib.log(
            f"  {name:<12} MAC: {mac or 'n/a':<20} "
            f"IPv4: {ip or 'n/a':<16} IPv6: {ip6 or 'n/a'}"
        )


if __name__ == "__main__":
    main()
