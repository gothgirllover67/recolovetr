#!/usr/bin/env python3
"""
Apply the official English patch to your own decrypted copy of the game.

This is the simple path: it does NOT need cpkmakec.exe, does NOT need your own
recog.bin, and does NOT need Python packages beyond the standard library -- just
xdelta3 and your own decrypted 1.07 install. If you want to build your own
translation, or customize this one, use tools/dev/ instead (see README.md).

usage:
    python apply_xdelta_patch.py <decrypted_install_dir> <output_dir>

<decrypted_install_dir> must contain eboot.bin and media/cpk/{Script,Table,UI}.cpk
straight from your own decrypted, version-1.07 copy of PCSG00782 (see README.md for
where that comes from -- Vita3K or a jailbroken Vita, either decrypts on install).

Output, under <output_dir>:
    eboot.bin
    media/cpk/Script.cpk
    media/cpk/Table.cpk
    media/cpk/UI.cpk

Copy these over your own install (or into your rePatch-style overlay), matching the
same relative paths, then reinstall/reboot so the game picks up the new archives.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES_DIR = os.path.normpath(os.path.join(HERE, '..', '..', 'patches'))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def find_xdelta3():
    exe = shutil.which('xdelta3')
    if exe:
        return exe
    sys.exit("ERROR: xdelta3 not found in PATH.\n"
              "Install it -- apt/brew/choco install xdelta3, or grab a build from "
              "the xdelta project's own releases -- and try again. See README.md.")


def apply_one(xdelta3_exe, original, patch_file, output):
    os.makedirs(os.path.dirname(output), exist_ok=True)
    result = subprocess.run([xdelta3_exe, '-d', '-f', '-s', original, patch_file, output])
    if result.returncode != 0 or not os.path.exists(output):
        sys.exit(f"ERROR: applying {patch_file} to {original} failed. This usually "
                  f"means your game version doesn't match what the patch was built "
                  f"against -- make sure you're on version 1.07.")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    install_dir, output_dir = sys.argv[1], sys.argv[2]
    xdelta3_exe = find_xdelta3()

    targets = [
        ('eboot.bin', 'eboot.xdelta', 'eboot.bin'),
        (os.path.join('media', 'cpk', 'Script.cpk'), 'script.xdelta',
         os.path.join('media', 'cpk', 'Script.cpk')),
        (os.path.join('media', 'cpk', 'Table.cpk'), 'table.xdelta',
         os.path.join('media', 'cpk', 'Table.cpk')),
        (os.path.join('media', 'cpk', 'UI.cpk'), 'ui.xdelta',
         os.path.join('media', 'cpk', 'UI.cpk')),
    ]

    for rel_original, patch_name, rel_output in targets:
        original = os.path.join(install_dir, rel_original)
        patch_file = os.path.join(PATCHES_DIR, patch_name)
        output = os.path.join(output_dir, rel_output)

        if not os.path.isfile(original):
            sys.exit(f"ERROR: {original} not found. Point this at your own decrypted "
                      f"1.07 install (see README.md).")
        if not os.path.isfile(patch_file):
            sys.exit(f"ERROR: {patch_file} not found -- this release is missing its "
                      f"xdelta patches.")

        apply_one(xdelta3_exe, original, patch_file, output)
        print(f"[{rel_original}] -> {output}")

    print()
    print("Done. Ready to install:", output_dir)
    print("Copy these four files over your own decrypted install (or into your")
    print("rePatch-style overlay), matching the same relative paths, then")
    print("reinstall/reboot so the game picks up the new archives.")


if __name__ == '__main__':
    main()
