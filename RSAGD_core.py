#!/usr/bin/env python3


import sys

import banner
from args import get_args
from commands import pem, ciphertool, attack, default


def main():
    banner.print()

    actions = {
        None: default.run,
        "pem": pem.run,
        "ciphertool": ciphertool.run,
        "attack": attack.run
    }

    try:
        args = get_args()
    except (ValueError, OSError) as e:
        print(f"[-] {e}", file=sys.stderr)

    actions[args.subp]()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[-] Interrupted")
    #except Exception as e:
    #    print(f"[E] Unhandled exception: {e}")
    else:
        sys.exit(0)

    sys.exit(1)
