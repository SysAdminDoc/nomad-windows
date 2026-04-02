/**
 * esbuild bundler config for NOMAD Field Desk
 *
 * Bundles all JS from web/static/js/ into web/static/dist/nomad.bundle.<hash>.js
 * and all CSS from web/static/css/ into web/static/dist/nomad.bundle.<hash>.css.
 * Writes web/static/dist/manifest.json mapping logical names to hashed filenames.
 *
 * Usage:  node esbuild.config.mjs            (production — minified)
 *         NODE_ENV=development node esbuild.config.mjs  (no minification)
 */

import * as esbuild from "esbuild";
import {
  readdirSync,
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  unlinkSync,
  renameSync,
} from "fs";
import { join, relative } from "path";
import { createHash } from "crypto";

const IS_PROD = process.env.NODE_ENV !== "development";
const JS_DIR = "web/static/js";
const CSS_DIR = "web/static/css";
const OUT_DIR = "web/static/dist";

// Ensure output directory exists
if (!existsSync(OUT_DIR)) {
  mkdirSync(OUT_DIR, { recursive: true });
}

// Collect JS entry points (skip vendored / minified libs)
const jsFiles = readdirSync(JS_DIR)
  .filter((f) => f.endsWith(".js") && !f.endsWith(".min.js"))
  .map((f) => join(JS_DIR, f));

// Collect CSS files
const cssFiles = existsSync(CSS_DIR)
  ? readdirSync(CSS_DIR)
      .filter((f) => f.endsWith(".css"))
      .map((f) => join(CSS_DIR, f))
  : [];

/**
 * Generate a short content-hash for a file's contents.
 */
function contentHash(filePath, length = 8) {
  const buf = readFileSync(filePath);
  return createHash("md5").update(buf).digest("hex").slice(0, length);
}

/**
 * Remove previous bundles from the output directory.
 */
function cleanOldBundles() {
  if (!existsSync(OUT_DIR)) return;
  for (const f of readdirSync(OUT_DIR)) {
    if (f.startsWith("nomad.bundle.")) {
      try {
        unlinkSync(join(OUT_DIR, f));
      } catch {
        // ignore
      }
    }
  }
}

// Clean stale bundles before building
cleanOldBundles();

const manifest = {};

// -- Bundle JS ---------------------------------------------------------------
if (jsFiles.length > 0) {
  // Build a virtual entry that imports all JS files so they end up in one bundle.
  // These are plain browser scripts (not ES modules), so esbuild will concatenate them.
  const tmpEntry = join(OUT_DIR, "_entry.js");
  const entryContents = jsFiles
    .map((f) => {
      let importPath = relative(OUT_DIR, f).replace(/\\/g, "/");
      if (!importPath.startsWith(".")) importPath = `./${importPath}`;
      return `import "${importPath}";`;
    })
    .join("\n");
  writeFileSync(tmpEntry, `${entryContents}\n`);

  try {
    await esbuild.build({
      entryPoints: [tmpEntry],
      bundle: true,
      minify: IS_PROD,
      sourcemap: false,
      outfile: join(OUT_DIR, "nomad.bundle.js"),
      format: "iife",
      target: ["es2020"],
      logLevel: "info",
    });
  } finally {
    try {
      unlinkSync(tmpEntry);
    } catch {
      // ignore
    }
  }

  // Rename with content hash
  const outFile = join(OUT_DIR, "nomad.bundle.js");
  if (existsSync(outFile)) {
    const hash = contentHash(outFile);
    const hashedName = `nomad.bundle.${hash}.js`;
    renameSync(outFile, join(OUT_DIR, hashedName));
    manifest["nomad.bundle.js"] = hashedName;
  }
}

// -- Bundle CSS --------------------------------------------------------------
if (cssFiles.length > 0) {
  const tmpCssEntry = join(OUT_DIR, "_entry.css");
  const cssEntryContents = cssFiles
    .map((f) => {
      let importPath = relative(OUT_DIR, f).replace(/\\/g, "/");
      if (!importPath.startsWith(".")) importPath = `./${importPath}`;
      return `@import "${importPath}";`;
    })
    .join("\n");
  writeFileSync(tmpCssEntry, `${cssEntryContents}\n`);

  try {
    await esbuild.build({
      entryPoints: [tmpCssEntry],
      bundle: true,
      minify: IS_PROD,
      sourcemap: false,
      outfile: join(OUT_DIR, "nomad.bundle.css"),
      logLevel: "info",
    });
  } finally {
    try {
      unlinkSync(tmpCssEntry);
    } catch {
      // ignore
    }
  }

  const outCss = join(OUT_DIR, "nomad.bundle.css");
  if (existsSync(outCss)) {
    const hash = contentHash(outCss);
    const hashedName = `nomad.bundle.${hash}.css`;
    renameSync(outCss, join(OUT_DIR, hashedName));
    manifest["nomad.bundle.css"] = hashedName;
  }
}

// -- Write manifest ----------------------------------------------------------
writeFileSync(
  join(OUT_DIR, "manifest.json"),
  JSON.stringify(manifest, null, 2) + "\n"
);

console.log("\nBuild manifest:", manifest);
