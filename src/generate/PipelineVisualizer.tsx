import { STAGES, stepsProgress, type StepsState } from "./pipelineViz";
import "./pipelineViz.css";

// Non-blocking, dismissible overlay that animates the real generation pipeline as a
// vertical step list — each stage shows pending → running → done/failed with a
// pulsing node, a scanning sweep over the live artifact, and a check on completion.
// Driven entirely by `steps` (updated from real server + client events by the caller);
// it renders no timers of its own, so what you watch is real progress.
export function PipelineVisualizer({
  steps, open, onClose, modelLabel, current,
}: {
  steps: StepsState;
  open: boolean;
  onClose: () => void;
  modelLabel?: string;      // e.g. "Nano Banana Pro" or "model 1/3 · …"
  current?: string;         // optional short caption (skin name / prompt)
}) {
  if (!open) return null;
  const frac = stepsProgress(steps);
  const allDone = frac >= 1;

  return (
    <div className="pviz-scrim" onClick={onClose}>
      <aside className="pviz" role="dialog" aria-label="Generation pipeline" onClick={(e) => e.stopPropagation()}>
        <header className="pviz-head">
          <div className="pviz-head-row">
            <span className="pviz-title">{allDone ? "Skin ready" : "Building your skin"}</span>
            {modelLabel && <span className="pviz-model">{modelLabel}</span>}
            <button className="pviz-x" onClick={onClose} title="Dismiss (generation keeps running)" aria-label="Dismiss">×</button>
          </div>
          <div className="pviz-bar"><div className="pviz-bar-fill" style={{ width: `${Math.round(frac * 100)}%` }} /></div>
        </header>

        <ol className="pviz-list">
          {STAGES.map((stage) => {
            const st = steps[stage.id];
            return (
              <li key={stage.id} className={`pviz-step ${st.status}`}>
                <span className="pviz-node" aria-hidden="true">
                  {st.status === "running" ? <span className="pviz-spin" />
                    : st.status === "done" ? <span className="pviz-check">✓</span>
                    : st.status === "failed" ? "✕"
                    : stage.glyph}
                </span>
                <div className="pviz-txt">
                  <div className="pviz-lbl">{stage.label}</div>
                  <div className="pviz-blurb">
                    {stage.blurb}
                    {st.status === "running" && <span className="pviz-dots" />}
                  </div>
                  {st.note && <div className="pviz-note">{st.note}</div>}
                </div>
                <span className={`pviz-thumb ${st.artifact ? "" : "empty"} ${st.status === "running" ? "running" : ""}`}>
                  {st.artifact && <img src={st.artifact} alt={`${stage.label} output`} />}
                </span>
              </li>
            );
          })}
        </ol>

        <footer className={`pviz-foot ${allDone ? "done" : ""}`}>
          <span className="pviz-live">{allDone ? "●" : "◉"}</span>
          <span>{allDone ? "Done — you can close this." : current ? current : "Watching real pipeline · dismiss anytime, it keeps running."}</span>
        </footer>
      </aside>
    </div>
  );
}
