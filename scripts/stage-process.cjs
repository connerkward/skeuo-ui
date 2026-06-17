// Postbuild: stage the standalone process page (site/) into dist/process/ so it
// deploys at skeuo.fm/process/ alongside the app. site/ keeps relative asset paths
// (process/*.png, favicon.svg), so a recursive copy preserves them; the finale
// iframe uses a relative "/?widget=1…" URL that resolves to the app on the domain.
const { cpSync, existsSync, mkdirSync } = require("node:fs");
const { resolve } = require("node:path");

const root = resolve(__dirname, "..");
const src = resolve(root, "site");
const dest = resolve(root, "dist", "process");

if (!existsSync(src)) { console.warn("[stage-process] no site/ dir — skipping"); process.exit(0); }
mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });
console.log("[stage-process] site/ → dist/process/");
