use crate::config::StrataConfig;
use crate::error::{Result, StrataError};
use crate::scanner::sessions;
use crate::ui;
use std::fmt::Write as _;
use std::fs;
use std::path::Path;

pub fn run_start(path: &Path, name: Option<&str>) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let sessions_dir = root.join(&config.sessions.dir);
    fs::create_dir_all(&sessions_dir)?;

    let session_id = generate_session_id(config.sessions.session_id_length);
    let date = today_iso();
    let desc = name.unwrap_or("unnamed");

    // Write current-session marker
    let marker_path = root.join(".strata").join("current-session");
    fs::write(&marker_path, &session_id)?;

    // Create daily note JSON stub
    if config.sessions.daily_notes {
        let filename = format!("{date}-{desc}-{session_id}.json");
        let note_path = sessions_dir.join(&filename);
        let json = format!(
            r#"{{"session_id":"{session_id}","date":"{date}","name":"{desc}","summary":"","decisions":[],"outputs":[],"tags":[]}}"#
        );
        fs::write(&note_path, json)?;
        ui::file_action("create", &format!("{}/{filename}", config.sessions.dir));
    }

    ui::success(&format!("Session started: {session_id}"));
    Ok(())
}

pub fn run_list(path: &Path, limit: usize) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let all_sessions = sessions::scan_sessions(&root, &config.sessions);

    if all_sessions.is_empty() {
        ui::info("No sessions found.");
        return Ok(());
    }

    let shown: Vec<_> = all_sessions.iter().take(limit).collect();

    let mut table = String::new();
    let _ = writeln!(
        table,
        "{:<12} {:<20} {:<10} Session ID",
        "Date", "Name", "Kind"
    );
    let _ = writeln!(table, "{}", "-".repeat(60));

    for s in &shown {
        let kind = match s.kind {
            sessions::SessionFileKind::DailyNote => "note",
            sessions::SessionFileKind::ContextSave => "save",
        };
        let _ = writeln!(
            table,
            "{:<12} {:<20} {:<10} {}",
            s.date, s.name, kind, s.session_id
        );
    }

    println!("{table}");

    if all_sessions.len() > limit {
        ui::info(&format!(
            "Showing {limit} of {} sessions",
            all_sessions.len()
        ));
    }

    Ok(())
}

pub fn run_save(path: &Path, session_id: Option<&str>) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let sessions_dir = root.join(&config.sessions.dir);
    fs::create_dir_all(&sessions_dir)?;

    // Determine session ID
    let sid = if let Some(id) = session_id {
        id.to_string()
    } else {
        let marker = root.join(".strata").join("current-session");
        if marker.exists() {
            fs::read_to_string(&marker)?.trim().to_string()
        } else {
            return Err(StrataError::General(
                "No active session. Start one with `strata session start` or pass --session."
                    .to_string(),
            ));
        }
    };

    let filename = format!("auto-context-save-{sid}.md");
    let save_path = sessions_dir.join(&filename);

    let content = format!(
        "# Context Save\n\nSession: `{sid}`\nSaved: {}\n\n## Working State\n\n<!-- Current task and progress -->\n\n## Key Decisions\n\n<!-- Decisions made this session -->\n",
        today_iso()
    );
    fs::write(&save_path, content)?;

    let rel = format!("{}/{filename}", config.sessions.dir);
    ui::success(&format!("Context saved: {rel}"));

    Ok(())
}

fn generate_session_id(length: u32) -> String {
    // Timestamp-based hash: take lower bytes of current time in nanos
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_nanos());
    let hash = now ^ (now >> 32) ^ (now >> 64);
    let hex = format!("{hash:016x}");
    hex[..length as usize].to_string()
}

fn today_iso() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs());
    let days = now / 86400;
    let (year, month, day) = days_to_ymd(days);
    format!("{year:04}-{month:02}-{day:02}")
}

fn days_to_ymd(mut days: u64) -> (u64, u64, u64) {
    days += 719_468;
    let era = days / 146_097;
    let doe = days - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}
