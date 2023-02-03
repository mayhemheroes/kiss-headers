#! /usr/bin/env python3
import sys

import atheris

import fuzz_helpers

with atheris.instrument_imports(include=["kiss_headers"]):
    import kiss_headers

def TestOneInput(data):
    fdp = fuzz_helpers.EnhancedFuzzedDataProvider(data)
    headers = kiss_headers.parse_it(fdp.ConsumeRemainingBytes())

    if fdp.ConsumeBool():
        kiss_headers.explain(headers)
    else:
        encoded = kiss_headers.encode(headers)
        decoded_headers = kiss_headers.decode(encoded)
        if decoded_headers != headers:
            raise AssertionError("Decoded data does not match encoded data")
def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
