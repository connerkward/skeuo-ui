import { useEffect, useRef, useState } from "react";
import { skinContent } from "./data";

// All live player state, decoupled from rendering so both the compositor and
// any region renderer can read/drive it. This is the "dynamic" half of the
// system — none of it is ever baked into a sprite.
export function usePlayer(skinId: string) {
  const content = skinContent[skinId] ?? skinContent.winamp;
  const [trackIdx, setTrackIdx] = useState(1);
  const [playing, setPlaying] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [volume, setVolume] = useState(0.78);
  const [balance, setBalance] = useState(0.5);
  const [shuffle, setShuffle] = useState(false);
  const [repeat, setRepeat] = useState(false);
  const [eqOn, setEqOn] = useState(true);
  const [eqAuto, setEqAuto] = useState(false);
  const [eqBands, setEqBands] = useState<number[]>(
    () => [0.62, 0.7, 0.58, 0.5, 0.46, 0.5, 0.56, 0.64, 0.7, 0.66, 0.6]
  );

  const track = content.tracks[trackIdx];
  const trackRef = useRef(track);
  trackRef.current = track;

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      setElapsed((e) => {
        if (e + 1 >= trackRef.current.seconds) {
          setTrackIdx((i) => (repeat ? i : (i + 1) % content.tracks.length));
          return 0;
        }
        return e + 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [playing, repeat, content.tracks.length]);

  const select = (i: number) => { setTrackIdx(i); setElapsed(0); };
  const next = () => select(shuffle
    ? Math.floor(Math.random() * content.tracks.length)
    : (trackIdx + 1) % content.tracks.length);
  const prev = () => select((trackIdx - 1 + content.tracks.length) % content.tracks.length);

  return {
    content, track, trackIdx,
    playing, elapsed, volume, balance, shuffle, repeat, eqOn, eqAuto, eqBands,
    setVolume, setBalance,
    setEqBand: (i: number, v: number) => setEqBands((b) => b.map((x, j) => (j === i ? v : x))),
    setEqOn, setEqAuto,
    toggleShuffle: () => setShuffle((v) => !v),
    toggleRepeat: () => setRepeat((v) => !v),
    play: () => setPlaying(true),
    pause: () => setPlaying((p) => !p),
    stop: () => { setPlaying(false); setElapsed(0); },
    eject: () => select(0),
    seekTo: (v: number) => setElapsed(Math.round(v * track.seconds)),
    select, next, prev,
  };
}

export type PlayerState = ReturnType<typeof usePlayer>;
