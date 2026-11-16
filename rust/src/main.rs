mod core;

use core::Variant;
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};

const VERSION: &str = env!("APP_VERSION");

#[derive(Clone)]
struct AppState {
    variant: Arc<Mutex<Variant>>,
}

impl AppState {
    fn current(&self) -> Variant {
        *self.variant.lock().unwrap()
    }
}

#[tauri::command]
fn version() -> Value {
    json!({ "ok": true, "version": VERSION })
}

fn version_tuple(s: &str) -> (u64, u64, u64) {
    let nums: Vec<u64> = s
        .trim_start_matches(['v', 'V'])
        .split('.')
        .take(3)
        .map(|p| p.parse().unwrap_or(0))
        .collect();
    (
        *nums.get(0).unwrap_or(&0),
        *nums.get(1).unwrap_or(&0),
        *nums.get(2).unwrap_or(&0),
    )
}

#[tauri::command]
fn check_update() -> Value {
    const URL: &str = "https://github.com/MisakaMikoto128/workbuddy-session-branch/releases/latest/download/update.json";
    let client = match reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(8))
        .user_agent("wb-session-branch-updater")
        .build()
    {
        Ok(c) => c,
        Err(e) => return json!({ "ok": false, "error": e.to_string() }),
    };
    let data: Value = match client.get(URL).send().and_then(|r| r.json()) {
        Ok(v) => v,
        Err(e) => return json!({ "ok": false, "error": e.to_string() }),
    };
    let latest = data.get("version").and_then(|x| x.as_str()).unwrap_or("");
    let has = version_tuple(latest) > version_tuple(VERSION);
    json!({
        "ok": true,
        "current": VERSION,
        "latest": latest,
        "hasUpdate": has,
        "publishedAt": data.get("published_at").and_then(|x| x.as_str()).unwrap_or(""),
        "page": "https://github.com/MisakaMikoto128/workbuddy-session-branch/releases/latest",
    })
}

#[tauri::command]
fn list_variants() -> Value {
    json!({ "ok": true, "data": core::variants() })
}

#[tauri::command]
fn get_variant(state: tauri::State<'_, AppState>) -> Value {
    json!({ "ok": true, "id": state.current().id() })
}

#[tauri::command]
fn set_variant(id: String, state: tauri::State<'_, AppState>) -> Value {
    match Variant::from_id(&id) {
        Some(v) => {
            *state.variant.lock().unwrap() = v;
            json!({ "ok": true, "id": v.id() })
        }
        None => json!({ "ok": false, "error": format!("未知版本: {}", id) }),
    }
}

#[tauri::command]
fn list_sessions(state: tauri::State<'_, AppState>) -> Value {
    match core::list_sessions(state.current()) {
        Ok(v) => v,
        Err(e) => json!({ "ok": false, "error": e }),
    }
}

#[tauri::command]
fn list_messages(session_id: String, state: tauri::State<'_, AppState>) -> Value {
    match core::list_messages(state.current(), &session_id) {
        Ok(v) => v,
        Err(e) => json!({ "ok": false, "error": e }),
    }
}

#[tauri::command]
fn preview_branch(session_id: String, at_id: String, title: String, state: tauri::State<'_, AppState>) -> Value {
    match core::preview_branch(state.current(), &session_id, &at_id, &title) {
        Ok(v) => v,
        Err(e) => json!({ "ok": false, "error": e }),
    }
}

#[tauri::command]
fn do_branch(session_id: String, at_id: String, title: String, state: tauri::State<'_, AppState>) -> Value {
    match core::do_branch(state.current(), &session_id, &at_id, &title) {
        Ok(v) => v,
        Err(e) => json!({ "ok": false, "error": e }),
    }
}

#[tauri::command]
fn migrate_session(session_id: String, target: String, title_hint: String, state: tauri::State<'_, AppState>) -> Value {
    let src = state.current();
    let dst = match Variant::from_id(&target) {
        Some(v) => v,
        None => return json!({ "ok": false, "error": format!("未知目标版本: {}", target) }),
    };
    match core::migrate_session(src, dst, &session_id, &title_hint) {
        Ok(v) => v,
        Err(e) => json!({ "ok": false, "error": e }),
    }
}

#[tauri::command]
fn delete_session(session_id: String, state: tauri::State<'_, AppState>) -> Value {
    match core::delete_session(state.current(), &session_id) {
        Ok(v) => v,
        Err(e) => json!({ "ok": false, "error": e }),
    }
}

#[tauri::command]
fn restore_session(session_id: String, state: tauri::State<'_, AppState>) -> Value {
    match core::restore_session(state.current(), &session_id) {
        Ok(v) => v,
        Err(e) => json!({ "ok": false, "error": e }),
    }
}

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            variant: Arc::new(Mutex::new(Variant::Domestic)),
        })
        .invoke_handler(tauri::generate_handler![
            version,
            check_update,
            list_variants,
            get_variant,
            set_variant,
            list_sessions,
            list_messages,
            preview_branch,
            do_branch,
            migrate_session,
            delete_session,
            restore_session
        ])
        .run(tauri::generate_context!())
        .expect("Tauri 启动失败");
}
