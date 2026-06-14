// Per-pixel click-through: clicks on the TRANSPARENT parts of the window pass to
// whatever app is behind; clicks on the skin itself hit the widget. macOS windows
// are rectangular and capture every click, so we hit-test the cursor against the
// skin's alpha and toggle the window's "ignore cursor events" accordingly.
//
// The catch: while ignoring, the webview receives NO pointer events, so it can't
// notice the cursor returning to the skin. We recover by polling the GLOBAL cursor
// (Tauri's window.cursorPosition, which works regardless of capture) and flipping
// back to interactive when it lands on an opaque pixel. Both `cursorPosition` and
// `setIgnoreCursorEvents` are built-in Tauri window commands — no Rust needed.

import { isTauri } from "../platform";

interface WinLike {
  cursorPosition: () => Promise<{ x: number; y: number }>;
  outerPosition: () => Promise<{ x: number; y: number }>;
  setIgnoreCursorEvents: (ignore: boolean) => Promise<void>;
}

const COLS = 96;
const ROWS = 144; // 2:3, matches the 1024×1536 frames
const ALPHA_MIN = 24; // treat near-transparent as pass-through (also drops the AA fringe)
const FRAME_ASPECT = 1024 / 1536;

let win: WinLike | null = null;
if (isTauri()) {
  void import("@tauri-apps/api/window").then((m) => { win = m.getCurrentWindow() as unknown as WinLike; });
}

let hit: Uint8Array | null = null; // COLS*ROWS opaque bitmap for the active skin
let ignoring = false;
let poll = 0;
let dragging = false; // don't flip to pass-through mid window-drag

export function setClickThroughDragging(v: boolean): void { dragging = v; }

async function buildHitMap(frameUrl: string): Promise<void> {
  hit = null; // until (re)built, opaqueAt returns true → fully interactive
  // Fetch the PNG bytes and decode via createImageBitmap. A plain `new Image()`
  // drawn to a canvas gets TAINTED under Tauri's asset protocol, so getImageData
  // returns blank (all-transparent) → every point reads as pass-through and the
  // window gets stuck click-through. A same-origin fetched blob is never tainted.
  let bmp: ImageBitmap;
  try {
    const res = await fetch(frameUrl);
    if (!res.ok) return;
    bmp = await createImageBitmap(await res.blob());
  } catch { return; }
  const c = document.createElement("canvas");
  c.width = COLS; c.height = ROWS;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  if (!ctx) { bmp.close?.(); return; }
  ctx.drawImage(bmp, 0, 0, COLS, ROWS);
  bmp.close?.();
  let data: Uint8ClampedArray;
  try { data = ctx.getImageData(0, 0, COLS, ROWS).data; } catch { return; }
  const bits = new Uint8Array(COLS * ROWS);
  let opaque = 0;
  for (let i = 0; i < COLS * ROWS; i++) {
    const on = data[i * 4 + 3] > ALPHA_MIN ? 1 : 0;
    bits[i] = on; opaque += on;
  }
  // FAIL-SAFE: a degenerate map (blank/all-transparent, or solid) is useless and
  // would either stick the window click-through or do nothing — leave hit null so
  // the widget stays fully interactive instead of getting stuck.
  const frac = opaque / (COLS * ROWS);
  if (frac < 0.05 || frac > 0.985) return;
  hit = bits;
}

// Is the CSS point (relative to the content top-left) over an opaque skin pixel?
// The skin fills the window height and is centered (width = height·2/3).
function opaqueAt(cssX: number, cssY: number): boolean {
  if (!hit) return true; // until the map loads, stay interactive
  const iw = window.innerWidth, ih = window.innerHeight;
  const frameW = ih * FRAME_ASPECT;
  const marginX = (iw - frameW) / 2;
  const nx = (cssX - marginX) / frameW;
  const ny = cssY / ih;
  if (nx < 0 || nx >= 1 || ny < 0 || ny >= 1) return false; // letterbox margin → pass-through
  const cx = Math.min(COLS - 1, (nx * COLS) | 0);
  const cy = Math.min(ROWS - 1, (ny * ROWS) | 0);
  return hit[cy * COLS + cx] === 1;
}

async function setIgnore(next: boolean): Promise<void> {
  if (!win || next === ignoring) return;
  ignoring = next;
  try { await win.setIgnoreCursorEvents(next); } catch { /* noop */ }
  if (next) startPoll(); else stopPoll();
}

function stopPoll(): void { if (poll) { clearInterval(poll); poll = 0; } }
function startPoll(): void {
  if (poll || !win) return;
  poll = window.setInterval(() => {
    if (!win) return;
    void Promise.all([win.cursorPosition(), win.outerPosition()]).then(([cur, out]) => {
      const dpr = window.devicePixelRatio || 1;
      // cursorPosition + outerPosition are both global physical px → relative CSS px
      const x = (cur.x - out.x) / dpr;
      const y = (cur.y - out.y) / dpr;
      const inWindow = x >= 0 && x < window.innerWidth && y >= 0 && y < window.innerHeight;
      // re-capture (and stop polling) once the cursor is back on the skin OR has
      // left the window entirely — only keep polling while over a transparent
      // pixel INSIDE the window, so we're not running 50Hz IPC all the time.
      if (!inWindow || opaqueAt(x, y)) void setIgnore(false);
    }).catch(() => {});
  }, 40);
}

function onMove(e: PointerEvent): void {
  if (ignoring || dragging) return; // poll owns the ignoring state; never flip mid-drag
  void setIgnore(!opaqueAt(e.clientX, e.clientY));
}

// Set up the listeners. Call updateClickThroughSkin() to (re)build the alpha map.
export function initClickThrough(): () => void {
  if (!isTauri()) return () => {};
  window.addEventListener("pointermove", onMove);
  return () => {
    window.removeEventListener("pointermove", onMove);
    stopPoll();
    void setIgnore(false);
  };
}

export function updateClickThroughSkin(skinId: string): void {
  if (!isTauri()) return;
  void buildHitMap(`/skins/${skinId}/frame.png`);
}
