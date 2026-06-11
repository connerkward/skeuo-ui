import { useEffect, useRef, useState } from "react";
import { skinContent, type Track } from "./data";
import { useAudio } from "./useAudio";

// EQ preset shapes (PRE + 10 bands), selected by the segmented control.
export const EQ_PRESETS: Record<string, number[]> = {
  FLAT: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
  ROCK: [0.62, 0.82, 0.7, 0.55, 0.42, 0.4, 0.5, 0.66, 0.78, 0.82, 0.8],
  POP:  [0.55, 0.42, 0.5, 0.66, 0.78, 0.8, 0.72, 0.56, 0.46, 0.44, 0.46],
  JAZZ: [0.58, 0.7, 0.6, 0.5, 0.56, 0.62, 0.58, 0.5, 0.54, 0.64, 0.7],
};
export const PRESET_NAMES = Object.keys(EQ_PRESETS);

// All live player state. Every control maps to a real action here.
export function usePlayer(skinId: string) {
  const content = skinContent[skinId] ?? skinContent.winamp;
  const [tracks, setTracks] = useState<Track[]>(content.tracks);
  const [trackIdx, setTrackIdx] = useState(1);
  const [playing, setPlaying] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [volume, setVolume] = useState(0.72);
  const [balance, setBalance] = useState(0.5);
  const [shuffle, setShuffle] = useState(false);
  const [repeatMode, setRepeatMode] = useState(2);          // 0 off · 1 one · 2 all
  const [eqOn, setEqOn] = useState(true);
  const [eqAuto, setEqAuto] = useState(false);
  const [eqPreset, setEqPreset] = useState(0);
  const [eqBands, setEqBands] = useState<number[]>(() => [...EQ_PRESETS.ROCK]);
  const [tone, setTone] = useState({ x: 0.5, y: 0.55 });     // xy pad → pan + tilt
  const [muted, setMuted] = useState(false);

  // reset the (mutable) playlist when the skin's content changes
  useEffect(() => { setTracks(content.tracks); setTrackIdx((i) => Math.min(i, content.tracks.length - 1)); }, [content]);

  const analyser = useAudio({ playing, volume, balance, eqBands, eqOn, muted, trackIdx, tone });

  const safeIdx = Math.min(trackIdx, tracks.length - 1);
  const track = tracks[safeIdx] ?? tracks[0];
  const len = tracks.length;
  const lenRef = useRef(len); lenRef.current = len;
  const trackRef = useRef(track); trackRef.current = track;

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      setElapsed((e) => {
        if (e + 1 >= (trackRef.current?.seconds ?? 1)) {
          if (repeatMode !== 1) setTrackIdx((i) => (i + 1) % lenRef.current);
          return 0;
        }
        return e + 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [playing, repeatMode]);

  const select = (i: number) => { setTrackIdx(i); setElapsed(0); };
  const next = () => select(shuffle ? Math.floor(Math.random() * len) : (safeIdx + 1) % len);
  const prev = () => select((safeIdx - 1 + len) % len);

  // playlist mutation (ADD / REM / SEL / MISC) — all visibly functional
  const addTrack = () => setTracks((t) => {
    const c = t[Math.min(safeIdx, t.length - 1)];
    const copy = [...t]; copy.splice(safeIdx + 1, 0, { ...c }); return copy;
  });
  const removeTrack = () => setTracks((t) => {
    if (t.length <= 1) return t;
    const copy = t.filter((_, j) => j !== safeIdx);
    setTrackIdx((i) => Math.min(i, copy.length - 1));
    return copy;
  });
  const sortList = () => setTracks((t) => {
    const copy = [...t];
    for (let i = copy.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [copy[i], copy[j]] = [copy[j], copy[i]]; }
    return copy;
  });

  return {
    content, tracks, track, trackIdx: safeIdx, analyser,
    playing, elapsed, volume, balance, shuffle, repeatMode,
    eqOn, eqAuto, eqPreset, eqBands, tone, muted,
    toggleMute: () => setMuted((v) => !v),
    setVolume, setBalance, setTone,
    setEqBand: (i: number, v: number) => { setEqBands((b) => b.map((x, j) => (j === i ? v : x))); },
    setEqOn,
    setEqAuto: (fn: (v: boolean) => boolean) => { setEqAuto((v) => { const nv = fn(v); if (nv) setEqPreset((p) => { const np = (p + 1) % PRESET_NAMES.length; setEqBands([...EQ_PRESETS[PRESET_NAMES[np]]]); return np; }); return nv; }); },
    setEqPreset: (i: number) => { setEqPreset(i); setEqBands([...EQ_PRESETS[PRESET_NAMES[i]]]); },
    setRepeatMode,
    toggleShuffle: () => setShuffle((v) => !v),
    play: () => setPlaying(true),
    pause: () => setPlaying((p) => !p),
    stop: () => { setPlaying(false); setElapsed(0); },
    eject: () => select(0),
    seekTo: (v: number) => setElapsed(Math.round(v * (track?.seconds ?? 0))),
    select, next, prev, addTrack, removeTrack, sortList,
  };
}

export type PlayerState = ReturnType<typeof usePlayer>;
