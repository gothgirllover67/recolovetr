#!/usr/bin/env python3
"""
Apply the official English DLC patch to your own decrypted copy of the story DLC.

Simple path, same idea as apply_xdelta_patch.py for the base game: no cpkmakec.exe,
no Python packages beyond the standard library, just xdelta3 and your own decrypted
DLC. Only Script.cpk is patched -- see README.md "DLC" for why Table.cpk isn't
included yet (it isn't translated) and UI.cpk never will be (no translatable text
in it).

usage:
    python apply_dlc_xdelta_patch.py <dlc_addcont_dir> <output_dir> [content_id ...]

<dlc_addcont_dir> is the folder that directly contains one subfolder per content ID
(Vita3K's ux0/addcont/PCSG00782/, or the equivalent pulled off a jailbroken Vita) --
each subfolder needs media/cpk/Script.cpk from your own decrypted, installed copy of
that DLC.

[content_id ...] optionally limits the run to specific DLC IDs; omit to patch every
DLC this release has a patch for.

Output, under <output_dir>/<content_id>/media/cpk/Script.cpk -- copy each content
ID's file over the matching addcont folder on your own install.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES_DLC_DIR = os.path.normpath(os.path.join(HERE, '..', '..', 'patches', 'dlc'))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def find_xdelta3():
    exe = shutil.which('xdelta3')
    if exe:
        return exe
    sys.exit("ERROR: xdelta3 not found in PATH. See README.md.")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    dlc_addcont_dir, output_dir = sys.argv[1], sys.argv[2]
    requested = sys.argv[3:]
    xdelta3_exe = find_xdelta3()

    if requested:
        content_ids = requested
    else:
        content_ids = sorted(
            d for d in os.listdir(PATCHES_DLC_DIR)
            if os.path.isdir(os.path.join(PATCHES_DLC_DIR, d))
        )

    if not content_ids:
        sys.exit(f"ERROR: no DLC patches found under {PATCHES_DLC_DIR}")

    for content_id in content_ids:
        original = os.path.join(dlc_addcont_dir, content_id, 'media', 'cpk', 'Script.cpk')
        patch_file = os.path.join(PATCHES_DLC_DIR, content_id, 'script.xdelta')
        output = os.path.join(output_dir, content_id, 'media', 'cpk', 'Script.cpk')

        if not os.path.isfile(original):
            print(f"[{content_id}] SKIP -- {original} not found")
            continue
        if not os.path.isfile(patch_file):
            print(f"[{content_id}] SKIP -- no patch shipped for this content ID")
            continue

        os.makedirs(os.path.dirname(output), exist_ok=True)
        result = subprocess.run([xdelta3_exe, '-d', '-f', '-s', original, patch_file, output])
        if result.returncode != 0 or not os.path.exists(output):
            print(f"[{content_id}] FAILED -- game version mismatch? See README.md.")
            continue
        print(f"[{content_id}] -> {output}")

    print()
    print("Done. Copy each content ID's Script.cpk over the matching addcont folder")
    print("on your own install, then reinstall/reboot.")


if __name__ == '__main__':
    main()
