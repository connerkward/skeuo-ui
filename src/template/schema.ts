/* ============================================================
   TEMPLATE SCHEMA  —  the single source of truth.

   A designer authors ONE Template: the canvas size and a flat list
   of Regions, each with a normalized rect, a kind (what widget it
   is), a content type (baked sprite vs. live dynamic content) and a
   z-layer (which styling layer it belongs to).

   The SAME template drives two consumers:
     1. the wireframe exporter — renders a labeled mockup + per-layer
        masks to hand to an image model for styling "in layers".
     2. the runtime compositor — lays widgets out at identical coords,
        so generated art and live React content always line up.
   ============================================================ */

// Which styling layer a region belongs to. The model styles each layer
// separately; the compositor stacks them in this order.
export type Layer = "frame" | "screen" | "components";

// What the region IS.
export type Kind =
  | "button"      // momentary press (transport, playlist ops)
  | "toggle"      // on/off state (shuffle, repeat, EQ on)
  | "slider-h"    // horizontal (seek, volume, balance)
  | "slider-v"    // vertical (EQ bands)
  | "display";    // a recessed screen that hosts dynamic content

// How the region's pixels are produced.
//   "sprite"  → baked into the generated art; React only adds an
//               invisible interactive hit-target / state filter on top.
//   "dynamic" → the art layer leaves this area BLANK (a styled empty
//               screen); React renders live content into it at runtime.
export type Content = "sprite" | "dynamic";

// For dynamic regions, what live content to render.
export type DynamicType =
  | "time"        // elapsed clock
  | "visualizer"  // spectrum analyzer
  | "marquee"     // scrolling track title
  | "meta"        // kbps / kHz / stereo
  | "minislider"  // vol/bal pair (still interactive, but live-rendered)
  | "eq-curve"    // EQ response line
  | "playlist"    // track rows
  | "title";      // station / window title text

// Normalized rect: x,y = top-left, all in [0,1] of the canvas.
export type Rect = { x: number; y: number; w: number; h: number };

export interface Region {
  id: string;
  kind: Kind;
  content: Content;
  layer: Layer;
  rect: Rect;
  label?: string;        // shown in the wireframe + used as a11y title
  dynamicType?: DynamicType;
  bind?: string;         // which player-state field this control drives
  group?: string;        // optional grouping (e.g. "eq-bands") for the band index
  index?: number;        // position within a group
}

export interface Template {
  id: string;
  name: string;
  // Canvas pixel size the art is generated at — defines the aspect ratio.
  canvas: { w: number; h: number };
  regions: Region[];
}
