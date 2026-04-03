use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct EmptyFolders;

impl LintRule for EmptyFolders {
    fn name(&self) -> &'static str {
        "empty-folders"
    }

    fn severity(&self) -> Severity {
        Severity::Info
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let mut diagnostics = Vec::new();

        for domain in &config.project.domains {
            let dir_name = format!("{}-{}", domain.prefix, domain.name);

            // Check if any scanned file starts with this domain prefix
            let has_content = scan.files.iter().any(|f| {
                let rel = f.to_string_lossy().replace('\\', "/");
                rel.starts_with(&dir_name) && !rel.ends_with("RULES.md")
            });

            if !has_content {
                diagnostics.push(Diagnostic::new(
                    self.name(),
                    self.severity(),
                    format!("Domain '{}' has no content files", domain.name),
                    format!("{dir_name}/"),
                ));
            }
        }

        diagnostics
    }
}
