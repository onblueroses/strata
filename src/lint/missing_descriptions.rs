use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct MissingDescriptions;

impl LintRule for MissingDescriptions {
    fn name(&self) -> &'static str {
        "missing-descriptions"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        let mut diagnostics = Vec::new();

        for (path, desc) in &scan.descriptions {
            if desc.is_none() {
                let rel = path.to_string_lossy().replace('\\', "/");
                diagnostics.push(Diagnostic {
                    rule: self.name().to_string(),
                    severity: self.severity(),
                    message: "No description found (add frontmatter or heading)".to_string(),
                    location: rel,
                });
            }
        }

        diagnostics.sort_by(|a, b| a.location.cmp(&b.location));
        diagnostics
    }
}
