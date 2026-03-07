use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct IndexFreshness;

impl LintRule for IndexFreshness {
    fn name(&self) -> &'static str {
        "index-freshness"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        let unindexed = scan.unindexed_files(root);

        unindexed
            .iter()
            .map(|file| {
                let rel = file
                    .strip_prefix(root)
                    .unwrap_or(file)
                    .to_string_lossy()
                    .replace('\\', "/");
                Diagnostic::new(
                    self.name(),
                    self.severity(),
                    format!("File not listed in INDEX.md: {rel}"),
                    "INDEX.md",
                )
            })
            .collect()
    }
}
