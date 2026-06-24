// Per-skin "now playing" flavor + a shared playlist. Each skin overrides the
// track list so the content reads in-world (Winamp demo MP3s, Fallout radio,
// Warcraft 3 score), but the structure is identical so the UI is skin-agnostic.

export interface Track {
  artist: string;
  title: string;
  seconds: number;
  cover?: string;   // album-art URL (real when Spotify-driven; absent for the mock playlists → CD/art uses a CSS fallback)
}

export interface SkinContent {
  station: string;        // text under the title bar / display header
  bitrate: string;        // e.g. "192" kbps
  khz: string;            // e.g. "44"
  tracks: Track[];
}

export const EQ_BANDS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"];

export const skinContent: Record<string, SkinContent> = {
  pebble: {
    station: "LILYPAD FM  ·  minimal mode",
    bitrate: "128",
    khz: "44",
    tracks: [
      { artist: "Ribbit", title: "Pond Loop", seconds: 184 },
      { artist: "Lo-Fi Toad", title: "Lily Drift", seconds: 211 },
      { artist: "Marsh", title: "Reeds at Dusk", seconds: 167 },
    ],
  },
  obelisk: {
    station: "OSSUARY 7  ·  vertebral relay",
    bitrate: "192",
    khz: "48",
    tracks: [
      { artist: "Lustmord", title: "Spine of the Tower", seconds: 402 },
      { artist: "Sunn O)))", title: "Marrow Drone", seconds: 511 },
      { artist: "Author & Punisher", title: "Fused Vertebrae", seconds: 286 },
      { artist: "Godflesh", title: "Bone Cabling", seconds: 254 },
      { artist: "Perturbator", title: "Horned Skull", seconds: 298 },
    ],
  },
  slab: {
    station: "WAR SLAB  ·  treaded chassis net",
    bitrate: "256",
    khz: "44",
    tracks: [
      { artist: "Front Line Assembly", title: "Tread Column", seconds: 312 },
      { artist: "KMFDM", title: "Vent Stack", seconds: 247 },
      { artist: "Ministry", title: "Antenna Array", seconds: 289 },
      { artist: "Gesaffelstein", title: "Squat Broad", seconds: 233 },
      { artist: "Justice", title: "Genesis (Chassis Mix)", seconds: 226 },
    ],
  },
  wmp: {
    station: "WMP9  ·  Now Playing · TradeSend Trance",
    bitrate: "160",
    khz: "44",
    tracks: [
      { artist: "009 Sound System", title: "Dreamscape", seconds: 339, cover: "/demo-covers/009-sound-system-dreamscape.jpg" },
      { artist: "009 Sound System", title: "With a Spirit", seconds: 312, cover: "/demo-covers/009-sound-system-with-a-spir.jpg" },
      { artist: "TradeSend", title: "Trance — Sound System Drea", seconds: 519 },
      { artist: "Darude", title: "Sandstorm", seconds: 225, cover: "/demo-covers/darude-sandstorm.jpg" },
      { artist: "Robert Miles", title: "Children (Dream Version)", seconds: 297, cover: "/demo-covers/robert-miles-children.jpg" },
      { artist: "ATB", title: "9 PM (Till I Come)", seconds: 212, cover: "/demo-covers/atb-9-pm-till-i-come.jpg" },
      { artist: "Alice Deejay", title: "Better Off Alone", seconds: 214, cover: "/demo-covers/alice-deejay-better-off-alon.jpg" },
      { artist: "Zombie Nation", title: "Kernkraft 400", seconds: 318, cover: "/demo-covers/zombie-nation-kernkraft-400.jpg" },
    ],
  },
  halo: {
    station: "UNSC TACCOM  ·  In Amber Clad relay",
    bitrate: "192",
    khz: "44",
    tracks: [
      { artist: "Martin O'Donnell", title: "Halo Theme (MJOLNIR Mix)", seconds: 261 },
      { artist: "Breaking Benjamin", title: "Blow Me Away", seconds: 209 },
      { artist: "Martin O'Donnell", title: "Peril", seconds: 229 },
      { artist: "Martin O'Donnell", title: "Heretic, Hero", seconds: 219 },
      { artist: "Incubus", title: "Follow (1st Movement of the Odyssey)", seconds: 437 },
      { artist: "Martin O'Donnell", title: "In Amber Clad", seconds: 144 },
      { artist: "Martin O'Donnell", title: "Unforgotten", seconds: 175 },
      { artist: "Hoobastank", title: "Connected", seconds: 235 },
    ],
  },
  winamp: {
    station: "WINAMP  ·  llama-whipping superhighway",
    bitrate: "192",
    khz: "44",
    tracks: [
      { artist: "DJ Mike Llama", title: "Llama Whippin' Intro", seconds: 8 },
      { artist: "Bran Van 3000", title: "Drinking in L.A. (Radio Edit)", seconds: 244, cover: "/demo-covers/drinking-in-la.jpg" },
      { artist: "Fatboy Slim", title: "Praise You", seconds: 343, cover: "/demo-covers/praise-you.jpg" },
      { artist: "The Crystal Method", title: "Busy Child", seconds: 437, cover: "/demo-covers/busy-child.jpg" },
      { artist: "Daft Punk", title: "Around the World", seconds: 429, cover: "/demo-covers/around-the-world.jpg" },
      { artist: "Aphex Twin", title: "Windowlicker", seconds: 366, cover: "/demo-covers/windowlicker.jpg" },
      { artist: "Moby", title: "Porcelain", seconds: 240, cover: "/demo-covers/porcelain.jpg" },
      { artist: "Underworld", title: "Born Slippy .NUXX", seconds: 569, cover: "/demo-covers/born-slippy.jpg" },
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
  fantasy: {
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
  aqua: {
    station: "iTUNES 4  ·  Mac OS X 10.2 Jaguar",
    bitrate: "320",
    khz: "44",
    tracks: [
      { artist: "Röyksopp", title: "Eple", seconds: 234 },
      { artist: "Air", title: "La Femme d'Argent", seconds: 429 },
      { artist: "Zero 7", title: "In the Waiting Line", seconds: 267 },
      { artist: "Thievery Corporation", title: "Lebanese Blonde", seconds: 251 },
      { artist: "Boards of Canada", title: "Roygbiv", seconds: 161 },
      { artist: "Bonobo", title: "Kiara", seconds: 247 },
      { artist: "Télépopmusik", title: "Breathe", seconds: 281 },
      { artist: "Lemon Jelly", title: "Nice Weather for Ducks", seconds: 300 },
    ],
  },
  hifi: {
    station: "FM 98.7  ·  Quadraphonic · Dolby NR",
    bitrate: "LP",
    khz: "33⅓",
    tracks: [
      { artist: "Fleetwood Mac", title: "The Chain", seconds: 268 },
      { artist: "Steely Dan", title: "Aja", seconds: 480 },
      { artist: "Pink Floyd", title: "Money", seconds: 382 },
      { artist: "Stevie Wonder", title: "Sir Duke", seconds: 232 },
      { artist: "The Doobie Brothers", title: "Long Train Runnin'", seconds: 199 },
      { artist: "Earth, Wind & Fire", title: "September", seconds: 215 },
      { artist: "Boston", title: "More Than a Feeling", seconds: 285 },
      { artist: "Supertramp", title: "The Logical Song", seconds: 241 },
    ],
  },
  papercraft: {
    station: "MIXTAPE  ·  hand-folded · side A",
    bitrate: "96",
    khz: "22",
    tracks: [
      { artist: "Sufjan Stevens", title: "Chicago", seconds: 226 },
      { artist: "The Postal Service", title: "Such Great Heights", seconds: 266 },
      { artist: "Feist", title: "1234", seconds: 183 },
      { artist: "Beirut", title: "Postcards from Italy", seconds: 251 },
      { artist: "Of Monsters and Men", title: "Little Talks", seconds: 266 },
      { artist: "Edward Sharpe", title: "Home", seconds: 305 },
      { artist: "Vampire Weekend", title: "A-Punk", seconds: 137 },
      { artist: "Fleet Foxes", title: "White Winter Hymnal", seconds: 147 },
    ],
  },
  frog: {
    station: "LILYPAD FM  ·  ribbit radio 24/7",
    bitrate: "64", khz: "22",
    tracks: [
      { artist: "Crazy Frog", title: "Axel F", seconds: 169 },
      { artist: "Paul McCartney", title: "We All Stand Together", seconds: 263 },
      { artist: "Kermit", title: "Rainbow Connection", seconds: 195 },
      { artist: "Hypnotoad", title: "ALL GLORY (loop)", seconds: 600 },
      { artist: "Les Claypool", title: "Amphibian", seconds: 312 },
      { artist: "Beck", title: "Hollow Log", seconds: 106 },
      { artist: "Aphex Twin", title: "Vordhosbn", seconds: 284 },
      { artist: "Squarepusher", title: "Tommib", seconds: 80 },
    ],
  },
  burger: {
    station: "DRIVE-THRU FM  ·  hot & fresh",
    bitrate: "256", khz: "44",
    tracks: [
      { artist: "Jimmy Buffett", title: "Cheeseburger in Paradise", seconds: 172 },
      { artist: "Weird Al", title: "Eat It", seconds: 199 },
      { artist: "Smashing Pumpkins", title: "Mayonaise", seconds: 353 },
      { artist: "Booker T & the MGs", title: "Green Onions", seconds: 175 },
      { artist: "Herb Alpert", title: "Whipped Cream", seconds: 155 },
      { artist: "Jack White", title: "Sixteen Saltines", seconds: 158 },
      { artist: "Fats Domino", title: "Blueberry Hill", seconds: 148 },
      { artist: "The B-52s", title: "Rock Lobster", seconds: 411 },
    ],
  },
  bondi: {
    station: "iTUNES PREVIEW  ·  bondi blue build",
    bitrate: "192", khz: "44",
    tracks: [
      { artist: "Eiffel 65", title: "Blue (Da Ba Dee)", seconds: 280 },
      { artist: "Daft Punk", title: "Digital Love", seconds: 301 },
      { artist: "Lenny Kravitz", title: "Fly Away", seconds: 221 },
      { artist: "Smash Mouth", title: "All Star", seconds: 200 },
      { artist: "Cher", title: "Believe", seconds: 239 },
      { artist: "Moby", title: "Bodyrock", seconds: 215 },
      { artist: "Jamiroquai", title: "Canned Heat", seconds: 332 },
      { artist: "Fatboy Slim", title: "Right Here Right Now", seconds: 386 },
    ],
  },
  toilet: {
    station: "PORCELAIN PALACE  ·  royal flush",
    bitrate: "96", khz: "32",
    tracks: [
      { artist: "TLC", title: "Waterfalls", seconds: 274 },
      { artist: "Handel", title: "Water Music — Allegro", seconds: 192 },
      { artist: "CCR", title: "Have You Ever Seen the Rain", seconds: 160 },
      { artist: "Toto", title: "Africa", seconds: 295 },
      { artist: "Prince", title: "Purple Rain", seconds: 520 },
      { artist: "Milli Vanilli", title: "Blame It on the Rain", seconds: 257 },
      { artist: "Gene Kelly", title: "Singin' in the Rain", seconds: 213 },
      { artist: "The Weather Girls", title: "It's Raining Men", seconds: 326 },
    ],
  },
  biomech: {
    station: "HIVE CLUSTER  ·  spawning pool ambience",
    bitrate: "13", khz: "13",
    tracks: [
      { artist: "Diablo Swing Orchestra", title: "Heroines", seconds: 322 },
      { artist: "Nine Inch Nails", title: "The Becoming", seconds: 331 },
      { artist: "Tool", title: "Parabol", seconds: 184 },
      { artist: "Igorrr", title: "Very Noise", seconds: 124 },
      { artist: "Meshuggah", title: "Bleed", seconds: 444 },
      { artist: "Aphex Twin", title: "Come to Daddy", seconds: 274 },
      { artist: "SOPHIE", title: "Faceshopping", seconds: 224 },
      { artist: "Mr. Bungle", title: "None of Them Knew They Were Robots", seconds: 366 },
    ],
  },
};

export function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
