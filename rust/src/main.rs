mod core;

use core::Variant;
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};

const VERSION: &str = "1.0.0";

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

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            variant: Arc::new(Mutex::new(Variant::Domestic)),
        })
        .invoke_handler(tauri::generate_handler![
            version,
            list_variants,
            get_variant,
            set_variant,
            list_sessions,
            list_messages,
            preview_branch,
            do_branch
        ])
        .run(tauri::generate_context!())
        .expect("Tauri 启动失败");
}
