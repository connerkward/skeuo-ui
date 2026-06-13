import { useEffect, useRef } from "react";
import { Composite } from "../player/Composite";
import { playerTemplate } from "../template/winamp-layout";
import { skinList } from "../player/skins";
import { useAspect, type Cfg } from "./cfg";

const layoutOf = (id: string): string => {
  const map: Record<string, string> = {
    maw: "radial", vortex: "radial", pebble: "minimal", obelisk: "hero/tall",
    slab: "wide", wmp: "capsule", halo: "capsule",
  };
  return map[id] ?? "classic";
};

// HERO — one skin, framed simply, with the live controls driven by a small
// loopable demo so a screen-capture reads as a working device. WIP framing:
// just a header strip and a technical caption, no marketing chrome.
export function ExportStage({ skin, cfg }: { skin: string; cfg: Cfg }) {
  const meta = skinList.find((s) => s.id === skin);
  const aspect = useAspect(skin);
  const deviceRef = useRef<HTMLDivElement>(null);
  const wellRef = useRef<HTMLDivElement>(null);

  // size the device to its well from the real template aspect
  useEffect(() => {
    const well = wellRef.current, dev = deviceRef.current;
    if (!well || !dev) return;
    const fit = () => {
      const bw = well.clientWidth, bh = well.clientHeight;
      const w = Math.min(bw, bh * aspect) * cfg.dev;
      dev.style.setProperty("--w", `${Math.round(w)}px`);
    };
    fit();
    const ro = new ResizeObserver(fit); ro.observe(well);
    return () => ro.disconnect();
  }, [aspect, cfg.dev]);

  // demo driver: gently exercise the real controls in a loopable cycle
  useEffect(() => {
    const root = deviceRef.current;
    if (!root) return;
    let stop = false;
    const timers: number[] = [];
    const at = (ms: number, fn: () => void) => timers.push(window.setTimeout(fn, ms));
    const drag = (el: Element, x0: number, y0: number, x1: number, y1: number, steps = 14) => {
      const opt = (x: number, y: number) => ({ clientX: x, clientY: y, bubbles: true, pointerId: 1, pointerType: "mouse" as const });
      el.dispatchEvent(new PointerEvent("pointerdown", opt(x0, y0)));
      for (let i = 1; i <= steps; i++) at((i / steps) * 520, () => {
        if (stop) return;
        const x = x0 + (x1 - x0) * (i / steps), y = y0 + (y1 - y0) * (i / steps);
        window.dispatchEvent(new PointerEvent("pointermove", opt(x, y)));
        if (i === steps) window.dispatchEvent(new PointerEvent("pointerup", opt(x, y)));
      });
    };
    const sweepKnob = (el: Element, up: boolean) => {
      const r = el.getBoundingClientRect();
      drag(el, r.left + r.width / 2, r.top + r.height / 2, r.left + r.width / 2, r.top + r.height / 2 + (up ? -90 : 90));
    };
    const rideFader = (el: Element, target: number) => {
      const r = el.getBoundingClientRect();
      drag(el, r.left + r.width / 2, r.top + r.height * 0.5, r.left + r.width / 2, r.top + (1 - target) * r.height, 10);
    };
    const cycle = () => {
      if (stop) return;
      const sw = Array.from(root.querySelectorAll(".flipsw"));
      const kn = Array.from(root.querySelectorAll(".knob"));
      const fd = Array.from(root.querySelectorAll(".sk-slider-v"));
      at(200, () => sw[0] && (sw[0] as HTMLElement).click());
      at(1100, () => kn[0] && sweepKnob(kn[0], true));
      at(2100, () => fd[2] && rideFader(fd[2], 0.85));
      at(2500, () => fd[5] && rideFader(fd[5], 0.25));
      at(3200, () => (sw[1] ?? sw[0]) && (sw[1] ?? sw[0] as HTMLElement) && ((sw[1] ?? sw[0]) as HTMLElement).click());
      at(4100, () => (kn[1] ?? kn[0]) && sweepKnob((kn[1] ?? kn[0]) as Element, false));
      at(5000, () => fd[2] && rideFader(fd[2], 0.45));
      at(5400, () => fd[5] && rideFader(fd[5], 0.6));
      at(6500, cycle);
    };
    at(700, cycle);
    return () => { stop = true; timers.forEach(clearTimeout); };
  }, [skin]);

  return (
    <>
      <div className="hdr">
        <span className="mark">skeuo<b>/ui</b></span>
        <span className="meta">wip · {skin}</span>
        <span className="spacer" />
        <span className="tag">live</span>
      </div>
      <div className="hero-dev" ref={wellRef}>
        <div ref={deviceRef}>
          <Composite template={playerTemplate} skinId={skin} />
        </div>
      </div>
      <div className="hero-cap">
        <span className="name">{(meta?.name ?? skin).replace(/\s*✦\s*$/, "")}</span>
        <span className="blurb">{meta?.blurb}</span>
        <span className="spec">layout {layoutOf(skin)} · webaudio spectrum · real switches/knobs · 2026-06-13</span>
      </div>
    </>
  );
}
