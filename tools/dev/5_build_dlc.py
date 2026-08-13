#!/usr/bin/env python3
"""
Extract, translate and repack the story DLC (Script.cpk + Table.cpk only -- see
"Which DLC files this touches" below).

Each DLC content ID restarts its own file-ID numbering at ID00000, so it needs its own
extraction and its own translation files -- unlike the base game, this is NOT something
that shares offsets with anything else. translation/dlc/<content_id>/script.csv and
table.tsv hold each DLC's own translation, same column layout as the base game's.

usage:
    python 5_build_dlc.py <dlc_addcont_dir> <work_dir> <cpkmakec.exe> [content_id ...]

<dlc_addcont_dir> is the folder that directly contains one subfolder per content ID
(e.g. Vita3K's ux0/addcont/PCSG00782/, or a jailbroken Vita's
ux0:addcont/PCSG00782/ pulled onto your PC) -- each subfolder must have
media/cpk/Script.cpk and media/cpk/Table.cpk from YOUR OWN decrypted, installed copy
of that DLC.

[content_id ...] optionally limits the run to specific DLC IDs (e.g. RECOLOVE00000006);
omit to do all four the translation data covers.

Output, under <work_dir>/dlc_output/<content_id>/media/cpk/:
    Script.cpk
    Table.cpk

Copy each content ID's two files over the matching addcont folder on your own install.

Which DLC files this touches: only Script.cpk (the story) and Table.cpk (event/item
titles). UI.cpk is skipped -- each DLC's UI.cpk is a 15KB manifest plus one opaque
128x128 texture (route thumbnail art, not a caption) and two 8x8 dummies, confirmed by
checking alpha: real captions in this game are roughly half fully-transparent, and this
isn't. CharaModel.cpk, CharaMotion.cpk, CharaTex.cpk and Common.cpk carry no text at
all (3D models, motion data, textures, shared assets) -- nothing to translate there
either, so DLC install folders keep those files exactly as your own copy already has
them; this script never touches them.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'lib'))
TRANSLATION_DLC = os.path.normpath(os.path.join(HERE, '..', '..', 'translation', 'dlc'))
sys.path.insert(0, LIB)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

import cpk_extract   # noqa: E402
import patch_text    # noqa: E402
import cpk_build      # noqa: E402


def build_one(content_id, dlc_addcont_dir, work_dir, cpkmakec_exe):
    print()
    print("=" * 60)
    print(f"DLC {content_id}")
    print("=" * 60)

    translation_dir = os.path.join(TRANSLATION_DLC, content_id)
    script_csv = os.path.join(translation_dir, 'script.csv')
    table_tsv = os.path.join(translation_dir, 'table.tsv')
    if not os.path.isfile(script_csv):
        print(f"  SKIP -- no translation data at {translation_dir}")
        return None

    dlc_dir = os.path.join(dlc_addcont_dir, content_id)
    script_cpk = os.path.join(dlc_dir, 'media', 'cpk', 'Script.cpk')
    table_cpk = os.path.join(dlc_dir, 'media', 'cpk', 'Table.cpk')
    for p in (script_cpk, table_cpk):
        if not os.path.isfile(p):
            print(f"  ERROR: {p} not found -- skipping this content ID.")
            return False

    content_work = os.path.join(work_dir, content_id)
    extracted_script = os.path.join(content_work, 'extracted', 'script')
    extracted_table = os.path.join(content_work, 'extracted', 'table')
    patched_script = os.path.join(content_work, 'patched', 'script')
    patched_table = os.path.join(content_work, 'patched', 'table')

    print("  extracting...")
    n = cpk_extract.extract_cpk(script_cpk, extracted_script)
    print(f"    script: {n} files")
    n = cpk_extract.extract_cpk(table_cpk, extracted_table)
    print(f"    table: {n} files")

    print("  patching...")
    applied, touched, errors = patch_text.patch(script_csv, extracted_script,
                                                 patched_script, padding='space')
    print(f"    script: applied {applied} lines in {touched} files"
          + (f", {len(errors)} issues" if errors else ""))
    for e in errors[:10]:
        print("      " + e)

    applied, touched, errors = patch_text.patch(table_tsv, extracted_table,
                                                 patched_table, padding='null')
    print(f"    table: applied {applied} lines in {touched} files"
          + (f", {len(errors)} issues" if errors else ""))
    for e in errors[:10]:
        print("      " + e)

    print("  building...")
    out_dir = os.path.join(work_dir, 'dlc_output', content_id, 'media', 'cpk')
    os.makedirs(out_dir, exist_ok=True)

    ok = True
    for name, orig_cpk, ext_dir, pat_dir in [
        ('Script.cpk', script_cpk, extracted_script, patched_script),
        ('Table.cpk', table_cpk, extracted_table, patched_table),
    ]:
        repack_dir = os.path.join(content_work, 'repack', name)
        if os.path.exists(repack_dir):
            shutil.rmtree(repack_dir)
        os.makedirs(repack_dir)
        for fn in os.listdir(ext_dir):
            shutil.copy2(os.path.join(ext_dir, fn), os.path.join(repack_dir, fn))
        if os.path.isdir(pat_dir):
            for fn in os.listdir(pat_dir):
                shutil.copy2(os.path.join(pat_dir, fn), os.path.join(repack_dir, fn))

        control_csv = os.path.join(content_work, name + '.control.csv')
        cpk_build.generate_control_csv(orig_cpk, repack_dir, control_csv)
        output_cpk = os.path.join(out_dir, name)
        cpk_build.run_cpkmakec(cpkmakec_exe, control_csv, repack_dir, output_cpk)
        print(f"    [build] {output_cpk}")
        if not cpk_build.validate(output_cpk, ext_dir, pat_dir):
            ok = False

    return ok


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    dlc_addcont_dir, work_dir, cpkmakec_exe = sys.argv[1:4]
    requested = sys.argv[4:]

    if not os.path.isfile(cpkmakec_exe):
        sys.exit(f"ERROR: cpkmakec.exe not found at {cpkmakec_exe}")

    if requested:
        content_ids = requested
    else:
        content_ids = sorted(
            d for d in os.listdir(TRANSLATION_DLC)
            if os.path.isdir(os.path.join(TRANSLATION_DLC, d))
        )

    results = {}
    for content_id in content_ids:
        results[content_id] = build_one(content_id, dlc_addcont_dir, work_dir, cpkmakec_exe)

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    for content_id, ok in results.items():
        status = "PASS" if ok else ("SKIPPED" if ok is None else "FAIL")
        print(f"  {content_id}: {status}")

    if any(ok is False for ok in results.values()):
        sys.exit(1)


if __name__ == '__main__':
    main()
