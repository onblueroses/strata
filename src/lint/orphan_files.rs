use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct OrphanFiles;

impl LintRule for OrphanFiles {
    fn name(&self) -> &'static str {
        "orphan-files"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        scan.orphan_files()
            .iter()
            .map(|path| {
                let rel = path.to_string_lossy().replace('\\', "/");
                Diagnostic::new(
                    self.name(),
                    self.severity(),
                    "File not referenced anywhere (not in INDEX.md or any crosslink)",
                    rel,
                )
            })
            .collect()
    }
}
