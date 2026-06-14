// Manual window dragging for the widget.
//
// Why not Tauri's native drag (startDragging / data-tauri-drag-region)? Both
// hand off to a macOS window-drag run-loop that (a) can't be validated with
// synthetic events and (b) silently no-ops if its JS import fails. This version
// moves the window ourselves via setPosition on pointer-move: fully in our
// control, testable, and DPI-correct. rAF-throttled so it stays smooth.

import { isTauri } from "../platform";
import { setClickThroughDragging } from "./clickthrough";

// Controls opt out so a grab on them clicks instead of dragging.
const NO_DRAG =
  "button, input, a, .tbtn, .knob, .xy, .seg, .flipsw, .pl-row, .sk-slider-h, .sk-slider-v, .sk-slider-arc, [data-no-drag]";

interface WinLike {
  outerPosition: () => Promise<{ x: number; y: number }>;
  setPosition: (p: unknown) => Promise<void>;
}
let win: WinLike | null = null;
let PhysicalPosition: (new (x: number, y: number) => unknown) | null = null;
if (isTauri()) {
  void import("@tauri-apps/api/window").then((m) => {
    win = m.getCurrentWindow() as unknown as WinLike;
    PhysicalPosition = m.PhysicalPosition;
  });
}

export function startWidgetDrag(e: React.PointerEvent): void {
  if (!win || !PhysicalPosition || e.button !== 0) return;
  if ((e.target as HTMLElement).closest(NO_DRAG)) return;

  const w = win;
  const Pos = PhysicalPosition;
  const dpr = window.devicePixelRatio || 1;
  const startX = e.screenX * dpr; // physical px of the cursor at grab
  const startY = e.screenY * dpr;
  let origin: { x: number; y: number } | null = null;
  let raf = 0;
  let pending: { x: number; y: number } | null = null;
  // outerPosition is async; if the pointer already moved before it resolved,
  // apply the latest pending move immediately so fast drags don't drop frames.
  void w.outerPosition().then((p) => {
    origin = { x: p.x, y: p.y };
    if (pending && !raf) raf = requestAnimationFrame(flush);
  });

  const flush = () => {
    raf = 0;
    if (origin && pending) void w.setPosition(new Pos(pending.x, pending.y));
  };
  const move = (ev: PointerEvent) => {
    if (!origin) return;
    pending = {
      x: Math.round(origin.x + (ev.screenX * dpr - startX)),
      y: Math.round(origin.y + (ev.screenY * dpr - startY)),
    };
    if (!raf) raf = requestAnimationFrame(flush);
  };
  const up = () => {
    if (raf) cancelAnimationFrame(raf);
    setClickThroughDragging(false);
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  setClickThroughDragging(true); // freeze click-through hit-testing during the drag
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}
