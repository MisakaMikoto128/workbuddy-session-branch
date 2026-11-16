use chrono::Local;
use rusqlite::Connection;
use serde_json::{json, Value};
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Variant {
    Domestic,
    International,
}

impl Variant {
    pub fn id(self) -> &'static str {
        match self {
            Variant::Domestic => "domestic",
            Variant::International => "international",
        }
    }
    pub fn name(self) -> &'static str {
        match self {
            Variant::Domestic => "WorkBuddy 国内版",
            Variant::International => "WorkBuddy AI 国际版",
        }
    }
    pub fn dir_name(self) -> &'static str {
        match self {
            Variant::Domestic => ".workbuddy",
            Variant::International => ".workbuddy-ai",
        }
    }
    pub fn from_id(s: &str) -> Option<Self> {
        match s {
            "domestic" => Some(Variant::Domestic),
            "international" => Some(Variant::International),
            _ => None,
        }
    }
    pub fn base(self) -> PathBuf {
        dirs::home_dir()
            .unwrap_or_default()
            .join(self.dir_name())
    }
    pub fn db(self) -> PathBuf {
        self.base().join("workbuddy.db")
    }
    pub fn projects(self) -> PathBuf {
        self.base().join("projects")
    }
    pub fn exists(self) -> bool {
        self.db().exists() && self.projects().exists()
    }
}

pub fn variants() -> Vec<Value> {
    [Variant::Domestic, Variant::International]
        .into_iter()
        .map(|v| {
            json!({
                "id": v.id(),
                "name": v.name(),
                "desc": format!("~/{}", v.dir_name()),
                "available": v.exists(),
            })
        })
        .collect()
}

fn fmt_time(ms: i64) -> String {
    if ms <= 0 {
        return String::new();
    }
    chrono::DateTime::from_timestamp(ms / 1000, 0)
        .map(|d| d.with_timezone(&Local).format("%Y-%m-%d %H:%M").to_string())
        .unwrap_or_default()
}

fn fmt_hms(ms: i64) -> String {
    if ms <= 0 {
        return String::new();
    }
    let dt = chrono::DateTime::from_timestamp(ms / 1000, 0)
        .map(|d| d.with_timezone(&Local))
        .unwrap_or_else(Local::now);
    dt.format("%H:%M:%S").to_string()
}

pub fn list_sessions(v: Variant) -> Result<Value, String> {
    let db = v.db();
    if !db.exists() {
        return Err(format!("数据库不存在: {}", db.display()));
    }
    let con = Connection::open_with_flags(&db, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|e| format!("打开数据库失败: {}", e))?;
    let mut stmt = con
        .prepare(
            "select id,title,custom_title,status,cwd,updated_at,model,source_mode \
             from sessions where deleted_at is null order by updated_at desc",
        )
        .map_err(|e| format!("查询会话失败: {}", e))?;
    let rows = stmt
        .query_map([], |r| {
            Ok((
                r.get::<_, String>(0)?,
                r.get::<_, Option<String>>(1)?,
                r.get::<_, Option<String>>(2)?,
                r.get::<_, Option<String>>(3)?,
                r.get::<_, Option<String>>(4)?,
                r.get::<_, Option<i64>>(5)?,
                r.get::<_, Option<String>>(6)?,
                r.get::<_, Option<String>>(7)?,
            ))
        })
        .map_err(|e| format!("读取会话失败: {}", e))?;

    let mut out = Vec::new();
    for r in rows {
        let r = r.map_err(|e| e.to_string())?;
        let count = count_messages(v, &r.0);
        out.push(json!({
            "id": r.0,
            "title": r.2.or(r.1).unwrap_or_else(|| "(无标题)".into()),
            "status": r.3.unwrap_or_default(),
            "cwd": r.4.unwrap_or_default(),
            "updated": fmt_time(r.5.unwrap_or(0)),
            "model": r.6.unwrap_or_default(),
            "mode": r.7.unwrap_or_default(),
            "count": count,
        }));
    }
    Ok(json!({ "ok": true, "data": out }))
}

fn find_jsonl(v: Variant, session_id: &str) -> Result<PathBuf, String> {
    let root = v.projects();
    let direct = root.join(format!("{}.jsonl", session_id));
    if direct.exists() {
        return Ok(direct);
    }
    let entries = fs::read_dir(&root).map_err(|e| format!("读取项目目录失败: {}", e))?;
    for e in entries.flatten() {
        let p = e.path();
        let candidate = p.join(format!("{}.jsonl", session_id));
        if candidate.exists() {
            return Ok(candidate);
        }
    }
    Err(format!("找不到会话文件: {}.jsonl", session_id))
}

