# Reco Love: Gold Beach English Fan Translation Patch v. 0.9

An unofficial English translation for *Reco Love: Gold Beach* on PS Vita, game
version **1.07** and 4 story DLC. Please note that you need the updated
version of the game. The script is MTL with Sugoi-14B-Ultra-HF with some edits.
I think the result, despite the byte-lenght limit, is fine for what it is:
70% of the script is ok with small stuff like messed up pronouns (it would
take too much time to edit 80k lines of script for such details, however, the tools
to pack your own translation are provided here, so feel free to do so), 15% of
a bit strange lines which meaning you kinda guess and 15% of harder to guess lines.
The text is easy enough though, it's not some chuunibyou writing, just everyday stuff. 

I've played through the game once. Some of the signs look a bit messy and some of
the lines are not alligned properly, but the game is fully beatable with the patch,
I've spent quite some time ironing out problems and mistakes. I plan on at least
fixing the DLC scripts which I still saw some things to fix and adding the translation
of the menu lines for the story DLCs. The end result at this point I think is worse
than an offical Japanese game translation, but better than some of the indie game
translations on Steam. 

Vita3k does not show the character models in the VN segments, but runs the game
with the patch, on Vita you need the rePatch plugin to make it work.

This is a fan translation patch, not a copy of the game. **This repository ships
no game files at all** -- only translation text, xdelta patches (which only make
sense applied to a copy you already have), and the tools to build or apply them
against your own legally-owned copy. 

## Status

| Layer | Coverage |
|---|---|
| ADV script (dialogue) | ~100% |
| Table.cpk (UI text: hints, names, filters, pose list) | 3642 of 3647 strings |
| eboot (menus, system text) | 613 of 615 strings |
| UI.cpk captions (baked into textures) | ~90% (probably missed some) |
| Story DLC script (4 routes: Uchima, Mana, Yuina, Isuzu) | ~100% but rough |
| Story DLC Table.cpk (event/item titles) | **not translated** ~250 rows across 4 DLC |

The few rows/strings left in Japanese in the base game are deliberate: junk
records the extractor picks up alongside real text, a name-entry placeholder,
and one string whose on-screen slot is too small for any English word to fit.

## Two ways to install

