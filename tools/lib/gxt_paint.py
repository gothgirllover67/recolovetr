"""Repaint a P8 label texture with English text, in place.

The labels are white glyphs with a dark navy outline fading out through the alpha
channel -- so the replacement is rendered the same way and quantised into a palette
built for exactly that: 16 blend steps from navy to white, 16 alpha steps each. That
mirrors how the original palettes are laid out (a navy ramp and a white ramp) and keeps
the result visually indistinguishable in style.

Dimensions never change, so the encoded texture is byte-for-byte the same length and is
written back over the original inside its .lac container.

The same label image is often stored in several places -- every pause-menu caption
exists both as a standalone .tex and inside 90_common_menu01_01menu.lac. Painting one
and leaving the others would put two languages on the same screen depending on which
copy a given view loads, so each repaint is propagated to every texture whose ORIGINAL
image was byte-identical. Duplicates are found by hashing decoded pixels, not by name.

Some textures are composites -- the "Main Menu" header carries an orb to the left of
its caption -- so an optional 4th column gives the text box as "x0,y0,x1,y1". Only that
rectangle is redrawn; everything outside it is copied from the original, which keeps
artwork that happens to share the texture intact. Without a box the whole texture is
treated as the caption.

Input is a TSV: source_name, gxt_index, english_text[, box][, max_width][, mode]
[, rotation][, align]. `align` is left/right/centre and overrides the guess made from
where the original ink sat, for captions that fill their texture edge to edge.
mode 'overlay' heals artwork under a white caption; 'plate' does the same for a
dark caption on a coloured button; 'plain' redraws inside the box with no outline;
'fill' wipes a caption off a flat plate by repainting the plate in its own colour.
usage: gxt_paint.py <index.tsv> <labels.tsv> <files_dir> <out_dir> [--preview sheet.png]
"""
import csv
import hashlib
import math
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gxt_lib import read_header, decode_p8, encode_p8, to_rgba, BASE_P8, BASE_UBC3
from bc3_encode import encode_bc3
import bc3_peek


def read_rgba(buf, info):
    """pixels of a texture, whichever of the two formats it is stored in"""
    if info["format"] == BASE_UBC3:
        raw = buf[info["data_offset"]:info["data_offset"] + info["data_size"]]
        return bc3_peek.bc3(bytes(raw), info["width"], info["height"], info["swizzled"])
    return to_rgba(*decode_p8(buf, info))


def write_rgba(buf, info, rgba):
    """put pixels back in place, same bytes long, so nothing in the container moves"""
    blocks = encode_bc3(rgba, info["swizzled"])
    if len(blocks) != info["data_size"]:
        raise ValueError("BC3 re-encode is %d bytes, slot holds %d"
                         % (len(blocks), info["data_size"]))
    buf[info["data_offset"]:info["data_offset"] + len(blocks)] = blocks

FONT_PATH = os.environ.get("RECOLOVE_FONT", "C:/Windows/Fonts/seguisb.ttf")
# Segoe UI Semibold -- ships with Windows, not redistributed here (only referenced
# by path, the same way any Windows application uses an installed system font).
# Every caption in this game's shipped translation was measured/fitted against this
# specific font's metrics, so a different font WILL shift where the halo lands and can
# clip against neighbouring artwork. Override with the RECOLOVE_FONT env var if you're
# not on Windows or don't have this font, but expect to re-check captions visually.
if not os.path.isfile(FONT_PATH):
    raise SystemExit(
        f"ERROR: font not found at {FONT_PATH}\n"
        f"gxt_paint.py needs Segoe UI Semibold (ships with Windows 10/11 at this "
        f"path) to render captions -- every box/size in ui_captions.tsv was measured "
        f"against its specific metrics. If you're not on Windows, or don't have this "
        f"font, set the RECOLOVE_FONT environment variable to a .ttf/.otf you do have "
        f"and re-check the preview.png this script writes -- captions may need their "
        f"boxes re-measured for a different font.")
