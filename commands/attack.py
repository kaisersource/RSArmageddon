import os
import sys

from shutil import copyfileobj
from pathlib import Path
from tempfile import TemporaryDirectory
from importlib import resources
from subprocess import TimeoutExpired

import sage
import attack_lib
from args import get_args
from utils import to_bytes_auto
from certs import encode_privkey
from crypto import uncipher


def parse_output(s):
    cleartexts = []
    keys = []
    for line in s.splitlines():
        line = line.strip()
        if not line:
            continue
        kind, _, value = map(str.strip, line.partition(":"))
        if kind == "cleartext":
            cleartexts.append(int(value))
        elif kind == "key":
            *key, name = value.split(",")
            key = tuple(int(x) if x else None for x in key)
            keys.append((key, name))
        else:
            raise ValueError(f"Unexpected return type '{kind}' from sage script")
    return cleartexts, keys


def run():
    args = get_args()
    keys = [":".join(map(str, key)) for key in args.pubkeys]

    with TemporaryDirectory() as attack_lib_dir:
        with resources.open_binary(attack_lib, "attack.py") as src:
            with open(Path(attack_lib_dir)/"attack.py", "wb") as dst:
                copyfileobj(src, dst)

        env = os.environ.copy()
        env["PYTHONPATH"] = attack_lib_dir

        for attack in args.attacks:
            try:
                script_manager = attack_path(attack)
            except ValueError as e:
                print(e, file=sys.stderr)
                continue

            with script_manager as script:
                try:
                    p = sage.run(script, *args.ciphertexts, *keys, env=env, timeout=args.timeout)
                except TimeoutExpired:
                    print(f"[W] Timeout expired for attack {attack}", file=sys.stderr)
                    continue

                if p.returncode:
                    continue

                cleartexts, keys = parse_output(p.stdout)

                if cleartexts:
                    print("[@] Cleartexts recovered", file=sys.stderr)
                    for text in cleartexts:
                        print(to_bytes_auto(text))

                if not keys:
                    continue

                if len(keys) == 1:
                    key, _ = keys[0]

                    if args.output_private is True:
                        sys.stdout.buffer.write(encode_privkey(*key, "PEM"))
                        print()
                    elif args.output_private:
                        with open(args.output_private, "wb") as f:
                            f.write(encode_privkey(*key, "PEM"))

                    for text, filename in args.ciphertexts:
                        text_bytes = to_bytes_auto(text)
                        print(f"[$] Decrypting 0x{text_bytes.hex()}", file=sys.stderr)
                        n, e, d, _, _ = key
                        cleartext = uncipher(text, n, e, d, args.padding)
                        cleartext_bytes = to_bytes_auto(cleartext)
                        if filename is True:
                            print(cleartext_bytes)
                        else:
                            with open(filename, "wb") as f:
                                f.write(cleartext_bytes)

                if args.output_dir is not None:
                    for key, name in keys:
                        with open(args.output_dir/f"{name}.pem", "wb") as f:
                            f.write(encode_privkey(*key, "PEM"))

                break
