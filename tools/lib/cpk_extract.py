#!/usr/bin/env python3
"""
Extracts every file out of an ITOC-based CRI CPK archive (the layout Script.cpk,
Table.cpk and UI.cpk all use in this game -- confirmed: TocOffset is unset, only
ItocOffset is), decompressing CRILAYLA-compressed entries as it goes.

No third-party dependencies -- pure Python 3 standard library.

usage: cpk_extract.py <archive.cpk> <out_dir>

Output: <out_dir>/ID#####.bin for every file the archive's ITOC lists.
"""
import struct
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


# ---------------------------------------------------------------------------
# CRI @UTF table parser (used for both the CPK header and the ITOC table)
# ---------------------------------------------------------------------------

STORAGE_NONE = 0x00
STORAGE_ZERO = 0x10
STORAGE_CONSTANT = 0x30
STORAGE_CONSTANT2 = 0x70


def read_utf_packet(data, offset):
    assert data[offset:offset + 4] == b'@UTF', \
        f"Not a @UTF packet at {offset}: {data[offset:offset + 8]!r}"
    table_size = struct.unpack('>I', data[offset + 4:offset + 8])[0]
    table_data = data[offset + 8:offset + 8 + table_size]
    return parse_utf_table(table_data), offset + 8 + table_size


def parse_utf_table(t):
    rows_offset, strings_offset, data_offset = struct.unpack('>III', t[0:12])
    num_columns = struct.unpack('>H', t[16:18])[0]
    num_rows = struct.unpack('>I', t[20:24])[0]

    def read_string(off):
        end = t.find(b'\x00', strings_offset + off)
        return t[strings_offset + off:end].decode('shift_jis', errors='replace')

    def read_raw_value(typ, pos):
        if typ == 0x00:
            return t[pos], pos + 1
        if typ == 0x01:
            return struct.unpack('>b', t[pos:pos + 1])[0], pos + 1
        if typ == 0x02:
            return struct.unpack('>H', t[pos:pos + 2])[0], pos + 2
        if typ == 0x03:
            return struct.unpack('>h', t[pos:pos + 2])[0], pos + 2
        if typ == 0x04:
            return struct.unpack('>I', t[pos:pos + 4])[0], pos + 4
        if typ == 0x05:
            return struct.unpack('>i', t[pos:pos + 4])[0], pos + 4
        if typ == 0x06:
            return struct.unpack('>Q', t[pos:pos + 8])[0], pos + 8
        if typ == 0x07:
            return struct.unpack('>q', t[pos:pos + 8])[0], pos + 8
        if typ == 0x08:
            return struct.unpack('>f', t[pos:pos + 4])[0], pos + 4
        if typ == 0x09:
            return struct.unpack('>d', t[pos:pos + 8])[0], pos + 8
        if typ == 0x0A:
            off = struct.unpack('>I', t[pos:pos + 4])[0]
            return read_string(off), pos + 4
        if typ == 0x0B:
            doff, dsize = struct.unpack('>II', t[pos:pos + 8])
            return t[data_offset + doff:data_offset + doff + dsize], pos + 8
        raise ValueError(f"Unknown column type {typ:#x}")

    pos = 24
    columns = []
    for _ in range(num_columns):
        flag = t[pos]
        pos += 1
        col_type = flag & 0x0f
        col_storage = flag & 0xf0
        name_off = struct.unpack('>I', t[pos:pos + 4])[0]
        pos += 4
        name = read_string(name_off)
        const_val = None
        if col_storage in (STORAGE_CONSTANT, STORAGE_CONSTANT2):
            const_val, pos = read_raw_value(col_type, pos)
        columns.append({'type': col_type, 'storage': col_storage, 'name': name, 'const': const_val})

    rows = []
    row_pos = rows_offset
    for _ in range(num_rows):
        pos = row_pos
        row = {}
        for col in columns:
            if col['storage'] in (STORAGE_ZERO, STORAGE_NONE):
                row[col['name']] = 0
                continue
            if col['storage'] in (STORAGE_CONSTANT, STORAGE_CONSTANT2):
                row[col['name']] = col['const']
                continue
            val, pos = read_raw_value(col['type'], pos)
            row[col['name']] = val
        rows.append(row)
        row_pos = pos

    return {'columns': columns, 'rows': rows}


