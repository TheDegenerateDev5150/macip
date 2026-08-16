#!/usr/bin/env python3
"""List the network interfaces visible on this system with their MAC and IP."""

import sys

import macip_lib
from macip_lib import MacipError


def main():
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
        ip = macip_lib.get_current_ip(name)
        macip_lib.log(
            f"  {name:<12} MAC: {mac or 'n/a':<20} IP: {ip or 'n/a'}"
        )


if __name__ == "__main__":
    main()
