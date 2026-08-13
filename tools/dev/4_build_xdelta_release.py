#!/usr/bin/env python3
"""
MAINTAINER-ONLY. Builds the xdelta patches shipped in ../../patches/ from a finished
build (dev/3_build_patch.py's output) diffed against the stock originals.

This is what makes tools/player/apply_xdelta_patch.py possible: since the diff is
taken against the STOCK ENCRYPTED eboot.bin and the STOCK archives directly (not the
decrypted/extracted intermediates), a player applying the patch never touches
sceutils, recog.bin, or cpkmakec.exe at all -- xdelta3 doesn't care what transformation
produced the "modified" side, only that the player's own stock file is byte-identical
to what this script diffed against, which it will be for anyone on the same game
version.

usage:
    python 4_build_xdelta_release.py <decrypted_install_dir> <built_output_dir>

<decrypted_install_dir> is the same stock 1.07 folder used throughout (must contain
eboot.bin and media/cpk/{Script,Table,UI}.cpk).
<built_output_dir> is dev/3_build_patch.py's output (must contain the same four files,
patched).

Writes ../../patches/{eboot,script,table,ui}.xdelta.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'lib'))
sys.path.insert(0, LIB)

import xdelta_patch  # noqa: E402


def find_xdelta3():
    import shutil
    exe = shutil.which('xdelta3')
    if exe:
        return exe
    sys.exit("ERROR: xdelta3 not found in PATH. Install it (apt/brew/choco install "
              "xdelta3, or grab a Windows build from the xdelta project) and try again.")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    install_dir, built_dir = sys.argv[1], sys.argv[2]
    xdelta3_exe = find_xdelta3()

    patches_dir = os.path.normpath(os.path.join(HERE, '..', '..', 'patches'))
    os.makedirs(patches_dir, exist_ok=True)

    targets = [
        ('eboot', os.path.join(install_dir, 'eboot.bin'),
         os.path.join(built_dir, 'eboot.bin')),
        ('script', os.path.join(install_dir, 'media', 'cpk', 'Script.cpk'),
         os.path.join(built_dir, 'media', 'cpk', 'Script.cpk')),
        ('table', os.path.join(install_dir, 'media', 'cpk', 'Table.cpk'),
         os.path.join(built_dir, 'media', 'cpk', 'Table.cpk')),
        ('ui', os.path.join(install_dir, 'media', 'cpk', 'UI.cpk'),
         os.path.join(built_dir, 'media', 'cpk', 'UI.cpk')),
    ]

    for name, original, modified in targets:
        for p in (original, modified):
            if not os.path.isfile(p):
                sys.exit(f"ERROR: {p} not found.")
        patch_out = os.path.join(patches_dir, name + '.xdelta')
        xdelta_patch.make_diff(original, modified, patch_out, xdelta3_exe)
        orig_size = os.path.getsize(original)
        patch_size = os.path.getsize(patch_out)
        print(f"[{name}] {orig_size} bytes -> patch {patch_size} bytes -> {patch_out}")

    print()
    print("Done. Verify with tools/player/apply_xdelta_patch.py against your own")
    print("stock files before shipping -- it should reproduce the built_output_dir")
    print("files exactly.")


if __name__ == '__main__':
    main()
