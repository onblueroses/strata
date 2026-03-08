use crate::error::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::hash::{DefaultHasher, Hash, Hasher};
use std::path::Path;

/// Records what was generated and content hashes for freshness detection.
///
/// Hashing uses `std::hash::DefaultHasher` (`SipHash`). Not stable across Rust
/// versions, but acceptable for a local dev tool - a version change just
/// triggers a one-time regeneration.
#[derive(Debug, Serialize, Deserialize)]
pub struct GenerationState {
    pub generated_at: String,
    pub strata_version: String,
    pub target: String,
    pub config_hash: u64,
    pub files: HashMap<String, FileState>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub git_commit: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct FileState {
    /// Hash of the generated content (below the marker).
    pub content_hash: u64,
    /// Hash of all source inputs that produced this file.
    pub source_hash: u64,
}

/// Compute a deterministic hash of a string's bytes.
pub fn hash_content(content: &str) -> u64 {
    let mut hasher = DefaultHasher::new();
    content.hash(&mut hasher);
    hasher.finish()
}

/// Save generation state to `.strata/state.json`.
pub fn save_state(root: &Path, state: &GenerationState) -> Result<()> {
    let state_path = root.join(".strata").join("state.json");
    let json = serde_json::to_string_pretty(state)?;
    std::fs::write(state_path, json)?;
    Ok(())
}

/// Load generation state from `.strata/state.json`.
pub fn load_state(root: &Path) -> Result<Option<GenerationState>> {
    let state_path = root.join(".strata").join("state.json");
    if !state_path.exists() {
        return Ok(None);
    }
    let content = std::fs::read_to_string(state_path)?;
    let state: GenerationState = serde_json::from_str(&content)?;
    Ok(Some(state))
}

/// Collect source content hashes for context.md.
/// Sources: PROJECT.md + all RULES.md files + skill metadata.
pub fn compute_context_source_hash(root: &Path, config: &crate::config::StrataConfig) -> u64 {
    let mut hasher = DefaultHasher::new();

    // PROJECT.md
    if let Ok(content) = std::fs::read_to_string(root.join("PROJECT.md")) {
        content.hash(&mut hasher);
    }

    // RULES.md per domain
    for domain in &config.project.domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        if let Ok(content) = std::fs::read_to_string(root.join(&dir_name).join("RULES.md")) {
            content.hash(&mut hasher);
        }
    }

    // Skills directory
    let skills_dir = root.join("skills");
    if let Ok(entries) = std::fs::read_dir(&skills_dir) {
        let mut skill_paths: Vec<_> = entries
            .flatten()
            .filter(|e| e.path().is_dir())
            .map(|e| e.path().join("SKILL.md"))
            .filter(|p| p.exists())
            .collect();
        skill_paths.sort();
        for path in skill_paths {
            if let Ok(content) = std::fs::read_to_string(&path) {
                content.hash(&mut hasher);
            }
        }
    }

    hasher.finish()
}

/// Compute source hash for a domain context file.
pub fn compute_domain_source_hash(root: &Path, domain_dir: &str) -> u64 {
    let mut hasher = DefaultHasher::new();

    // RULES.md
    if let Ok(content) = std::fs::read_to_string(root.join(domain_dir).join("RULES.md")) {
        content.hash(&mut hasher);
    }

    // All non-RULES files in the domain
    if let Ok(entries) = std::fs::read_dir(root.join(domain_dir)) {
        let mut paths: Vec<_> = entries
            .flatten()
            .filter(|e| e.file_name() != "RULES.md" && e.path().is_file())
            .map(|e| e.path())
            .collect();
        paths.sort();
        for path in paths {
            if let Ok(content) = std::fs::read_to_string(&path) {
                content.hash(&mut hasher);
            }
        }
    }

    hasher.finish()
}

/// Build generation state from generated files and config.
/// Shared by `generate` and `update` commands.
pub fn build_generation_state(
    root: &Path,
    config: &crate::config::StrataConfig,
    config_path: &Path,
    files: &[(String, String)],
    target: crate::config::AgentTarget,
    git_commit: Option<String>,
) -> GenerationState {
    let config_content = std::fs::read_to_string(config_path).unwrap_or_default();
    let mut file_states = HashMap::new();

    for (rel_path, content) in files {
        let source_hash = if rel_path == ".strata/context.md" {
            compute_context_source_hash(root, config)
        } else if rel_path.starts_with(".strata/domains/") {
            let domain_dir = rel_path
                .strip_prefix(".strata/domains/")
                .and_then(|s| s.strip_suffix(".md"))
                .unwrap_or("");
            compute_domain_source_hash(root, domain_dir)
        } else {
            hash_content(content)
        };

        file_states.insert(
            rel_path.clone(),
            FileState {
                content_hash: hash_content(content),
                source_hash,
            },
        );
    }

    GenerationState {
        generated_at: now_iso(),
        strata_version: env!("CARGO_PKG_VERSION").to_string(),
        target: target.to_string(),
        config_hash: hash_content(&config_content),
        files: file_states,
        git_commit,
    }
}

/// ISO-8601 timestamp without external deps.
fn now_iso() -> String {
    let epoch = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);

    let secs_per_day: u64 = 86400;
    let days = epoch / secs_per_day;
    let time_of_day = epoch % secs_per_day;
    let hours = time_of_day / 3600;
    let minutes = (time_of_day % 3600) / 60;
    let seconds = time_of_day % 60;

    let (year, month, day) = civil_from_days(days as i64);

    format!("{year:04}-{month:02}-{day:02}T{hours:02}:{minutes:02}:{seconds:02}Z")
}

/// Convert days since epoch to civil date. Algorithm from Howard Hinnant.
fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097) as u32;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = i64::from(yoe) + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    #[test]
    fn hash_deterministic() {
        let h1 = hash_content("hello world");
        let h2 = hash_content("hello world");
        assert_eq!(h1, h2);
    }

    #[test]
    fn hash_different_inputs() {
        let h1 = hash_content("hello");
        let h2 = hash_content("world");
        assert_ne!(h1, h2);
    }

    #[test]
    fn roundtrip_state() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::create_dir_all(dir.path().join(".strata")).unwrap();

        let state = GenerationState {
            generated_at: "2026-03-08T12:00:00Z".to_string(),
            strata_version: "0.2.0".to_string(),
            target: "generic".to_string(),
            config_hash: 12345,
            files: HashMap::from([(
                ".strata/context.md".to_string(),
                FileState {
                    content_hash: 111,
                    source_hash: 222,
                },
            )]),
            git_commit: None,
        };

        save_state(dir.path(), &state).unwrap();
        let loaded = load_state(dir.path()).unwrap().unwrap();
        assert_eq!(loaded.generated_at, "2026-03-08T12:00:00Z");
        assert_eq!(loaded.strata_version, "0.2.0");
        assert_eq!(loaded.target, "generic");
        assert_eq!(loaded.config_hash, 12345);
        assert_eq!(loaded.files[".strata/context.md"].content_hash, 111);
        assert_eq!(loaded.files[".strata/context.md"].source_hash, 222);
    }

    #[test]
    fn load_missing_state() {
        let dir = tempfile::tempdir().unwrap();
        let loaded = load_state(dir.path()).unwrap();
        assert!(loaded.is_none());
    }
}
