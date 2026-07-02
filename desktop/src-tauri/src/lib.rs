//! Tauri shell for Recap.
//!
//! This layer is intentionally "dumb": every command spawns the Python bridge
//! (`recap-bridge` / `python -m desktop_bridge`), writes a JSON payload on stdin and
//! reads JSON on stdout. All real logic lives in Python (src/desktop_bridge.py), where
//! it is unit-tested. `run_recap` streams newline-delimited JSON and forwards each
//! progress line to the webview as a `recap-progress` event.
//!
//! Bridge invocation is configured via environment variables (with dev-friendly
//! defaults documented in desktop/README.md):
//!   - `RECAP_BRIDGE_BIN`  full path to an installed `recap-bridge` executable; or
//!   - `RECAP_PYTHON`      python executable (default: `python`) used with `-m desktop_bridge`,
//!     together with `RECAP_SRC` (added to `PYTHONPATH`).
//! The app's data directory is passed to the bridge via `RECAP_DESKTOP_DATA_DIR`.

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, State};

struct RunState {
    cancel: Arc<AtomicBool>,
}

fn bridge_command(app: &AppHandle) -> Result<Command, String> {
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Не удалось определить каталог данных: {e}"))?;
    std::fs::create_dir_all(&data_dir).ok();

    let mut cmd = if let Ok(bin) = std::env::var("RECAP_BRIDGE_BIN") {
        Command::new(bin)
    } else {
        let python = std::env::var("RECAP_PYTHON").unwrap_or_else(|_| "python".to_string());
        let mut c = Command::new(python);
        c.arg("-m").arg("desktop_bridge");
        if let Ok(src) = std::env::var("RECAP_SRC") {
            c.env("PYTHONPATH", src);
        }
        c
    };
    cmd.env("RECAP_DESKTOP_DATA_DIR", data_dir);

    // REL-003: this is a GUI app (windows_subsystem = "windows"); without CREATE_NO_WINDOW,
    // Windows opens a visible console for every bridge spawn (settings, history, each run…).
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }

    Ok(cmd)
}

/// One-shot bridge call: write `payload` to stdin, parse the final JSON line of stdout.
fn run_bridge(app: &AppHandle, command: &str, payload: Value) -> Result<Value, String> {
    let mut cmd = bridge_command(app)?;
    cmd.arg(command)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());

    let mut child = cmd.spawn().map_err(|e| format!("Не удалось запустить bridge: {e}"))?;
    {
        let mut stdin = child.stdin.take().ok_or("Нет stdin у процесса bridge")?;
        stdin
            .write_all(payload.to_string().as_bytes())
            .map_err(|e| e.to_string())?;
    } // stdin dropped/closed here

    let output = child.wait_with_output().map_err(|e| e.to_string())?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let last = stdout
        .lines()
        .filter(|l| !l.trim().is_empty())
        .last()
        .ok_or("Пустой ответ от bridge")?;
    let value: Value = serde_json::from_str(last).map_err(|e| format!("Некорректный ответ bridge: {e}"))?;
    if let Some(err) = value.get("error").and_then(|v| v.as_str()) {
        return Err(err.to_string());
    }
    Ok(value)
}

// ── One-shot commands ───────────────────────────────────────────────────────

#[tauri::command]
async fn get_settings(app: AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "get_settings", json!({})))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn save_settings(app: AppHandle, settings: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "save_settings", settings))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn set_api_key(app: AppHandle, provider: String, api_key: String) -> Result<Value, String> {
    let payload = json!({ "provider": provider, "api_key": api_key });
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "set_api_key", payload))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn delete_api_key(app: AppHandle, provider: String) -> Result<Value, String> {
    let payload = json!({ "provider": provider });
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "delete_api_key", payload))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn test_connection(app: AppHandle, provider: String) -> Result<Value, String> {
    let payload = json!({ "provider": provider });
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "test_connection", payload))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn get_history(app: AppHandle) -> Result<Value, String> {
    let value = tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "get_history", json!({})))
        .await
        .map_err(|e| e.to_string())??;
    // Frontend expects the items array directly.
    Ok(value.get("items").cloned().unwrap_or_else(|| json!([])))
}

#[tauri::command]
async fn delete_history_item(app: AppHandle, id: String) -> Result<Value, String> {
    let payload = json!({ "id": id });
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "delete_history_item", payload))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn export_summary(app: AppHandle, req: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "export_summary", req))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn read_text(app: AppHandle, path: Option<String>) -> Result<Value, String> {
    let payload = json!({ "path": path });
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "read_text", payload))
        .await
        .map_err(|e| e.to_string())?
}

// ── Streaming run ─────────────────────────────────────────────────────────────

