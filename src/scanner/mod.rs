pub mod frontmatter;
pub mod fs;
pub mod hooks;
pub mod index;
pub mod links;
pub mod memory;
pub mod rules;
pub mod sessions;
pub mod skills;
pub mod specs;

use crate::config::{LinkMode, StrataConfig};
use crate::error::Result;
use std::collections::{HashMap, HashSet};
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
    /// Skill metadata from skills/*/SKILL.md.
    pub skills: Vec<skills::SkillMeta>,
    /// Memory layer file metadata.
    pub memory_files: Vec<memory::MemoryFileMeta>,
    /// Lifecycle hook metadata.
    pub hooks: Vec<hooks::HookMeta>,
    /// Spec file metadata.
    pub specs: Vec<specs::SpecMeta>,
    /// Session file metadata.
    pub sessions: Vec<sessions::SessionMeta>,
    /// Project root.
    pub root: PathBuf,
}

impl ProjectScan {
    /// Find crosslinks that point to non-existent files.
    /// Resolution strategy depends on `link_mode`:
    /// - `Path`: resolve relative to source file's directory (default for code projects)
    /// - `Name`: search by filename anywhere in the project (Obsidian/vault behavior)
    ///
    /// In both modes, if a target doesn't resolve, tries appending `.md` extension.
    pub fn dead_links(&self, link_mode: LinkMode) -> Vec<(PathBuf, String)> {
        // Pre-build a filename lookup set for Name mode
        let filename_set: HashSet<String> = if link_mode == LinkMode::Name {
            self.files
                .iter()
                .filter_map(|f| {
                    f.file_name()
                        .and_then(|n| n.to_str())
                        .map(std::string::ToString::to_string)
                })
                .collect()
        } else {
            HashSet::new()
        };

        self.crosslinks
            .iter()
            .filter(|(source, target)| {
                match link_mode {
                    LinkMode::Path => {
                        let source_dir = self
                            .root
                            .join(source)
                            .parent()
                            .map_or_else(|| self.root.clone(), Path::to_path_buf);
                        let resolved = source_dir.join(target);
                        // Try exact path, then with .md extension
                        let exists = resolved.canonicalize().is_ok() || resolved.exists() || {
                            let with_md = resolved.with_file_name(format!(
                                "{}.md",
                                resolved.file_name().unwrap_or_default().to_string_lossy()
                            ));
                            with_md.canonicalize().is_ok() || with_md.exists()
                        };
                        !exists
                    }
                    LinkMode::Name => {
                        // Try exact filename match, then with .md extension
                        let name = Path::new(target)
                            .file_name()
                            .unwrap_or_default()
                            .to_string_lossy()
                            .to_string();
                        let exists = filename_set.contains(&name)
                            || filename_set.contains(&format!("{name}.md"));
                        !exists
                    }
                }
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
                !is_meta_file(f) && !indexed.contains(&rel)
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
                !is_meta_file(f) && !indexed.contains(&rel) && !referenced.contains(&rel)
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

    let scan_exts = &config.structure.scan_extensions;
    for file in &files {
        let abs_path = root.join(file);
        if abs_path.is_file() && is_scannable_file(file, scan_exts) {
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

    // Scan skills
    let skills = skills::scan_skills(root);

    // Scan memory layer files
    let memory_files = memory::scan_memory_files(root, &config.memory);

    // Scan lifecycle hooks
    let hook_metas = hooks::scan_hooks(root, &config.hooks);

    // Scan specs
    let spec_metas = specs::scan_specs(root, &config.specs);

    // Scan sessions
    let session_metas = sessions::scan_sessions(root, &config.sessions);

    Ok(ProjectScan {
        files,
        index_entries,
        crosslinks,
        descriptions,
        domain_rules,
        skills,
        memory_files,
        hooks: hook_metas,
        specs: spec_metas,
        sessions: session_metas,
        root: root.to_path_buf(),
    })
}

pub fn is_meta_file(path: &Path) -> bool {
    let path_str = path.to_string_lossy();
    // Everything under .strata/ is meta
    if path_str.starts_with(".strata/") || path_str.starts_with(".strata\\") {
        return true;
    }

    path.file_name()
        .and_then(|n| n.to_str())
        .is_some_and(|name| {
            matches!(
                name,
                "INDEX.md" | "PROJECT.md" | "RULES.md" | "strata.toml" | ".gitignore" | "MEMORY.md"
            )
        })
}

fn is_scannable_file(path: &Path, scan_extensions: &[String]) -> bool {
    match path.extension().and_then(|e| e.to_str()) {
        Some(ext) => scan_extensions.iter().any(|allowed| allowed == ext),
        None => false,
    }
}
