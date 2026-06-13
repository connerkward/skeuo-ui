import { useCallback, useRef, useState } from "react";

// Horizontal swipe gesture for the mobile skin switcher. Pointer/touch events
// (Pointer Events API) on the carriage; tracks live drag offset for a rubber-
// banding follow, then commits to prev/next on release past a threshold.
//
// `count` is the number of pages (skins + the trailing "create" page). The hook
// is layout-agnostic: it reports the active index and a px drag delta; the
// consumer translates a track by `index * -width + dragX`.

export interface SwipeState {
  index: number;
  dragX: number; // live horizontal offset during an active drag (px)
  dragging: boolean;
  goTo: (i: number) => void;
  bind: {
    onPointerDown: (e: React.PointerEvent) => void;
    onPointerMove: (e: React.PointerEvent) => void;
    onPointerUp: (e: React.PointerEvent) => void;
    onPointerCancel: (e: React.PointerEvent) => void;
  };
}

export function useSwipe(count: number, initial = 0): SwipeState {
  const [index, setIndex] = useState(initial);
  const [dragX, setDragX] = useState(0);
  const [dragging, setDragging] = useState(false);
  // a swipe must be mostly-horizontal AND clear a distance threshold to commit;
  // otherwise it snaps back (so taps / vertical scrolls don't switch skins).
  const start = useRef<{ x: number; y: number; locked: boolean | null } | null>(null);

  const goTo = useCallback(
    (i: number) => setIndex(Math.max(0, Math.min(count - 1, i))),
    [count],
  );

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    // ignore drags that begin on an interactive control so the player's own
    // knobs / sliders / buttons keep working; the swipe only owns empty body.
    if ((e.target as HTMLElement).closest("button, .knob, .sk-slider-h, .sk-slider-v, .sk-slider-arc, .xy, .pl-list, .region-dyn")) {
      start.current = null;
      return;
    }
    start.current = { x: e.clientX, y: e.clientY, locked: null };
    setDragging(true);
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    const s = start.current;
    if (!s) return;
    const dx = e.clientX - s.x;
    const dy = e.clientY - s.y;
    // lock axis on first meaningful move: horizontal → swipe, vertical → bail
    if (s.locked === null && Math.abs(dx) + Math.abs(dy) > 8) {
      s.locked = Math.abs(dx) > Math.abs(dy);
      if (s.locked) {
        try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); } catch { /* noop */ }
      }
    }
    if (s.locked === true) {
      e.preventDefault();
      // rubber-band the over-scroll at the two ends
      const atStart = index === 0 && dx > 0;
      const atEnd = index === count - 1 && dx < 0;
      setDragX(atStart || atEnd ? dx * 0.32 : dx);
    }
  }, [index, count]);

  const finish = useCallback((e: React.PointerEvent) => {
    const s = start.current;
    start.current = null;
    setDragging(false);
    const w = (e.currentTarget as HTMLElement).clientWidth || 1;
    const dx = dragX;
    setDragX(0);
    if (s?.locked && Math.abs(dx) > Math.min(70, w * 0.18)) {
      setIndex((i) => Math.max(0, Math.min(count - 1, dx < 0 ? i + 1 : i - 1)));
    }
  }, [dragX, count]);

  return {
    index,
    dragX,
    dragging,
    goTo,
    bind: { onPointerDown, onPointerMove, onPointerUp: finish, onPointerCancel: finish },
  };
}
