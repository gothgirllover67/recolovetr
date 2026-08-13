#!/usr/bin/env python3
"""
MAINTAINER-ONLY. Builds the DLC xdelta patches shipped in ../../patches/dlc/ from
5_build_dlc.py's output, diffed against each DLC's stock Script.cpk.

Table.cpk is deliberately skipped here: translation/dlc/*/table.tsv is still 100%
untranslated (see README.md "DLC"), so 5_build_dlc.py's built Table.cpk has no actual
translated content -- it differs from stock only in how cpkmakec happened to
recompress it, which isn't something worth shipping a patch for. Re-run this once
table.tsv has real translations in it; the check below will start including it
automatically the day the built and stock Table.cpk actually differ in a way that
matters (it does not try to detect "content differs vs just recompressed" itself --
that's still your call to make once table.tsv is filled in).

usage:
    python 6_build_dlc_xdelta.py <dlc_addcont_dir> <built_dlc_output_dir> [content_id ...]

<dlc_addcont_dir> is the same stock DLC folder used by 5_build_dlc.py.
<built_dlc_output_dir> is 5_build_dlc.py's <work>/dlc_output/ (contains one
<content_id>/media/cpk/ per DLC it built).

Writes ../../patches/dlc/<content_id>/script.xdelta.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'lib'))
sys.path.insert(0, LIB)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

import xdelta_patch  # noqa: E402


def find_xdelta3():
    import shutil
    exe = shutil.which('xdelta3')
    if exe:
        return exe
    sys.exit("ERROR: xdelta3 not found in PATH.")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    dlc_addcont_dir, built_dir = sys.argv[1], sys.argv[2]
    requested = sys.argv[3:]
    xdelta3_exe = find_xdelta3()

    patches_dlc_dir = os.path.normpath(os.path.join(HERE, '..', '..', 'patches', 'dlc'))

    if requested:
        content_ids = requested
    else:
        content_ids = sorted(
            d for d in os.listdir(built_dir) if os.path.isdir(os.path.join(built_dir, d))
        )

    for content_id in content_ids:
        original = os.path.join(dlc_addcont_dir, content_id, 'media', 'cpk', 'Script.cpk')
        modified = os.path.join(built_dir, content_id, 'media', 'cpk', 'Script.cpk')
        if not os.path.isfile(original) or not os.path.isfile(modified):
            print(f"[{content_id}] SKIP -- missing Script.cpk on one side")
            continue

        out_dir = os.path.join(patches_dlc_dir, content_id)
        os.makedirs(out_dir, exist_ok=True)
        patch_out = os.path.join(out_dir, 'script.xdelta')
        xdelta_patch.make_diff(original, modified, patch_out, xdelta3_exe)
        print(f"[{content_id}] {os.path.getsize(original)} bytes -> "
              f"patch {os.path.getsize(patch_out)} bytes -> {patch_out}")

    print()
    print("Table.cpk skipped for all DLC -- see this script's docstring.")


if __name__ == '__main__':
    main()
