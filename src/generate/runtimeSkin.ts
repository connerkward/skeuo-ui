import type { DonorStyle } from "./pipeline";
import type { Template } from "../template/schema";

// A skin produced at runtime by POST /api/generate — frame (public URL) + its
// template, registered client-side and selected immediately. (Re-homed here from the
// retired CreatePanel; CreateWizard is the live create UI.)
export interface RuntimeSkin {
  id: string;
  name: string;
  blurb: string;
  style: DonorStyle;    // donor for sprites/palette (resolves via [data-skin])
  frameUrl: string;
  template: Template;
  // true when the pipeline produced per-skin control sprites for THIS skin
  // (served at /api/asset/skins/<id>/sprites/<bind>.png). When set, the player
  // renders those instead of the donor style's bundled sprites.
  sprites?: boolean;
  font?: string;        // logomark display font (Director pick); falls back to Cinzel
  hidden?: boolean;     // hidden from the gallery, but KEPT in storage (raw materials
                        // are never destroyed — "delete" = hide for future processing)
}
