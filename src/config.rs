use crate::error::{Result, StrataError};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

/// A single user-defined lint rule from strata.toml.
/// Check types: `file_exists`, `file_missing`, `content_contains`, `frontmatter_key`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CustomRuleSpec {
    pub name: String,
    /// `"error"`, `"warning"`, or `"info"`
    #[serde(default = "default_severity")]
    pub severity: String,
    /// `"file_exists"`, `"file_missing"`, `"content_contains"`, or `"frontmatter_key"`
    pub check: String,
    /// Glob pattern for file matching (relative to project root)
    pub glob: String,
    pub message: String,
    /// Required for `content_contains`
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pattern: Option<String>,
    /// Required for `frontmatter_key`
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub key: Option<String>,
    /// For `content_contains`: true = flag when pattern absent, false = flag when present
    #[serde(default)]
    pub negate: bool,
}

fn default_severity() -> String {
    "warning".to_string()
}

/// Workspace (monorepo) configuration.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WorkspaceConfig {
    /// Member project directories (relative paths from workspace root).
    #[serde(default)]
    pub members: Vec<String>,
}

/// Top-level strata.toml configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StrataConfig {
    #[serde(default)]
    pub project: ProjectConfig,
    #[serde(default)]
    pub structure: StructureConfig,
    #[serde(default)]
    pub lint: LintConfig,
    #[serde(default)]
    pub context: ContextConfig,
    #[serde(default)]
    pub memory: MemoryConfig,
    #[serde(default)]
    pub hooks: HooksConfig,
    #[serde(default)]
    pub specs: SpecsConfig,
    #[serde(default)]
    pub sessions: SessionsConfig,
    #[serde(default)]
    pub targets: TargetsConfig,
    #[serde(default)]
    pub skills: SkillsConfig,
    #[serde(default)]
    pub custom_rules: Vec<CustomRuleSpec>,
    #[serde(default)]
    pub workspace: WorkspaceConfig,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ProjectConfig {
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub domains: Vec<DomainConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DomainConfig {
    pub name: String,
    pub prefix: String,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LinkMode {
    /// Resolve links as relative paths from the source file (default for code projects).
    #[default]
    Path,
    /// Resolve links by matching filename anywhere in the project (Obsidian/vault behavior).
    Name,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StructureConfig {
    /// Glob patterns for files/dirs to ignore during scanning.
    #[serde(default = "default_ignore_patterns")]
    pub ignore: Vec<String>,

    /// Whether to require frontmatter descriptions in all files.
    #[serde(default)]
    pub require_descriptions: bool,

    /// How crosslinks are resolved: "path" (relative paths) or "name" (filename match).
    #[serde(default)]
    pub link_mode: LinkMode,

    /// File extensions to scan for crosslinks and descriptions.
    /// Overrides the built-in default list when specified.
    #[serde(default = "default_scan_extensions")]
    pub scan_extensions: Vec<String>,
}

impl Default for StructureConfig {
    fn default() -> Self {
        Self {
            ignore: default_ignore_patterns(),
            require_descriptions: false,
            link_mode: LinkMode::default(),
            scan_extensions: default_scan_extensions(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LintConfig {
    /// Rules to disable (by slug).
    #[serde(default)]
    pub disable: Vec<String>,

    /// Treat warnings as errors.
    #[serde(default)]
    pub strict: bool,

    /// Days before `last_verified:` dates trigger a stale-dates warning.
    #[serde(default = "default_stale_verified_days")]
    pub stale_verified_days: u32,

    /// Days before `_Last updated:_` dates trigger a stale-dates warning.
    #[serde(default = "default_stale_updated_days")]
    pub stale_updated_days: u32,

    /// Days before `WAITING (` markers trigger a waiting-markers warning.
    #[serde(default = "default_stale_waiting_days")]
    pub stale_waiting_days: u32,
}

impl Default for LintConfig {
    fn default() -> Self {
        Self {
            disable: Vec::new(),
            strict: false,
            stale_verified_days: default_stale_verified_days(),
            stale_updated_days: default_stale_updated_days(),
            stale_waiting_days: default_stale_waiting_days(),
        }
    }
}

/// Character budgets for context generation.
/// Controls how much content is loaded into AI agent context windows.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[expect(
    clippy::struct_field_names,
    reason = "all fields represent distinct budgets; the _budget suffix is intentional"
)]
pub struct ContextConfig {
    #[serde(default = "default_project_budget")]
    pub project_budget: u32,
    #[serde(default = "default_index_budget")]
    pub index_budget: u32,
    #[serde(default = "default_rules_budget")]
    pub rules_budget: u32,
    #[serde(default = "default_skill_budget")]
    pub skill_budget: u32,
}

impl Default for ContextConfig {
    fn default() -> Self {
        Self {
            project_budget: default_project_budget(),
            index_budget: default_index_budget(),
            rules_budget: default_rules_budget(),
            skill_budget: default_skill_budget(),
        }
    }
}

/// Configuration for the memory layer (MEMORY.md, CLAUDE.md, etc.).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryConfig {
    /// Which files count as memory layer files.
    #[serde(default = "default_memory_files")]
    pub files: Vec<String>,
    /// Per-file character budget (~800 tokens at 4 chars/token).
    #[serde(default = "default_memory_budget")]
    pub budget: u32,
}

impl Default for MemoryConfig {
    fn default() -> Self {
        Self {
            files: default_memory_files(),
            budget: default_memory_budget(),
        }
    }
}

/// Lifecycle hook configuration.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct HooksConfig {
    #[serde(default)]
    pub session_start: String,
    #[serde(default)]
    pub session_stop: String,
    #[serde(default)]
    pub pre_compact: String,
    #[serde(default)]
    pub post_edit: String,
    #[serde(default)]
    pub notification: String,
}

/// Spec system configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpecsConfig {
    #[serde(default = "default_specs_dir")]
    pub dir: String,
    #[serde(default = "default_true")]
    pub require_session_ownership: bool,
    #[serde(default = "default_max_steps_per_phase")]
    pub max_steps_per_phase: u32,
}

impl Default for SpecsConfig {
    fn default() -> Self {
        Self {
            dir: default_specs_dir(),
            require_session_ownership: true,
            max_steps_per_phase: default_max_steps_per_phase(),
        }
    }
}

/// Session tracking configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionsConfig {
    #[serde(default = "default_sessions_dir")]
    pub dir: String,
    #[serde(default = "default_true")]
    pub daily_notes: bool,
    #[serde(default = "default_true")]
    pub context_save: bool,
    #[serde(default = "default_session_id_length")]
    pub session_id_length: u32,
    #[serde(default = "default_staleness_days")]
    pub staleness_days: u32,
}

impl Default for SessionsConfig {
    fn default() -> Self {
        Self {
            dir: default_sessions_dir(),
            daily_notes: true,
            context_save: true,
            session_id_length: default_session_id_length(),
            staleness_days: default_staleness_days(),
        }
    }
}

/// Agent target output configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TargetsConfig {
    #[serde(default)]
    pub default: AgentTarget,
}