# ---------------------------------------------------------------------------
# CRILAYLA decompressor
# ---------------------------------------------------------------------------

def decompress_crilayla(data):
    if data[0:8] != b'CRILAYLA':
        return data
    uncompressed_size = struct.unpack('<I', data[8:12])[0]
    uncompressed_header_offset = struct.unpack('<I', data[12:16])[0]

    result = bytearray(uncompressed_size + 0x100)
    result[0:0x100] = data[16 + uncompressed_header_offset:
                            16 + uncompressed_header_offset + 0x100]

    input_offset = len(data) - 0x100 - 1
    output_end = 0x100 + uncompressed_size - 1

    bit_pool = 0
    bits_left = 0
    bytes_output = 0
    vle_lens = [2, 3, 5, 8]

    def get_next_bits(n):
        nonlocal input_offset, bit_pool, bits_left
        out_bits = 0
        produced = 0
        while produced < n:
            if bits_left == 0:
                bit_pool = data[input_offset]
                input_offset -= 1
                bits_left = 8
            take = min(n - produced, bits_left)
            out_bits = (out_bits << take) | \
                ((bit_pool >> (bits_left - take)) & ((1 << take) - 1))
            bits_left -= take
            produced += take
        return out_bits

    while bytes_output < uncompressed_size:
        if get_next_bits(1) > 0:
            back_offset = output_end - bytes_output + get_next_bits(13) + 3
            back_len = 3
            lvl = 0
            while True:
                chunk = get_next_bits(vle_lens[lvl])
                back_len += chunk
                if chunk != ((1 << vle_lens[lvl]) - 1):
                    break
                if lvl < len(vle_lens) - 1:
                    lvl += 1
            for i in range(back_len):
                result[output_end - bytes_output] = result[back_offset - i]
                bytes_output += 1
        else:
            result[output_end - bytes_output] = get_next_bits(8)
            bytes_output += 1

    return bytes(result)


# ---------------------------------------------------------------------------
# CPK / ITOC extraction
# ---------------------------------------------------------------------------

def extract_cpk(cpk_path, out_dir):
    data = open(cpk_path, 'rb').read()
    if data[:4] != b'CPK ':
        raise SystemExit(
            f"ERROR: {cpk_path} does not start with 'CPK ' magic bytes.\n"
            f"This usually means the file is still PFS-encrypted rather than a plain\n"
            f"decrypted archive -- point this at a file straight out of your own\n"
            f"legally-installed, decrypted copy of the game (see the README).")

    header_table, _ = read_utf_packet(data, 16)
    row = header_table['rows'][0]
    content_offset = row['ContentOffset']
    align = row['Align']
    itoc_offset = row['ItocOffset']
    toc_offset = row['TocOffset']

    if not itoc_offset:
        raise SystemExit(
            f"ERROR: {cpk_path} does not use the ITOC-only layout this tool expects "
            f"(ItocOffset==0, TocOffset={toc_offset}). Script.cpk, Table.cpk and "
            f"UI.cpk are all ITOC-only in this game -- if you're pointing this at a "
            f"different archive, it needs a TOC-aware reader instead.")

    itoc_table, _ = read_utf_packet(data, itoc_offset + 16)
    irow = itoc_table['rows'][0]
    table_l, _ = read_utf_packet(irow['DataL'], 0)
    table_h, _ = read_utf_packet(irow['DataH'], 0)

    entries = {}
    for r in table_l['rows']:
        entries[r['ID']] = r['FileSize']
    for r in table_h['rows']:
        entries[r['ID']] = r['FileSize']

    os.makedirs(out_dir, exist_ok=True)

    offset = content_offset
    written = 0
    for fid in sorted(entries.keys()):
        fsize = entries[fid]
        raw = data[offset:offset + fsize]
        content = decompress_crilayla(raw) if raw[:8] == b'CRILAYLA' else raw
        with open(os.path.join(out_dir, f'ID{fid:05d}.bin'), 'wb') as f:
            f.write(content)
        written += 1
        padded = ((fsize + align - 1) // align) * align
        offset += padded

    return written


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    cpk_path, out_dir = sys.argv[1], sys.argv[2]
    written = extract_cpk(cpk_path, out_dir)
    print(f'[extract] {written} files -> {out_dir}')


if __name__ == '__main__':
    main()
