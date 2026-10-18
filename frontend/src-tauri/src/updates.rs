//! In-app updates: check, download (signature-verified by the updater plugin),
//! stop HARIKA's engine, install and restart.
//!
//! The update address is the one in tauri.conf.json unless
//! `<app data>/settings/updates.json` holds {"url": "..."}, so where updates are
//! published can change without rebuilding (and a local test server can be used).

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, Url};
use tauri_plugin_updater::{Updater, UpdaterExt};

#[derive(Serialize, Clone)]
pub struct UpdateInfo {
    pub version: String,
    pub current: String,
    pub notes: Option<String>,
}

#[derive(Serialize, Clone)]
struct Progress {
    downloaded: u64,
    total: Option<u64>,
}

fn custom_endpoint(app: &AppHandle) -> Option<Url> {
    let path = app.path().app_data_dir().ok()?.join("settings").join("updates.json");
    let text = std::fs::read_to_string(path).ok()?;
    let value: serde_json::Value = serde_json::from_str(&text).ok()?;
    Url::parse(value.get("url")?.as_str()?).ok()
}

fn updater(app: &AppHandle) -> Result<Updater, String> {
    let mut builder = app.updater_builder();
    if let Some(url) = custom_endpoint(app) {
        builder = builder.endpoints(vec![url]).map_err(|e| e.to_string())?;
    }
    builder.build().map_err(|e| e.to_string())
}

/// Whether a newer HARIKA is available.
#[tauri::command]
pub async fn check_update(app: AppHandle) -> Result<Option<UpdateInfo>, String> {
    let update = updater(&app)?.check().await.map_err(|e| e.to_string())?;
    Ok(update.map(|u| UpdateInfo { version: u.version.clone(), current: u.current_version.clone(), notes: u.body.clone() }))
}

/// Download, verify, stop the engine, install and restart.
#[tauri::command]
pub async fn install_update(app: AppHandle) -> Result<(), String> {
    let Some(update) = updater(&app)?.check().await.map_err(|e| e.to_string())? else {
        return Err("HARIKA is already up to date.".into());
    };
    let mut downloaded: u64 = 0;
    let handle = app.clone();
    let bytes = update
        .download(
            move |chunk, total| {
                downloaded += chunk as u64;
                let _ = handle.emit("update-progress", Progress { downloaded, total });
            },
            || {},
        )
        .await
        .map_err(|e| e.to_string())?;
    // The installer replaces the engine's files, so the engine must not be running.
    crate::stop_backend(&app);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let _ = std::process::Command::new("taskkill")
            .args(["/IM", "harika-backend.exe", "/T", "/F"])
            .creation_flags(0x0800_0000)
            .status();
    }
    update.install(bytes).map_err(|e| e.to_string())?;
    app.restart();
}
