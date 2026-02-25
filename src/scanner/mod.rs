pub mod frontmatter;
pub mod fs;
pub mod index;
pub mod links;
pub mod rules;

use crate::config::StrataConfig;
use crate::error::Result;
use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// Result of scanning an entire project.
#[derive(Debug)]
pub struct ProjectScan {
    /// All files found in the project (relative paths).
    pub files: Vec<PathBuf>,
    /// Parsed INDEX.md entries.
    pub index_entries: Vec<index::IndexEntry>,
    /// Crosslinks found: (`source_file`, `target_path_string`).
    pub crosslinks: Vec<(PathBuf, String)>,
    /// Frontmatter/description per file.
    pub descriptions: HashMap<PathBuf, Option<String>>,
    /// RULES.md parse results per domain directory.
    pub domain_rules: HashMap<PathBuf, rules::DomainRules>,
    /// Project root.
    pub root: PathBuf,
}

impl ProjectScan {
    /// Find crosslinks that point to non-existent files.
    /// Resolves link targets relative to the source file's directory.
    pub fn dead_links(&self) -> Vec<(PathBuf, String)> {
        self.crosslinks
            .iter()
            .filter(|(source, target)| {
                // Resolve relative to source file's parent directory
                let source_dir = self
                    .root
                    .join(source)
                    .parent()
                    .map_or_else(|| self.root.clone(), std::path::Path::to_path_buf);
                let resolved = source_dir.join(target);
                // Canonicalize to handle ../ etc., fallback to simple exists check
                let exists = resolved.canonicalize().map(|p| p.exists()).unwrap_or(false)
                    || resolved.exists();
                !exists
            })
            .map(|(source, target)| (source.clone(), target.clone()))
            .collect()
    }

    /// Find files that are not listed in INDEX.md.
    pub fn unindexed_files(&self, root: &Path) -> Vec<PathBuf> {
        let indexed: std::collections::HashSet<String> = self
            .index_entries
            .iter()
            .map(|e| e.path.replace('\\', "/"))
            .collect();

        self.files
            .iter()
            .filter(|f| {
                let rel = f.to_string_lossy().replace('\\', "/");
                // Skip meta files
                !rel.ends_with("INDEX.md")
                    && !rel.ends_with("PROJECT.md")
                    && !rel.ends_with("RULES.md")
                    && !rel.ends_with("strata.toml")
                    && !rel.ends_with(".gitignore")
                    && !indexed.contains(&rel)
            })
            .map(|f| root.join(f))
            .collect()
    }

    /// Find files that are not referenced by any crosslink and not in INDEX.md.
    pub fn orphan_files(&self) -> Vec<PathBuf> {
        let referenced: std::collections::HashSet<String> = self
            .crosslinks
            .iter()
            .map(|(_, target)| target.replace('\\', "/"))
            .collect();

        let indexed: std::collections::HashSet<String> = self
            .index_entries
            .iter()
            .map(|e| e.path.replace('\\', "/"))
            .collect();

        self.files
            .iter()
            .filter(|f| {
                let rel = f.to_string_lossy().replace('\\', "/");
                // Skip meta files
                !rel.ends_with("INDEX.md")
                    && !rel.ends_with("PROJECT.md")
                    && !rel.ends_with("RULES.md")
                    && !rel.ends_with("strata.toml")
                    && !rel.ends_with(".gitignore")
                    && !indexed.contains(&rel)
                    && !referenced.contains(&rel)
            })
            .cloned()
            .collect()
    }
}

/// Run a full project scan.
pub fn scan_project(root: &Path, config: &StrataConfig) -> Result<ProjectScan> {
    let files = fs::walk_project(root, &config.structure.ignore)?;

    // Parse INDEX.md
    let index_path = root.join("INDEX.md");
    let index_entries = if index_path.exists() {
        index::parse_index(&index_path)?
    } else {
        Vec::new()
    };

    // Collect crosslinks and descriptions
    let mut crosslinks = Vec::new();
    let mut descriptions = HashMap::new();

    for file in &files {
        let abs_path = root.join(file);
        if abs_path.is_file() && is_scannable_file(file) {
            if let Ok(content) = std::fs::read_to_string(&abs_path) {
                // Parse crosslinks
                let file_links = links::parse_links(&content);
                for link in file_links {
                    crosslinks.push((file.clone(), link));
                }

                // Parse description
                let desc = frontmatter::extract_description(&content);
                descriptions.insert(file.clone(), desc);
            }
        }
    }

    // Parse RULES.md files per domain
    let mut domain_rules = HashMap::new();
    for domain in &config.project.domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        let rules_path = root.join(&dir_name).join("RULES.md");
        if rules_path.exists() {
            if let Ok(parsed) = rules::parse_rules(&rules_path) {
                domain_rules.insert(PathBuf::from(&dir_name), parsed);
            }
        }
    }

    Ok(ProjectScan {
        files,
        index_entries,
        crosslinks,
        descriptions,
        domain_rules,
        root: root.to_path_buf(),
    })
}

fn is_scannable_file(path: &Path) -> bool {
    match path.extension().and_then(|e| e.to_str()) {
        // Only scan files that plausibly contain markdown crosslinks.
        // Exclude config formats (toml, yaml, json) - they use [[]] and []() for
        // different purposes and generate false positive crosslinks.
        Some(ext) => matches!(
            ext,
            "md" | "txt"
                | "rs"
                | "py"
                | "js"
                | "ts"
                | "jsx"
                | "tsx"
                | "html"
                | "css"
                | "sh"
                | "bash"
                | "zsh"
                | "go"
                | "rb"
                | "java"
                | "c"
                | "cpp"
                | "h"
                | "hpp"
        ),
        None => false,
    }
}
