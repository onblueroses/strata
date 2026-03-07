use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct DeadLinks;

impl LintRule for DeadLinks {
    fn name(&self) -> &'static str {
        "dead-links"
    }

    fn severity(&self) -> Severity {
        Severity::Error
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        scan.dead_links(config.structure.link_mode)
            .iter()
            .map(|(source, link)| {
                Diagnostic::new(
                    self.name(),
                    self.severity(),
                    format!("Dead crosslink to '{}'", link.target),
                    source.to_string_lossy().replace('\\', "/"),
                )
                .with_span(link.line, link.column)
            })
            .collect()
    }
}