impl Default for TargetsConfig {
    fn default() -> Self {
        Self {
            default: AgentTarget::Generic,
        }
    }
}

/// Skill eval/optimize configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillsConfig {
    /// Backend CLI to use for trigger testing (e.g. "claude-code").
    #[serde(default = "default_eval_backend")]
    pub eval_backend: String,
    /// Number of parallel worker threads for eval.
    #[serde(default = "default_eval_workers")]
    pub eval_workers: u32,
    /// Timeout in seconds per query.
    #[serde(default = "default_eval_timeout")]
    pub eval_timeout: u64,
    /// Minimum trigger rate for positive queries to pass.
    #[serde(default = "default_trigger_threshold")]
    pub trigger_threshold: f64,
    /// How many times each query is run (higher = more stable signal).
    #[serde(default = "default_runs_per_query")]
    pub runs_per_query: u32,
    /// Fraction of eval set held out as test set during optimization.
    #[serde(default = "default_holdout")]
    pub holdout: f64,
    /// Maximum optimization iterations.
    #[serde(default = "default_max_iterations")]
    pub max_iterations: u32,
    /// Optional model override passed to backend.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
}

impl Default for SkillsConfig {
    fn default() -> Self {
        Self {
            eval_backend: default_eval_backend(),
            eval_workers: default_eval_workers(),
            eval_timeout: default_eval_timeout(),
            trigger_threshold: default_trigger_threshold(),
            runs_per_query: default_runs_per_query(),
            holdout: default_holdout(),
            max_iterations: default_max_iterations(),
            model: None,
        }
    }
}

fn default_eval_backend() -> String {
    "claude-code".to_string()
}

