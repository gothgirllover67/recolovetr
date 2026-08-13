"""Decode a BC3 (DXT5) GXT texture just far enough to look at it.

The patch's own codec only handles P8, which is every texture that carries a caption.
The DLC UI archives hold BC3 instead, so this exists purely to answer "is there text on
it?" -- it decodes to PNG and stops. Nothing here writes textures back.

usage: bc3_peek.py <file.bin> <gxt_offset_hex> <out.png>
"""
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from gxt_lib import read_header, swizzle_map


def bc3(data, w, h, swizzled):
    """decode BC3 block data into an RGBA array"""
    out = np.zeros((h, w, 4), np.uint8)
    bw, bh = w // 4, h // 4

    # swizzle_map says where the i-th STORED element belongs in the linear image --
    # gxt_lib's unswizzle uses it as `out[map] = src`. Reading it the other way round,
    # as "which stored block goes here", scrambles the picture while leaving every
    # block's own colours correct, which is exactly how this looked before.
    order = swizzle_map(bw, bh) if swizzled else np.arange(bw * bh)

    for n in range(bw * bh):
        dest = int(order[n])
        by, bx = divmod(dest, bw)
        if by >= bh or bx >= bw:
            continue
        b = data[n * 16:n * 16 + 16]
        if len(b) < 16:
            break

        a0, a1 = b[0], b[1]
        abits = int.from_bytes(b[2:8], "little")
        alpha = [a0, a1]
        if a0 > a1:
            alpha += [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)]
        else:
            alpha += [((5 - k) * a0 + k * a1) // 5 for k in range(1, 5)] + [0, 255]

        c0, c1 = int.from_bytes(b[8:10], "little"), int.from_bytes(b[10:12], "little")

        def rgb(c):
            return (((c >> 11) & 31) * 255 // 31,
                    ((c >> 5) & 63) * 255 // 63,
                    (c & 31) * 255 // 31)

        p = [rgb(c0), rgb(c1)]
        p.append(tuple((2 * p[0][k] + p[1][k]) // 3 for k in range(3)))
        p.append(tuple((p[0][k] + 2 * p[1][k]) // 3 for k in range(3)))
        cbits = int.from_bytes(b[12:16], "little")

        for py in range(4):
            for px in range(4):
                j = py * 4 + px
                out[by * 4 + py, bx * 4 + px, :3] = p[(cbits >> (2 * j)) & 3]
                out[by * 4 + py, bx * 4 + px, 3] = alpha[(abits >> (3 * j)) & 7]
    return out


def decode(path, off, swizzled=None):
    d = open(path, "rb").read()
    info = read_header(d, off)
    w, h = info["width"], info["height"]
    raw = d[info["data_offset"]:info["data_offset"] + w * h]
    sw = info["swizzled"] if swizzled is None else swizzled
    return Image.fromarray(bc3(raw, w, h, sw), "RGBA")


if __name__ == "__main__":
    path, off, out_path = sys.argv[1], int(sys.argv[2], 16), sys.argv[3]
    img = decode(path, off)
    img.save(out_path)
    print("%dx%d -> %s" % (img.width, img.height, out_path))
