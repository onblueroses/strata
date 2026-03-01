use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct ContextBudget;

impl LintRule for ContextBudget {
    fn name(&self) -> &'static str {
        "context-budget"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let mut diagnostics = Vec::new();
        let budgets = &config.context;

        // Check PROJECT.md
        let project_md = root.join("PROJECT.md");
        if let Ok(content) = std::fs::read_to_string(&project_md) {
            let len = content.len();
            if len > budgets.project_budget as usize {
                diagnostics.push(Diagnostic {
                    rule: self.name().to_string(),
                    severity: self.severity(),
                    message: format!(
                        "PROJECT.md is {len} chars, budget is {}",
                        budgets.project_budget
                    ),
                    location: "PROJECT.md".to_string(),
                });
            }
        }

        // Check INDEX.md
        let index_md = root.join("INDEX.md");
        if let Ok(content) = std::fs::read_to_string(&index_md) {
            let len = content.len();
            if len > budgets.index_budget as usize {
                diagnostics.push(Diagnostic {
                    rule: self.name().to_string(),
                    severity: self.severity(),
                    message: format!(
                        "INDEX.md is {len} chars, budget is {}",
                        budgets.index_budget
                    ),
                    location: "INDEX.md".to_string(),
                });
            }
        }

        // Check each domain RULES.md
        for domain_dir in scan.domain_rules.keys() {
            let rules_path = root.join(domain_dir).join("RULES.md");
            if let Ok(content) = std::fs::read_to_string(&rules_path) {
                let len = content.len();
                if len > budgets.rules_budget as usize {
                    let location = format!("{}/RULES.md", domain_dir.display());
                    diagnostics.push(Diagnostic {
                        rule: self.name().to_string(),
                        severity: self.severity(),
                        message: format!(
                            "{location} is {len} chars, budget is {}",
                            budgets.rules_budget
                        ),
                        location,
                    });
                }
            }
        }

        // Check each skill SKILL.md
        for skill in &scan.skills {
            if skill.char_count > budgets.skill_budget as usize {
                let location = skill.path.to_string_lossy().replace('\\', "/");
                diagnostics.push(Diagnostic {
                    rule: self.name().to_string(),
                    severity: self.severity(),
                    message: format!(
                        "{location} is {} chars, budget is {}",
                        skill.char_count, budgets.skill_budget
                    ),
                    location,
                });
            }
        }

        diagnostics
    }
}
