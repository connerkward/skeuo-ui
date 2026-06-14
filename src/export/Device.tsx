import { useEffect, useRef } from "react";
import { Composite } from "../player/Composite";
import { playerTemplate } from "../template/winamp-layout";
import { useAspect } from "./cfg";

// A single LIVE skin (real working controls + spectrum + screens). Size it by
// pixel WIDTH (`w`, preferred — height follows the template aspect) or by pixel
// HEIGHT (`h`, derives width from aspect). Used by the motion-graphics scenes so
// the devices that stream past are the animated product, not static body art.
export function Device({ skin, w, h, className, style }: {
  skin: string; w?: number; h?: number; className?: string; style?: React.CSSProperties;
}) {
  const aspect = useAspect(skin);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const px = w != null ? w : h != null ? Math.round(h * aspect) : 360;
    ref.current?.style.setProperty("--w", `${px}px`);
  }, [aspect, w, h]);
  return (
    <div ref={ref} className={`device ${className ?? ""}`} style={style}>
      <Composite template={playerTemplate} skinId={skin} />
    </div>
  );
}
