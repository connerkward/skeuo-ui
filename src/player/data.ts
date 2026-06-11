// Per-skin "now playing" flavor + a shared playlist. Each skin overrides the
// track list so the content reads in-world (Winamp demo MP3s, Fallout radio,
// Warcraft 3 score), but the structure is identical so the UI is skin-agnostic.

export interface Track {
  artist: string;
  title: string;
  seconds: number;
}

export interface SkinContent {
  station: string;        // text under the title bar / display header
  bitrate: string;        // e.g. "192" kbps
  khz: string;            // e.g. "44"
  tracks: Track[];
}

export const EQ_BANDS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"];

export const skinContent: Record<string, SkinContent> = {
  winamp: {
    station: "WINAMP  ·  llama-whipping superhighway",
    bitrate: "192",
    khz: "44",
    tracks: [
      { artist: "DJ Mike Llama", title: "Llama Whippin' Intro", seconds: 8 },
      { artist: "Bran Van 3000", title: "Drinking in L.A. (Radio Edit)", seconds: 244 },
      { artist: "Fatboy Slim", title: "Praise You", seconds: 343 },
      { artist: "The Crystal Method", title: "Busy Child", seconds: 437 },
      { artist: "Daft Punk", title: "Around the World", seconds: 429 },
      { artist: "Aphex Twin", title: "Windowlicker", seconds: 366 },
      { artist: "Moby", title: "Porcelain", seconds: 240 },
      { artist: "Underworld", title: "Born Slippy .NUXX", seconds: 569 },
    ],
  },
  fallout: {
    station: "RADIO NEW VEGAS  ·  RobCo PIP-OS v7.1.0.8",
    bitrate: "128",
    khz: "22",
    tracks: [
      { artist: "The Ink Spots", title: "I Don't Want to Set the World on Fire", seconds: 188 },
      { artist: "Bing Crosby", title: "Dear Hearts and Gentle People", seconds: 165 },
      { artist: "Cole Porter", title: "Anything Goes", seconds: 201 },
      { artist: "Roy Brown", title: "Mighty, Mighty Man", seconds: 158 },
      { artist: "Eddy Arnold", title: "It's a Sin", seconds: 172 },
      { artist: "Jack Shaindlin", title: "Way Back Home", seconds: 144 },
      { artist: "Marty Robbins", title: "Big Iron", seconds: 236 },
      { artist: "Dean Martin", title: "Aint That a Kick in the Head", seconds: 137 },
    ],
  },
  warcraft: {
    station: "KINGDOM OF AZEROTH  ·  Score & Battle Themes",
    bitrate: "256",
    khz: "48",
    tracks: [
      { artist: "Tracy W. Bush", title: "Human Theme 1 — Reign of Chaos", seconds: 214 },
      { artist: "Glenn Stafford", title: "Orc Theme — Blood and Thunder", seconds: 232 },
      { artist: "Jason Hayes", title: "Undead Theme — The Scourge", seconds: 245 },
      { artist: "Derek Duke", title: "Night Elf Theme — Whisper of Trees", seconds: 268 },
      { artist: "Tracy W. Bush", title: "Arthas, My Son", seconds: 198 },
      { artist: "Glenn Stafford", title: "Power of the Horde", seconds: 221 },
      { artist: "Jason Hayes", title: "The Culling", seconds: 203 },
      { artist: "Derek Duke", title: "Illidan's Theme", seconds: 256 },
    ],
  },
};

export function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