INK = np.array([255, 255, 255], dtype=np.float64)
EDGE = np.array([19, 28, 55], dtype=np.float64)


def build_palette(ink=INK, edge=EDGE):
    """16 edge->ink blend steps x 16 alpha steps = 256 entries"""
    pal = np.zeros((256, 4), dtype=np.uint8)
    for t in range(16):
        rgb = edge + (ink - edge) * (t / 15.0)
        for a in range(16):
            pal[t * 16 + a, :3] = np.round(rgb)
            pal[t * 16 + a, 3] = round(a * 255 / 15)
    return pal


PALETTE = build_palette()


def sample_colours(rgba):
    """pick the caption's own ink and outline colours out of the original

    Captions are not all white: the status screen writes in orange, "Remedial" in a
    yellow gradient. Rendering everything white would be visibly wrong, so the two
    dominant colours of the existing glyphs are reused -- the brightest frequent one
    as the ink, the darkest frequent one as the outline.
    """
    a = rgba[:, :, 3]
    rgb = rgba[:, :, :3].astype(np.int32)
    solid = a > 200
    if solid.sum() < 20:
        return INK, EDGE
    cols, counts = np.unique(rgb[solid], axis=0, return_counts=True)
    common = cols[counts >= max(3, counts.max() // 20)]
    lum = common.sum(axis=1)
    ink = common[lum.argmax()].astype(np.float64)

    fringe = (a > 60) & (rgb.sum(axis=2) < lum.max() * 0.55)
    if fringe.sum() >= 20:
        fcols, fcounts = np.unique(rgb[fringe], axis=0, return_counts=True)
        edge = fcols[fcounts.argmax()].astype(np.float64)
    else:
        edge = ink * 0.12
    return ink, edge


def quantise(rgba, ink=INK, edge=EDGE):
    """RGBA image -> palette indices for PALETTE"""
    arr = rgba.astype(np.float64)
    a = arr[:, :, 3]
    rgb = arr[:, :, :3]
    # how far each pixel sits along the navy->white axis
    axis = ink - edge
    denom = float(axis @ axis) or 1.0
    t = ((rgb - edge) @ axis) / denom
    t = np.clip(t, 0.0, 1.0)
    ti = np.round(t * 15).astype(np.int64)
    ai = np.round(a / 255.0 * 15).astype(np.int64)
    idx = ti * 16 + ai
    idx[a == 0] = 0                      # fully transparent -> one canonical entry
    return idx.astype(np.uint8)


def quantise_general(rgba):
    """RGBA -> (indices, palette) for an image that also carries artwork.

    A composite keeps real colours outside the caption, so the fixed navy/white ramp
    cannot represent it. Exact palettes are used whenever the result fits in 256
    colours -- which it usually does, since the preserved pixels come from a 256-entry
    palette to begin with -- and only otherwise are colours merged.
    """
    flat = rgba.reshape(-1, 4)
    colours, inverse, counts = np.unique(flat, axis=0, return_inverse=True,
                                         return_counts=True)
    if len(colours) <= 256:
        pal = np.zeros((256, 4), dtype=np.uint8)
        pal[:len(colours)] = colours
        return inverse.astype(np.uint8).reshape(rgba.shape[:2]), pal

    keep = colours[np.argsort(-counts)[:256]].astype(np.int32)
    # nearest kept colour for every distinct colour, then remap through `inverse`
    src = colours.astype(np.int32)
    best = np.empty(len(src), dtype=np.int64)
    step = 4096
    for s in range(0, len(src), step):
        chunk = src[s:s + step]
        d = ((chunk[:, None, :] - keep[None, :, :]) ** 2).sum(axis=2)
        best[s:s + step] = d.argmin(axis=1)
    pal = np.zeros((256, 4), dtype=np.uint8)
    pal[:len(keep)] = keep
    return best[inverse].astype(np.uint8).reshape(rgba.shape[:2]), pal


def _dilate(mask, radius):
    out = mask.copy()
    for _ in range(radius):
        g = out
        out = g.copy()
        out[1:, :] |= g[:-1, :]
        out[:-1, :] |= g[1:, :]
        out[:, 1:] |= g[:, :-1]
        out[:, :-1] |= g[:, 1:]
    return out


def text_mask(rgba):
    """the caption layer on an icon composite

    These icons are drawn at one flat alpha (135, 156 or 179 depending on the icon)
    and the caption is painted over them fully opaque and near-white, so the two
    separate cleanly on alpha and luminance -- there is no dark outline to key on.
    """
    al = rgba[:, :, 3]
    lum = rgba[:, :, :3].mean(axis=2)
    return _dilate((al > 240) & (lum > 235), 2)


def plate_mask(rgba, thresh=55):
    """the caption on a coloured button plate, whichever way round the contrast runs

    text_mask keys on "bright and opaque", which only finds white glyphs. Setting
    buttons are the opposite: a dark caption on a yellow or blue plate, so brightness
    tells you nothing. What does hold either way is that the plate is a smooth field
    and the caption is thin strokes -- a median filter wide enough to swallow the
    strokes leaves the plate behind, and whatever differs from it is the text.
    """
    opaque = rgba[:, :, 3] > 128
    # the plate's own rim is a sharp edge and would read as "differs from background",
    # so pull the search area in from the border before comparing
    inner = ~_dilate(~opaque, 4)
    img = Image.fromarray(rgba[:, :, :3], "RGB")
    bg = img.filter(ImageFilter.MedianFilter(9)).filter(ImageFilter.MedianFilter(9))
    diff = np.abs(np.asarray(img, dtype=np.int32)
                  - np.asarray(bg, dtype=np.int32)).sum(axis=2)
    return _dilate(inner & (diff > thresh), 2)


def inpaint(rgba, mask, rounds=64):
    """fill masked pixels from their unmasked neighbours, repeatedly"""
    out = rgba.astype(np.float64).copy()
    todo = mask.copy()
    for _ in range(rounds):
        if not todo.any():
            break
        known = ~todo
        acc = np.zeros_like(out)
        cnt = np.zeros(out.shape[:2])
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src = np.roll(np.roll(out, dy, axis=0), dx, axis=1)
            k = np.roll(np.roll(known, dy, axis=0), dx, axis=1)
            acc += src * k[:, :, None]
            cnt += k
        fillable = todo & (cnt > 0)
        if not fillable.any():
            break
        safe = np.where(cnt[:, :, None] > 0, cnt[:, :, None], 1)
        out[fillable] = (acc / safe)[fillable]
        todo &= ~fillable
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def render_plain(text, width, height, box, max_width=None):
    """white caption with no outline -- what the icon composites actually use"""
    x0, x1, y0, y1 = box
    target_h = max(8, y1 - y0 + 1)
    limit = max_width if max_width else (x1 - x0 + 1)
    centred = abs(((x0 + x1) / 2) - width / 2) <= width * 0.10

    def draw_at(size):
        font = ImageFont.truetype(FONT_PATH, size)
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        x = (width - (r - l)) // 2 - l if centred else x0 - l
        y = (y0 + y1) // 2 - (b - t) // 2 - t
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
        out = np.array(img)
        # Hard-edge the alpha instead of leaving PIL's antialiasing in. quantise_general
        # keeps at most 256 distinct (R,G,B,A) tuples for the whole composite, and an
        # antialiased glyph edge contributes dozens of near-duplicate "white at alpha
        # 103, 109, 110, 113..." entries that are each too rare individually to survive
        # that cut -- on a texture that already has a gradient-heavy icon eating most of
        # the budget, that silently drops the whole caption with no error anywhere. A
        # binary mask costs one flat colour+alpha pair instead.
        out[:, :, 3] = np.where(out[:, :, 3] > 100, 255, 0)
        return out

    size = target_h
    out = draw_at(size)
    while size > 8:
        ys, xs = np.nonzero(out[:, :, 3])
        if len(xs) == 0:
            break
        if (xs.max() - xs.min() + 1) <= limit:
            break
        size -= 1
        out = draw_at(size)
    return out


def render(text, width, height, box, max_width=None, ink=None, edge=None, align=None):
    """draw centred white text with a dark outline inside the original's text box

    max_width matters for framed buttons: the texture is wider than the frame drawn
    over it, so fitting to the texture lets a long English label spill past the button.
    The usable width is the widest ORIGINAL caption in the same set -- for the twelve
    personality buttons that is 170px out of a 256px texture.
    """
    x0, x1, y0, y1 = box
    target_h = max(8, y1 - y0 + 1)
    limit = max_width if max_width else width - 12
    ink = INK if ink is None else ink
    edge = EDGE if edge is None else edge
    ink_t = tuple(int(v) for v in ink) + (255,)
    edge_t = tuple(int(v) for v in edge) + (255,)

    # Keep the original alignment. Screen headers sit at the left edge of a wide
    # texture; centring those would slide the caption into the middle of the screen.
    # A caption whose box is centred within ~10% of the texture is treated as centred,
    # anything else keeps its left edge where the Japanese one started.
    # Keep whichever edge the original was anchored to. The button-hint strip right
    # aligns its captions against the button glyph that follows, so left aligning a
    # shorter English word there would pull it away from its icon.
    # The heuristic misreads a caption that happens to fill its texture: the Free Reco
    # Session name plates all hug the right edge, but the longest of them spans almost
    # the full width, so its box centre lands near the middle and it would be centred
    # while its neighbours stayed right. `align` overrides the guess for those cases.
    if align in ("centre", "center"):
        centred, right = True, False
    elif align == "right":
        centred, right = False, True
    elif align == "left":
        centred, right = False, False
    else:
        centred = abs(((x0 + x1) / 2) - width / 2) <= width * 0.10
        right = (not centred) and (width - 1 - x1) <= width * 0.10

    def draw_at(size):
        font = ImageFont.truetype(FONT_PATH, size)
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        l, t, r, b = draw.textbbox((0, 0), text, font=font, stroke_width=3)
        if centred:
            x = (width - (r - l)) // 2 - l
        elif right:
            x = x1 - (r - l) - l
        else:
            x = x0 - l
        # Centre on the ORIGINAL text box, not on the texture. Most captions sit in the
        # middle of their strip, so this changed nothing for them -- but the Free Reco
        # Session menu items carry their text in the top quarter of a 256x128 tile, and
        # centring on the texture dropped it 30px down the tile.
        y = (y0 + y1) // 2 - (b - t) // 2 - t
        draw.text((x, y), text, font=font, fill=ink_t,
                  stroke_width=3, stroke_fill=edge_t)

        # soft halo, matching the faded navy fringe on the originals
        halo = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(halo).text((x, y), text, font=font, fill=edge_t,
                                  stroke_width=4, stroke_fill=edge_t)
        halo = halo.filter(ImageFilter.GaussianBlur(2.0))
        return np.array(Image.alpha_composite(halo, img))

    # Fit against what is actually painted, not against the glyph metrics: the outline
    # and its blurred halo add roughly 14px of width that font.getbbox never reports,
    # which is exactly how long captions ended up spilling past their button frame.
    size = target_h
    out = draw_at(size)
    while size > 8:
        ys, xs = np.nonzero(out[:, :, 3])
        if len(xs) == 0:
            break
        if (xs.max() - xs.min() + 1) <= limit and (ys.max() - ys.min() + 1) <= height:
            break
        size -= 1
        out = draw_at(size)
    return out


def main():
    index_path, labels_path, files_dir, out_dir = sys.argv[1:5]
    preview = None
    if "--preview" in sys.argv:
        preview = sys.argv[sys.argv.index("--preview") + 1]

    index = {}
    all_p8 = []
    for r in csv.DictReader(open(index_path, encoding="utf-8"), delimiter="\t"):
        index[(r["source_name"], r["gxt_index"])] = r
        # UBC3 joins P8 here now that there is an encoder for it. Without one these
        # captions -- the Save button, the camera's Gyro and Finder labels -- simply
        # could not be translated.
        if r["format"] in ("P8", "UBC3"):
            all_p8.append(r)

    # group textures by the pixels they currently hold, so a repaint can follow copies
    raw = {}

    def buf_of(fid):
        if fid not in raw:
            raw[fid] = open(os.path.join(files_dir, fid + ".bin"), "rb").read()
        return raw[fid]

    groups = {}
    for r in all_p8:
        d = buf_of(r["file_id"])
        info = read_header(d, int(r["gxt_offset"], 16))
        h = hashlib.sha1(b"%d:%d:" % (info["width"], info["height"])
                         + read_rgba(d, info).tobytes()).hexdigest()
        groups.setdefault(h, []).append(r)

    labels = []
    with open(labels_path, encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3 or not parts[2].strip():
                continue
            box = None
            maxw = None
            if len(parts) > 3 and parts[3].strip():
                box = tuple(int(v) for v in parts[3].split(","))
            maxw = int(parts[4]) if len(parts) > 4 and parts[4].strip() else None
            mode = parts[5].strip() if len(parts) > 5 and parts[5].strip() else ""
            rot = float(parts[6]) if len(parts) > 6 and parts[6].strip() else 0.0
            align = parts[7].strip() if len(parts) > 7 and parts[7].strip() else None
            labels.append((parts[0], parts[1], parts[2], box, maxw, mode, rot, align))

    os.makedirs(out_dir, exist_ok=True)
    buffers = {}
    tiles = []
    done = 0
    for source_name, gxt_index, text, region, maxw, mode, rot, align in labels:
        key = (source_name, gxt_index)
        if key not in index:
            print("no such texture: %s #%s" % key)
            continue
        r = index[key]
        orig = buf_of(r["file_id"])
        info = read_header(orig, int(r["gxt_offset"], 16))
        orig_rgba = read_rgba(orig, info)

        # Edit whatever is already in the buffer, not the pristine file. A plate can
        # carry several captions -- the pause bar has five side by side -- and each is a
        # separate label row on the same texture; reading the original every time meant
        # only the last one survived.
        work = buffers.get(r["file_id"], orig)
        old_rgba = read_rgba(work, read_header(work, int(r["gxt_offset"], 16)))

        if mode == "fill":
            # A caption on a small flat plate. overlay and plate both heal by inpainting
            # from around the text, but here the text fills most of the plate, so the
            # heal drags in whatever is outside and the plate loses its colour. A flat
            # plate does not need reconstructing: every opaque pixel in the box is set to
            # the plate's own dominant colour, which erases the caption exactly.
            rx0, ry0, rx1, ry1 = region
            # Sample the plate colour from a band just OUTSIDE the box, not inside it.
            # Inside, the caption is usually the largest single colour -- white ink on a
            # blue button -- so the dominant colour came back white and the repaint left
            # a pale rectangle across the plate.
            pad = 4
            h_, w_ = old_rgba.shape[:2]
            oy0, oy1 = max(0, ry0 - pad), min(h_ - 1, ry1 + pad)
            ox0, ox1 = max(0, rx0 - pad), min(w_ - 1, rx1 + pad)
            ring = np.zeros((h_, w_), bool)
            ring[oy0:oy1 + 1, ox0:ox1 + 1] = True
            ring[ry0:ry1 + 1, rx0:rx1 + 1] = False
            ring &= old_rgba[:, :, 3] > 128
            if not ring.any():
                ring = np.zeros((h_, w_), bool)
                ring[ry0:ry1 + 1, rx0:rx1 + 1] = old_rgba[ry0:ry1 + 1,
                                                          rx0:rx1 + 1, 3] > 128
            cols, counts = np.unique(old_rgba[:, :, :3][ring], axis=0, return_counts=True)
            plate = cols[counts.argmax()]
            sub = old_rgba[ry0:ry1 + 1, rx0:rx1 + 1]
            opaque = sub[:, :, 3] > 128

            m = text_mask(old_rgba)
            keep = np.zeros_like(m)
            keep[ry0:ry1 + 1, rx0:rx1 + 1] = True
            m &= keep
            if not m.any():
                m = np.zeros_like(keep)
                m[ry0:ry1 + 1, rx0:rx1 + 1] = opaque

            # Wipe the box outright -- colour AND alpha. Setting only the opaque pixels
            # left the glyph outlines behind: they are drawn at an alpha below 128, so
            # "opaque" skipped them, and a half-transparent pixel in an otherwise solid
            # plate reads as a dark hole in the shape of the original character.
            healed = old_rgba.copy()
            healed[ry0:ry1 + 1, rx0:rx1 + 1, :3] = plate
            healed[ry0:ry1 + 1, rx0:rx1 + 1, 3] = 255

            ys, xs = np.nonzero(m)
            band = (int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()))
            ink, edge = sample_colours(old_rgba[ry0:ry1 + 1, rx0:rx1 + 1])
            painted = render(text, info["width"], info["height"], band, maxw,
                             ink, edge, align)
            rgba = np.array(Image.alpha_composite(
                Image.fromarray(healed, "RGBA"), Image.fromarray(painted, "RGBA")))
        elif mode in ("overlay", "plate"):
            # caption painted over artwork: lift it out, heal the picture, redraw
            m = plate_mask(old_rgba) if mode == "plate" else text_mask(old_rgba)
            if not m.any():
                # nothing separated out -- fall back to the opaque area so the caption
                # is still placed sensibly instead of crashing on an empty box
                print("  %s #%s: caption did not separate, using the opaque area"
                      % (source_name, gxt_index))
                m = (old_rgba[:, :, 3] > 128)
            if region:
                # a plate that also carries a button glyph: heal only inside the
                # caption's own rectangle so the glyph outside it survives untouched
                rx0, ry0, rx1, ry1 = region
                keep = np.zeros_like(m)
                keep[ry0:ry1 + 1, rx0:rx1 + 1] = True
                m &= keep
            ys, xs = np.nonzero(m)
            band = (int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()))
            healed = inpaint(old_rgba, m)
            if region:
                # a plate button: its caption has the usual outline. Sample colours
                # from inside the region only -- sampling the whole texture lets a
                # common border colour (a gold frame's maroon shadow, say) outvote the
                # caption's own ink and gives the text someone else's outline colour.
                rx0, ry0, rx1, ry1 = region
                ink, edge = sample_colours(old_rgba[ry0:ry1 + 1, rx0:rx1 + 1])
                painted = render(text, info["width"], info["height"], band, maxw, ink, edge, align)
            else:
                # icon composites carry plain white glyphs with no outline at all
                painted = render_plain(text, info["width"], info["height"], band, maxw)
            rgba = np.array(Image.alpha_composite(
                Image.fromarray(healed, "RGBA"), Image.fromarray(painted, "RGBA")))
        elif region:
            rx0, ry0, rx1, ry1 = region
            w, h = rx1 - rx0 + 1, ry1 - ry0 + 1
            sub = old_rgba[ry0:ry1 + 1, rx0:rx1 + 1, 3]
            ys, xs = np.nonzero(sub)
            box = (int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())) \
                if len(xs) else (0, w - 1, 0, h - 1)
            # mode 'plain' drops the outline. At the size of the controller legend's
            # 長押し labels the 3px stroke plus its halo closes the gaps between glyphs
            # and the caption reads as a dark pill; the originals have no outline at all.
            draw_fn = render_plain if mode == "plain" else render
            painted = draw_fn(text, w, h, box, maxw)
            rgba = old_rgba.copy()
            rgba[ry0:ry1 + 1, rx0:rx1 + 1] = painted
        else:
            alpha = old_rgba[:, :, 3]
            ys, xs = np.nonzero(alpha)
            box = (int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())) if len(xs) \
                else (0, info["width"] - 1, 0, info["height"] - 1)
            ink, edge = sample_colours(old_rgba)
            limit = maxw
            fit_box = box
            if rot:
                # The measured box is the tilted caption's bounding rectangle, which is
                # both wider and taller than the glyphs. Undo the rotation to recover
                # the real text extent, otherwise a short word gets rendered oversized
                # next to a long one on the same screen.
                th = math.radians(abs(rot))
                c, sn = math.cos(th), math.sin(th)
                det = c * c - sn * sn
                bw = box[1] - box[0] + 1
                bh = box[3] - box[2] + 1
                if det > 0.2:
                    tw = max(8, int((bw * c - bh * sn) / det))
                    thh = max(8, int((bh * c - bw * sn) / det))
                    cx = (box[0] + box[1]) // 2
                    cy = (box[2] + box[3]) // 2
                    fit_box = (cx - tw // 2, cx + tw // 2, cy - thh // 2, cy + thh // 2)
                    limit = tw
            rgba = render(text, info["width"], info["height"], fit_box, limit, ink, edge, align)
            if rot:
                cx = (box[0] + box[1]) / 2.0
                cy = (box[2] + box[3]) / 2.0
                rgba = np.array(Image.fromarray(rgba, "RGBA").rotate(
                    rot, resample=Image.BICUBIC, center=(cx, cy)))

        is_bc3 = r["format"] == "UBC3"
        if is_bc3:
            # BC3 keeps full colour per block, so there is no palette to fit and the
            # pixels go back as they are.
            new_idx = new_pal = None
        elif region or mode in ("overlay", "plate", "fill"):
            new_idx, new_pal = quantise_general(rgba)
        else:
            new_idx = quantise(rgba, ink, edge)
            new_pal = build_palette(ink, edge)

        # Group on the pristine pixels: `groups` was built from the untouched files, so
        # hashing the working copy would stop finding a caption's duplicates from the
        # second label onwards.
        h = hashlib.sha1(b"%d:%d:" % (info["width"], info["height"])
                         + orig_rgba.tobytes()).hexdigest()
        targets = groups.get(h, [r])
        for t in targets:
            fid = t["file_id"]
            if fid not in buffers:
                buffers[fid] = bytearray(buf_of(fid))
            tinfo = read_header(buffers[fid], int(t["gxt_offset"], 16))
            if is_bc3:
                write_rgba(buffers[fid], tinfo, rgba)
            else:
                encode_p8(buffers[fid], tinfo, new_idx, new_pal)
            done += 1
        if len(targets) > 1:
            print("  %s #%s -> %s (+%d copies)"
                  % (source_name, gxt_index, text, len(targets) - 1))
        if preview:
            shown = rgba if is_bc3 else to_rgba(new_idx, new_pal)
            tiles.append((Image.fromarray(shown, "RGBA"),
                          "%s #%s  %s" % (source_name, gxt_index, text)))

    for fid, buf in buffers.items():
        open(os.path.join(out_dir, fid + ".bin"), "wb").write(bytes(buf))

    print("repainted %d textures in %d files -> %s" % (done, len(buffers), out_dir))

    if preview and tiles:
        w = max(t[0].width for t in tiles) + 8
        h = sum(t[0].height + 18 for t in tiles) + 4
        sheet = Image.new("RGBA", (w, h), (28, 28, 38, 255))
        d = ImageDraw.Draw(sheet)
        y = 4
        for img, cap in tiles:
            d.text((4, y), cap, fill=(150, 170, 200, 255))
            y += 14
            sheet.alpha_composite(img, (4, y))
            y += img.height + 4
        sheet.convert("RGB").save(preview)
        print("preview -> %s" % preview)


if __name__ == "__main__":
    main()
