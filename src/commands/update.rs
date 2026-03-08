use crate::config::{AgentTarget, StrataConfig};
use crate::error::Result;
use crate::state;
use crate::ui;
use std::fs;
use std::path::Path;

pub fn run(path: &Path, target: Option<AgentTarget>) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, config_path) = StrataConfig::load(&root)?;
    let scan = crate::scanner::scan_project(&root, &config)?;

    // Default to target from state.json if available (no --target needed after first generate)
    let resolved_target = target
        .or_else(|| {
            state::load_state(&root)
                .ok()
                .flatten()
                .and_then(|s| parse_target(&s.target))
        })
        .unwrap_or(config.targets.default);

    ui::header("Updating context files");

    // Refresh INDEX.md
    super::fix::regenerate_index_md(&root, &scan, &config)?;

    // Generate all content in memory
    let files = super::generate::generate_all(&root, &config, &scan, resolved_target)?;
    let prev_state = state::load_state(&root)?;

    let (updated, unchanged) = write_changed(&root, &files, prev_state.as_ref())?;

    // Build and save new state
    let git_commit = crate::git::head_commit(&root);
    let gen_state = state::build_generation_state(
        &root,
        &config,
        &config_path,
        &files,
        resolved_target,
        git_commit,
    );
    state::save_state(&root, &gen_state)?;

    if updated == 0 {
        ui::success("All context files are up to date.");
    } else {
        ui::success(&format!(
            "Updated {updated} file(s), {unchanged} unchanged."
        ));
    }

    Ok(())
}

/// Write only files whose content hash differs from previous state.
fn write_changed(
    root: &Path,
    files: &[(String, String)],
    prev_state: Option<&state::GenerationState>,
) -> Result<(usize, usize)> {
    let mut updated = 0;
    let mut unchanged = 0;

    for (rel_path, content) in files {
        let new_hash = state::hash_content(content);
        let changed = prev_state
            .and_then(|s| s.files.get(rel_path))
            .is_none_or(|prev| prev.content_hash != new_hash);

        if changed {
            let abs_path = root.join(rel_path);
            if let Some(parent) = abs_path.parent() {
                fs::create_dir_all(parent)?;
            }

            if rel_path.starts_with(".strata/") {
                super::generate::write_with_marker(&abs_path, content)?;
            } else {
                fs::write(&abs_path, content)?;
            }
            ui::file_action("update", rel_path);
            updated += 1;
        } else {
            unchanged += 1;
        }
    }

    Ok((updated, unchanged))
}

fn parse_target(s: &str) -> Option<AgentTarget> {
    match s {
        "generic" => Some(AgentTarget::Generic),
        "claude" => Some(AgentTarget::Claude),
        "cursor" => Some(AgentTarget::Cursor),
        "copilot" => Some(AgentTarget::Copilot),
        _ => None,
    }
}
