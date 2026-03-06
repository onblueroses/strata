use crate::config::SessionsConfig;
use std::path::{Path, PathBuf};

/// What kind of session file this is.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionFileKind {
    DailyNote,
    ContextSave,
}

/// Metadata about a session file.
#[derive(Debug, Clone)]
pub struct SessionMeta {
    /// Session ID extracted from the filename.
    pub session_id: String,
    /// Date portion of the filename (YYYY-MM-DD).
    pub date: String,
    /// Descriptive name from the filename (between date and session ID).
    pub name: String,
    /// What kind of session file.
    pub kind: SessionFileKind,
    /// Relative path from project root.
    pub path: PathBuf,
}

/// Scan the sessions directory and collect metadata.
pub fn scan_sessions(root: &Path, config: &SessionsConfig) -> Vec<SessionMeta> {
    let sessions_dir = root.join(&config.dir);
    if !sessions_dir.is_dir() {
        return Vec::new();
    }

    let Ok(entries) = std::fs::read_dir(&sessions_dir) else {
        return Vec::new();
    };

    let mut sessions: Vec<SessionMeta> = entries
        .flatten()
        .filter_map(|e| {
            let abs = e.path();
            if !abs.is_file() {
                return None;
            }
            let rel = abs.strip_prefix(root).unwrap_or(&abs).to_path_buf();
            let filename = abs.file_name()?.to_str()?;
            parse_session_filename(filename, rel)
        })
        .collect();

    sessions.sort_by(|a, b| b.date.cmp(&a.date).then_with(|| a.name.cmp(&b.name)));
    sessions
}

/// Parse a session filename into metadata.
///
/// Expected formats:
/// - Daily note JSON: `2026-03-04-feature-work-abc12345.json`
/// - Context save MD: `auto-context-save-abc12345.md`
fn parse_session_filename(filename: &str, rel_path: PathBuf) -> Option<SessionMeta> {
    if let Some(stem) = filename.strip_suffix(".json") {
        // Daily note: YYYY-MM-DD-name-sessionid
        // Minimum: YYYY-MM-DD-X-12345678 (date + at least one name segment + 8-char ID)
        if stem.len() < 18 {
            return None;
        }
        let date = &stem[..10];
        // Validate date format roughly
        if date.len() != 10 || date.as_bytes()[4] != b'-' || date.as_bytes()[7] != b'-' {
            return None;
        }
        let rest = &stem[11..]; // after "YYYY-MM-DD-"
        // Session ID is last segment after final hyphen
        if let Some(last_hyphen) = rest.rfind('-') {
            let name = &rest[..last_hyphen];
            let session_id = &rest[last_hyphen + 1..];
            if session_id.is_empty() {
                return None;
            }
            return Some(SessionMeta {
                session_id: session_id.to_string(),
                date: date.to_string(),
                name: name.to_string(),
                kind: SessionFileKind::DailyNote,
                path: rel_path,
            });
        }
        None
    } else if let Some(stem) = filename.strip_suffix(".md") {
        // Context save: auto-context-save-sessionid
        let prefix = "auto-context-save-";
        if let Some(session_id) = stem.strip_prefix(prefix) {
            if session_id.is_empty() {
                return None;
            }
            return Some(SessionMeta {
                session_id: session_id.to_string(),
                date: String::new(),
                name: "context-save".to_string(),
                kind: SessionFileKind::ContextSave,
                path: rel_path,
            });
        }
        None
    } else {
        None
    }
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    #[test]
    fn parse_daily_note() {
        let meta = parse_session_filename(
            "2026-03-04-feature-work-abc12345.json",
            PathBuf::from(".strata/sessions/2026-03-04-feature-work-abc12345.json"),
        )
        .unwrap();
        assert_eq!(meta.date, "2026-03-04");
        assert_eq!(meta.name, "feature-work");
        assert_eq!(meta.session_id, "abc12345");
        assert_eq!(meta.kind, SessionFileKind::DailyNote);
    }

    #[test]
    fn parse_context_save() {
        let meta = parse_session_filename(
            "auto-context-save-abc12345.md",
            PathBuf::from(".strata/sessions/auto-context-save-abc12345.md"),
        )
        .unwrap();
        assert_eq!(meta.session_id, "abc12345");
        assert_eq!(meta.kind, SessionFileKind::ContextSave);
    }

    #[test]
    fn parse_invalid_filename() {
        assert!(parse_session_filename("random.txt", PathBuf::from("random.txt")).is_none());
        assert!(parse_session_filename("short.json", PathBuf::from("short.json")).is_none());
    }

    #[test]
    fn scan_sessions_empty() {
        let dir = tempfile::tempdir().unwrap();
        let config = SessionsConfig::default();
        let sessions = scan_sessions(dir.path(), &config);
        assert!(sessions.is_empty());
    }

    #[test]
    fn scan_sessions_finds_files() {
        let dir = tempfile::tempdir().unwrap();
        let sessions_dir = dir.path().join(".strata").join("sessions");
        std::fs::create_dir_all(&sessions_dir).unwrap();

        std::fs::write(
            sessions_dir.join("2026-03-04-test-abc12345.json"),
            r#"{"summary":"test"}"#,
        )
        .unwrap();
        std::fs::write(
            sessions_dir.join("auto-context-save-abc12345.md"),
            "# Context\n",
        )
        .unwrap();

        let config = SessionsConfig::default();
        let sessions = scan_sessions(dir.path(), &config);
        assert_eq!(sessions.len(), 2);
    }
}
