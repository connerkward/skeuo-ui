import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ExportStage } from "./ExportStage";
import { GridSheet } from "./GridSheet";
import { SpriteSheet } from "./SpriteSheet";
import { FanSheet, CenterSheet, ScatterSheet } from "./Layouts";
import { readCfg, cssVars } from "./cfg";
// the export pages reuse the live player + every skin's CSS
import "../skins/app.css";
import "../skins/player.css";
import "../skins/winamp.css";
import "../skins/frog.css";
import "../skins/burger.css";
import "../skins/bondi.css";
import "../skins/toilet.css";
import "../skins/biomech.css";
import "../skins/wmp.css";
import "../skins/halo.css";
import "./export.css";

const q = new URLSearchParams(location.search);
const mode = q.get("mode") ?? "hero";
const skin = q.get("skin") ?? "maw";
const cfg = readCfg();

const body =
  mode === "sprites" ? <SpriteSheet cfg={cfg} /> :
  mode === "grid" ? <GridSheet cfg={cfg} /> :
  mode === "fan" ? <FanSheet cfg={cfg} /> :
  mode === "center" ? <CenterSheet cfg={cfg} center={q.get("center") ?? undefined} /> :
  mode === "scatter" ? <ScatterSheet cfg={cfg} /> :
  <ExportStage skin={skin} cfg={cfg} />;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <div className={`root mode-${mode}`} style={cssVars(cfg)}>{body}</div>
  </StrictMode>
);
