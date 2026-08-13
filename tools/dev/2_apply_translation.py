#!/usr/bin/env python3
"""
STEP 2 of 3 -- apply a translation to the resources 1_extract_resources.py produced.

By default this applies the English translation shipped in ../translation/. To use
your own translation instead (a different language, your own edits, a fork of this
project), point --translation-dir at a folder with the same four files and the same
column layout:

    script.csv        columns: file_id, offset_hex, en_text        (comma-separated)
    table.tsv         columns: file_id, offset_hex, en_text        (tab-separated)
    eboot.tsv         "vaddr<TAB>text" per line, no header, # comments allowed
    ui_captions.tsv   columns: source_name, gxt_index, english,
                                box, max_width, mode, rotation, align  (tab-separated)

Any row can be blank/missing in en_text (or english) -- that row is just skipped, so a
partial translation works fine.

usage:
    python 2_apply_translation.py <extracted_dir> <patched_dir> [--translation-dir DIR]

<extracted_dir> is 1_extract_resources.py's output. <patched_dir> is created fresh with:
    script/*.bin     -- only files that had at least one translated line
    table/*.bin      -- only files that had at least one translated line
    eboot.elf        -- always written (a copy even if nothing applied)
    ui/*.bin         -- only files with at least one repainted texture
    ui/preview.png   -- contact sheet of every repainted texture, for a quick look
"""
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'lib'))
DEFAULT_TRANSLATION = os.path.normpath(os.path.join(HERE, '..', '..', 'translation'))
sys.path.insert(0, LIB)

import patch_text  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 2:
        print(__doc__)
        sys.exit(1)
    extracted_dir, patched_dir = args

    translation_dir = DEFAULT_TRANSLATION
    if '--translation-dir' in sys.argv:
        translation_dir = sys.argv[sys.argv.index('--translation-dir') + 1]

    script_csv = os.path.join(translation_dir, 'script.csv')
    table_tsv = os.path.join(translation_dir, 'table.tsv')
    eboot_tsv = os.path.join(translation_dir, 'eboot.tsv')
    ui_tsv = os.path.join(translation_dir, 'ui_captions.tsv')
    for p in (script_csv, table_tsv, eboot_tsv, ui_tsv):
        if not os.path.isfile(p):
            sys.exit(f"ERROR: translation file not found: {p}\n"
                      f"(--translation-dir currently points at {translation_dir})")

    os.makedirs(patched_dir, exist_ok=True)
    had_errors = False

    print("=" * 60)
    print("STEP 1/4: Script.cpk text")
    print("  padding=space -- the ADV text renderer stalls on null padding")
    print("=" * 60)
    applied, touched, errors = patch_text.patch(
        script_csv, os.path.join(extracted_dir, 'script', 'files'),
        os.path.join(patched_dir, 'script'), padding='space')
    print(f"applied {applied} lines in {touched} files")
    if errors:
        had_errors = True
        print(f"{len(errors)} lines did not fit and were skipped -- see the list below")
        for e in errors[:20]:
            print('  ' + e)

    print()
    print("=" * 60)
    print("STEP 2/4: Table.cpk text")
    print("=" * 60)
    applied, touched, errors = patch_text.patch(
        table_tsv, os.path.join(extracted_dir, 'table', 'files'),
        os.path.join(patched_dir, 'table'), padding='null')
    print(f"applied {applied} lines in {touched} files")
    if errors:
        had_errors = True
        print(f"{len(errors)} lines did not fit and were skipped -- see the list below")
        for e in errors[:20]:
            print('  ' + e)

    print()
    print("=" * 60)
    print("STEP 3/4: eboot text")
    print("=" * 60)
    eboot_elf_in = os.path.join(extracted_dir, 'eboot.elf')
    eboot_elf_out = os.path.join(patched_dir, 'eboot.elf')
    result = subprocess.run([sys.executable, os.path.join(LIB, 'eboot_patch.py'),
                              eboot_elf_in, eboot_tsv, eboot_elf_out])
    if result.returncode != 0:
        had_errors = True

    print()
    print("=" * 60)
    print("STEP 4/4: UI.cpk captions (texture repainting)")
    print("  Read the output for \"no such texture\" -- a label aimed at a container")
    print("  name that doesn't exist is silently not drawn, and that's the one")
    print("  failure this step won't stop the build for.")
    print("=" * 60)
    ui_index = os.path.join(extracted_dir, 'ui', 'index.tsv')
    if not os.path.isfile(ui_index):
        sys.exit(f"ERROR: {ui_index} not found -- did 1_extract_resources.py finish "
                  f"its UI.cpk indexing step?")
    ui_out = os.path.join(patched_dir, 'ui')
    os.makedirs(ui_out, exist_ok=True)
    preview = os.path.join(ui_out, 'preview.png')
    result = subprocess.run([sys.executable, os.path.join(LIB, 'gxt_paint.py'),
                              ui_index, ui_tsv, os.path.join(extracted_dir, 'ui', 'files'),
                              ui_out, '--preview', preview])
    if result.returncode != 0:
        had_errors = True

    print()
    print("Done. Patched files are under:", patched_dir)
    if had_errors:
        print("Some steps reported issues above -- review them before building.")
    print("Next: run 3_build_patch.py")


if __name__ == '__main__':
    main()
