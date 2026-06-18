// Skeuo — Tauri shell for BOTH the macOS desktop widget and the iOS app.
//
// The webview loads the SAME React bundle as the website; Tauri injects its
// global so the frontend boots into the right mode (a transparent floating skin
// on desktop, the full-screen site on iOS). This Rust side does only what the
// web can't:
//   • register the skeuo:// scheme (web→desktop handoff + the system-browser
//     OAuth return both arrive as deep links / loopback)
//   • run the one-shot 127.0.0.1 loopback that captures the Spotify OAuth code
//   • DESKTOP ONLY: the menu-bar tray + hide-to-tray + window-state restore
// Everything tray/window related is desktop-gated — iOS has a single full-screen
// webview and none of that applies.

#[cfg(desktop)]
use tauri::Manager;

// (skin id, display name) for the desktop tray "Skins" submenu. Ids must match
// the registry in src/player/skins.ts.
#[cfg(desktop)]
const SKINS: &[(&str, &str)] = &[
    ("manray", "Man Ray"),
    ("pebble", "Pebble"),
    ("maw", "Angler Maw"),
    ("obelisk", "Bone Totem"),
    ("slab", "War Slab"),
    ("scarab", "Scarab"),
    ("vortex", "Vortex"),
    ("frog", "Froggo"),
    ("burger", "Burger Deluxe"),
    ("bondi", "Bondi"),
    ("biomech", "Biomech"),
    ("halo", "Halo"),
    ("wmp", "Media Capsule"),
];

// Tracks the desktop always-on-top state so the tray check item and the window
// stay in sync (the OS has no reliable getter we depend on).
#[cfg(desktop)]
struct AlwaysOnTop(std::sync::atomic::AtomicBool);

