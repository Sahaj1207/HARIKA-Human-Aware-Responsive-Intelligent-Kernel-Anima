//! HARIKA desktop shell: tray icon, global hotkey, floating orb window and the
//! lifecycle of the local Python backend.

mod glow;
mod updates;

use std::fs::File;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, PhysicalPosition, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

/// Development uses the usual dev port; installed builds use an uncommon one so
/// HARIKA doesn't collide with other local servers on :8000.
const BACKEND_PORT: u16 = if cfg!(debug_assertions) { 8000 } else { 47801 };
// Includes a 24px transparent margin so the panel's glow is never clipped.
const ORB_WIDTH: f64 = 600.0;
const ORB_HEIGHT: f64 = 244.0;

/// The backend process this app started (None when one was already running).
struct Backend(Mutex<Option<Child>>);

/// Set while HARIKA quits or installs an update, so the watchdog doesn't bring the engine back.
static STOPPING: AtomicBool = AtomicBool::new(false);
const WATCH_EVERY: Duration = Duration::from_secs(5);
/// Silence this long (after the engine has answered once) counts as the engine having died.
const MISSES_BEFORE_RESTART: u32 = 3;
/// A freshly started engine gets this long to load before silence counts.
const STARTUP_GRACE: Duration = Duration::from_secs(120);
const MAX_RESTARTS: usize = 3;
const RESTART_WINDOW: Duration = Duration::from_secs(600);

fn summon_shortcut() -> Shortcut {
    Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space)
}

fn backend_running() -> bool {
    let addr = std::net::SocketAddr::from(([127, 0, 0, 1], BACKEND_PORT));
    TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
}

/// How to start the backend: the bundled program shipped with the installer, or
/// (when developing) the repository's backend with its virtualenv.
fn backend_command(app: &AppHandle) -> Option<(Command, String)> {
    let exe_name = if cfg!(windows) { "harika-backend.exe" } else { "harika-backend" };
    if let Ok(resources) = app.path().resource_dir() {
        let bundled = resources.join("backend").join(exe_name);
        if bundled.exists() {
            let mut command = Command::new(&bundled);
            command.args(["--port", &BACKEND_PORT.to_string()]);
            if let Ok(data) = app.path().app_data_dir() {
                // Memories, reminders and settings live in the user's app-data folder.
                let _ = std::fs::create_dir_all(&data);
                command.env("HARIKA_DATA_DIR", &data).current_dir(&data);
            }
            return Some((command, bundled.display().to_string()));
        }
    }

    // Development: HARIKA_BACKEND_DIR, or the repo's backend folder.
    let dir = std::env::var_os("HARIKA_BACKEND_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../../backend")));
    let python = if cfg!(windows) {
        dir.join(".venv").join("Scripts").join("python.exe")
    } else {
        dir.join(".venv").join("bin").join("python")
    };
    if !python.exists() {
        return None;
    }
    let mut command = Command::new(&python);
    command
        .args(["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", &BACKEND_PORT.to_string()])
        .current_dir(&dir);
    Some((command, python.display().to_string()))
}

fn start_backend(app: &AppHandle) -> Option<Child> {
    if backend_running() {
        log::info!("Using the HARIKA backend that is already running on port {BACKEND_PORT}");
        return None;
    }
    let Some((mut command, program)) = backend_command(app) else {
        log::error!("No HARIKA backend found to start (neither bundled nor a development virtualenv).");
        return None;
    };
    let log_file = app
        .path()
        .app_log_dir()
        .ok()
        .and_then(|logs| std::fs::create_dir_all(&logs).ok().map(|_| logs.join("backend.log")))
        .and_then(|path| File::create(path).ok());
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
            log::info!("Started HARIKA backend (pid {}) with {program}", child.id());
            Some(child)
        }
        Err(err) => {
            log::error!("Could not start the HARIKA backend with {program}: {err}");
            None
        }
    }
}

/// Keeps the engine running: if the one HARIKA started exits, or the engine stops answering,
/// it is started again (at most MAX_RESTARTS times in RESTART_WINDOW, so a broken engine
/// doesn't restart forever). The window shows "offline" meanwhile and reconnects by itself.
fn watch_backend(app: AppHandle) {
    std::thread::spawn(move || {
        let mut started_at = Instant::now();
        let mut answered = false;
        let mut misses = 0;
        let mut restarts: Vec<Instant> = Vec::new();
        loop {
            std::thread::sleep(WATCH_EVERY);
            if STOPPING.load(Ordering::SeqCst) {
                return;
            }
            let exited = match app.state::<Backend>().0.lock().unwrap().as_mut() {
                Some(child) => matches!(child.try_wait(), Ok(Some(_))),
                None => false,
            };
            if !exited && backend_running() {
                answered = true;
                misses = 0;
                continue;
            }
            misses += 1;
            let silent_too_long = misses >= MISSES_BEFORE_RESTART && (answered || started_at.elapsed() > STARTUP_GRACE);
            if !exited && !silent_too_long {
                continue;
            }
            restarts.retain(|at| at.elapsed() < RESTART_WINDOW);
            if restarts.len() >= MAX_RESTARTS {
                log::error!("The HARIKA engine keeps stopping; not restarting it again for now.");
                continue;
            }
            log::warn!("The HARIKA engine stopped answering; starting it again.");
            stop_backend_child(&app);
            if STOPPING.load(Ordering::SeqCst) {
                return;
            }
            let child = start_backend(&app);
            *app.state::<Backend>().0.lock().unwrap() = child;
            restarts.push(Instant::now());
            started_at = Instant::now();
            answered = false;
            misses = 0;
        }
    });
}

/// Stops HARIKA's engine for good (quitting, or installing an update).
pub(crate) fn stop_backend(app: &AppHandle) {
    STOPPING.store(true, Ordering::SeqCst);
    stop_backend_child(app);
}

fn stop_backend_child(app: &AppHandle) {
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
    show_orb(app);
}

/// Called by the orb page when "Hey HARIKA" is heard: place and show it.
#[tauri::command]
fn summon_orb(app: AppHandle) {
    show_orb(&app);
}

fn show_orb(app: &AppHandle) {
    let Some(orb) = app.get_webview_window("orb") else { return };
    if orb.is_visible().unwrap_or(false) {
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
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
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
        .invoke_handler(tauri::generate_handler![
            summon_orb,
            glow::show_glow,
            glow::hide_glow,
            updates::check_update,
            updates::install_update
        ])
        .setup(|app| {
            let handle = app.handle();
            let child = start_backend(handle);
            *app.state::<Backend>().0.lock().unwrap() = child;
            watch_backend(handle.clone());
            build_orb(handle)?;
            glow::build(handle)?;
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
