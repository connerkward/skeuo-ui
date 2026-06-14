// Skeuo desktop widget — Tauri shell.
//
// The webview loads the SAME React bundle as the website; Tauri injects its
// global so the frontend boots into widget mode (single transparent skin). This
// Rust side does only what the web can't:
//   • register the skeuo:// scheme + single-instance forwarding (web→desktop
//     handoff and the Spotify OAuth callback both arrive as deep links)
//   • build the menu-bar tray (switch skin, toggle always-on-top, show/quit)
//   • hide-to-tray on window close instead of quitting
// Skin switching and OAuth are handled in JS (see src/desktop/deeplink.ts); the
// tray just emits a `set-skin` event the webview listens for.

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{
    menu::{CheckMenuItem, MenuBuilder, MenuItem, SubmenuBuilder},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager, WindowEvent,
};

// (skin id, display name) for the tray "Skins" submenu. Ids must match the
// registry in src/player/skins.ts.
const SKINS: &[(&str, &str)] = &[
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

// Tracks the always-on-top state so the tray check item and the window stay in
// sync (the OS has no reliable getter we depend on).
struct AlwaysOnTop(AtomicBool);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default();

    #[cfg(desktop)]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            // second launch (clicking a skeuo:// link while running): surface the
            // window. The deep-link plugin delivers the URL to the JS listener.
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.show();
                let _ = w.set_focus();
            }
        }));
    }

    builder
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_opener::init())
        // remembers the widget's position + size across reopens
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .manage(AlwaysOnTop(AtomicBool::new(false)))
        .setup(|app| {
            // make sure skeuo:// resolves to us on dev / first run (on macOS the
            // bundled Info.plist also declares it, but this covers the dev shell)
            #[cfg(desktop)]
            {
                use tauri_plugin_deep_link::DeepLinkExt;
                let _ = app.deep_link().register_all();
            }
            // restore the widget's last position + size (no-op on first run)
            {
                use tauri_plugin_window_state::{StateFlags, WindowExt};
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.restore_state(StateFlags::all());
                }
            }
            build_tray(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            // closing the widget hides it to the tray rather than quitting, so it
            // behaves like a desktop toy you tuck away
            if let WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running the Skeuo widget");
}

fn build_tray(app: &tauri::App) -> tauri::Result<()> {
    // Skins submenu — each item carries id "skin:<id>"; the handler emits it.
    let mut skins = SubmenuBuilder::new(app, "Skins");
    for (id, name) in SKINS {
        let item = MenuItem::with_id(app, format!("skin:{id}"), *name, true, None::<&str>)?;
        skins = skins.item(&item);
    }
    let skins_menu = skins.build()?;

    let aot = CheckMenuItem::with_id(app, "toggle-aot", "Always on top", true, false, None::<&str>)?;
    let show = MenuItem::with_id(app, "show", "Show widget", true, None::<&str>)?;
    let connect = MenuItem::with_id(app, "connect", "Connect Spotify", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit Skeuo", true, None::<&str>)?;

    let menu = MenuBuilder::new(app)
        .item(&skins_menu)
        .separator()
        .item(&aot)
        .item(&show)
        .item(&connect)
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
                        let _ = w.show();
                        let _ = w.set_focus();
                    }
                }
                "connect" => {
                    let _ = app.emit("tray-connect", ());
                }
                "quit" => {
                    // persist position/size before exiting so it reopens in place
                    use tauri_plugin_window_state::{AppHandleExt, StateFlags};
                    let _ = app.save_window_state(StateFlags::all());
                    app.exit(0);
                }
                _ => {}
            }
        })
        .on_tray_icon_event(|tray, event| {
            // left-click the menu-bar icon toggles the widget's visibility
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
                        let _ = w.show();
                        let _ = w.set_focus();
                    }
                }
            }
        })
        .build(app)?;

    Ok(())
}
