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
//!
//! The app's data directory is passed to the bridge via `RECAP_DESKTOP_DATA_DIR`.

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};

/// A long-lived `recap-bridge serve` process kept warm across runs so the Whisper model is not
/// reloaded every run (PERF-001). Only `run_recap` uses it; a broken worker falls back to a fresh
/// spawn-per-call run, so a worker bug degrades to "slow but correct", never "broken".
struct Worker {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

struct RunState {
    cancel: Arc<AtomicBool>,
    worker: Arc<Mutex<Option<Worker>>>,
}

/// Locate a frozen `recap-bridge` shipped beside the app executable (portable layout:
/// `<exe dir>/recap-bridge/recap-bridge[.exe]`). Returns None in dev, so the Python fallback runs.
fn bundled_bridge_path() -> Option<PathBuf> {
    let dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
    let name = if cfg!(windows) { "recap-bridge.exe" } else { "recap-bridge" };
    let candidate = dir.join("recap-bridge").join(name);
    candidate.is_file().then_some(candidate)
}

fn bridge_command(app: &AppHandle) -> Result<Command, String> {
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Не удалось определить каталог данных: {e}"))?;
    std::fs::create_dir_all(&data_dir).ok();

    let mut cmd = if let Ok(bin) = std::env::var("RECAP_BRIDGE_BIN") {
        Command::new(bin)
    } else if let Some(bundled) = bundled_bridge_path() {
        // Portable build: a frozen `recap-bridge` ships next to the app executable, so the app
        // needs no Python install and no env vars (see docs/portable-build.md).
        Command::new(bundled)
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
    // Force UTF-8 for the bridge's stdio: on Windows a piped/redirected stdout/stderr defaults to
    // the cp1252 ("charmap") codec, so writing Cyrillic/CJK (JSON results, streamed LLM tokens)
    // raises "'charmap' codec can't encode". PYTHONUTF8=1 makes all Python I/O UTF-8.
    cmd.env("PYTHONUTF8", "1");

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
        .next_back()
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
async fn list_models(app: AppHandle, provider: String) -> Result<Value, String> {
    let payload = json!({ "provider": provider });
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "list_models", payload))
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
async fn save_summary(app: AppHandle, req: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || run_bridge(&app, "save_summary", req))
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
    let worker = state.worker.clone();
    tauri::async_runtime::spawn_blocking(move || match run_via_worker(&app, &cancel, &worker, &req) {
        Ok(v) => Ok(v),
        // A genuine run error propagates just like the spawn-per-call path.
        Err(WorkerError::Run(msg)) => Err(msg),
        // The worker is unusable: drop it (kill any dead child) and fall back to a fresh spawn —
        // slow (model reloads) but correct. Next run will spawn a fresh worker.
        Err(WorkerError::Broken(reason)) => {
            eprintln!("recap: warm-model worker unusable ({reason}); falling back to spawn-per-call");
            if let Ok(mut guard) = worker.lock() {
                if let Some(mut w) = guard.take() {
                    let _ = w.child.kill();
                }
            }
            streaming_blocking(&app, cancel, "run_recap", req)
        }
    })
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

/// Watcher thread that writes the cancel flag file the moment the user cancels — needed because
/// the reader thread blocks on a long silent transcription stage (no progress lines). Returns a
/// `done` flag to stop it and its join handle.
fn spawn_flag_watcher(cancel: Arc<AtomicBool>, flag_path: PathBuf) -> (Arc<AtomicBool>, JoinHandle<()>) {
    let done = Arc::new(AtomicBool::new(false));
    let handle = {
        let done = done.clone();
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
    (done, handle)
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

    let (watcher_done, watcher) = spawn_flag_watcher(cancel.clone(), flag_path.clone());

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

/// Failure modes of a worker run. `Run` = the run itself errored (propagate, same as spawn-per-call);
/// `Broken` = the worker/pipe is unusable (caller drops the worker and falls back to a fresh spawn).
enum WorkerError {
    Run(String),
    Broken(String),
}

fn spawn_worker(app: &AppHandle) -> Result<Worker, String> {
    let mut cmd = bridge_command(app)?;
    cmd.arg("serve")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    let mut child = cmd.spawn().map_err(|e| format!("Не удалось запустить worker: {e}"))?;
    let stdin = child.stdin.take().ok_or("Нет stdin у worker")?;
    let stdout = child.stdout.take().ok_or("Нет stdout у worker")?;
    Ok(Worker {
        child,
        stdin,
        stdout: BufReader::new(stdout),
    })
}

/// Run `run_recap` through the persistent warm-model worker. The `Mutex` guard is held for the
/// whole run, so runs are serialised here (not assumed from the UI). The worker's stdout never
/// EOFs between runs, so we read until the terminal `result`/`error` line and leave the pipe open.
fn run_via_worker(
    app: &AppHandle,
    cancel: &Arc<AtomicBool>,
    worker: &Arc<Mutex<Option<Worker>>>,
    req: &Value,
) -> Result<Value, WorkerError> {
    let flag_path = cancel_flag_path();
    let _ = std::fs::remove_file(&flag_path);
    let mut req = req.clone();
    if let Some(obj) = req.as_object_mut() {
        obj.insert("cancel_flag".to_string(), json!(flag_path.to_string_lossy()));
    }
    let (done, watcher) = spawn_flag_watcher(cancel.clone(), flag_path.clone());

    let finish = |done: &Arc<AtomicBool>, flag: &PathBuf, watcher: JoinHandle<()>| {
        done.store(true, Ordering::SeqCst);
        let _ = watcher.join();
        let _ = std::fs::remove_file(flag);
    };

    let mut guard = match worker.lock() {
        Ok(g) => g,
        Err(_) => {
            finish(&done, &flag_path, watcher);
            return Err(WorkerError::Broken("worker mutex poisoned".to_string()));
        }
    };
    if guard.is_none() {
        match spawn_worker(app) {
            Ok(w) => *guard = Some(w),
            Err(e) => {
                finish(&done, &flag_path, watcher);
                return Err(WorkerError::Broken(e));
            }
        }
    }
    let w = guard.as_mut().unwrap();

    let mut req_line = req.to_string();
    req_line.push('\n');
    if let Err(e) = w.stdin.write_all(req_line.as_bytes()).and_then(|_| w.stdin.flush()) {
        finish(&done, &flag_path, watcher);
        return Err(WorkerError::Broken(e.to_string()));
    }

    let outcome: Result<Value, WorkerError>;
    let mut line = String::new();
    loop {
        line.clear();
        match w.stdout.read_line(&mut line) {
            Ok(0) => {
                outcome = Err(WorkerError::Broken("worker закрыл stdout".to_string()));
                break;
            }
            Ok(_) => {}
            Err(e) => {
                outcome = Err(WorkerError::Broken(e.to_string()));
                break;
            }
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let value: Value = match serde_json::from_str(trimmed) {
            Ok(v) => v,
            Err(_) => continue,
        };
        match value.get("type").and_then(|v| v.as_str()) {
            Some("progress") => {
                if let Some(event) = value.get("event") {
                    let _ = app.emit("recap-progress", event);
                }
            }
            Some("result") => {
                outcome = value
                    .get("result")
                    .cloned()
                    .ok_or_else(|| WorkerError::Broken("пустой result от worker".to_string()));
                break;
            }
            Some("error") => {
                outcome = Err(WorkerError::Run(
                    value
                        .get("error")
                        .and_then(|v| v.as_str())
                        .unwrap_or("Ошибка выполнения")
                        .to_string(),
                ));
                break;
            }
            _ => {}
        }
    }
    drop(guard);
    finish(&done, &flag_path, watcher);
    outcome
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(RunState {
            cancel: Arc::new(AtomicBool::new(false)),
            worker: Arc::new(Mutex::new(None)),
        })
        .invoke_handler(tauri::generate_handler![
            get_settings,
            save_settings,
            set_api_key,
            delete_api_key,
            test_connection,
            list_models,
            get_history,
            delete_history_item,
            export_summary,
            save_summary,
            read_text,
            run_recap,
            resummarize,
            cancel_run,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // Kill the persistent worker on exit — a long-lived process left orphaned holds the GPU.
            if let RunEvent::Exit = event {
                if let Some(state) = app_handle.try_state::<RunState>() {
                    if let Ok(mut guard) = state.worker.lock() {
                        if let Some(mut w) = guard.take() {
                            let _ = w.child.kill();
                        }
                    }
                }
            }
        });
}
