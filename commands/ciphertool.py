import sys

from pathlib import Path
from functools import partial

from args import args
from utils import output
from crypto import cipher, uncipher
from utils import int_from_path, output_text, compute_d, compute_n, compute_pubkey, complete_privkey, DEFAULT_E


def run():
    n, e, d, p, q, phi = args.n, args.e, args.d, args.p, args.q, args.phi
    if args.command == "encrypt":
        n, e = compute_pubkey(n, e, d, p, q, phi)
        f = partial(cipher, n=n, e=e)
    else:
        if e is None:
            e = DEFAULT_E
        d = compute_d(n, e, d, p, q, phi)
        n = compute_n(n, e, d, p, q, phi)
        f = partial(uncipher, n=n, e=e, d=d)

    if not args.inputs:
        output.error("Nothing to do")

    for text, base_filename in args.inputs: # TODO: implement args.inputs parsing func
        if isinstance(text, Path):
            text = int_from_path(text)
        elif isinstance(text, bytes):
            text = int.from_bytes(text, "big")
        first_line = True
        for std in args.encryption_standard:
            filename = base_filename
            if filename is not True and len(std) > 1:
                filename = f"{filename}.{std}"
            try:
                output_data = f(text, std=std)
            except ValueError as e:
                output.error(f"{std}: {e}")
                continue
            encoding = None
            if args.command == "decrypt":
                encoding = args.encoding
                label = "plaintext"
            else:
                label = "ciphertext"
            if len(args.encryption_standard) > 1:
                if not first_line:
                    output.newline()
                first_line = False
                output.info(f"Using encryption standard {std}")
            output_text(label, output_data, filename, encoding=encoding, json_output=args.json) # TODO: add enc std label for stdout