const fn default_eval_workers() -> u32 {
    4
}

const fn default_eval_timeout() -> u64 {
    30
}

const fn default_trigger_threshold() -> f64 {
    0.5
}

const fn default_runs_per_query() -> u32 {
    1
}

const fn default_holdout() -> f64 {
    0.4
}

const fn default_max_iterations() -> u32 {
    5
}

/// Supported AI agent targets for context generation.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, clap::ValueEnum)]
#[serde(rename_all = "lowercase")]
pub enum AgentTarget {
    #[default]
    Generic,
    Claude,
    Cursor,
    Copilot,
}

impl std::fmt::Display for AgentTarget {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Generic => write!(f, "generic"),
            Self::Claude => write!(f, "claude"),
            Self::Cursor => write!(f, "cursor"),
            Self::Copilot => write!(f, "copilot"),
        }
    }
}

/// Init preset tiers.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, clap::ValueEnum)]
#[serde(rename_all = "lowercase")]
pub enum Preset {
    #[default]
    Minimal,
    Standard,
    Full,
}

impl std::fmt::Display for Preset {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Minimal => write!(f, "minimal"),
            Self::Standard => write!(f, "standard"),
            Self::Full => write!(f, "full"),
        }
    }
}

fn default_specs_dir() -> String {
    ".strata/specs".to_string()
}

fn default_sessions_dir() -> String {
    ".strata/sessions".to_string()
}

const fn default_max_steps_per_phase() -> u32 {
    6
}

const fn default_session_id_length() -> u32 {
    8
}

const fn default_staleness_days() -> u32 {
    7
}

const fn default_stale_verified_days() -> u32 {
    7
}

const fn default_stale_updated_days() -> u32 {
    60
}

const fn default_stale_waiting_days() -> u32 {
    30
}

const fn default_true() -> bool {
    true
}

pub(crate) fn default_memory_files() -> Vec<String> {
    vec!["MEMORY.md".to_string()]
}

const fn default_memory_budget() -> u32 {
    3200
}

const fn default_project_budget() -> u32 {
    3000
}
const fn default_index_budget() -> u32 {
    8000
}
const fn default_rules_budget() -> u32 {
    1500
}
const fn default_skill_budget() -> u32 {
    5000
}

fn default_ignore_patterns() -> Vec<String> {
    vec![
        ".git".to_string(),
        ".strata".to_string(),
        "node_modules".to_string(),
        "target".to_string(),
        ".DS_Store".to_string(),
        "Thumbs.db".to_string(),
    ]
}

fn default_scan_extensions() -> Vec<String> {
    [
        "md", "txt", "rs", "py", "js", "ts", "jsx", "tsx", "html", "css", "sh", "bash", "zsh",
        "go", "rb", "java", "c", "cpp", "h", "hpp",
    ]
    .iter()
    .map(|s| (*s).to_string())
    .collect()
}

impl StrataConfig {
    /// Returns true if this config declares workspace members.
    pub fn is_workspace(&self) -> bool {
        !self.workspace.members.is_empty()
    }

    /// Load each workspace member's config. Returns `(member_root, config)` pairs.
    pub fn load_workspace_members(
        root: &Path,
        config: &StrataConfig,
    ) -> Result<Vec<(PathBuf, StrataConfig)>> {
        config
            .workspace
            .members
            .iter()
            .map(|member| {
                let member_root = root.join(member);
                if !member_root.is_dir() {
                    return Err(StrataError::General(format!(
                        "workspace member '{}' not found at {}",
                        member,
                        member_root.display()
                    )));
                }
                let (member_config, _) = StrataConfig::load(&member_root)?;
                Ok((member_root, member_config))
            })
            .collect()
    }

    /// Find and read strata.toml starting from `dir`, walking up to ancestors.
    pub fn load(dir: &Path) -> Result<(Self, PathBuf)> {
        let config_path = find_config(dir)?;
        let contents = std::fs::read_to_string(&config_path)?;
        let config: Self = toml::from_str(&contents).map_err(|e| StrataError::Config {
            path: config_path.clone(),
            message: e.to_string(),
        })?;
        Ok((config, config_path))
    }

    /// Write config to the given path.
    pub fn save(&self, path: &Path) -> Result<()> {
        let contents = toml::to_string_pretty(self)?;
        std::fs::write(path, contents)?;
        Ok(())
    }

