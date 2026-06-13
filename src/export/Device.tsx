import { useEffect, useRef } from "react";
import { Composite } from "../player/Composite";
import { playerTemplate } from "../template/winamp-layout";
import { useAspect } from "./cfg";

// A single live skin sized to an explicit pixel height (width derives from the
// real template aspect). Used by the artistic layouts (fan / center / scatter)
// where each device is placed/rotated independently.
export function Device({ skin, h }: { skin: string; h: number }) {
  const aspect = useAspect(skin);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.style.setProperty("--w", `${Math.round(h * aspect)}px`);
  }, [aspect, h]);
  return (
    <div ref={ref} className="device">
      <Composite template={playerTemplate} skinId={skin} />
    </div>
  );
}
