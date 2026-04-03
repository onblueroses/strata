use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use crate::state;
use std::path::Path;

pub struct ContextFreshness;

impl LintRule for ContextFreshness {
    fn name(&self) -> &'static str {
        "context-freshness"
    }

    fn severity(&self) -> Severity {
        Severity::Info
    }

    fn check(&self, _scan: &ProjectScan, root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let context_md = root.join(".strata").join("context.md");
        if !context_md.exists() {
            return Vec::new();
        }

        // Try hash-based check via state.json first
        if let Ok(Some(gen_state)) = state::load_state(root) {
            return check_with_state(root, config, &gen_state);
        }

        // Fallback: mtime-based check (no state.json yet)
        check_with_mtime(root)
    }
}

fn check_with_state(
    root: &Path,
    config: &StrataConfig,
    gen_state: &state::GenerationState,
) -> Vec<Diagnostic> {
    let mut stale_sources: Vec<String> = Vec::new();

    // Check context.md source hash
    if let Some(file_state) = gen_state.files.get(".strata/context.md") {
        let current_hash = state::compute_context_source_hash(root, config);
        if current_hash != file_state.source_hash {
            stale_sources.push("project sources".to_string());
        }
    }

    // Check domain file source hashes
    for (path, file_state) in &gen_state.files {
        if let Some(domain_dir) = path
            .strip_prefix(".strata/domains/")
            .and_then(|s| s.strip_suffix(".md"))
        {
            let current_hash = state::compute_domain_source_hash(root, domain_dir);
            if current_hash != file_state.source_hash {
                stale_sources.push(format!("{domain_dir}/"));
            }
        }
    }

    // Check config hash
    let config_path = root.join("strata.toml");
    if let Ok(content) = std::fs::read_to_string(config_path) {
        if state::hash_content(&content) != gen_state.config_hash {
            stale_sources.push("strata.toml".to_string());
        }
    }

    if !stale_sources.is_empty() {
        return vec![Diagnostic::new(
            "context-freshness",
            Severity::Info,
            format!(
                ".strata/context.md is stale (changed: {}). Run `strata generate` to refresh.",
                stale_sources.join(", ")
            ),
            ".strata/context.md",
        )];
    }

    // Hashes match, but check if commits have passed since generation
    if let Some(ref gen_commit) = gen_state.git_commit {
        if let Some(current_commit) = crate::git::head_commit(root) {
            if gen_commit != &current_commit {
                if let Some(distance) =
                    crate::git::commit_distance(root, gen_commit, &current_commit)
                {
                    if distance > 0 {
                        return vec![Diagnostic::new(
                            "context-freshness",
                            Severity::Info,
                            format!(
                                "Context may be stale ({distance} commit(s) since generation). Run `strata diff` to check."
                            ),
                            ".strata/context.md",
                        )];
                    }
                }
            }
        }
    }

    Vec::new()
}

fn check_with_mtime(root: &Path) -> Vec<Diagnostic> {
    let context_md = root.join(".strata").join("context.md");
    let Ok(context_mtime) = std::fs::metadata(&context_md).and_then(|m| m.modified()) else {
        return Vec::new();
    };

    let mut stale_sources: Vec<String> = Vec::new();

    // Check PROJECT.md
    let project_md = root.join("PROJECT.md");
    if let Ok(meta) = std::fs::metadata(&project_md)
        && let Ok(mtime) = meta.modified()
        && mtime > context_mtime
    {
        stale_sources.push("PROJECT.md".to_string());
    }

    // Check RULES.md files
    if let Ok(entries) = std::fs::read_dir(root) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                let rules_path = path.join("RULES.md");
                if let Ok(meta) = std::fs::metadata(&rules_path)
                    && let Ok(mtime) = meta.modified()
                    && mtime > context_mtime
                {
                    let dir_name = entry.file_name().to_string_lossy().to_string();
                    stale_sources.push(format!("{dir_name}/RULES.md"));
                }
            }
        }
    }

    if stale_sources.is_empty() {
        return Vec::new();
    }

    vec![Diagnostic::new(
        "context-freshness",
        Severity::Info,
        format!(
            ".strata/context.md is stale (modified sources: {}). Run `strata generate` to refresh.",
            stale_sources.join(", ")
        ),
        ".strata/context.md",
    )]
}
