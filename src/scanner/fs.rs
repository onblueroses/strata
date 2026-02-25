use crate::error::Result;
use ignore::overrides::OverrideBuilder;
use ignore::WalkBuilder;
use std::path::{Path, PathBuf};

/// Walk the project tree, returning relative paths of all files.
/// Respects .gitignore natively via the `ignore` crate, plus custom
/// ignore patterns from strata.toml config.
pub fn walk_project(root: &Path, ignore_patterns: &[String]) -> Result<Vec<PathBuf>> {
    let mut builder = WalkBuilder::new(root);
    builder
        .hidden(false) // Don't auto-skip hidden files; strata config controls this
        .git_ignore(true)
        .git_global(true)
        .git_exclude(true)
        .follow_links(false);

    // Convert strata ignore patterns to override blacklist entries.
    // The `ignore` crate uses gitignore semantics: a pattern without `/`
    // matches the filename component at any depth. Blacklisted directories
    // are not descended into.
    if !ignore_patterns.is_empty() {
        let mut ob = OverrideBuilder::new(root);
        for pattern in ignore_patterns {
            ob.add(&format!("!{pattern}")).map_err(|e| {
                crate::error::StrataError::General(format!(
                    "Invalid ignore pattern '{pattern}': {e}"
                ))
            })?;
        }
        let overrides = ob.build().map_err(|e| {
            crate::error::StrataError::General(format!("Failed to build ignore overrides: {e}"))
        })?;
        builder.overrides(overrides);
    }

    let mut files = Vec::new();
    for result in builder.build() {
        let entry = result.map_err(|e| {
            crate::error::StrataError::General(format!("Walk error: {e}"))
        })?;

        if !entry.file_type().is_some_and(|ft| ft.is_file()) {
            continue;
        }

        if let Ok(rel) = entry.path().strip_prefix(root) {
            let rel_str = rel.to_string_lossy().replace('\\', "/");
            if !rel_str.is_empty() {
                files.push(rel.to_path_buf());
            }
        }
    }

    files.sort();
    Ok(files)
}
