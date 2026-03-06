use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use crate::scanner::sessions::SessionFileKind;
use std::path::Path;

pub struct SessionStructure;

impl LintRule for SessionStructure {
    fn name(&self) -> &'static str {
        "session-structure"
    }

    fn severity(&self) -> Severity {
        Severity::Info
    }

    fn check(&self, scan: &ProjectScan, root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        let mut diagnostics = Vec::new();

        for session in &scan.sessions {
            let loc = session.path.to_string_lossy().to_string();
            let abs = root.join(&session.path);

            match session.kind {
                SessionFileKind::DailyNote => {
                    // Validate JSON is parseable
                    if let Ok(content) = std::fs::read_to_string(&abs) {
                        if serde_json::from_str::<serde_json::Value>(&content).is_err() {
                            diagnostics.push(Diagnostic {
                                rule: self.name().to_string(),
                                severity: self.severity(),
                                message: format!(
                                    "Daily note '{}' contains invalid JSON",
                                    session.name
                                ),
                                location: loc,
                            });
                        }
                    }
                }
                SessionFileKind::ContextSave => {
                    // Check for at least one heading
                    if let Ok(content) = std::fs::read_to_string(&abs) {
                        let has_heading = content.lines().any(|l| l.starts_with('#'));
                        if !has_heading {
                            diagnostics.push(Diagnostic {
                                rule: self.name().to_string(),
                                severity: self.severity(),
                                message: format!(
                                    "Context save for session '{}' has no markdown headings",
                                    session.session_id
                                ),
                                location: loc,
                            });
                        }
                    }
                }
            }
        }

        diagnostics
    }
}
