#!/usr/bin/env python3
"""
STEP 1 of 3 -- extract resources from YOUR OWN decrypted copy of the game.

This tool never touches a game file we don't ship (we don't ship any) -- it only reads
files that already exist on your machine because you own and installed the game. See
README.md for what "decrypted" means and where to get these files (a jailbroken Vita,
or Vita3K, which decrypts on install).

Point this at the top-level folder of your decrypted 1.07 install -- the one that
directly contains eboot.bin and a media/ folder -- plus your own recog.bin (see below),
and it extracts everything the next two steps need.

usage:
    python 1_extract_resources.py <decrypted_install_dir> <recog.bin> <out_dir>

<decrypted_install_dir> must contain:
    eboot.bin
    media/cpk/Script.cpk
    media/cpk/Table.cpk
    media/cpk/UI.cpk
    media/afs/UI.als

<recog.bin> is YOUR OWN 512-byte NoNpDrm work.bin for this game (PCSG00782), generated
from your own license the same way any Vita homebrew tool generates one for a title you
own. It is not an eboot and not something that can be shared between installs -- every
copy is tied to the account that licensed the game. Needed only to decrypt eboot.bin
into plain code; nothing else in this step needs it.

Output, under <out_dir>:
    script/files/ID#####.bin   -- every file from Script.cpk, decompressed
    table/files/ID#####.bin    -- every file from Table.cpk, decompressed
    ui/files/ID#####.bin       -- every file from UI.cpk, decompressed
    ui/index.tsv               -- every GXT texture block located inside ui/files
    eboot.elf                  -- eboot.bin decrypted to a plain ELF

Nothing here is specific to the English translation -- this step is the same regardless
of what translation you plan to apply in step 2.
"""
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'lib'))
sys.path.insert(0, LIB)

import cpk_extract  # noqa: E402


def check_exists(path, what):
    if not os.path.exists(path):
        sys.exit(f"ERROR: {what} not found at:\n  {path}\n"
                  f"See README.md for where this comes from.")


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    install_dir, recog_bin, out_dir = sys.argv[1:4]

    eboot_bin = os.path.join(install_dir, 'eboot.bin')
    script_cpk = os.path.join(install_dir, 'media', 'cpk', 'Script.cpk')
    table_cpk = os.path.join(install_dir, 'media', 'cpk', 'Table.cpk')
    ui_cpk = os.path.join(install_dir, 'media', 'cpk', 'UI.cpk')
    ui_als = os.path.join(install_dir, 'media', 'afs', 'UI.als')

    for path, what in [(eboot_bin, 'eboot.bin'), (script_cpk, 'Script.cpk'),
                        (table_cpk, 'Table.cpk'), (ui_cpk, 'UI.cpk'),
                        (ui_als, 'media/afs/UI.als'), (recog_bin, 'recog.bin')]:
        check_exists(path, what)

    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("STEP 1/3: extracting Script.cpk, Table.cpk, UI.cpk")
    print("=" * 60)
    n = cpk_extract.extract_cpk(script_cpk, os.path.join(out_dir, 'script', 'files'))
    print(f"[script] {n} files")
    n = cpk_extract.extract_cpk(table_cpk, os.path.join(out_dir, 'table', 'files'))
    print(f"[table]  {n} files")
    n = cpk_extract.extract_cpk(ui_cpk, os.path.join(out_dir, 'ui', 'files'))
    print(f"[ui]     {n} files")

    print()
    print("=" * 60)
    print("STEP 2/3: indexing UI.cpk's GXT texture blocks")
    print("=" * 60)
    ui_files_dir = os.path.join(out_dir, 'ui', 'files')
    ui_index_tsv = os.path.join(out_dir, 'ui', 'index.tsv')
    subprocess.run([sys.executable, os.path.join(LIB, 'gxt_index.py'),
                     ui_files_dir, ui_als, ui_index_tsv], check=True)

    print()
    print("=" * 60)
    print("STEP 3/3: decrypting eboot.bin")
    print("=" * 60)
    eboot_elf = os.path.join(out_dir, 'eboot.elf')
    sceutils_dir = os.path.join(LIB, 'sceutils')
    result = subprocess.run(
        [sys.executable, os.path.join(sceutils_dir, 'self2elf.py'),
         '-i', os.path.abspath(eboot_bin), '-o', os.path.abspath(eboot_elf),
         '-k', os.path.abspath(recog_bin)],
        cwd=sceutils_dir)
    if result.returncode != 0 or not os.path.exists(eboot_elf):
        sys.exit("ERROR: eboot.bin decryption failed -- see the error above. "
                 "A TypeError inside pycryptodome usually means recog.bin is missing "
                 "or is not actually a NoNpDrm work.bin (see README.md).")
    print(f"[eboot] decrypted -> {eboot_elf}")

    print()
    print("Done. Extracted resources are under:", out_dir)
    print("Next: run 2_apply_translation.py")


if __name__ == '__main__':
    main()
