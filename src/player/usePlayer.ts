import { useEffect, useRef, useState } from "react";
import { skinContent, type Track } from "./data";
import { useAudio } from "./useAudio";
import type { SpotifyDrive } from "../spotify/useSpotify";

// EQ preset shapes (PRE + 10 bands), selected by the segmented control.
export const EQ_PRESETS: Record<string, number[]> = {
  FLAT: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
  ROCK: [0.62, 0.82, 0.7, 0.55, 0.42, 0.4, 0.5, 0.66, 0.78, 0.82, 0.8],
  POP:  [0.55, 0.42, 0.5, 0.66, 0.78, 0.8, 0.72, 0.56, 0.46, 0.44, 0.46],
  JAZZ: [0.58, 0.7, 0.6, 0.5, 0.56, 0.62, 0.58, 0.5, 0.54, 0.64, 0.7],
};
export const PRESET_NAMES = Object.keys(EQ_PRESETS);

// All live player state. Every control maps to a real action here.
//
// `drive` (optional) is the Spotify override: when present, the skin controls
// REAL Spotify playback and the screens reflect the polled current track /
// progress / volume / playlist. When absent, the local WebAudio demo runs
// exactly as before. The integration is a thin layer at the end of this hook —
// the WebAudio graph is muted in Spotify mode (real audio comes from Spotify),
// and the displayed values + transport actions are swapped for the drive's.
export function usePlayer(skinId: string, drive?: SpotifyDrive | null) {
  const spotify = !!drive;
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

  // In Spotify mode the demo oscillators stay silent (audio plays via Spotify);
  // the visualizer still animates off the analyser node, just with no signal.
  const analyser = useAudio({ playing: playing && !spotify, volume, balance, eqBands, eqOn, muted: muted || spotify, trackIdx, tone });

  const safeIdx = Math.min(trackIdx, tracks.length - 1);
  const track = tracks[safeIdx] ?? tracks[0];
  const len = tracks.length;
  const lenRef = useRef(len); lenRef.current = len;
  const trackRef = useRef(track); trackRef.current = track;

  useEffect(() => {
    if (spotify || !playing) return;     // Spotify mode: elapsed comes from polling
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
  }, [playing, repeatMode, spotify]);

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

  const local = {
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

  // SPOTIFY MODE: same shape, but displayed values + transport come from the
  // real-playback `drive`. EQ/tone/balance stay local cosmetic state (Spotify
  // has no per-stream EQ API), so those keep their local behavior; everything
  // the screens read (track/progress/volume/playlist) and every transport
  // action map to Spotify. trackIdx falls back to the local highlight when the
  // current track isn't found in the chosen playlist.
  if (drive) {
    const spTracks = drive.tracks.length ? drive.tracks : [drive.track];
    const spIdx = drive.trackIdx >= 0 ? drive.trackIdx : 0;
    return {
      ...local,
      tracks: spTracks,
      track: drive.track,
      trackIdx: spIdx,
      playing: drive.playing,
      elapsed: drive.elapsedSec,
      volume: drive.volume,
      shuffle: drive.shuffle,
      repeatMode: drive.repeatMode,
      setVolume: drive.setVolume,
      toggleShuffle: drive.toggleShuffle,
      setRepeatMode: (i: number) => { for (let k = 0; k < ((i - drive.repeatMode + 3) % 3); k++) drive.cycleRepeat(); },
      play: drive.play,
      pause: () => (drive.playing ? drive.pause() : drive.play()),
      stop: drive.pause,
      eject: () => drive.selectTrack(0),
      seekTo: (v: number) => drive.seekTo(v),
      select: (i: number) => drive.selectTrack(i),
      next: drive.next,
      prev: drive.prev,
      // playlist mutation has no Spotify analogue from this surface — no-op in
      // Spotify mode so the ADD/REM/SEL/MISC faces don't desync the real list
      addTrack: () => {}, removeTrack: () => {}, sortList: () => {},
    };
  }

  return local;
}

export type PlayerState = ReturnType<typeof usePlayer>;
