use crate::config::{AgentTarget, StrataConfig};
use crate::error::Result;
use crate::state;
use crate::ui;
use std::fs;
use std::path::Path;

pub fn run(path: &Path, target: Option<AgentTarget>) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, config_path) = StrataConfig::load(&root)?;

    ui::header("Updating context files");

    if config.is_workspace() {
        let members = StrataConfig::load_workspace_members(&root, &config)?;
        let mut total_updated = 0;
        let mut total_unchanged = 0;
        for (member_root, member_config) in &members {
            let member_name = member_root
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("?");
            let scan = crate::scanner::scan_project(member_root, member_config)?;
            let resolved_target = target
                .or_else(|| {
                    state::load_state(member_root)
                        .ok()
                        .flatten()
                        .and_then(|s| parse_target(&s.target))
                })
                .unwrap_or_else(|| {
                    member_config
                        .targets
                        .active
                        .first()
                        .copied()
                        .unwrap_or_default()
                });
            super::fix::regenerate_index_md(member_root, &scan, member_config)?;
            let files =
                super::generate::generate_all(member_root, member_config, &scan, resolved_target)?;
            let prev_state = state::load_state(member_root)?;
            let (updated, unchanged) = write_changed(member_root, &files, prev_state.as_ref())?;
            let git_commit = crate::git::head_commit(member_root);
            let member_config_path = member_root.join("strata.toml");
            let gen_state = state::build_generation_state(
                member_root,
                member_config,
                &member_config_path,
                &files,
                resolved_target,
                git_commit,
            );
            state::save_state(member_root, &gen_state)?;
            ui::success(&format!(
                "[{member_name}] {updated} updated, {unchanged} unchanged"
            ));
            total_updated += updated;
            total_unchanged += unchanged;
        }
        println!();
        if total_updated == 0 {
            ui::success("All context files are up to date.");
        } else {
            ui::success(&format!(
                "Updated {total_updated} file(s), {total_unchanged} unchanged."
            ));
        }
        return Ok(());
    }

    let scan = crate::scanner::scan_project(&root, &config)?;

    // Default to target from state.json if available (no --target needed after first generate)
    let resolved_target = target
        .or_else(|| {
            state::load_state(&root)
                .ok()
                .flatten()
                .and_then(|s| parse_target(&s.target))
        })
        .unwrap_or_else(|| config.targets.active.first().copied().unwrap_or_default());

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
        "claude-code" => Some(AgentTarget::ClaudeCode),
        "opencode" => Some(AgentTarget::OpenCode),
        "pi" => Some(AgentTarget::Pi),
        _ => None,
    }
}
