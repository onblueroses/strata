use crate::error::{Result, StrataError};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

/// Top-level strata.toml configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StrataConfig {
    pub project: ProjectConfig,
    #[serde(default)]
    pub structure: StructureConfig,
    #[serde(default)]
    pub lint: LintConfig,
    #[serde(default)]
    pub context: ContextConfig,
    #[serde(default)]
    pub memory: MemoryConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectConfig {
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

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LintConfig {
    /// Rules to disable (by slug).
    #[serde(default)]
    pub disable: Vec<String>,

    /// Treat warnings as errors.
    #[serde(default)]
    pub strict: bool,
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
}
