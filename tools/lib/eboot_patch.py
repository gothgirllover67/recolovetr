"""Apply a translation table to the decrypted eboot.elf.

Accepts either form of TSV:
  - the worklist from build_worklist.py (header with source/addr/en_text columns;
    only source=EBOOT rows are used, rows with an empty en_text are skipped)
  - a bare two-column "vaddr<TAB>text" table
Lines starting with # and blank lines are ignored; \\n in text becomes a real newline.

Each replacement is written in place over the original string plus whatever zero
padding follows it, so the new UTF-8 text must fit in len+slack bytes. Nothing moves,
so pointers, relocations and segment sizes stay valid.

usage: apply_patch.py <in.elf> <translations.tsv> <out.elf>
"""
import struct
import sys

# Windows consoles often default to a codepage (cp1251, cp932, ...) that can't encode
# every character a translation might legitimately contain -- reconfigure stdout to
# UTF-8 so a progress line never crashes the run partway through a build.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

elf_in, table_path, elf_out = sys.argv[1], sys.argv[2], sys.argv[3]

d = bytearray(open(elf_in, "rb").read())

# map vaddr -> file offset via the PT_LOAD headers
phoff = struct.unpack("<I", d[28:32])[0]
phnum = struct.unpack("<H", d[44:46])[0]
loads = []
for i in range(phnum):
    o = phoff + i * 32
    p_type, p_off, p_va, p_pa, p_fsz, p_msz, p_fl, p_al = struct.unpack("<8I", d[o:o + 32])
    if p_type == 1:
        loads.append((p_va, p_off, p_fsz))


def to_offset(va):
    for p_va, p_off, p_fsz in loads:
        if p_va <= va < p_va + p_fsz:
            return p_off + (va - p_va)
    raise ValueError("vaddr %#x is not inside any PT_LOAD segment" % va)


def budget(off):
    """original string length plus the zero padding that follows it"""
    end = off
    while d[end] != 0:
        end += 1
    pad = end
    while d[pad] == 0:
        pad += 1
    return end - off, pad - end - 1


lines = open(table_path, encoding="utf-8").read().split("\n")

# worklist format? then locate the columns and keep only the eboot rows
cols = lines[0].split("\t") if lines else []
worklist = "addr" in cols and "en_text" in cols
if worklist:
    i_src = cols.index("source") if "source" in cols else None
    i_addr = cols.index("addr")
    i_en = cols.index("en_text")

applied = 0
errors = 0
skipped = 0
for lineno, line in enumerate(lines, 1):
    line = line.rstrip("\r")
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    parts = line.split("\t")

    if worklist:
        if lineno == 1:
            continue
        if len(parts) <= i_en:
            continue
        if i_src is not None and parts[i_src] != "EBOOT":
            continue
        if not parts[i_en].strip():
            skipped += 1
            continue
        va_s, new = parts[i_addr], parts[i_en]
    else:
        if len(parts) < 2:
            print("line %d: expected 'vaddr<TAB>text'" % lineno)
            errors += 1
            continue
        va_s, new = parts[0].strip(), parts[1]
        if va_s.lower() in ("vaddr", "offset"):
            continue
    va = int(va_s, 16)
    new = new.replace("\\n", "\n").encode("utf-8")

    off = to_offset(va)
    orig_len, slack = budget(off)
    room = orig_len + slack

    old_text = bytes(d[off:off + orig_len]).decode("utf-8", "replace")
    if len(new) > room:
        print("line %d: %#x needs %d bytes, only %d available  (%s)"
              % (lineno, va, len(new), room, old_text[:24]))
        errors += 1
        continue

    d[off:off + room + 1] = new + b"\x00" * (room + 1 - len(new))
    applied += 1
    print("%#x  %-30s -> %s" % (va, old_text[:30], new.decode("utf-8").replace("\n", "\\n")))

open(elf_out, "wb").write(d)
print()
print("applied %d, failed %d, untranslated %d -> %s" % (applied, errors, skipped, elf_out))
sys.exit(1 if errors else 0)