- **Just want to play?** Use `tools/player/`, it patches your own game files
  directly with the xdelta diffs in `patches/`. Start at [Playing](#playing).
- **Want to rebuild, retarget to a new game version, or make your own
  translation?** Use `tools/dev/`, the full extract/patch/pack pipeline this
  release was built with. Start at [Rebuilding / making your own translation](#rebuilding--making-your-own-translation).

Both need the same starting point: your own decrypted copy of the game (see
[Getting your own decrypted files](#getting-your-own-decrypted-files-and-recogbin)).

## Legal

*Reco Love: Gold Beach* is a commercial visual novel. This project does not
distribute the game, any of its assets, or any decrypted/decompiled copy of its
code -- doing so would infringe the original publisher's copyright and this
project won't do it. What's in this repository is:

- **Translation text** (`translation/`) -- Japanese source strings paired with
  their English translation, keyed by file and byte offset. Comparable to a
  diff: it only makes sense applied on top of a copy of the game you already
  have, and by itself doesn't run or reproduce the game.
- **xdelta patches** (`patches/`) -- binary diffs between the stock archives
  and this translation's build of them. Same idea as any ROM-hacking patch:
  useless without your own copy of the original to apply it to.
- **Tools** (`tools/`) -- scripts that read files *you* extract from *your
  own* legally-installed, decrypted copy of the game, and write the
  translation into them (or apply/generate the patches above). Nothing here
  downloads, cracks, or decrypts a copy you don't already have the keys to.

**You need to own the game.** Every tool here only works against a decrypted
install that already exists on your machine because you bought and installed
the game yourself.

## Getting your own decrypted files and work.bin

The tools need plaintext files, not the PFS-encrypted ones a PKG installs. Two
ways to get them, both starting from a copy of the game you own:

- **Vita3K.** Install the game and the 1.07 update in Vita3K; it decrypts on
  install. The decrypted install then sits under Vita3K's
  `ux0/app/PCSG00782/` folder.
- **A jailbroken/modded Vita.** Same idea: the console decrypts the app on
  install, and you can pull `ux0:app/PCSG00782/` off the memory card in VitaShell
  with "OpenDecrypted:.

`work.bin` is only needed for `tools/dev/` (rebuilding).

## Playing

[DeltaPatcher](https://github.com/marco-calautti/DeltaPatcher)
is a free, cross-platform GUI built on the same xdelta3 library.
Apply each file in `patches/` to the matching stock file yourself:

| Patch | Apply to | Produces |
|---|---|---|
| `patches/eboot.xdelta` | your `eboot.bin` | translated `eboot.bin` |
| `patches/script.xdelta` | your `media/cpk/Script.cpk` | translated `Script.cpk` |
| `patches/table.xdelta` | your `media/cpk/Table.cpk` | translated `Table.cpk` |
| `patches/ui.xdelta` | your `media/cpk/UI.cpk` | translated `UI.cpk` |

Either way, the result is four files:

```
eboot.bin
media/cpk/Script.cpk
media/cpk/Table.cpk
media/cpk/UI.cpk
```

Copy these over your own decrypted install in Vita3k or to rePatch/PCSG00782 
folder.

A patch that doesn't apply cleanly (xdelta3 reports a checksum mismatch on the
source file) almost always means your copy isn't on version 1.07 -- update
first.

## Rebuilding / making your own translation

The full pipeline `tools/dev/` was built with -- also how the xdelta patches in
`patches/` were generated in the first place.

### Requirements

- Python 3.8+, `pip install -r requirements.txt` (numpy, Pillow, pycryptodome)
- **Windows, with Segoe UI Semibold available** (ships with Windows 10/11 at
  `C:/Windows/Fonts/seguisb.ttf`). Step 2's caption repainting renders text
  with this font specifically -- every caption's box and size in
  `translation/ui_captions.tsv` was measured against its exact metrics. Not on
  Windows, or missing that font? Set the `RECOLOVE_FONT` environment variable
  to a `.ttf`/`.otf` you do have; step 2 writes `work/patched/ui/preview.png`,
  a contact sheet of every repainted caption -- check it, since a different
  font can shift text enough to clip against neighbouring artwork.
- Your own `work.bin` for PCSG00782 (see above)
- Your own copy of `cpkmakec.exe`, CRI Middleware's CPK archive tool. It's
  proprietary and not included here -- search "CRI File System Tools" (any
  recent version works; this game's archives are the plain ITOC layout every
  version has supported for years). Widely used across CRI-engine game
  modding, not specific to this project.
- `xdelta3` -- only if you're regenerating `patches/` with step 4.

### Usage

Four steps, in order, each reading the previous step's output:

```
pip install -r requirements.txt

python tools/dev/1_extract_resources.py <decrypted_install_dir> <recog.bin> work/extracted
python tools/dev/2_apply_translation.py work/extracted work/patched
python tools/dev/3_build_patch.py <decrypted_install_dir> work/extracted work/patched work/output <cpkmakec.exe>
python tools/dev/4_build_xdelta_release.py <decrypted_install_dir> work/output   # optional, regenerates patches/
```

(Or edit the paths at the top of the matching `.bat` file in `tools/dev/` and
double-click it.)

Step 3 prints `[PASS]` for each of Script.cpk, Table.cpk and UI.cpk -- it
re-extracts what it just built with an independent reader and checks every
file against what was intended, byte for byte. Don't install a patch where any
of the three didn't say `[PASS]`.

Step 3's output lands in `work/output/`, in the same four-file layout
described in [Playing](#playing) above -- install it the same way.

### Using your own translation

Step 2 defaults to the English translation in `translation/`, but nothing
about steps 1, 3 or 4 is English-specific. To translate into a different
language, fix a line you don't like, or fork this into a different project
entirely: make a folder with the same four files and the same columns
(documented at the top of `tools/dev/2_apply_translation.py`), then run

```
python tools/dev/2_apply_translation.py work/extracted work/patched --translation-dir path/to/your/translation
```

`translation/script.csv` and `translation/table.tsv` both carry the original
Japanese alongside the English, specifically so a translation can be re-keyed
by matching text instead of trusting offsets that shift between game versions.

## DLC

The four story DLC (Uchima Yuko, Mana, Yuina, Isuzu Kokomi) each ship as their
own content ID under `addcont/PCSG00782/`, with their own `Script.cpk` and
`Table.cpk`. `translation/dlc/` holds one subfolder per content ID
with that DLC's own `script.csv` and
`table.tsv`, same column layout as the base game's.

Dev-pipeline:

```
python tools/dev/5_build_dlc.py <dlc_addcont_dir> work <cpkmakec.exe>
```

`<dlc_addcont_dir>` is the folder that directly contains one subfolder per
content ID (Vita3K's `ux0/addcont/PCSG00782/`, or the equivalent pulled off a
jailbroken Vita) -- each subfolder needs `media/cpk/Script.cpk` and
`media/cpk/Table.cpk` from your own decrypted, installed copy of that DLC.
Add specific content IDs as extra arguments to build only those (e.g. `...
RECOLOVE00000006`); omit them to build every DLC `translation/dlc/` covers.

This only touches `Script.cpk` and `Table.cpk` inside each DLC. `UI.cpk` is
skipped deliberately -- each one is a 15KB manifest plus a single fully-opaque
128x128 texture (route thumbnail art, not a caption; real captions in this
game are roughly half fully-transparent) and two 8x8 dummies. `CharaModel.cpk`,
`CharaMotion.cpk`, `CharaTex.cpk` and `Common.cpk` carry no text at all (3D
models, motion data, shared assets) -- this script never touches them, so your
own copies of those files (and of `UI.cpk`) go in the DLC folder unchanged.

Output lands in `<work>/dlc_output/<content_id>/media/cpk/Script.cpk` and
`Table.cpk` -- copy those two files over the matching DLC folder on your own
install, same as the base game's four files.

Table.cpk translation for the DLC (event/item titles, ~250 rows across all
four) hasn't been done yet -- `translation/dlc/*/table.tsv` currently has the
Japanese source with every `en_text` blank, which this script's patcher
correctly treats as "nothing to change here" rather than blanking anything
out. The DLC still builds and installs fine without it; those specific titles
just stay in Japanese until someone fills that file in.

The xdelta patches for DLC are not final, I plan on returning to fix them.
However, they are playable. You need to put the whole decrypted DLC with
the swapped Script.cpk file into reAddcont/PCSG00782/. Or just swap
the files in Vita3l's DLC folder.

## How tools work

- `tools/lib/cpk_extract.py` -- unpacks a CPK archive (decompressing CRILAYLA
  as needed) into one file per internal ID.
- `tools/lib/patch_text.py` -- writes translated text into an extracted file at
  a byte offset, measuring the real available room by scanning for the zero
  padding that follows the original string rather than trusting a stale length
  figure.
- `tools/lib/gxt_paint.py` (+ `gxt_lib.py`, `gxt_index.py`, `bc3_*.py`) --
  finds and repaints the GXT texture blocks that hold on-screen captions,
  keeping every texture's exact original byte size.
- `tools/lib/eboot_patch.py` -- writes translated strings into the decrypted
  eboot ELF by virtual address.
- `tools/lib/sceutils/self2elf.py` -- decrypts a SELF (the format every Vita
  executable ships in) into a plain ELF, given your`work.bin`.
- `tools/lib/cpk_build.py` -- regenerates the control file `cpkmakec.exe`
  needs from the original archive's own file-ID list, runs it, and validates
  the result independently.
- `tools/bin/vita-make-fself.exe` -- wraps the patched ELF back into a "fake
  self" (the unsigned executable format a jailbroken Vita or Vita3K runs
  directly; no NPDRM signing needed).
- `tools/lib/xdelta_patch.py` -- thin wrapper around the `xdelta3` CLI, shared
  by `tools/dev/4_build_xdelta_release.py` (maintainer: build the patches) and
  `tools/player/apply_xdelta_patch.py` (player: apply them).

`patches/` works the way it does specifically so the player path never needs
`sceutils`, `work.bin`, or `cpkmakec.exe`: each patch is diffed against the
**stock, still-encrypted** `eboot.bin` and the **stock, unmodified** `.cpk`
archives, not against any decrypted intermediate. xdelta3 doesn't care what
produced the "modified" side of a diff -- only that the file you apply it to
is byte-identical to the "original" side, which it will be for anyone on the
same game version.


## Credits

- `tools/lib/sceutils/` is TeamMolecule's `sceutils`, MIT licensed --
  **except `keys.py`**, which isn't from that project at all; see
  [A note on tools/lib/sceutils/keys.py](#a-note-on-toolslibsceutilskeyspy)
  above.
- `tools/bin/vita-make-fself.exe`, `libvita-export.dll`, `libvita-import.dll`
  and `libvita-yaml.dll` are built from the MIT-licensed VitaSDK project.
  `libwinpthread-1.dll` alongside them is not VitaSDK -- it's the MinGW-w64
  runtime's winpthreads library (MIT-style), pulled in because these binaries
  were built with MinGW.
- xdelta3 (used to build and apply `patches/`) and DeltaPatcher (a GUI front
  end for it) are separate open-source projects, not included here.

## License

The tools and translation text in this repository are MIT licensed -- see
`LICENSE`. This does not extend to *Reco Love: Gold Beach* itself, and
`tools/lib/sceutils/keys.py` has its own, murkier provenance -- see
[A note on tools/lib/sceutils/keys.py](#a-note-on-toolslibsceutilskeyspy).
