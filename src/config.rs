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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StructureConfig {
    /// Glob patterns for files/dirs to ignore during scanning.
    #[serde(default = "default_ignore_patterns")]
    pub ignore: Vec<String>,

    /// Whether to require frontmatter descriptions in all files.
    #[serde(default)]
    pub require_descriptions: bool,
}

impl Default for StructureConfig {
    fn default() -> Self {
        Self {
            ignore: default_ignore_patterns(),
            require_descriptions: false,
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
