"""Index every GXT block inside the files unpacked from UI.cpk.

A .lac is an FPAC container that can hold many GXT blocks -- 01name_resource.lac alone
holds 35, and 04rsm_rec_resource.lac holds 135. Scanning per file would miss almost all
of them, so this walks every "GXT\\0" occurrence and records where it sits.

Columns: file_id, source_name, gxt_index, gxt_offset, data_offset, data_size,
         palette_offset, format, swizzled, width, height

Sizes are exact: P8 stores width*height index bytes followed by a 256-entry RGBA
palette, so a repainted texture re-encodes to the identical byte length and can be
written back in place without moving anything in the container.

usage: gxt_index.py <files_dir> <archive.als> <out.tsv>
"""
import os
import struct
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

files_dir, als_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

BASE = {
    0x0C000000: "U8U8U8U8",
    0x85000000: "UBC1",
    0x86000000: "UBC2",
    0x87000000: "UBC3",
    0x94000000: "P4",
    0x95000000: "P8",
}

names = {}
with open(als_path, encoding="utf-8", errors="replace") as f:
    for i, line in enumerate(l for l in f.read().split("\n") if l.strip()):
        names["ID%05d" % i] = os.path.basename(line)

rows = []
for name in sorted(os.listdir(files_dir)):
    d = open(os.path.join(files_dir, name), "rb").read()
    file_id = os.path.splitext(name)[0]
    pos = d.find(b"GXT\x00")
    idx = 0
    while pos >= 0:
        if pos + 64 <= len(d):
            magic, ver, num_tex, data_off, data_size, n_p4, n_p8, _ = \
                struct.unpack("<8I", d[pos:pos + 32])
            tex_off, tex_size, pal_idx, flags, tex_type, tex_fmt, w, h, mips, _ = \
                struct.unpack("<6I2H2H", d[pos + 32:pos + 64])
            # sanity: a real header has a plausible version and in-range data
            if ver == 0x10000003 and 0 < w <= 4096 and 0 < h <= 4096 \
                    and pos + tex_off + tex_size <= len(d):
                base = tex_fmt & 0xFF000000
                pal_off = pos + tex_off + tex_size if base in (0x95000000, 0x94000000) else -1
                rows.append((file_id, names.get(file_id, ""), idx, pos,
                             pos + tex_off, tex_size, pal_off,
                             BASE.get(base, hex(base)), 1 if tex_type == 0 else 0, w, h))
                idx += 1
        pos = d.find(b"GXT\x00", pos + 1)

with open(out_path, "w", encoding="utf-8", newline="\n") as f:
    f.write("file_id\tsource_name\tgxt_index\tgxt_offset\tdata_offset\tdata_size"
            "\tpalette_offset\tformat\tswizzled\twidth\theight\n")
    for r in rows:
        f.write("%s\t%s\t%d\t%#x\t%#x\t%#x\t%#x\t%s\t%d\t%d\t%d\n" % r)

import collections
fmt = collections.Counter(r[7] for r in rows)
print("textures: %d in %d files -> %s"
      % (len(rows), len(set(r[0] for r in rows)), out_path))
for k, v in fmt.most_common():
    print("  %-10s %d" % (k, v))
