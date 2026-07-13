#!/usr/bin/env python3
"""Atheris fuzz harness for kiss-headers.

Exercises the public parsing API (`parse_it`) plus the explain/encode/decode
paths on arbitrary input. Atheris instruments the imported kiss_headers
modules, so libFuzzer drives the parser toward new code paths.

Run modes (driven by the compiled launcher `parse-fuzz` / `parse-fuzz-standalone`):
  * fuzzing      — `python3 fuzz_parser.py [libFuzzer args]`
  * single input — `python3 fuzz_parser.py <file>` (libFuzzer runs it once)
"""
import sys

import atheris

sys.path.insert(0, "/mayhem/mayhem")
import fuzz_helpers

with atheris.instrument_imports(include=["kiss_headers"]):
    import kiss_headers


def TestOneInput(data: bytes) -> None:
    fdp = fuzz_helpers.EnhancedFuzzedDataProvider(data)
    try:
        headers = kiss_headers.parse_it(fdp.ConsumeRemainingBytes())

        if fdp.ConsumeBool():
            kiss_headers.explain(headers)
        else:
            encoded = kiss_headers.encode(headers)
            decoded_headers = kiss_headers.decode(encoded)
            if decoded_headers != headers:
                raise AssertionError("Decoded data does not match encoded data")
    except (UnicodeError, ValueError):
        # Encoding/value errors from pathological input are not defects.
        pass


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
