#!/usr/bin/env python3
"""Patch NetHack-cn wasm helpers needed by the web client."""

from __future__ import annotations

import argparse
from pathlib import Path


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

    const glyphInfoPtr = _malloc(36);

    try {
        _map_glyphinfo(x, y, glyph, mgflags >>> 0, glyphInfoPtr);

        const ttychar = getValue(glyphInfoPtr + 4, "i32");
        return {
            glyph: getValue(glyphInfoPtr, "i32"),
            ch: ttychar,
            ttychar,
            framecolor: getValue(glyphInfoPtr + 8, "i32"),
            glyphflags: getValue(glyphInfoPtr + 12, "i32"),
            color: getValue(glyphInfoPtr + 16, "i32"),
            symidx: getValue(glyphInfoPtr + 20, "i32"),
            customcolor: getValue(glyphInfoPtr + 24, "i32"),
            color256idx: getValue(glyphInfoPtr + 28, "i16"),
            tileidx: getValue(glyphInfoPtr + 30, "i16"),
            x,
            y,
            mgflags,
        };
    } finally {
        _free(glyphInfoPtr);
    }
}
function tileIndexForGlyph(glyph) {
    const info = mapGlyphInfoHelper(glyph, 0, 0, 0);
    return info ? info.tileidx : -1;
}
// used by update_inventory"""

REQUIRED_EXPORTED_FUNCTIONS = ("_free", "_map_glyphinfo")


def replace_once(source: str, marker: str, replacement: str) -> str:
    if marker not in source:
        raise RuntimeError(f"Unable to find patch marker: {marker!r}")
    return source.replace(marker, replacement, 1)


def patch_libnhmain(source_root: Path) -> None:
    libnhmain = source_root / "sys" / "libnh" / "libnhmain.c"
    source = libnhmain.read_text()

    if 'installHelper(mapGlyphInfoHelper, "mapGlyphInfoHelper");' not in source:
        source = replace_once(source, JS_INSTALL_MARKER, JS_INSTALL_PATCH)

    if "function mapGlyphInfoHelper(glyph" not in source:
        source = replace_once(source, JS_HELPER_MARKER, JS_HELPER_PATCH)

    libnhmain.write_text(source)


def append_exported_functions(source: str) -> str:
    lines = source.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if "EXPORTED_FUNCTIONS=" not in line:
            continue

        missing = [
            function_name
            for function_name in REQUIRED_EXPORTED_FUNCTIONS
            if function_name not in line
        ]
        if not missing:
            return source

        close_bracket = line.rfind("]")
        if close_bracket < 0:
            raise RuntimeError("Unable to find EXPORTED_FUNCTIONS closing bracket.")

        insertion = "".join(f",'{function_name}'" for function_name in missing)
        lines[index] = line[:close_bracket] + insertion + line[close_bracket:]
        return "".join(lines)

    raise RuntimeError("Unable to find EXPORTED_FUNCTIONS in wasm hints.")


def patch_wasm_exports(source_root: Path) -> None:
    hints_root = source_root / "sys" / "unix" / "hints"
    patched_any = False

    for hints in hints_root.rglob("*"):
        if not hints.is_file():
            continue

        source = hints.read_text()
        if "EXPORTED_FUNCTIONS=" not in source:
            continue

        hints.write_text(append_exported_functions(source))
        patched_any = True

    if not patched_any:
        raise RuntimeError("Unable to find wasm hints with EXPORTED_FUNCTIONS.")


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
    patch_libnhmain(source_root)
    patch_wasm_exports(source_root)


if __name__ == "__main__":
    main()