    /// Find the project root (directory containing strata.toml).
    pub fn find_root(dir: &Path) -> Result<PathBuf> {
        let config_path = find_config(dir)?;
        config_path
            .parent()
            .map(Path::to_path_buf)
            .ok_or_else(|| StrataError::General("config path has no parent".to_string()))
    }
}

/// Walk up from `dir` looking for strata.toml.
fn find_config(dir: &Path) -> Result<PathBuf> {
    let mut current = dir.to_path_buf();
    loop {
        let candidate = current.join("strata.toml");
        if candidate.exists() {
            return Ok(candidate);
        }
        if !current.pop() {
            return Err(StrataError::NotAProject);
        }
    }
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    #[test]
    fn test_default_config_roundtrip() {
        let config = StrataConfig {
            project: ProjectConfig {
                name: "test-project".to_string(),
                description: "A test project".to_string(),
                domains: vec![DomainConfig {
                    name: "Core".to_string(),
                    prefix: "01".to_string(),
                }],
            },
            structure: StructureConfig::default(),
            lint: LintConfig::default(),
            context: ContextConfig::default(),
            memory: MemoryConfig::default(),
            hooks: HooksConfig::default(),
            specs: SpecsConfig::default(),
            sessions: SessionsConfig::default(),
            targets: TargetsConfig::default(),
            skills: SkillsConfig::default(),
            custom_rules: vec![],
            workspace: WorkspaceConfig::default(),
        };
        let serialized = toml::to_string_pretty(&config).unwrap();
        let deserialized: StrataConfig = toml::from_str(&serialized).unwrap();
        assert_eq!(deserialized.project.name, "test-project");
        assert_eq!(deserialized.project.domains.len(), 1);
    }

    #[test]
    fn test_minimal_config_parse() {
        let toml_str = r#"
[project]
name = "minimal"
"#;
        let config: StrataConfig = toml::from_str(toml_str).unwrap();
        assert_eq!(config.project.name, "minimal");
        assert!(config.project.domains.is_empty());
        assert!(!config.structure.ignore.is_empty()); // defaults applied
    }

    #[test]
    fn test_custom_rules_parse() {
        let toml_str = r#"
[project]
name = "test"

[[custom_rules]]
name = "require-changelog"
severity = "warning"
check = "file_exists"
glob = "CHANGELOG.md"
message = "CHANGELOG.md is missing"

[[custom_rules]]
name = "no-bare-todos"
severity = "error"
check = "content_contains"
glob = "**/*.md"
pattern = "TODO"
negate = false
message = "bare TODO found"
"#;
        let config: StrataConfig = toml::from_str(toml_str).unwrap();
        assert_eq!(config.custom_rules.len(), 2);
        let first = &config.custom_rules[0];
        assert_eq!(first.name, "require-changelog");
        assert_eq!(first.severity, "warning");
        assert_eq!(first.check, "file_exists");
        let second = &config.custom_rules[1];
        assert_eq!(second.pattern.as_deref(), Some("TODO"));
        assert!(!second.negate);
    }

    #[test]
    fn test_custom_rules_missing_section_uses_default() {
        let toml_str = r#"
[project]
name = "test"
"#;
        let config: StrataConfig = toml::from_str(toml_str).unwrap();
        assert!(config.custom_rules.is_empty());
    }

    #[test]
    fn test_workspace_config_parse() {
        let toml_str = r#"
[project]
name = "workspace-root"

[workspace]
members = ["client", "server", "shared"]
"#;
        let config: StrataConfig = toml::from_str(toml_str).unwrap();
        assert!(config.is_workspace());
        assert_eq!(config.workspace.members, ["client", "server", "shared"]);
    }

    #[test]
    fn test_workspace_missing_section_is_not_workspace() {
        let toml_str = r#"
[project]
name = "single"
"#;
        let config: StrataConfig = toml::from_str(toml_str).unwrap();
        assert!(!config.is_workspace());
    }

    #[test]
    fn test_custom_rule_spec_defaults() {
        let toml_str = r#"
[project]
name = "test"

[[custom_rules]]
name = "my-rule"
check = "file_exists"
glob = "README.md"
message = "README is missing"
"#;
        let config: StrataConfig = toml::from_str(toml_str).unwrap();
        let rule = &config.custom_rules[0];
        assert_eq!(rule.severity, "warning"); // default
        assert!(!rule.negate); // default
        assert!(rule.pattern.is_none());
        assert!(rule.key.is_none());
    }
}
