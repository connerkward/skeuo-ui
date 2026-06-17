// Generate public/og-image.png (1200x630) from existing skin frames + skeuo.fm wordmark.
// Resvg renders an SVG that composes three canted skin players on a dark stage with
// the brand mark + tagline. Run: node scripts/make-og.cjs
const fs = require('fs');
const path = require('path');
const { Resvg } = require('@resvg/resvg-js');

const ROOT = path.resolve(__dirname, '..');
const W = 1200, H = 630;

function dataUri(p) {
  const b = fs.readFileSync(path.join(ROOT, p));
  return 'data:image/png;base64,' + b.toString('base64');
}

// Three frames: blue translucent (bondi), military (halo), chrome cthulhu (vortex).
const bondi = dataUri('public/skins/bondi/frame.png');   // 1696x2528
const halo  = dataUri('public/skins/halo/frame.png');    // 1024x1536
const vortex = dataUri('public/skins/vortex/frame.png');  // 1024x1536

// Embed the favicon as a sized <image> (a bare inline <svg> with no width/height
// expands to fill the parent in Resvg). data: URI keeps the 64x64 box exact.
const faviconUri = 'data:image/svg+xml;base64,' +
  fs.readFileSync(path.join(ROOT, 'public/favicon.svg')).toString('base64');

// Player display: keep a 1024:1536 (2:3) display box; scale frames to fit it.
function player(href, x, y, w, rot) {
  const h = w * 1536 / 1024;
  return `
  <g transform="translate(${x} ${y}) rotate(${rot})" filter="url(#drop)">
    <image href="${href}" x="${-w/2}" y="${-h/2}" width="${w}" height="${h}"
           preserveAspectRatio="xMidYMid meet"/>
  </g>`;
}

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <radialGradient id="bg" cx="62%" cy="78%" r="95%">
      <stop offset="0" stop-color="#16241d"/>
      <stop offset=".5" stop-color="#0f1216"/>
      <stop offset="1" stop-color="#080a0c"/>
    </radialGradient>
    <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#000" stop-opacity="0"/>
      <stop offset="1" stop-color="#000" stop-opacity=".55"/>
    </linearGradient>
    <filter id="drop" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="26" stdDeviation="30" flood-color="#000" flood-opacity=".7"/>
    </filter>
  </defs>

  <rect width="${W}" height="${H}" fill="url(#bg)"/>
  <rect x="0" y="${H*0.55}" width="${W}" height="${H*0.45}" fill="url(#floor)"/>

  <!-- player trio, right side, fanned. width = display box width; height auto 2:3 -->
  ${player(vortex, 1075, 330, 190, 8)}
  ${player(halo,   1000, 300, 198, -2)}
  ${player(bondi,  885, 318, 232, -7)}

  <!-- brand knob (favicon), 56x56 -->
  <image href="${faviconUri}" x="72" y="56" width="58" height="58"/>

  <!-- wordmark -->
  <text x="144" y="100" font-family="ui-sans-serif, -apple-system, Helvetica, Arial, sans-serif"
        font-size="52" font-weight="800" letter-spacing="-1.2" fill="#e8eaef">skeuo<tspan fill="#2dff6e">.fm</tspan></text>

  <!-- headline -->
  <text x="72" y="290" font-family="ui-sans-serif, -apple-system, Helvetica, Arial, sans-serif"
        font-size="52" font-weight="800" letter-spacing="-1" fill="#f3f5f8">A sentence becomes</text>
  <text x="72" y="350" font-family="ui-sans-serif, -apple-system, Helvetica, Arial, sans-serif"
        font-size="52" font-weight="800" letter-spacing="-1" fill="#f3f5f8">a <tspan fill="#5cc8ff">real music player</tspan>.</text>

  <!-- subhead -->
  <text x="74" y="418" font-family="ui-monospace, SFMono-Regular, Menlo, monospace"
        font-size="22" fill="#9aa0ab">AI-generated skeuomorphic body</text>
  <text x="74" y="450" font-family="ui-monospace, SFMono-Regular, Menlo, monospace"
        font-size="22" fill="#9aa0ab">+ working controls driving real Spotify.</text>

  <!-- url chip -->
  <g transform="translate(74 502)">
    <rect x="0" y="0" width="232" height="42" rx="21" fill="#15171c" stroke="#2a2e36" stroke-width="1.5"/>
    <circle cx="26" cy="21" r="5" fill="#2dff6e"/>
    <text x="44" y="29" font-family="ui-monospace, Menlo, monospace" font-size="19" fill="#cfd4dc"
          letter-spacing=".5">skeuo.fm</text>
  </g>
</svg>`;

const resvg = new Resvg(svg, { background: 'transparent', fitTo: { mode: 'width', value: W } });
const png = resvg.render().asPng();
const out = path.join(ROOT, 'public/og-image.png');
fs.writeFileSync(out, png);
console.log('wrote', out, png.length, 'bytes');
