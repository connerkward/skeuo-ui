import { useState } from "react";
import { Composite } from "./player/Composite";
import { playerTemplate } from "./template/winamp-layout";
import { skinList } from "./player/skins";
import "./skins/app.css";
import "./skins/player.css";
import "./skins/winamp.css";
import "./skins/fallout.css";
import "./skins/warcraft.css";

// expose the single-source-of-truth template for tooling (wireframe/mask export)
(window as unknown as { __template: unknown }).__template = playerTemplate;

export default function App() {
  const [skinId, setSkinId] = useState(skinList[0].id);
  const [wire, setWire] = useState(false);

  return (
    <div className="page">
      <aside className="sidebar">
        <h1>Skin</h1>
        {skinList.map((s) => (
          <button
            key={s.id}
            className={`style-btn ${s.id === skinId ? "active" : ""}`}
            onClick={() => setSkinId(s.id)}
          >
            <span className="name">{s.name}</span>
            <span className="blurb">{s.blurb}</span>
          </button>
        ))}
        <label className="wire-toggle-row">
          <input type="checkbox" checked={wire} onChange={(e) => setWire(e.target.checked)} />
          <span>Wireframe (template)</span>
        </label>
        <div className="hint">
          One template → many skins. Buttons / sliders are baked sprites;
          the clock, spectrum, marquee &amp; playlist are live.
        </div>
      </aside>
      <main className="stage">
        <div className="stage-inner">
          <Composite template={playerTemplate} skinId={skinId} showWireframe={wire} />
        </div>
      </main>
    </div>
  );
}
