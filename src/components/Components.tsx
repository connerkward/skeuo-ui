import { useEffect, useRef, useState } from "react";
import type { ComponentSpec } from "../types";
import { toPanelCoords } from "../styles/packs";

interface Props {
  spec: ComponentSpec;
  spriteUrl: string;
}

export function Component({ spec, spriteUrl }: Props) {
  const pc = toPanelCoords(spec);
  const style: React.CSSProperties = {
    left: `${pc.x * 100}%`,
    top: `${pc.y * 100}%`,
    width: `${pc.w * 100}%`,
    height: `${pc.h * 100}%`,
    ["--btn-img" as string]: `url(${spriteUrl})`,
  };

  if (spec.kind === "button") return <ButtonCmp spec={spec} style={style} />;
  if (spec.kind === "switch") return <SwitchCmp spec={spec} style={style} />;
  if (spec.kind === "slider-v") return <SliderVCmp spec={spec} style={style} />;
  return <SliderHCmp spec={spec} style={style} />;
}

function ButtonCmp({ spec, style }: { spec: ComponentSpec; style: React.CSSProperties }) {
  return (
    <div className="cmp" style={style}>
      <button title={spec.label ?? spec.id} />
    </div>
  );
}

function SwitchCmp({ spec, style }: { spec: ComponentSpec; style: React.CSSProperties }) {
  const [on, setOn] = useState(spec.id === "eq-on" || spec.id === "shuffle");
  return (
    <div className="cmp" style={style}>
      <button
        className="sk-switch"
        data-on={on}
        onClick={() => setOn(v => !v)}
        title={`${spec.label ?? spec.id}: ${on ? "ON" : "OFF"}`}
      />
    </div>
  );
}

function SliderVCmp({ spec, style }: { spec: ComponentSpec; style: React.CSSProperties }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [value, setValue] = useState(0);
  const dragRef = useRef(false);
  const setFromEvent = (clientY: number) => {
    const t = trackRef.current; if (!t) return;
    const r = t.getBoundingClientRect();
    setValue(Math.max(0, Math.min(1, 1 - (clientY - r.top) / r.height)));
  };
  useEffect(() => {
    const onMove = (e: MouseEvent) => { if (dragRef.current) setFromEvent(e.clientY); };
    const onUp = () => { dragRef.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, []);

  return (
    <div className="cmp" style={style}>
      <div
        className="sk-slider-v"
        ref={trackRef}
        onMouseDown={(e) => { dragRef.current = true; setFromEvent(e.clientY); }}
        title={`${spec.id}: ${(value * 100).toFixed(0)}%`}
      >
        <div className="rail" />
        <div className="thumb" style={{ bottom: `${value * 100}%` }} />
      </div>
    </div>
  );
}

function SliderHCmp({ spec, style }: { spec: ComponentSpec; style: React.CSSProperties }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [value, setValue] = useState(0);
  const dragRef = useRef(false);
  const setFromEvent = (clientX: number) => {
    const t = trackRef.current; if (!t) return;
    const r = t.getBoundingClientRect();
    setValue(Math.max(0, Math.min(1, (clientX - r.left) / r.width)));
  };
  useEffect(() => {
    const onMove = (e: MouseEvent) => { if (dragRef.current) setFromEvent(e.clientX); };
    const onUp = () => { dragRef.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, []);

  return (
    <div className="cmp" style={style}>
      <div
        className="sk-slider-h"
        ref={trackRef}
        onMouseDown={(e) => { dragRef.current = true; setFromEvent(e.clientX); }}
      >
        <div className="rail" />
        <div className="thumb" style={{ left: `${value * 100}%` }} />
      </div>
    </div>
  );
}
