import { useMemo } from "react";
import { components } from "../styles/packs";
import { Component } from "./Components";
import type { PanelId } from "../types";

interface Props {
  styleId: string;
}

export function Frame({ styleId }: Props) {
  const byPanel = useMemo(() => ({
    main:     components.filter(c => c.panel === "main"),
    eq:       components.filter(c => c.panel === "eq"),
    playlist: components.filter(c => c.panel === "playlist"),
  }), []);

  const panelBg = (pid: PanelId): React.CSSProperties => ({
    "--panel-bg": `url(/sprites/${styleId}/panel-${pid}.png)`,
  } as React.CSSProperties);

  return (
    <div className="app-window">
      {(["main", "eq", "playlist"] as PanelId[]).map((pid) => (
        <div key={pid} className={`panel panel-${pid}`} style={panelBg(pid)}>
          {byPanel[pid].map((c) => (
            <Component
              key={c.id}
              spec={c}
              spriteUrl={`/sprites/${styleId}/${c.id}.png`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
