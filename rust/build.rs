use std::process::Command;

fn main() {
    tauri_build::build();

    // 版本号唯一来源 = git tag（打在 HEAD 上优先，否则最近 tag）
    let tag = Command::new("git")
        .args(["tag", "--points-at", "HEAD"])
        .output()
        .ok()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .filter(|s| !s.is_empty())
        .or_else(|| {
            Command::new("git")
                .args(["describe", "--tags", "--abbrev=0"])
                .output()
                .ok()
                .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
                .filter(|s| !s.is_empty())
        })
        .unwrap_or_else(|| "0.0.0-dev".to_string());

    println!("cargo:rustc-env=APP_VERSION={}", tag);
    println!("cargo:rerun-if-changed=../.git/refs/tags");
}
