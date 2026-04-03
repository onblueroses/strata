use crate::config::HooksConfig;
use std::path::{Path, PathBuf};

/// Metadata about a configured lifecycle hook.
#[derive(Debug, Clone)]
pub struct HookMeta {
    /// Hook event name (`session_start`, `session_stop`, etc.).
    pub event: String,
    /// Configured path relative to project root.
    pub path: PathBuf,
    /// Whether the file exists on disk.
    pub exists: bool,
    /// Whether the file has executable permission (Unix only; always true on Windows).
    pub is_executable: bool,
    /// Whether the file starts with a shebang line.
    pub has_shebang: bool,
    /// Total character count (0 if file doesn't exist).
    pub char_count: usize,
}

/// Scan all configured hooks and collect metadata.
pub fn scan_hooks(root: &Path, config: &HooksConfig) -> Vec<HookMeta> {
    let entries = [
        ("session_start", &config.session_start),
        ("session_stop", &config.session_stop),
        ("pre_compact", &config.pre_compact),
        ("post_edit", &config.post_edit),
        ("notification", &config.notification),
    ];

    entries
        .iter()
        .filter(|(_, path)| !path.is_empty())
        .map(|(event, rel_path)| {
            let abs_path = root.join(rel_path);
            let (exists, is_executable, has_shebang, char_count) = if abs_path.is_file() {
                let content = std::fs::read_to_string(&abs_path).unwrap_or_default();
                let shebang = content.starts_with("#!");
                let executable = is_executable_file(&abs_path);
                (true, executable, shebang, content.len())
            } else {
                (false, false, false, 0)
            };

            HookMeta {
                event: (*event).to_string(),
                path: PathBuf::from(rel_path),
                exists,
                is_executable,
                has_shebang,
                char_count,
            }
        })
        .collect()
}

#[cfg(unix)]
fn is_executable_file(path: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    std::fs::metadata(path)
        .map(|m| m.permissions().mode() & 0o111 != 0)
        .unwrap_or(false)
}

#[cfg(not(unix))]
fn is_executable_file(_path: &Path) -> bool {
    // Windows doesn't have Unix-style executable bits; treat as always executable.
    true
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    #[test]
    fn empty_config_no_hooks() {
        let dir = tempfile::tempdir().unwrap();
        let config = HooksConfig::default();
        let hooks = scan_hooks(dir.path(), &config);
        assert!(hooks.is_empty());
    }

    #[test]
    fn configured_but_missing_file() {
        let dir = tempfile::tempdir().unwrap();
        let config = HooksConfig {
            session_start: ".strata/hooks/session-start.sh".to_string(),
            ..HooksConfig::default()
        };
        let hooks = scan_hooks(dir.path(), &config);
        assert_eq!(hooks.len(), 1);
        assert!(!hooks[0].exists);
        assert_eq!(hooks[0].event, "session_start");
    }

    #[test]
    fn existing_hook_with_shebang() {
        let dir = tempfile::tempdir().unwrap();
        let hooks_dir = dir.path().join(".strata").join("hooks");
        std::fs::create_dir_all(&hooks_dir).unwrap();
        std::fs::write(
            hooks_dir.join("session-start.sh"),
            "#!/usr/bin/env bash\necho hello\n",
        )
        .unwrap();

        let config = HooksConfig {
            session_start: ".strata/hooks/session-start.sh".to_string(),
            ..HooksConfig::default()
        };
        let hooks = scan_hooks(dir.path(), &config);
        assert_eq!(hooks.len(), 1);
        assert!(hooks[0].exists);
        assert!(hooks[0].has_shebang);
        assert!(hooks[0].char_count > 0);
    }

    #[test]
    fn hook_without_shebang() {
        let dir = tempfile::tempdir().unwrap();
        let hooks_dir = dir.path().join(".strata").join("hooks");
        std::fs::create_dir_all(&hooks_dir).unwrap();
        std::fs::write(hooks_dir.join("session-start.sh"), "echo hello\n").unwrap();

        let config = HooksConfig {
            session_start: ".strata/hooks/session-start.sh".to_string(),
            ..HooksConfig::default()
        };
        let hooks = scan_hooks(dir.path(), &config);
        assert_eq!(hooks.len(), 1);
        assert!(hooks[0].exists);
        assert!(!hooks[0].has_shebang);
    }
}
