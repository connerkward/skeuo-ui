import { useRef } from "react";

// Synth DISABLED (mock mode).
//
// This used to be a generative WebAudio engine (a detuned saw-chord pad through
// EQ → pan → volume → analyser) so every control made real sound. As a desktop
// widget that drives the user's Spotify, generating its own audio is just noise,
// so the synth is off: no AudioContext is ever created, nothing plays.
//
// The EQ/spectrum still animates because the Visualizer falls back to its built
// in mock animation whenever no AnalyserNode is supplied (we return a ref that
// stays null). The EQ sliders + curve readout remain live UI; they simply don't
// drive any audio. To bring the synth back, restore this file from git history.

export interface AudioState {
  playing: boolean;
  volume: number;
  balance: number;
  eqBands: number[];
  eqOn: boolean;
  muted: boolean;
  trackIdx: number;
  tone: { x: number; y: number };
}

// Arg kept so usePlayer's call site is unchanged; it's intentionally ignored.
export function useAudio(_s: AudioState): React.RefObject<AnalyserNode | null> {
  return useRef<AnalyserNode | null>(null);
}
