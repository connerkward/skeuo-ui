import { useEffect, useRef, useState } from "react";
import { skinContent } from "./data";

// EQ preset shapes (PRE + 10 bands), selected by the segmented control.
export const EQ_PRESETS: Record<string, number[]> = {
  FLAT: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
  ROCK: [0.62, 0.82, 0.7, 0.55, 0.42, 0.4, 0.5, 0.66, 0.78, 0.82, 0.8],
  POP:  [0.55, 0.42, 0.5, 0.66, 0.78, 0.8, 0.72, 0.56, 0.46, 0.44, 0.46],
  JAZZ: [0.58, 0.7, 0.6, 0.5, 0.56, 0.62, 0.58, 0.5, 0.54, 0.64, 0.7],
};
export const PRESET_NAMES = Object.keys(EQ_PRESETS);

// All live player state, decoupled from rendering. The "dynamic" half of the
// system — none of it is ever baked into a sprite.
export function usePlayer(skinId: string) {
  const content = skinContent[skinId] ?? skinContent.winamp;
  const [trackIdx, setTrackIdx] = useState(1);
  const [playing, setPlaying] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [volume, setVolume] = useState(0.72);
  const [balance, setBalance] = useState(0.5);
  const [shuffle, setShuffle] = useState(false);
  const [repeatMode, setRepeatMode] = useState(2);          // 0 off · 1 one · 2 all
  const [eqOn, setEqOn] = useState(true);
  const [eqAuto, setEqAuto] = useState(false);
  const [eqPreset, setEqPreset] = useState(0);               // index into PRESET_NAMES
  const [eqBands, setEqBands] = useState<number[]>(() => [...EQ_PRESETS.ROCK]);
  const [tone, setTone] = useState({ x: 0.5, y: 0.55 });     // xy pad

  const track = content.tracks[trackIdx];
  const trackRef = useRef(track);
  trackRef.current = track;

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      setElapsed((e) => {
        if (e + 1 >= trackRef.current.seconds) {
          if (repeatMode !== 1) setTrackIdx((i) => (i + 1) % content.tracks.length);
          return 0;
        }
        return e + 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [playing, repeatMode, content.tracks.length]);

  const select = (i: number) => { setTrackIdx(i); setElapsed(0); };
  const next = () => select(shuffle
    ? Math.floor(Math.random() * content.tracks.length)
    : (trackIdx + 1) % content.tracks.length);
  const prev = () => select((trackIdx - 1 + content.tracks.length) % content.tracks.length);

  return {
    content, track, trackIdx,
    playing, elapsed, volume, balance, shuffle, repeatMode,
    eqOn, eqAuto, eqPreset, eqBands, tone,
    setVolume, setBalance, setTone,
    setEqBand: (i: number, v: number) => { setEqBands((b) => b.map((x, j) => (j === i ? v : x))); },
    setEqOn, setEqAuto,
    setEqPreset: (i: number) => { setEqPreset(i); setEqBands([...EQ_PRESETS[PRESET_NAMES[i]]]); },
    setRepeatMode,
    toggleShuffle: () => setShuffle((v) => !v),
    play: () => setPlaying(true),
    pause: () => setPlaying((p) => !p),
    stop: () => { setPlaying(false); setElapsed(0); },
    eject: () => select(0),
    seekTo: (v: number) => setElapsed(Math.round(v * track.seconds)),
    select, next, prev,
  };
}

export type PlayerState = ReturnType<typeof usePlayer>;
