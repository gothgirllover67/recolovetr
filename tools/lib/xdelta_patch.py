#!/usr/bin/env python3
"""
Thin wrapper around the xdelta3 command-line tool.

xdelta3 is a widely-used, actively-maintained open-source binary diff/patch tool
(BSD-licensed) -- not included here, same reasoning as cpkmakec.exe: it's a common
external tool, not something specific to this project, so you provide your own copy.
Most package managers have it (apt install xdelta3, brew install xdelta, choco install
xdelta3), or grab a Windows build from the xdelta project's own releases.

Two operations:
    make_diff(original, modified, patch_out, xdelta3_exe)
        Writes a .vcdiff patch that turns `original` into `modified`.
    apply_diff(original, patch_in, output, xdelta3_exe)
        Applies a patch to `original`, writing `output` -- verified byte-for-byte
        against what the patch was built against (xdelta3 checksums this internally
        and fails loudly on a mismatched source file).
"""
import subprocess
import sys


def make_diff(original, modified, patch_out, xdelta3_exe="xdelta3"):
    subprocess.run(
        [xdelta3_exe, "-e", "-f", "-9", "-s", original, modified, patch_out],
        check=True,
    )


def apply_diff(original, patch_in, output, xdelta3_exe="xdelta3"):
    subprocess.run(
        [xdelta3_exe, "-d", "-f", "-s", original, patch_in, output],
        check=True,
    )


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        print("usage: xdelta_patch.py make <original> <modified> <patch_out> [xdelta3_exe]")
        print("       xdelta_patch.py apply <original> <patch_in> <output> [xdelta3_exe]")
        sys.exit(1)

    mode = sys.argv[1]
    a, b, c = sys.argv[2], sys.argv[3], sys.argv[4]
    exe = sys.argv[5] if len(sys.argv) > 5 else "xdelta3"

    if mode == "make":
        make_diff(a, b, c, exe)
    elif mode == "apply":
        apply_diff(a, b, c, exe)
    else:
        sys.exit("mode must be 'make' or 'apply'")


if __name__ == "__main__":
    main()
