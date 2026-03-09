pub mod context_budget;
pub mod context_freshness;
pub mod custom_rules;
pub mod dead_links;
pub mod empty_folders;
pub mod hook_budget;
pub mod hook_structure;
pub mod index_freshness;
pub mod memory_budget;
pub mod memory_structure;
pub mod missing_descriptions;
pub mod orphan_files;
pub mod rules_completeness;
pub mod session_structure;
pub mod skill_structure;
pub mod spec_ownership;
pub mod spec_stale;
pub mod spec_structure;
pub mod starter_skills;

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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub line: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub column: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub end_line: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub end_column: Option<u32>,
}

impl Diagnostic {
    pub fn new(
        rule: impl Into<String>,
        severity: Severity,
        message: impl Into<String>,
        location: impl Into<String>,
    ) -> Self {
        Self {
            rule: rule.into(),
            severity,
            message: message.into(),
            location: location.into(),
            line: None,
            column: None,
            end_line: None,
            end_column: None,
        }
    }

    pub fn with_span(mut self, line: u32, column: u32) -> Self {
        self.line = Some(line);
        self.column = Some(column);
        self
    }

    #[expect(
        dead_code,
        reason = "reserved for when lint rules provide end positions"
    )]
    pub fn with_end_span(mut self, end_line: u32, end_column: u32) -> Self {
        self.end_line = Some(end_line);
        self.end_column = Some(end_column);
        self
    }
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
            Box::new(memory_budget::MemoryBudget),
            Box::new(memory_structure::MemoryStructure),
            Box::new(hook_structure::HookStructure),
            Box::new(hook_budget::HookBudget),
            Box::new(spec_structure::SpecStructure),
            Box::new(spec_stale::SpecStale),
            Box::new(spec_ownership::SpecOwnership),
            Box::new(session_structure::SessionStructure),
            Box::new(starter_skills::StarterSkills),
        ];

        let disabled = &config.lint.disable;
        let mut rules: Vec<Box<dyn LintRule>> = all_rules
            .into_iter()
            .filter(|r| !disabled.contains(&r.name().to_string()))
            .collect();

        // Append user-defined custom rules from config
        for spec in &config.custom_rules {
            if !disabled.contains(&spec.name) {
                rules.push(Box::new(custom_rules::CustomRule::new(spec.clone())));
            }
        }

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
