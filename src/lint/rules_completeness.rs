use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct RulesCompleteness;

impl LintRule for RulesCompleteness {
    fn name(&self) -> &str {
        "rules-completeness"
    }

    fn severity(&self) -> Severity {
        Severity::Error
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let mut diagnostics = Vec::new();

        for domain in &config.project.domains {
            let dir_name = format!("{}-{}", domain.prefix, domain.name);
            let dir_path = std::path::PathBuf::from(&dir_name);

            match scan.domain_rules.get(&dir_path) {
                None => {
                    diagnostics.push(Diagnostic {
                        rule: self.name().to_string(),
                        severity: self.severity(),
                        message: format!("RULES.md missing for domain '{}'", domain.name),
                        location: format!("{}/RULES.md", dir_name),
                    });
                }
                Some(rules) => {
                    if !rules.has_purpose {
                        diagnostics.push(Diagnostic {
                            rule: self.name().to_string(),
                            severity: self.severity(),
                            message: format!(
                                "RULES.md for '{}' is missing a Purpose section",
                                domain.name
                            ),
                            location: format!("{}/RULES.md", dir_name),
                        });
                    }
                    if !rules.has_boundaries {
                        diagnostics.push(Diagnostic {
                            rule: self.name().to_string(),
                            severity: self.severity(),
                            message: format!(
                                "RULES.md for '{}' is missing a Boundaries section",
                                domain.name
                            ),
                            location: format!("{}/RULES.md", dir_name),
                        });
                    }
                }
            }
        }

        diagnostics
    }
}
