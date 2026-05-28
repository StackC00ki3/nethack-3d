import fs from "node:fs/promises";
import {
  generateGlyphCatalogSource,
  getGeneratedCatalogPathForVersion,
  getGlyphCatalogTargets,
  resolveProjectRoot,
} from "./catalog-generator.mjs";

function normalizeRequestedVersion(value) {
  if (value === "5" || value === "5.0" || value === "5.0.0") {
    return "5.0";
  }
  return value;
}

function resolveRequestedVersions() {
  const versions = [];
  for (let index = 2; index < process.argv.length; index += 1) {
    const arg = process.argv[index];
    if (arg === "--version" || arg === "-v") {
      const value = process.argv[index + 1];
      if (value) {
        versions.push(normalizeRequestedVersion(value));
        index += 1;
      }
      continue;
    }
    if (arg.startsWith("--version=")) {
      versions.push(normalizeRequestedVersion(arg.slice("--version=".length)));
    }
  }
  return versions;
}

function resolveExpectedGlyphKinds(version) {
  const expectedKinds = [
    "mon",
    "pet",
    "invis",
    "detect",
    "body",
    "ridden",
    "obj",
    "cmap",
    "explode",
    "zap",
    "swallow",
    "warning",
  ];
  if (version !== "slashem") {
    expectedKinds.push("statue");
  }
  return expectedKinds;
}

function validateGeneratedSource(source, version) {
  const maxGlyphMatch = source.match(/maxGlyph:\s*(\d+),/);
  if (!maxGlyphMatch) {
    throw new Error("Unable to find maxGlyph in generated catalog");
  }
  const maxGlyph = Number(maxGlyphMatch[1]);

  const entries = [...source.matchAll(/\{\s*glyph:\s*(\d+),\s*kind:\s*"([a-z_]+)"/g)];
  if (entries.length !== maxGlyph) {
    throw new Error(
      `Catalog entry count mismatch: expected ${maxGlyph}, got ${entries.length}`
    );
  }

  const seenKinds = new Set(entries.map((match) => match[2]));
  const expectedKinds = new Set(resolveExpectedGlyphKinds(version));
  for (const kind of expectedKinds) {
    if (!seenKinds.has(kind)) {
      throw new Error(`Missing expected glyph kind '${kind}' in catalog`);
    }
  }

  const rangeMatches = [
    ...source.matchAll(
      /\{\s*key:\s*"GLYPH_[A-Z_]+",\s*kind:\s*"[a-z_]+",\s*start:\s*(\d+),\s*endExclusive:\s*(\d+)\s*\}/g
    ),
  ];
  if (!rangeMatches.length) {
    throw new Error("No glyph ranges found in generated catalog");
  }

  let coverage = 0;
  for (const match of rangeMatches) {
    const start = Number(match[1]);
    const endExclusive = Number(match[2]);
    if (endExclusive < start) {
      throw new Error(`Invalid glyph range ${start}..${endExclusive}`);
    }
    coverage += endExclusive - start;
  }
  if (coverage !== maxGlyph) {
    throw new Error(
      `Glyph range coverage mismatch: expected ${maxGlyph}, got ${coverage}`
    );
  }
}

async function main() {
  const projectRoot = resolveProjectRoot();
  const requestedVersions = new Set(resolveRequestedVersions());
  const targets = getGlyphCatalogTargets().filter(
    (target) =>
      requestedVersions.size === 0 || requestedVersions.has(target.version),
  );
  if (targets.length === 0) {
    throw new Error(
      `No matching glyph catalog target for version(s): ${[...requestedVersions].join(", ")}`,
    );
  }

  for (const target of targets) {
    const outputPath = getGeneratedCatalogPathForVersion(
      projectRoot,
      target.version,
    );
    const [expectedSource, currentSource] = await Promise.all([
      generateGlyphCatalogSource(projectRoot, target.version),
      fs.readFile(outputPath, "utf8"),
    ]);

    if (currentSource !== expectedSource) {
      console.error(
        `Glyph catalog is stale (${target.version}): ${outputPath}\nRun: npm run glyphs:generate`,
      );
      process.exit(1);
    }

    validateGeneratedSource(currentSource, target.version);
  }

  console.log("Glyph catalogs are up to date.");
  process.exit(0);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