fn count_messages(v: Variant, session_id: &str) -> i64 {
    find_jsonl(v, session_id)
        .ok()
        .and_then(|p| {
            let f = File::open(p).ok()?;
            let mut n = 0i64;
            for line in BufReader::new(f).lines().flatten() {
                if line.contains("\"type\": \"message\"") || line.contains("\"type\":\"message\"") {
                    n += 1;
                }
            }
            Some(n)
        })
        .unwrap_or(-1)
}

#[derive(Clone)]
struct Msg {
    id: String,
    role: String,
    parent: String,
    text: String,
    time: String,
}

fn clean_title(text: &str) -> String {
    let mut out = String::new();
    let mut skip = false;
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        if skip {
            if c == '>' {
                skip = false;
            }
            continue;
        }
        if c == '<' {
            let rest: String = chars.clone().collect();
            if rest.to_lowercase().starts_with("system-reminder") {
                skip = true;
                continue;
            }
            skip = true;
            continue;
        }
        out.push(c);
    }
    out.split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .chars()
        .take(70)
        .collect()
}

fn parse_records(v: Variant, session_id: &str) -> Result<Vec<Value>, String> {
    let path = find_jsonl(v, session_id)?;
    let f = File::open(path).map_err(|e| format!("打开会话失败: {}", e))?;
    let mut out = Vec::new();
    for line in BufReader::new(f).lines().flatten() {
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(val) = serde_json::from_str::<Value>(&line) {
            out.push(val);
        }
    }
    Ok(out)
}

fn message_preview(rec: &Value) -> String {
    if let Some(content) = rec.get("content") {
        if let Some(arr) = content.as_array() {
            for item in arr {
                if let Some(t) = item.get("text").and_then(|x| x.as_str()) {
                    return clean_title(t);
                }
            }
        }
    }
    String::new()
}

fn messages_of(records: &[Value]) -> Vec<Msg> {
    records
        .iter()
        .filter(|r| r.get("type").and_then(|x| x.as_str()) == Some("message"))
        .map(|r| Msg {
            id: r.get("id").and_then(|x| x.as_str()).unwrap_or("").to_string(),
            role: r.get("role").and_then(|x| x.as_str()).unwrap_or("?").to_string(),
            parent: r
                .get("parentId")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            text: message_preview(r),
            time: fmt_hms(r.get("timestamp").and_then(|x| x.as_i64()).unwrap_or(0)),
        })
        .collect()
}

pub fn list_messages(v: Variant, session_id: &str) -> Result<Value, String> {
    let recs = parse_records(v, session_id)?;
    let ms = messages_of(&recs);
    let data: Vec<Value> = ms
        .iter()
        .enumerate()
        .map(|(i, m)| {
            json!({
                "index": i,
                "id": m.id,
                "role": m.role,
                "parent": m.parent,
                "text": m.text,
                "time": m.time,
            })
        })
        .collect();
    let head_id = ms.last().map(|m| m.id.clone()).unwrap_or_default();
    Ok(json!({
        "ok": true,
        "data": data,
        "total": data.len(),
        "headId": head_id,
        "timelineOrder": "oldest-first",
    }))
}

fn build_branch(records: &[Value], at_id: Option<&str>) -> Vec<Value> {
    let by_id: std::collections::HashMap<String, &Value> = records
        .iter()
        .filter_map(|r| r.get("id").and_then(|x| x.as_str()).map(|id| (id.to_string(), r)))
        .collect();
    let ms = messages_of(records);

    let mut keep_ids = std::collections::HashSet::new();
    if let Some(at) = at_id {
        let mut cur = ms.iter().find(|m| m.id.starts_with(at) || m.text.contains(at));
        while let Some(m) = cur {
            keep_ids.insert(m.id.clone());
            cur = if m.parent.is_empty() {
                None
            } else {
                ms.iter().find(|x| x.id == m.parent)
            };
        }
    }

    records
        .iter()
        .filter(|r| {
            let t = r.get("type").and_then(|x| x.as_str()).unwrap_or("");
            if t == "session-meta" || t == "ai-title" {
                return true;
            }
            if at_id.is_none() {
                return true;
            }
            if t == "message" {
                return r
                    .get("id")
                    .and_then(|x| x.as_str())
                    .map(|id| keep_ids.contains(id))
                    .unwrap_or(false);
            }
            if t == "file-history-snapshot" {
                return r
                    .get("messageId")
                    .and_then(|x| x.as_str())
                    .map(|id| keep_ids.contains(id))
                    .unwrap_or(false);
            }
            let mut pid = r.get("parentId").and_then(|x| x.as_str()).unwrap_or("");
            let mut seen = std::collections::HashSet::new();
            while !pid.is_empty() && !seen.contains(pid) {
                if keep_ids.contains(pid) {
                    return true;
                }
                seen.insert(pid);
                pid = by_id
                    .get(pid)
                    .and_then(|p| p.get("parentId"))
                    .and_then(|x| x.as_str())
                    .unwrap_or("");
            }
            false
        })
        .cloned()
        .collect()
}

