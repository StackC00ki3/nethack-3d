import fs from "node:fs/promises";
import path from "node:path";
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
    const source = await generateGlyphCatalogSource(projectRoot, target.version);
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    await fs.writeFile(outputPath, source, "utf8");
    console.log(`Generated glyph catalog (${target.version}): ${outputPath}`);
  }
  process.exit(0);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});
