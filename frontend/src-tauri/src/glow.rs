//! The screen glow: a transparent, click-through window over the whole screen whose
//! edges light up while HARIKA listens, thinks, speaks or works on the screen.
//!
//! It never takes focus, never shows in the taskbar, and lets every click through to
//! the apps underneath. It is hidden (costing nothing) whenever HARIKA is idle; the
//! glow page itself asks to be shown or hidden as HARIKA's live events arrive.

use tauri::{AppHandle, Manager, PhysicalPosition, PhysicalSize, WebviewUrl, WebviewWindowBuilder};

const LABEL: &str = "glow";

pub fn build(app: &AppHandle) -> tauri::Result<()> {
    let window = WebviewWindowBuilder::new(app, LABEL, WebviewUrl::App("index.html?window=glow".into()))
        .title("HARIKA glow")
        .decorations(false)
        .transparent(true)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .resizable(false)
        .focused(false)
        .focusable(false)
        .visible(false)
        .build()?;
    window.set_ignore_cursor_events(true)?;
    Ok(())
}

/// Cover the monitor the mouse is on, without taking focus from the user's app.
#[tauri::command]
pub fn show_glow(app: AppHandle) {
    let Some(glow) = app.get_webview_window(LABEL) else { return };
    let monitor = glow
        .cursor_position()
        .ok()
        .and_then(|p| glow.monitor_from_point(p.x, p.y).ok().flatten())
        .or_else(|| app.primary_monitor().ok().flatten());
    if let Some(monitor) = monitor {
        let _ = glow.set_position(PhysicalPosition::new(monitor.position().x, monitor.position().y));
        let _ = glow.set_size(PhysicalSize::new(monitor.size().width, monitor.size().height));
    }
    if !glow.is_visible().unwrap_or(false) {
        let _ = glow.show();
        let _ = glow.set_ignore_cursor_events(true); // re-applied: some systems reset it on show
        let _ = glow.set_always_on_top(true);
    }
}

#[tauri::command]
pub fn hide_glow(app: AppHandle) {
    if let Some(glow) = app.get_webview_window(LABEL) {
        let _ = glow.hide();
    }
}
