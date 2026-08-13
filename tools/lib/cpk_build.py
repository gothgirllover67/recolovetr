#!/usr/bin/env python3
"""
Repacks a staged folder of files (originals + patched overlay) back into a CPK, in the
same ITOC-only, forcecompress layout the original archive used, then independently
verifies the result by re-reading it with our own parser rather than trusting
cpkmakec.exe's exit code.

Three things happen, in order:
  1. generate_control_csv  -- reads the ORIGINAL archive to get the exact list of file
     IDs it must contain, and writes the control CSV cpkmakec.exe needs.
  2. run_cpkmakec           -- invokes cpkmakec.exe. -mode=ID -forcecompress
     reproduces the stock layout (ITOC only, no TOC/GTOC -- a repack with extra tables
     is the known shape of a black-screen crash when DLC is also installed).
  3. validate               -- re-extracts the new archive with our own reader and
     compares every file against what was intended: byte-identical to the original for
     untouched files, byte-identical to the patched copy for files that were edited.

usage: cpk_build.py <original.cpk> <repack_dir> <output.cpk> <cpkmakec.exe>
                     [--original-files original_files_dir] [--patched-files patched_dir]

repack_dir must already contain every ID#####.bin the original had (originals overlaid
with patched copies) -- stage it yourself, e.g.:
    robocopy original_files repack_dir *.bin /E
    robocopy patched_files  repack_dir *.bin /E

--original-files/--patched-files are only needed to run the validation step; omit both
to skip validation (not recommended).
"""
import os
import struct
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


# --- @UTF / ITOC / TOC parsing, shared by generation and validation ---

def read_utf_packet(data, offset):
    assert data[offset:offset + 4] == b'@UTF', \
        f"Not a @UTF packet at {offset}: {data[offset:offset + 8]!r}"
    table_size = struct.unpack('>I', data[offset + 4:offset + 8])[0]
    table_data = data[offset + 8:offset + 8 + table_size]
    return parse_utf_table(table_data)


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
        if col_storage in (0x30, 0x70):
            const_val, pos = read_raw_value(col_type, pos)
        columns.append({'type': col_type, 'storage': col_storage, 'name': name, 'const': const_val})

    rows = []
    row_pos = rows_offset
    for _ in range(num_rows):
        pos = row_pos
        row = {}
        for col in columns:
            if col['storage'] in (0x10, 0x00):
                row[col['name']] = 0
                continue
            if col['storage'] in (0x30, 0x70):
                row[col['name']] = col['const']
                continue
            val, pos = read_raw_value(col['type'], pos)
            row[col['name']] = val
        rows.append(row)
        row_pos = pos

    return {'columns': columns, 'rows': rows}


def decompress_crilayla(data):
    if data[0:8] != b'CRILAYLA':
        return data
    uncompressed_size = struct.unpack('<I', data[8:12])[0]
    uncompressed_header_offset = struct.unpack('<I', data[12:16])[0]
    result = bytearray(uncompressed_size + 0x100)
    result[0:0x100] = data[16 + uncompressed_header_offset:16 + uncompressed_header_offset + 0x100]
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
            out_bits = (out_bits << take) | ((bit_pool >> (bits_left - take)) & ((1 << take) - 1))
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


def get_all_ids(cpk_path):
    data = open(cpk_path, 'rb').read()
    header = read_utf_packet(data, 16)
    row = header['rows'][0]
    itoc_table = read_utf_packet(data, row['ItocOffset'] + 16)
    irow = itoc_table['rows'][0]
    table_l = parse_utf_table(irow['DataL'][8:])
    table_h = parse_utf_table(irow['DataH'][8:])
    ids = set()
    for r in table_l['rows']:
        ids.add(r['ID'])
    for r in table_h['rows']:
        ids.add(r['ID'])
    return sorted(ids)


def generate_control_csv(original_cpk, repack_dir, output_csv):
    """Control CSV format for cpkmakec.exe: dirname,filename,fileid,Uncompress,usrdir,""
    -- proven-working pattern, not fully documented (cpkmakec is closed-source)."""
    ids = get_all_ids(original_cpk)
    missing = []
    lines = []
    for fid in ids:
        fname = f'ID{fid:05d}.bin'
        if not os.path.isfile(os.path.join(repack_dir, fname)):
            missing.append(fname)
        lines.append(f'{fname},/{fname},{fid},Uncompress,/bin,""')

    with open(output_csv, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(lines) + '\n')

    if missing:
        raise SystemExit(
            f"ERROR: {len(missing)} files the original archive needs are missing "
            f"from {repack_dir}, starting with {missing[:10]}. Every ID must be "
            f"present (originals + patched overlay) before packing.")
    return len(ids)


def run_cpkmakec(cpkmakec_exe, control_csv, repack_dir, output_cpk):
    # subprocess.run's cwd= only changes the CHILD's working directory -- any
    # relative path in the argument list still gets resolved against it, not
    # against the cwd this function was called from, so everything below must
    # be made absolute first.
    cpkmakec_exe = os.path.abspath(cpkmakec_exe)
    control_csv = os.path.abspath(control_csv)
    repack_dir = os.path.abspath(repack_dir)
    output_cpk = os.path.abspath(output_cpk)

    if os.path.exists(output_cpk):
        os.remove(output_cpk)
    subprocess.run([
        cpkmakec_exe, control_csv, os.path.basename(output_cpk),
        f'-dir={repack_dir}\\', '-align=2048', '-mode=ID', '-forcecompress',
        '-noerrorstop',
    ], check=True, cwd=os.path.dirname(output_cpk) or '.')

    # cpkmakec resolves a bare output name against -dir, so recover it if it
    # landed inside the staging folder instead of next to the control CSV.
    if not os.path.exists(output_cpk):
        staged = os.path.join(repack_dir, os.path.basename(output_cpk))
        if os.path.exists(staged):
            os.replace(staged, output_cpk)
    if not os.path.exists(output_cpk):
        raise SystemExit(f"ERROR: cpkmakec did not produce {output_cpk}.")


