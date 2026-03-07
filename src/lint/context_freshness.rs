use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct ContextFreshness;

impl LintRule for ContextFreshness {
    fn name(&self) -> &'static str {
        "context-freshness"
    }

    fn severity(&self) -> Severity {
        Severity::Info
    }

    fn check(&self, _scan: &ProjectScan, root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        let context_md = root.join(".strata").join("context.md");
        if !context_md.exists() {
            return Vec::new(); // No generated context = silent
        }

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
            self.name(),
            self.severity(),
            format!(
                ".strata/context.md is stale (modified sources: {}). Run `strata generate` to refresh.",
                stale_sources.join(", ")
            ),
            ".strata/context.md",
        )]
    }
}
