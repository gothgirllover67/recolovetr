"""Encode an RGBA image back into the BC3 blocks a GXT texture stores.

WHY THIS EXISTS

Most captions in this game are 8-bit palette images, which re-encode losslessly, and
that is what gxt_paint.py has been repainting all along. The rest are BC3, and without
an encoder they simply could not be translated: the Save button, the camera's Gyro and
Finder labels, the legal notice on the boot splash. bc3_peek.py could already read them.
This is the other half.

HOW BC3 STORES A 4x4 BLOCK, in sixteen bytes

  0..1   two alpha endpoints
  2..7   sixteen 3-bit alpha indices
  8..11  two RGB565 colour endpoints
  12..15 sixteen 2-bit colour indices

With a0 > a1 the alpha ramp has eight steps; with c0 > c1 the colour ramp has four.
Both are chosen that way here, which is the higher-quality mode and the one the game's
own textures use.

CHOOSING THE ENDPOINTS

Colour endpoints come from the ends of the block's principal axis, not from a per-channel
min and max: a red-on-blue block has the same per-channel bounds as a magenta-on-black
one, and treating them alike is what makes text edges muddy. The axis is found from the
covariance of the block's pixels, then every pixel is projected onto it.

Fully transparent pixels are excluded from that fit. In a caption most of the block is
transparent background whose colour is arbitrary, and letting it vote pulls the endpoints
away from the ink.

ROUND TRIP

encode(decode(x)) is not x -- BC3 is lossy by construction. What matters is that decoding
what this writes gives back something visually identical, and the self-test at the bottom
of this file checks exactly that against the game's own textures.

usage:  from bc3_encode import encode_bc3
        blocks = encode_bc3(rgba, swizzled)     # rgba: (h, w, 4) uint8
        python bc3_encode.py --selftest        # round-trip against real textures
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gxt_lib import swizzle_map


def _fit_alpha(a):
    """eight-step ramp between the block's alpha extremes"""
    lo, hi = int(a.min()), int(a.max())
    if hi == lo:
        return hi, lo, np.zeros(16, np.uint8)
    a0, a1 = hi, lo                      # a0 > a1 selects the eight-value ramp
    ramp = np.array([a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)],
                    np.int32)
    idx = np.abs(a.astype(np.int32)[:, None] - ramp[None, :]).argmin(axis=1)
    return a0, a1, idx.astype(np.uint8)


def _to565(c):
    r, g, b = [int(round(v)) for v in c]
    r = min(255, max(0, r)); g = min(255, max(0, g)); b = min(255, max(0, b))
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def _from565(v):
    return np.array([((v >> 11) & 31) * 255 // 31,
                     ((v >> 5) & 63) * 255 // 63,
                     (v & 31) * 255 // 31], np.int32)


def _fit_colour(rgb, opaque):
    """endpoints from the ends of the block's principal axis"""
    pts = rgb[opaque] if opaque.any() else rgb
    if len(pts) == 0:
        return 0, 0, np.zeros(16, np.uint8)
    mean = pts.mean(axis=0)
    centred = pts - mean
    if len(pts) > 1:
        # principal axis; fall back to the grey axis when the block is flat
        cov = centred.T @ centred
        w, v = np.linalg.eigh(cov)
        axis = v[:, -1]
        if not np.isfinite(axis).all() or np.allclose(axis, 0):
            axis = np.array([1.0, 1.0, 1.0])
    else:
        axis = np.array([1.0, 1.0, 1.0])

    t = centred @ axis
    lo, hi = mean + axis * t.min(), mean + axis * t.max()

    c0, c1 = _to565(hi), _to565(lo)
    if c0 == c1:
        # a flat block still needs c0 > c1 to stay in four-colour mode
        c1 = max(0, c0 - 1)
    if c0 < c1:
        c0, c1 = c1, c0

    p0, p1 = _from565(c0), _from565(c1)
    palette = np.stack([p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3])
    d = ((rgb.astype(np.int32)[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
    return c0, c1, d.argmin(axis=1).astype(np.uint8)


def encode_block(px):
    """px: (16, 4) uint8 in row-major order within the block -> 16 bytes"""
    a = px[:, 3]
    rgb = px[:, :3]
    opaque = a > 8

    a0, a1, aidx = _fit_alpha(a)
    abits = 0
    for i, v in enumerate(aidx):
        abits |= int(v) << (3 * i)

    c0, c1, cidx = _fit_colour(rgb, opaque)
    cbits = 0
    for i, v in enumerate(cidx):
        cbits |= int(v) << (2 * i)

    return (bytes([a0, a1]) + abits.to_bytes(6, "little")
            + c0.to_bytes(2, "little") + c1.to_bytes(2, "little")
            + cbits.to_bytes(4, "little"))


def encode_bc3(rgba, swizzled):
    """rgba: (h, w, 4) uint8 -> the block stream, in the order the file stores it"""
    h, w = rgba.shape[:2]
    if w % 4 or h % 4:
        raise ValueError("BC3 needs both sides to be a multiple of 4, got %dx%d" % (w, h))
    bw, bh = w // 4, h // 4

    # bc3_peek reads stored block n into linear position order[n]; writing is the
    # inverse, so the same map is walked the same way.
    order = swizzle_map(bw, bh) if swizzled else np.arange(bw * bh)

    out = bytearray(bw * bh * 16)
    for n in range(bw * bh):
        dest = int(order[n])
        by, bx = divmod(dest, bw)
        if by >= bh or bx >= bw:
            continue
        block = rgba[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4].reshape(16, 4)
        out[n * 16:n * 16 + 16] = encode_block(block)
    return bytes(out)


def _selftest():
    """decode a real texture, re-encode it, decode again, and measure the drift"""
    import csv
    import importlib.util
    from gxt_lib import read_header

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location("bc3", os.path.join(root, "tools",
                                                                     "bc3_peek.py"))
    peek = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(peek)

    with open(os.path.join(root, "ui107_textures.tsv"), encoding="utf-8") as f:
        tex = [r for r in csv.DictReader(f, delimiter="\t") if r["format"] == "UBC3"]
    tex = [r for r in tex if 32 <= int(r["width"]) <= 512 and 16 <= int(r["height"]) <= 128]

    print("%-40s %8s %8s" % ("texture", "max err", "mean err"))
    for r in tex[:8]:
        p = os.path.join(root, "ui107", "files", r["file_id"] + ".bin")
        d = open(p, "rb").read()
        info = read_header(d, int(r["gxt_offset"], 16))
        raw = d[info["data_offset"]:info["data_offset"] + info["data_size"]]
        first = peek.bc3(raw, info["width"], info["height"], info["swizzled"])
        again = encode_bc3(first, info["swizzled"])
        second = peek.bc3(again, info["width"], info["height"], info["swizzled"])
        err = np.abs(first.astype(np.int32) - second.astype(np.int32))
        print("%-40s %8d %8.2f" % (r["source_name"][:38] + "#" + r["gxt_index"],
                                   err.max(), err.mean()))
        if len(again) != len(raw):
            print("   SIZE MISMATCH: %d written, %d expected" % (len(again), len(raw)))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        print(__doc__)
