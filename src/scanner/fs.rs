use crate::error::Result;
use globset::{Glob, GlobSetBuilder};
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// Walk the project tree, returning relative paths of all files.
/// Respects ignore patterns from config.
pub fn walk_project(root: &Path, ignore_patterns: &[String]) -> Result<Vec<PathBuf>> {
    let ignore_set = build_ignore_set(ignore_patterns)?;
    let mut files = Vec::new();

    for entry in WalkDir::new(root)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| {
            let path = e.path();
            if let Ok(rel) = path.strip_prefix(root) {
                let rel_str = rel.to_string_lossy().replace('\\', "/");
                // Skip ignored directories/files
                if rel_str.is_empty() {
                    return true;
                }
                !should_ignore(&rel_str, &ignore_set)
            } else {
                true
            }
        })
    {
        let entry = entry?;
        if entry.file_type().is_file() {
            if let Ok(rel) = entry.path().strip_prefix(root) {
                files.push(rel.to_path_buf());
            }
        }
    }

    files.sort();
    Ok(files)
}

fn build_ignore_set(patterns: &[String]) -> Result<globset::GlobSet> {
    let mut builder = GlobSetBuilder::new();
    for pattern in patterns {
        // Match both as exact name and as glob
        let glob = Glob::new(pattern).or_else(|_| Glob::new(&format!("**/{}", pattern)))?;
        builder.add(glob);
        // Also add a variant that matches directory prefix
        if let Ok(g) = Glob::new(&format!("{}/**", pattern)) {
            builder.add(g);
        }
    }
    Ok(builder.build()?)
}

fn should_ignore(rel_path: &str, ignore_set: &globset::GlobSet) -> bool {
    // Check each path component
    for component in rel_path.split('/') {
        if ignore_set.is_match(component) {
            return true;
        }
    }
    ignore_set.is_match(rel_path)
}

impl From<globset::Error> for crate::error::StrataError {
    fn from(e: globset::Error) -> Self {
        crate::error::StrataError::General(format!("Glob pattern error: {}", e))
    }
}
