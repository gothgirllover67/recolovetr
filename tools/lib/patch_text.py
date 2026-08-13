#!/usr/bin/env python3
"""
Writes translated text into files extracted from a CPK by cpk_extract.py.

Works for any archive whose strings are null-terminated UTF-8 at a fixed byte offset
(Script.cpk and Table.cpk both are). A translation source is a CSV or TSV with at least
these columns (extra columns are ignored):

    file_id                  e.g. ID00001 (matches ID00001.bin in files_dir)
    offset_hex OR offset     byte offset of the string within that file, hex,
                              e.g. 00001fcb or 0x3ac (either column name works)
    en_text                  the replacement text (\\n becomes a real newline)

.csv is read comma-delimited, .tsv tab-delimited -- pick the extension accordingly.

Room for the replacement is measured directly from the file, not trusted from a column:
starting at offset_hex, scan forward to the original string's null terminator, then
keep scanning through the zero padding that follows until a non-zero byte turns up.
That whole span, minus one byte reserved for a fresh terminator, is what the
replacement must fit in. This works whether the slot has generous slack or none at
all, and never depends on a byte_length figure computed by a different tool at a
different time.

Padding: the byte used to fill whatever's left of the slot after the terminator.
Two archives in this game disagree about which one is safe -- Table.cpk wants null
(0x00, the correct choice for a plain C string) while Script.cpk's ADV text renderer
stalls if it reads null bytes as part of the string, so its slots need space (0x20).
Default is null; pass --padding space for Script.cpk.

usage: patch_text.py <translation.csv|.tsv> <files_dir> <out_dir> [--padding null|space]
"""
import csv
import os
import sys
from collections import defaultdict

# error messages can echo back a snippet of the original Japanese text; make sure a
# narrow Windows console codepage can't crash the run over a print() call.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def load_rows(path):
    delim = '\t' if path.lower().endswith('.tsv') else ','
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=delim))


def budget(data, off):
    """Scan from off: (original string length, zero padding after it)."""
    end = off
    while data[end] != 0:
        end += 1
    pad = end
    while pad < len(data) and data[pad] == 0:
        pad += 1
    return end - off, pad - end


def patch(csv_path, files_dir, out_dir, padding='null'):
    pad_byte = b'\x00' if padding == 'null' else b'\x20'
    os.makedirs(out_dir, exist_ok=True)

    rows = load_rows(csv_path)
    if not rows:
        return 0, 0, []
    off_col = 'offset_hex' if 'offset_hex' in rows[0] else 'offset'

    by_file = defaultdict(list)
    for row in rows:
        en = (row.get('en_text') or '').strip()
        if not en:
            continue
        by_file[row['file_id']].append(row)

    applied = 0
    errors = []
    touched = 0

    for file_id, file_rows in sorted(by_file.items()):
        src = os.path.join(files_dir, file_id + '.bin')
        if not os.path.isfile(src):
            errors.append('missing source file: %s' % src)
            continue
        data = bytearray(open(src, 'rb').read())
        changed = False

        for row in file_rows:
            off_str = row[off_col]
            off = int(off_str, 16)
            en = row['en_text'].replace('\\n', '\n')
            new = en.encode('utf-8')

            if off >= len(data):
                errors.append('%s @ %s: offset past end of file (%d bytes)'
                               % (file_id, off_str, len(data)))
                continue

            orig_len, slack = budget(data, off)
            room = orig_len + slack - 1  # keep at least one terminator byte

            if len(new) > room:
                old = bytes(data[off:off + orig_len]).decode('utf-8', 'replace')
                errors.append('%s @ %s: needs %d bytes, only %d available  (%s)'
                               % (file_id, off_str, len(new), room, old[:24]))
                continue

            data[off:off + room] = new + pad_byte * (room - len(new))
            data[off + room] = 0
            applied += 1
            changed = True

        if changed:
            with open(os.path.join(out_dir, file_id + '.bin'), 'wb') as f:
                f.write(data)
            touched += 1

    return applied, touched, errors


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 3:
        print(__doc__)
        sys.exit(1)
    csv_path, files_dir, out_dir = args

    padding = 'null'
    if '--padding' in sys.argv:
        padding = sys.argv[sys.argv.index('--padding') + 1]
        if padding not in ('null', 'space'):
            sys.exit('--padding must be null or space')

    applied, touched, errors = patch(csv_path, files_dir, out_dir, padding)

    print('applied %d replacements in %d files -> %s' % (applied, touched, out_dir))
    if errors:
        print('%d issues:' % len(errors))
        for e in errors[:50]:
            print('  ' + e)
        if len(errors) > 50:
            print('  ... and %d more' % (len(errors) - 50))
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
