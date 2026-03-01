pub mod context_budget;
pub mod context_freshness;
pub mod dead_links;
pub mod empty_folders;
pub mod index_freshness;
pub mod missing_descriptions;
pub mod orphan_files;
pub mod rules_completeness;
pub mod skill_structure;

use crate::config::StrataConfig;
use crate::scanner::ProjectScan;
use serde::Serialize;
use std::path::Path;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Severity {
    Error,
    Warning,
    Info,
}

#[derive(Debug, Clone, Serialize)]
pub struct Diagnostic {
    pub rule: String,
    pub severity: Severity,
    pub message: String,
    pub location: String,
}

pub trait LintRule {
    fn name(&self) -> &str;
    fn severity(&self) -> Severity;
    fn check(&self, scan: &ProjectScan, root: &Path, config: &StrataConfig) -> Vec<Diagnostic>;
}

pub struct LintEngine {
    rules: Vec<Box<dyn LintRule>>,
}

impl std::fmt::Debug for LintEngine {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("LintEngine")
            .field("rules", &format!("[{} rules]", self.rules.len()))
            .finish()
    }
}

impl LintEngine {
    pub fn new(config: &StrataConfig) -> Self {
        let all_rules: Vec<Box<dyn LintRule>> = vec![
            Box::new(rules_completeness::RulesCompleteness),
            Box::new(index_freshness::IndexFreshness),
            Box::new(dead_links::DeadLinks),
            Box::new(missing_descriptions::MissingDescriptions),
            Box::new(orphan_files::OrphanFiles),
            Box::new(empty_folders::EmptyFolders),
            Box::new(context_budget::ContextBudget),
            Box::new(context_freshness::ContextFreshness),
            Box::new(skill_structure::SkillStructure),
        ];

        let disabled = &config.lint.disable;
        let rules = all_rules
            .into_iter()
            .filter(|r| !disabled.contains(&r.name().to_string()))
            .collect();

        Self { rules }
    }

    pub fn run(&self, scan: &ProjectScan, root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let mut diagnostics = Vec::new();
        for rule in &self.rules {
            diagnostics.extend(rule.check(scan, root, config));
        }
        // Sort: errors first, then warnings, then info
        diagnostics.sort_by_key(|d| match d.severity {
            Severity::Error => 0,
            Severity::Warning => 1,
            Severity::Info => 2,
        });
        diagnostics
    }
}
