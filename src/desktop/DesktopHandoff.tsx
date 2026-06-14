// DesktopHandoff — the website → desktop-app bridge, shown in the sidebar.
//
// "Open in desktop player" navigates to skeuo://skin/<id>. If the Mac app is
// installed, macOS launches it already wearing this skin; if not, nothing
// visible happens (browsers can't tell us), so we always show "Download for
// Mac" right beside it as the fallback path.

import "./handoff.css";

const REPO = "https://github.com/connerkward/skeuo-ui";
const RELEASES = `${REPO}/releases/latest`;

export function DesktopHandoff({ skinId, skinName }: { skinId: string; skinName: string }) {
  const openDesktop = () => {
    // a hidden iframe avoids a "page can't be displayed" flash if the scheme
    // isn't registered; if it IS, the OS hands the URL to the app.
    const f = document.createElement("iframe");
    f.style.display = "none";
    f.src = `skeuo://skin/${encodeURIComponent(skinId)}`;
    document.body.appendChild(f);
    setTimeout(() => f.remove(), 1500);
  };

  return (
    <div className="dh-panel">
      <div className="dh-head">
        <span className="dh-dot" />
        <span className="dh-title">Desktop player</span>
      </div>
      <p className="dh-note">
        Run <b>{skinName}</b> as a transparent floating widget on your Mac,
        driving your real Spotify.
      </p>
      <div className="dh-row">
        <button className="dh-open" onClick={openDesktop} title={`skeuo://skin/${skinId}`}>
          ⤓ Open in desktop player
        </button>
        <a className="dh-dl" href={RELEASES} target="_blank" rel="noreferrer">
          Download for Mac
        </a>
      </div>
    </div>
  );
}
