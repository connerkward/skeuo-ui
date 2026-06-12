/* ============================================================
   TEMPLATE SCHEMA  —  the single source of truth.

   A designer authors ONE Template: the canvas size and a flat list
   of Regions, each with a normalized rect, a kind (what it is), a
   content type (baked sprite / live dynamic / pure decoration) and a
   z-layer (which styling layer it belongs to).

   The SAME template drives two consumers:
     1. the wireframe / control exporter — renders a labeled blueprint
        to hand to an image model for styling "in layers".
     2. the runtime compositor — lays widgets out at identical coords,
        so generated art and live React content always line up.
   ============================================================ */

export type Layer = "frame" | "screen" | "components";

// What the region IS.
export type Kind =
  | "button"      // momentary press
  | "toggle"      // on/off state
  | "slider-h"    // horizontal slider
  | "slider-v"    // vertical slider
  | "knob"        // rotary knob (drag to turn)
  | "segmented"   // pick one of N segments
  | "xy"          // 2D pad (drag a puck)
  | "display"     // recessed screen hosting dynamic content
  | "flourish";   // pure decoration — non-interactive ornament

// How the region's pixels are produced.
//   "sprite"     → baked into the generated art; React adds an invisible
//                  interactive hit-target / moving part on top.
//   "dynamic"    → art leaves the area blank; React renders live content.
//   "decoration" → baked art ONLY; no runtime element at all. These exist
//                  to give the model anchored space for ornament and to vary
//                  each skin's silhouette without touching the controls.
export type Content = "sprite" | "dynamic" | "decoration";

export type DynamicType =
  | "time" | "visualizer" | "marquee" | "meta"
  | "eq-curve" | "playlist" | "title";

export type Rect = { x: number; y: number; w: number; h: number };

export interface Region {
  id: string;
  kind: Kind;
  content: Content;
  layer: Layer;
  rect: Rect;
  label?: string;
  dynamicType?: DynamicType;
  bind?: string;          // which player-state field this control drives
  group?: string;         // grouping (e.g. "eq-bands")
  index?: number;         // position within a group
  options?: string[];     // segmented: the segment labels
  flourish?: string;      // decoration: a hint label (CORNER, RAIL, CREST…)
  shape?: "ellipse";      // round well: circular button face / elliptical glass
}

export interface Template {
  id: string;
  name: string;
  canvas: { w: number; h: number };
  regions: Region[];
}