pub fn preview_branch(
    v: Variant,
    session_id: &str,
    at_id: &str,
    title: &str,
) -> Result<Value, String> {
    let recs = parse_records(v, session_id)?;
    let kept = build_branch(&recs, if at_id.is_empty() { None } else { Some(at_id) });
    Ok(json!({
        "ok": true,
        "srcMessages": messages_of(&recs).len(),
        "keptMessages": messages_of(&kept).len(),
        "srcRecords": recs.len(),
        "keptRecords": kept.len(),
        "title": title,
    }))
}

pub fn do_branch(
    v: Variant,
    session_id: &str,
    at_id: &str,
    title: &str,
) -> Result<Value, String> {
    let src_path = find_jsonl(v, session_id)?;
    let recs = parse_records(v, session_id)?;
    let kept = build_branch(&recs, if at_id.is_empty() { None } else { Some(at_id) });
    let new_id = uuid::Uuid::new_v4().to_string();

    let db_path = v.db();
    let con = Connection::open(&db_path).map_err(|e| format!("打开数据库失败: {}", e))?;

    let cols: Vec<String> = {
        let mut s = con
            .prepare("PRAGMA table_info(sessions)")
            .map_err(|e| e.to_string())?;
        let rows = s
            .query_map([], |r| r.get::<_, String>(1))
            .map_err(|e| e.to_string())?;
        rows.filter_map(|x| x.ok()).collect()
    };

    let src_values: Vec<rusqlite::types::Value> = {
        let mut s = con
            .prepare("select * from sessions where id=?1")
            .map_err(|e| e.to_string())?;
        let mut rows = s.query([session_id]).map_err(|e| e.to_string())?;
        match rows.next().map_err(|e| e.to_string())? {
            Some(r) => (0..cols.len())
                .map(|i| {
                    r.get_ref(i)
                        .map(|v| rusqlite::types::Value::from(v))
                        .map_err(|e| e.to_string())
                })
                .collect::<Result<Vec<_>, _>>()?,
            None => return Err("源会话不在 sessions 表中".to_string()),
        }
    };

    let stamp = Local::now().format("%Y%m%d-%H%M%S");
    let backup = dirs::home_dir()
        .unwrap_or_default()
        .join(v.dir_name())
        .join(format!("workbuddy.db.bak-branch-{}", stamp));
    con.backup(rusqlite::DatabaseName::Main, &backup, None)
        .map_err(|e| format!("备份失败: {}", e))?;

    let now = Local::now().timestamp_millis();
    let mut values: Vec<rusqlite::types::Value> = Vec::new();
    for (i, col) in cols.iter().enumerate() {
        let raw = src_values[i].clone();
        let val = match col.as_str() {
            "id" => rusqlite::types::Value::Text(new_id.clone()),
            "title" | "custom_title" => rusqlite::types::Value::Text(title.to_string()),
            "created_at" | "updated_at" | "last_activity_at" => rusqlite::types::Value::Integer(now),
            "status" => rusqlite::types::Value::Text("completed".into()),
            "deleted_at" | "buddy_snapshot_id" => rusqlite::types::Value::Null,
            "unread" | "agent_dirty" => rusqlite::types::Value::Integer(0),
            _ => raw,
        };
        values.push(val);
    }
    let placeholders = vec!["?"; cols.len()].join(",");
    let sql = format!("insert into sessions ({}) values ({})", cols.join(","), placeholders);
    let params: Vec<&dyn rusqlite::ToSql> = values
        .iter()
        .map(|v| v as &dyn rusqlite::ToSql)
        .collect();
    con.execute(&sql, params.as_slice())
        .map_err(|e| format!("写入会话失败: {}", e))?;

    let dst_path = src_path.with_file_name(format!("{}.jsonl", new_id));
    let mut f = File::create(&dst_path).map_err(|e| format!("创建会话文件失败: {}", e))?;
    for r in &kept {
        let mut obj = r.clone();
        obj["sessionId"] = json!(new_id);
        writeln!(f, "{}", serde_json::to_string(&obj).unwrap()).map_err(|e| e.to_string())?;
    }

    Ok(json!({
        "ok": true,
        "newId": new_id,
        "title": title,
        "keptMessages": messages_of(&kept).len(),
        "backup": backup.to_string_lossy(),
        "file": dst_path.to_string_lossy(),
    }))
}
