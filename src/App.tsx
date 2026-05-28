import { useState } from "react";
import { packs } from "./styles/packs";
import { Frame } from "./components/Frame";
import "./styles/base.css";

export default function App() {
  const [styleId, setStyleId] = useState(packs[0].id);
  const [size, setSize] = useState({ w: 760, h: 540 });

  return (
    <div className="page">
      <aside className="sidebar">
        <h1>Skin</h1>
        {packs.map((p) => (
          <button
            key={p.id}
            className={`style-btn ${p.id === styleId ? "active" : ""}`}
            onClick={() => setStyleId(p.id)}
          >
            <span className="name">{p.name}</span>
            <span className="blurb">{p.blurb}</span>
          </button>
        ))}
        <div className="hint">
          <kbd>↘</kbd> drag corner to resize.
          <br />Chrome 9-slices, components reflow & hide at narrow widths.
          <div className="size-readout">window: {size.w}×{size.h}px</div>
        </div>
      </aside>
      <main className="stage">
        <Frame styleId={styleId} onSize={setSize} />
      </main>
    </div>
  );
}