#[tauri::command]
async fn cancel_run(state: State<'_, RunState>) -> Result<(), String> {
    state.cancel.store(true, Ordering::SeqCst);
    Ok(())
}

#[tauri::command]
async fn run_recap(app: AppHandle, state: State<'_, RunState>, req: Value) -> Result<Value, String> {
    state.cancel.store(false, Ordering::SeqCst);
    let cancel = state.cancel.clone();
    tauri::async_runtime::spawn_blocking(move || streaming_blocking(&app, cancel, "run_recap", req))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn resummarize(app: AppHandle, state: State<'_, RunState>, req: Value) -> Result<Value, String> {
    state.cancel.store(false, Ordering::SeqCst);
    let cancel = state.cancel.clone();
    tauri::async_runtime::spawn_blocking(move || streaming_blocking(&app, cancel, "resummarize", req))
        .await
        .map_err(|e| e.to_string())?
}

/// Per-run path for the cooperative cancellation flag file (ARCH-002). Unique per run so a
/// stale flag from a previous run can never auto-cancel the next one.
fn cancel_flag_path() -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    std::env::temp_dir().join(format!("recap-cancel-{}-{}.flag", std::process::id(), nanos))
}

fn streaming_blocking(app: &AppHandle, cancel: Arc<AtomicBool>, command: &str, req: Value) -> Result<Value, String> {
    // Cooperative cancellation: the bridge polls this flag file between stages. On cancel we
    // create the file and let the bridge unwind normally — it returns a real
    // RunResult("cancelled") (transcript path preserved) and records history. No kill(), so
    // Python's `finally` blocks run (no orphaned temp WAV / stranded ffmpeg).
    let flag_path = cancel_flag_path();
    let _ = std::fs::remove_file(&flag_path); // never start with a stale flag

    let mut req = req;
    if let Some(obj) = req.as_object_mut() {
        obj.insert("cancel_flag".to_string(), json!(flag_path.to_string_lossy()));
    }

    let mut cmd = bridge_command(app)?;
    cmd.arg(command)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());

    let mut child = cmd.spawn().map_err(|e| format!("Не удалось запустить bridge: {e}"))?;
    {
        let mut stdin = child.stdin.take().ok_or("Нет stdin у процесса bridge")?;
        stdin
            .write_all(req.to_string().as_bytes())
            .map_err(|e| e.to_string())?;
    } // close stdin so the bridge starts processing

    // Watcher thread: write the flag file the moment the user cancels, even while the main
    // thread is blocked reading a long silent transcription stage (no progress lines).
    let watcher_done = Arc::new(AtomicBool::new(false));
    let watcher = {
        let cancel = cancel.clone();
        let done = watcher_done.clone();
        let flag_path = flag_path.clone();
        std::thread::spawn(move || {
            while !done.load(Ordering::SeqCst) {
                if cancel.load(Ordering::SeqCst) {
                    let _ = std::fs::write(&flag_path, b"1");
                    return;
                }
                std::thread::sleep(Duration::from_millis(100));
            }
        })
    };

    let stdout = child.stdout.take().ok_or("Нет stdout у процесса bridge")?;
    let reader = BufReader::new(stdout);

    let mut final_result: Option<Value> = None;
    let mut stream_error: Option<String> = None;
    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(e) => {
                stream_error = Some(e.to_string());
                break;
            }
        };
        if line.trim().is_empty() {
            continue;
        }
        let value: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue, // ignore non-JSON noise
        };
        match value.get("type").and_then(|v| v.as_str()) {
            Some("progress") => {
                if let Some(event) = value.get("event") {
                    let _ = app.emit("recap-progress", event);
                }
            }
            Some("result") => {
                final_result = value.get("result").cloned();
            }
            Some("error") => {
                stream_error = Some(
                    value
                        .get("error")
                        .and_then(|v| v.as_str())
                        .unwrap_or("Ошибка выполнения")
                        .to_string(),
                );
                break;
            }
            _ => {}
        }
    }
    let _ = child.wait();
    watcher_done.store(true, Ordering::SeqCst);
    let _ = watcher.join();
    let _ = std::fs::remove_file(&flag_path);

    if let Some(err) = stream_error {
        return Err(err);
    }
    final_result.ok_or_else(|| "Не получен результат от bridge".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(RunState {
            cancel: Arc::new(AtomicBool::new(false)),
        })
        .invoke_handler(tauri::generate_handler![
            get_settings,
            save_settings,
            set_api_key,
            delete_api_key,
            test_connection,
            get_history,
            delete_history_item,
            export_summary,
            read_text,
            run_recap,
            resummarize,
            cancel_run,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
