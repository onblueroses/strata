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
