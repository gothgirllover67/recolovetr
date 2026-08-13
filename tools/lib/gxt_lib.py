"""Read and write the P8 textures used by Reco Love's UI.

Format, as confirmed against the real data:
  GXT header, then per-texture: width*height bytes of palette indices followed by a
  256-entry palette. Palette entries are stored B,G,R,A. Pixels are in Morton (swizzled)
  order when the texture's type field is 0.

Because the pixel count and the palette size are both fixed by the dimensions, a
repainted texture re-encodes to exactly the same byte length and can be written back
over the original inside its container -- no offsets move, so the .lac never changes
size and neither does anything downstream of it.

The swizzle map is built with numpy and cached per (width, height): the same handful
of shapes repeat across thousands of textures, so this turns the whole archive from
minutes of Python loops into a couple of seconds.
"""
import struct

import numpy as np

BASE_P8 = 0x95000000
BASE_UBC3 = 0x87000000

_maps = {}


def _compact1by1(x):
    x = x & 0x55555555
    x = (x ^ (x >> 1)) & 0x33333333
    x = (x ^ (x >> 2)) & 0x0F0F0F0F
    x = (x ^ (x >> 4)) & 0x00FF00FF
    x = (x ^ (x >> 8)) & 0x0000FFFF
    return x


def swizzle_map(width, height):
    """linear index -> morton index, so linear[map] == morton_order_pixels"""
    key = (width, height)
    if key in _maps:
        return _maps[key]

    i = np.arange(width * height, dtype=np.int64)
    mn = min(width, height)
    k = mn.bit_length() - 1
    mx = _compact1by1(i)
    my = _compact1by1(i >> 1)
    high = (i >> (2 * k)) << (2 * k)
    if height < width:
        j = high | ((my & (mn - 1)) << k) | (mx & (mn - 1))
        x, y = j // height, j % height
    else:
        j = high | ((mx & (mn - 1)) << k) | (my & (mn - 1))
        y, x = j // width, j % width
    linear = y * width + x           # for morton position i, the linear position
    _maps[key] = linear
    return linear


def unswizzle(buf, width, height):
    src = np.frombuffer(buf, dtype=np.uint8, count=width * height)
    out = np.empty(width * height, dtype=np.uint8)
    out[swizzle_map(width, height)] = src
    return out.reshape(height, width)


def swizzle(arr, width, height):
    flat = np.ascontiguousarray(arr).reshape(-1)
    return flat[swizzle_map(width, height)].tobytes()


def read_header(data, gxt_offset):
    o = gxt_offset
    magic, ver, num_tex, data_off, data_size, n_p4, n_p8, _ = \
        struct.unpack("<8I", data[o:o + 32])
    tex_off, tex_size, pal_idx, flags, tex_type, tex_fmt, w, h, mips, _ = \
        struct.unpack("<6I2H2H", data[o + 32:o + 64])
    return {
        "data_offset": o + tex_off,
        "data_size": tex_size,
        "palette_offset": o + tex_off + tex_size,
        "format": tex_fmt & 0xFF000000,
        "swizzled": tex_type == 0,
        "width": w,
        "height": h,
    }


def decode_p8(data, info):
    """-> (H, W) index array, (256, 4) RGBA palette"""
    w, h = info["width"], info["height"]
    px = data[info["data_offset"]:info["data_offset"] + w * h]
    pal_raw = data[info["palette_offset"]:info["palette_offset"] + 1024]
    pal = np.frombuffer(pal_raw, dtype=np.uint8).reshape(256, 4)
    rgba = pal[:, [2, 1, 0, 3]].copy()          # BGRA -> RGBA
    idx = unswizzle(px, w, h) if info["swizzled"] else \
        np.frombuffer(px, dtype=np.uint8).reshape(h, w).copy()
    return idx, rgba


def to_rgba(idx, palette):
    return palette[idx]


def encode_p8(data, info, idx, palette):
    """write indices + palette back into `data` (a bytearray) at the same offsets"""
    w, h = info["width"], info["height"]
    px = swizzle(idx, w, h) if info["swizzled"] else np.ascontiguousarray(idx).tobytes()
    assert len(px) == w * h, "pixel buffer changed size"
    data[info["data_offset"]:info["data_offset"] + w * h] = px
    bgra = palette[:, [2, 1, 0, 3]].astype(np.uint8)
    data[info["palette_offset"]:info["palette_offset"] + 1024] = bgra.tobytes()