// One-shot loopback listener for the native OAuth redirect. Loopback
// (http://127.0.0.1) is the redirect type Spotify guarantees for native apps, so
// BOTH shells (macOS widget + iOS app) register http://127.0.0.1:14565/callback;
// we bind it, capture the ?code=... the system browser redirects to, reply with a
// small page, and hand the full callback URL back to JS for the PKCE exchange.
//
// On iOS the system browser (Safari) is a SEPARATE app, so after it loads the
// loopback URL the user is still in Safari — the reply page bounces to the app's
// OWN skeuo:// scheme (which Spotify never sees) to pull focus back to Skeuo.
#[tauri::command]
async fn oauth_loopback() -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(|| {
        use std::io::{Read, Write};
        use std::net::TcpListener;
        let listener = TcpListener::bind("127.0.0.1:14565").map_err(|e| e.to_string())?;
        let (mut stream, _) = listener.accept().map_err(|e| e.to_string())?;
        let mut buf = [0u8; 4096];
        let n = stream.read(&mut buf).map_err(|e| e.to_string())?;
        let req = String::from_utf8_lossy(&buf[..n]);
        // first request line: "GET /callback?code=... HTTP/1.1"
        let path = req
            .lines()
            .next()
            .and_then(|l| l.split_whitespace().nth(1))
            .unwrap_or("/")
            .to_string();
        // detect the iOS Safari UA so only the phone gets the skeuo:// bounce
        // (on desktop the same-app browser doesn't need it and would just prompt)
        let ua_mobile = req
            .lines()
            .find(|l| l.to_ascii_lowercase().starts_with("user-agent:"))
            .map(|l| {
                let l = l.to_ascii_lowercase();
                l.contains("iphone") || l.contains("ipad") || l.contains("ipod")
            })
            .unwrap_or(false);
        let body = if ua_mobile {
            "<!doctype html><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\">\
             <body style=\"font:17px -apple-system,system-ui,sans-serif;padding:48px 28px;color:#222;text-align:center\">\
             <p>Connected to Spotify.</p><p><a href=\"skeuo://connected\" style=\"color:#1db954;font-weight:600\">Return to Skeuo →</a></p>\
             <script>setTimeout(function(){location.replace('skeuo://connected')},350)</script></body>"
        } else {
            "<!doctype html><meta charset=utf-8>\
             <body style=\"font:16px -apple-system,system-ui,sans-serif;padding:48px;color:#222\">\
             Skeuo is connected to Spotify. You can close this tab and return to the widget.</body>"
        };
        let resp = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            body.len(),
            body
        );
        let _ = stream.write_all(resp.as_bytes());
        let _ = stream.flush();
        Ok(format!("http://127.0.0.1:14565{path}"))
    })
    .await
    .map_err(|e| e.to_string())?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default();

    // Desktop-only plugins: single-instance (forward a second skeuo:// launch) and
    // window-state (remember the widget's position/size). Neither applies on iOS.
    #[cfg(desktop)]
    {
        builder = builder
            .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.show();
                    let _ = w.set_focus();
                }
            }))
            .plugin(tauri_plugin_window_state::Builder::default().build())
            .manage(AlwaysOnTop(std::sync::atomic::AtomicBool::new(false)));
    }

    builder
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![oauth_loopback])
        .setup(|app| {
            #[cfg(desktop)]
            {
                // make sure skeuo:// resolves to us on dev / first run
                use tauri_plugin_deep_link::DeepLinkExt;
                let _ = app.deep_link().register_all();
                // restore the widget's last position + size; show on the current Space
                use tauri_plugin_window_state::{StateFlags, WindowExt};
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.restore_state(StateFlags::all());
                    let _ = w.set_visible_on_all_workspaces(true);
                }
                build_tray(app)?;
            }
            let _ = app; // silence unused-var on mobile (no setup work there)
            Ok(())
        })
        .on_window_event(|_window, _event| {
            // desktop: closing the widget hides it to the tray instead of quitting
            #[cfg(desktop)]
            if let tauri::WindowEvent::CloseRequested { api, .. } = _event {
                let _ = _window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Skeuo");
}

#[cfg(desktop)]
fn build_tray(app: &tauri::App) -> tauri::Result<()> {
    use tauri::menu::{CheckMenuItem, MenuBuilder, MenuItem, SubmenuBuilder};
    use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
    use tauri::Emitter;
    use std::sync::atomic::Ordering;

    // Skins submenu — each item carries id "skin:<id>"; the handler emits it.
    let mut skins = SubmenuBuilder::new(app, "Skins");
    for (id, name) in SKINS {
        let item = MenuItem::with_id(app, format!("skin:{id}"), *name, true, None::<&str>)?;
        skins = skins.item(&item);
    }
    let skins_menu = skins.build()?;

    let aot = CheckMenuItem::with_id(app, "toggle-aot", "Always on top", true, false, None::<&str>)?;
    let show = MenuItem::with_id(app, "show", "Show widget", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit Skeuo", true, None::<&str>)?;

    let menu = MenuBuilder::new(app)
        .item(&skins_menu)
        .separator()
        .item(&aot)
        .item(&show)
        .separator()
        .item(&quit)
        .build()?;

    let aot_item = aot.clone();
    TrayIconBuilder::with_id("main")
        .icon(app.default_window_icon().unwrap().clone())
        .icon_as_template(true)
        .tooltip("Skeuo")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(move |app, event| {
            let id = event.id().0.as_str();
            if let Some(skin) = id.strip_prefix("skin:") {
                let _ = app.emit("set-skin", skin.to_string());
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.show();
                    let _ = w.set_focus();
                }
                return;
            }
            match id {
                "toggle-aot" => {
                    let state = app.state::<AlwaysOnTop>();
                    let next = !state.0.load(Ordering::Relaxed);
                    state.0.store(next, Ordering::Relaxed);
                    let _ = aot_item.set_checked(next);
                    if let Some(w) = app.get_webview_window("main") {
                        let _ = w.set_always_on_top(next);
                    }
                }
                "show" => {
                    if let Some(w) = app.get_webview_window("main") {
                        let _ = w.unminimize();
                        let _ = w.show();
                        let _ = w.set_focus();
                    }
                }
                "quit" => {
                    use tauri_plugin_window_state::{AppHandleExt, StateFlags};
                    let _ = app.save_window_state(StateFlags::all());
                    app.exit(0);
                }
                _ => {}
            }
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(w) = app.get_webview_window("main") {
                    if w.is_visible().unwrap_or(false) {
                        let _ = w.hide();
                    } else {
                        let _ = w.unminimize();
                        let _ = w.show();
                        let _ = w.set_focus();
                    }
                }
            }
        })
        .build(app)?;

    Ok(())
}
