#!/usr/bin/env python3
"""
STEP 3 of 3 -- repack everything 2_apply_translation.py produced into the archive
formats the game actually loads, and assemble a folder ready to install.

usage:
    python 3_build_patch.py <decrypted_install_dir> <extracted_dir> <patched_dir>
                             <output_dir> <cpkmakec.exe>

<decrypted_install_dir> is the same folder you gave 1_extract_resources.py -- this
step reads the ORIGINAL archives from it again, to get the exact file-ID list each
repack must contain and to independently verify the result afterwards.

<cpkmakec.exe> is CRI Middleware's own archive tool. It is not included here -- it's
proprietary and not ours to redistribute. See README.md for where fan translation and
modding communities usually get a copy (search "CRI File System Tools" together with
this game's engine or platform; any recent version works, this game always shipped
with plain ITOC archives).

Output, under <output_dir>:
    eboot.bin
    media/cpk/Script.cpk
    media/cpk/Table.cpk
    media/cpk/UI.cpk

That layout mirrors a Vita app install (ux0:app/PCSG00782/) -- copy its contents over
your own decrypted install (or into a "rePatch"-style overlay folder if that's how
you install patches) and the four files above are the whole patch.

Every archive rebuild is validated independently -- re-extracted with our own reader
and compared byte-for-byte against what was intended -- and this script stops at the
first one that doesn't print [PASS], rather than shipping a folder with a silently
broken archive in it.
"""
import os
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'lib'))
sys.path.insert(0, LIB)

import cpk_build  # noqa: E402

# PCSG00782's own auth id, read out of its stock eboot by build_eboot107.bat's original
# author. A "fake self" carries no NPDRM block and needs none -- this is not a signing
# key, just an identifier vita-make-fself stamps into the header.
EBOOT_AUTHID = '0x210000101cce030e'


def stage_repack_dir(original_files_dir, patched_files_dir, repack_dir):
    if os.path.exists(repack_dir):
        shutil.rmtree(repack_dir)
    os.makedirs(repack_dir)
    for fn in os.listdir(original_files_dir):
        shutil.copy2(os.path.join(original_files_dir, fn), os.path.join(repack_dir, fn))
    if os.path.isdir(patched_files_dir):
        for fn in os.listdir(patched_files_dir):
            shutil.copy2(os.path.join(patched_files_dir, fn), os.path.join(repack_dir, fn))


def build_archive(name, original_cpk, extracted_files_dir, patched_files_dir,
                   work_dir, output_cpk, cpkmakec_exe):
    print()
    print("=" * 60)
    print(f"Building {name}")
    print("=" * 60)
    repack_dir = os.path.join(work_dir, name.lower() + '_repack')
    stage_repack_dir(extracted_files_dir, patched_files_dir, repack_dir)

    control_csv = os.path.join(work_dir, name.lower() + '_control.csv')
    n = cpk_build.generate_control_csv(original_cpk, repack_dir, control_csv)
    print(f"[control] {n} file IDs")

    cpk_build.run_cpkmakec(cpkmakec_exe, control_csv, repack_dir, output_cpk)
    print(f"[build] {output_cpk}")

    ok = cpk_build.validate(output_cpk, extracted_files_dir, patched_files_dir)
    if not ok:
        sys.exit(f"ERROR: {name} failed validation -- do not install this patch. "
                  f"See the [FAIL] lines above.")


def main():
    if len(sys.argv) != 6:
        print(__doc__)
        sys.exit(1)
    install_dir, extracted_dir, patched_dir, output_dir, cpkmakec_exe = sys.argv[1:6]

    if not os.path.isfile(cpkmakec_exe):
        sys.exit(f"ERROR: cpkmakec.exe not found at {cpkmakec_exe}\nSee README.md.")

    work_dir = os.path.join(output_dir, '_build')
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'media', 'cpk'), exist_ok=True)

    build_archive(
        'Script', os.path.join(install_dir, 'media', 'cpk', 'Script.cpk'),
        os.path.join(extracted_dir, 'script', 'files'),
        os.path.join(patched_dir, 'script'),
        work_dir, os.path.join(output_dir, 'media', 'cpk', 'Script.cpk'), cpkmakec_exe)

    build_archive(
        'Table', os.path.join(install_dir, 'media', 'cpk', 'Table.cpk'),
        os.path.join(extracted_dir, 'table', 'files'),
        os.path.join(patched_dir, 'table'),
        work_dir, os.path.join(output_dir, 'media', 'cpk', 'Table.cpk'), cpkmakec_exe)

    build_archive(
        'UI', os.path.join(install_dir, 'media', 'cpk', 'UI.cpk'),
        os.path.join(extracted_dir, 'ui', 'files'),
        os.path.join(patched_dir, 'ui'),
        work_dir, os.path.join(output_dir, 'media', 'cpk', 'UI.cpk'), cpkmakec_exe)

    print()
    print("=" * 60)
    print("Building eboot.bin")
    print("=" * 60)
    patched_elf = os.path.join(patched_dir, 'eboot.elf')
    mkfself = os.path.join(LIB, '..', 'bin', 'vita-make-fself.exe')
    mkfself = os.path.normpath(mkfself)
    output_eboot = os.path.join(output_dir, 'eboot.bin')
    if os.path.exists(output_eboot):
        os.remove(output_eboot)
    subprocess.run([mkfself, '-c', '-a', EBOOT_AUTHID, patched_elf, output_eboot],
                    check=True)
    if not os.path.exists(output_eboot):
        sys.exit("ERROR: vita-make-fself produced nothing.")
    print(f"[build] {output_eboot}")

    shutil.rmtree(work_dir, ignore_errors=True)

    print()
    print("=" * 60)
    print("Done. Ready to install:", output_dir)
    print("=" * 60)
    print("  eboot.bin")
    print("  media/cpk/Script.cpk")
    print("  media/cpk/Table.cpk")
    print("  media/cpk/UI.cpk")
    print()
    print("Copy these over your own decrypted PCSG00782 install (or into your")
    print("rePatch-style overlay), matching the same relative paths.")


if __name__ == '__main__':
    main()
