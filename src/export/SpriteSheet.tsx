import { spriteUrl, skinList } from "../player/skins";
import type { Cfg } from "./cfg";

// IG "hardware" contact sheet: each skin's actual AI control SPRITES — the flip
// switch in both states, the knob cap, two molded transport faces, the fader
// cap. WIP/technical framing.
const DEFAULT = ["frog", "burger", "bondi", "wmp", "halo", "biomech"];

const PARTS: { name: string; label: string; cls?: string }[] = [
  { name: "switch-off", label: "sw·off", cls: "switch" },
  { name: "switch-on", label: "sw·on", cls: "switch" },
  { name: "knob", label: "knob" },
  { name: "btn-play", label: "play" },
  { name: "btn-stop", label: "stop" },
  { name: "thumb", label: "fader", cls: "wide" },
];

export function SpriteSheet({ cfg }: { cfg: Cfg }) {
  const skins = cfg.skins && cfg.skins.length ? cfg.skins : DEFAULT;
  return (
    <>
      <div className="hdr">
        <span className="mark">skeuo<b>/ui</b></span>
        <span className="meta">hardware · switches / knobs / buttons</span>
        <span className="spacer" />
        <span className="tag">per-skin sprites</span>
      </div>
      <div className="sprite-body">
        {skins.map((id) => {
          const meta = skinList.find((s) => s.id === id);
          return (
            <div className="sk-row" key={id}>
              <div className="sk-name">
                <b>{(meta?.name ?? id).replace(/\s*✦\s*$/, "")}</b>
                <span>{id}</span>
              </div>
              <div className="sk-parts">
                {PARTS.map((p) => (
                  <div className={`part ${p.cls === "wide" ? "wide" : ""}`} key={p.name}>
                    <div className={`cell ${p.cls === "switch" ? "switch" : ""}`}>
                      <img src={spriteUrl(id, p.name)} alt={`${id} ${p.name}`} />
                    </div>
                    <label>{p.label}</label>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <div className="ftr">
        <span>same flip switch rendered off|on → toggling swaps real art</span>
        <span className="spacer" />
        <span>gpt-image · transparent</span>
      </div>
    </>
  );
}