def extract_all(cpk_path):
    data = open(cpk_path, 'rb').read()
    if data[:4] != b'CPK ':
        raise SystemExit(f"ERROR: {cpk_path} doesn't start with 'CPK ' -- not a valid CPK file.")
    header = read_utf_packet(data, 16)
    row = header['rows'][0]
    toc_offset = row['TocOffset']
    itoc_offset = row['ItocOffset']
    result = {}

    if toc_offset:
        toc_table = read_utf_packet(data, toc_offset + 16)
        base = toc_offset if toc_offset < row['ContentOffset'] else row['ContentOffset']
        for r in toc_table['rows']:
            fid = r['ID']
            file_offset = base + r['FileOffset']
            raw = data[file_offset:file_offset + r['FileSize']]
            result[fid] = decompress_crilayla(raw) if raw[:8] == b'CRILAYLA' else raw
        return result

    if itoc_offset:
        content_offset = row['ContentOffset']
        align = row['Align']
        itoc_table = read_utf_packet(data, itoc_offset + 16)
        irow = itoc_table['rows'][0]
        table_l = parse_utf_table(irow['DataL'][8:])
        table_h = parse_utf_table(irow['DataH'][8:])
        entries = {}
        for r in table_l['rows']:
            entries[r['ID']] = r['FileSize']
        for r in table_h['rows']:
            entries[r['ID']] = r['FileSize']
        offset = content_offset
        for fid in sorted(entries.keys()):
            fsize = entries[fid]
            raw = data[offset:offset + fsize]
            result[fid] = decompress_crilayla(raw) if raw[:8] == b'CRILAYLA' else raw
            offset += ((fsize + align - 1) // align) * align
        return result

    raise SystemExit("ERROR: neither TocOffset nor ItocOffset is set -- can't read this CPK.")


def validate(new_cpk, original_dir, patched_dir):
    """Returns True (and prints [PASS]) if every file in new_cpk matches what was
    intended -- byte-identical to the original if untouched, byte-identical to the
    patched copy if it was supposed to be edited. Prints [FAIL] and details otherwise."""
    extracted = extract_all(new_cpk)
    original_files = {int(f[2:7]): f for f in os.listdir(original_dir) if f.startswith('ID') and f.endswith('.bin')}
    patched_files = {int(f[2:7]): f for f in os.listdir(patched_dir) if f.startswith('ID') and f.endswith('.bin')} \
        if os.path.isdir(patched_dir) else {}

    expected_ids = set(original_files.keys())
    got_ids = set(extracted.keys())
    missing = expected_ids - got_ids
    extra = got_ids - expected_ids

    mismatched_patched, mismatched_untouched = [], []
    ok_patched = ok_untouched = 0
    for fid in sorted(expected_ids & got_ids):
        new_content = extracted[fid]
        if fid in patched_files:
            expected = open(os.path.join(patched_dir, patched_files[fid]), 'rb').read()
            if new_content == expected:
                ok_patched += 1
            else:
                mismatched_patched.append(fid)
        else:
            expected = open(os.path.join(original_dir, original_files[fid]), 'rb').read()
            if new_content == expected:
                ok_untouched += 1
            else:
                mismatched_untouched.append(fid)

    print(f'[validate] untouched files matching original: {ok_untouched}')
    print(f'[validate] patched files matching intended patch: {ok_patched}')
    if missing:
        print(f'[FAIL] {len(missing)} file IDs missing from the new archive: {sorted(missing)[:20]}')
    if extra:
        print(f'[WARNING] {len(extra)} unexpected extra file IDs: {sorted(extra)[:20]}')
    if mismatched_untouched:
        print(f'[FAIL] {len(mismatched_untouched)} untouched files differ from the original '
              f'(should never happen): {mismatched_untouched[:20]}')
    if mismatched_patched:
        print(f"[FAIL] {len(mismatched_patched)} patched files don't match the intended patch: "
              f'{mismatched_patched[:20]}')

    ok = not (missing or mismatched_untouched or mismatched_patched)
    print('[PASS]' if ok else '[FAIL] do NOT ship this archive yet.')
    return ok


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 4:
        print(__doc__)
        sys.exit(1)
    original_cpk, repack_dir, output_cpk, cpkmakec_exe = args

    original_files_dir = None
    patched_dir = None
    if '--original-files' in sys.argv:
        original_files_dir = sys.argv[sys.argv.index('--original-files') + 1]
    if '--patched-files' in sys.argv:
        patched_dir = sys.argv[sys.argv.index('--patched-files') + 1]

    control_csv = output_cpk + '.control.csv'
    n = generate_control_csv(original_cpk, repack_dir, control_csv)
    print(f'[control] {n} file IDs -> {control_csv}')

    run_cpkmakec(cpkmakec_exe, control_csv, repack_dir, output_cpk)
    print(f'[build] {output_cpk}')

    if original_files_dir and patched_dir:
        ok = validate(output_cpk, original_files_dir, patched_dir)
        sys.exit(0 if ok else 1)
    else:
        print('[validate] skipped -- pass --original-files and --patched-files to verify')


if __name__ == '__main__':
    main()
