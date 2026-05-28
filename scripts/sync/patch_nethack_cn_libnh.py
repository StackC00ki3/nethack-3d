#!/usr/bin/env python3
"""Patch NetHack-cn libnh wasm helpers needed by the web client."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


CONFIG_GUARD_RE = r"^[ \t]*#[ \t]*define[ \t]+CONFIG_H\b[^\n]*\n"
CONFIG_TILE_PATCH = """
/* nethack-3d reads glyph_info.tileidx from the wasm runtime. */
#ifndef TILES_IN_GLYPHMAP
#define TILES_IN_GLYPHMAP
#endif
"""

C_MARKER = "void js_helpers_init();\nvoid js_constants_init();\nvoid js_globals_init();\n"
C_PATCH = """void js_helpers_init();
void js_constants_init();
void js_globals_init();

static glyph_info nh3d_last_glyphinfo;

EMSCRIPTEN_KEEPALIVE int
nh3d_map_glyphinfo_ptr(int glyph, int x, int y, unsigned mgflags)
{
    if (glyph < 0 || glyph >= MAX_GLYPH)
        return 0;
    map_glyphinfo((coordxy) x, (coordxy) y, glyph, mgflags,
                  &nh3d_last_glyphinfo);
    return (int) &nh3d_last_glyphinfo;
}
"""

JS_INSTALL_MARKER = 'installHelper(setPointerValue, "setPointerValue");'
JS_INSTALL_PATCH = """installHelper(setPointerValue, "setPointerValue");
installHelper(mapGlyphInfoHelper, "mapGlyphInfoHelper");
installHelper(tileIndexForGlyph, "tileIndexForGlyph");"""

JS_HELPER_MARKER = "// used by update_inventory"
JS_HELPER_PATCH = """function mapGlyphInfoHelper(glyph, x = 0, y = 0, mgflags = 0) {
    glyph = Math.trunc(Number(glyph));
    x = Math.trunc(Number(x) || 0);
    y = Math.trunc(Number(y) || 0);
    mgflags = Math.trunc(Number(mgflags) || 0);
    if (!Number.isFinite(glyph))
        return null;

    const ptr = _nh3d_map_glyphinfo_ptr(glyph, x, y, mgflags >>> 0);
    if (!ptr)
        return null;

    const ttychar = getValue(ptr + 4, "i32");
    return {
        glyph: getValue(ptr, "i32"),
        ch: ttychar,
        ttychar,
        framecolor: getValue(ptr + 8, "i32"),
        glyphflags: getValue(ptr + 12, "i32"),
        color: getValue(ptr + 16, "i32"),
        symidx: getValue(ptr + 20, "i32"),
        customcolor: getValue(ptr + 24, "i32"),
        color256idx: getValue(ptr + 28, "i16"),
        tileidx: getValue(ptr + 30, "i16"),
        x,
        y,
        mgflags,
    };
}
function tileIndexForGlyph(glyph) {
    const info = mapGlyphInfoHelper(glyph, 0, 0, 0);
    return info ? info.tileidx : -1;
}
// used by update_inventory"""


def replace_once(source: str, marker: str, replacement: str) -> str:
    if marker not in source:
        raise RuntimeError(f"Unable to find patch marker: {marker!r}")
    return source.replace(marker, replacement, 1)


def patch_config(source_root: Path) -> None:
    config = source_root / "include" / "config.h"
    source = config.read_text()

    if not re.search(
        r"^[ \t]*#[ \t]*define[ \t]+TILES_IN_GLYPHMAP\b",
        source,
        re.MULTILINE,
    ):
        match = re.search(CONFIG_GUARD_RE, source, re.MULTILINE)
        if match is None:
            raise RuntimeError("Unable to find config.h include guard.")
        source = source[: match.end()] + CONFIG_TILE_PATCH + source[match.end() :]

    config.write_text(source)


def patch_libnhmain(source_root: Path) -> None:
    libnhmain = source_root / "sys" / "libnh" / "libnhmain.c"
    source = libnhmain.read_text()

    if "nh3d_map_glyphinfo_ptr" not in source:
        source = replace_once(source, C_MARKER, C_PATCH)

    if 'installHelper(mapGlyphInfoHelper, "mapGlyphInfoHelper");' not in source:
        source = replace_once(source, JS_INSTALL_MARKER, JS_INSTALL_PATCH)

    if "function mapGlyphInfoHelper(glyph" not in source:
        source = replace_once(source, JS_HELPER_MARKER, JS_HELPER_PATCH)

    libnhmain.write_text(source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source_root",
        nargs="?",
        default=".",
        help="Path to the checked-out NetHack-cn source tree.",
    )
    args = parser.parse_args()
    source_root = Path(args.source_root).resolve()
    patch_config(source_root)
    patch_libnhmain(source_root)


if __name__ == "__main__":
    main()
