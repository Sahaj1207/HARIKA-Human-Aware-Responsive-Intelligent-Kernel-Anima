//! HARIKA desktop shell: tray icon, global hotkey, floating orb window and the
//! lifecycle of the local Python backend.

use std::fs::File;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, PhysicalPosition, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

const BACKEND_ADDR: &str = "127.0.0.1:8000";
const ORB_WIDTH: f64 = 560.0;
const ORB_HEIGHT: f64 = 220.0;

/// The backend process this app started (None when one was already running).
struct Backend(Mutex<Option<Child>>);

fn summon_shortcut() -> Shortcut {
    Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space)
}

fn backend_running() -> bool {
    TcpStream::connect_timeout(&BACKEND_ADDR.parse().unwrap(), Duration::from_millis(300)).is_ok()
}

/// Development layout: the repository's backend folder with its virtualenv.
/// HARIKA_BACKEND_DIR overrides it. (Installers will ship a bundled backend instead.)
fn backend_dir() -> PathBuf {
    std::env::var_os("HARIKA_BACKEND_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../../backend")))
}

fn start_backend(app: &AppHandle) -> Option<Child> {
    if backend_running() {
        log::info!("Using the HARIKA backend that is already running on {BACKEND_ADDR}");
        return None;
    }
    let dir = backend_dir();
    let python = if cfg!(windows) {
        dir.join(".venv").join("Scripts").join("python.exe")
    } else {
        dir.join(".venv").join("bin").join("python")
    };
    let log_file = app
        .path()
        .app_log_dir()
        .ok()
        .and_then(|logs| std::fs::create_dir_all(&logs).ok().map(|_| logs.join("backend.log")))
        .and_then(|path| File::create(path).ok());

    let mut command = Command::new(&python);
    command
        .args(["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"])
        .current_dir(&dir);
    match log_file.and_then(|f| f.try_clone().ok().map(|g| (f, g))) {
        Some((out, err)) => command.stdout(out).stderr(err),
        None => command.stdout(Stdio::null()).stderr(Stdio::null()),
    };
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: no console flashing up
    }
    match command.spawn() {
        Ok(child) => {
            log::info!("Started HARIKA backend (pid {}) from {}", child.id(), dir.display());
            Some(child)
        }
        Err(err) => {
            log::error!("Could not start the HARIKA backend with {}: {err}", python.display());
            None
        }
    }
}

fn stop_backend(app: &AppHandle) {
    if let Some(mut child) = app.state::<Backend>().0.lock().unwrap().take() {
        // A Windows virtualenv python.exe is a launcher that starts the real
        // interpreter as a child, so the whole process tree must be ended.
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            let _ = Command::new("taskkill")
                .args(["/PID", &child.id().to_string(), "/T", "/F"])
                .creation_flags(0x0800_0000)
                .status();
        }
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

/// Show the orb near the top centre of the screen the user is on, or hide it.
fn toggle_orb(app: &AppHandle) {
    let Some(orb) = app.get_webview_window("orb") else { return };
    if orb.is_visible().unwrap_or(false) {
        let _ = orb.hide();
        return;
    }
    let monitor = orb
        .current_monitor()
        .ok()
        .flatten()
        .or_else(|| app.primary_monitor().ok().flatten());
    if let Some(monitor) = monitor {
        let scale = monitor.scale_factor();
        let size = monitor.size();
        let origin = monitor.position();
        let x = origin.x + ((size.width as f64 - ORB_WIDTH * scale) / 2.0) as i32;
        let y = origin.y + (size.height as f64 * 0.18) as i32;
        let _ = orb.set_position(PhysicalPosition::new(x, y));
    }
    let _ = orb.show();
    let _ = orb.set_focus();
}

fn build_orb(app: &AppHandle) -> tauri::Result<()> {
    WebviewWindowBuilder::new(app, "orb", WebviewUrl::App("index.html?window=orb".into()))
        .title("HARIKA")
        .inner_size(ORB_WIDTH, ORB_HEIGHT)
        .decorations(false)
        .transparent(true)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .resizable(false)
        .visible(false)
        .build()?;
    Ok(())
}

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Open HARIKA", true, None::<&str>)?;
    let summon = MenuItem::with_id(app, "summon", "Ask HARIKA  (Ctrl+Shift+Space)", true, None::<&str>)?;
    let starts_at_login = app.autolaunch().is_enabled().unwrap_or(false);
    let autostart = CheckMenuItem::with_id(app, "autostart", "Start at login", true, starts_at_login, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit HARIKA", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let menu = Menu::with_items(app, &[&open, &summon, &separator, &autostart, &separator, &quit])?;

    let autostart_item = autostart.clone();
    TrayIconBuilder::with_id("harika")
        .icon(app.default_window_icon().cloned().expect("bundle icon"))
        .tooltip("HARIKA")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(move |app, event| match event.id.as_ref() {
            "open" => show_main(app),
            "summon" => toggle_orb(app),
            "autostart" => {
                // Login items change only when the user ticks this box.
                let manager = app.autolaunch();
                let enable = !manager.is_enabled().unwrap_or(false);
                let result = if enable { manager.enable() } else { manager.disable() };
                if let Err(err) = result {
                    log::error!("Could not change start-at-login: {err}");
                }
                let _ = autostart_item.set_checked(manager.is_enabled().unwrap_or(false));
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                show_main(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show_main(app)))
        .plugin(tauri_plugin_autostart::Builder::new().build())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, shortcut, event| {
                    if event.state() == ShortcutState::Pressed
                        && shortcut.matches(Modifiers::CONTROL | Modifiers::SHIFT, Code::Space)
                    {
                        toggle_orb(app);
                    }
                })
                .build(),
        )
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle();
            let child = start_backend(handle);
            *app.state::<Backend>().0.lock().unwrap() = child;
            build_orb(handle)?;
            build_tray(handle)?;
            if let Err(err) = handle.global_shortcut().register(summon_shortcut()) {
                // Another app owns the hotkey; HARIKA stays usable from the tray.
                log::warn!("Could not register Ctrl+Shift+Space: {err}");
            }
            Ok(())
        })
        .on_window_event(|window, event| match event {
            // Closing the main window keeps HARIKA running in the tray.
            WindowEvent::CloseRequested { api, .. } if window.label() == "main" => {
                api.prevent_close();
                let _ = window.hide();
            }
            // The orb behaves like a launcher: clicking elsewhere dismisses it.
            WindowEvent::Focused(false) if window.label() == "orb" => {
                let _ = window.hide();
            }
            _ => {}
        })
        .build(tauri::generate_context!())
        .expect("error while building HARIKA");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            stop_backend(handle);
        }
    });
}
