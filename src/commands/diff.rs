use crate::config::StrataConfig;
use crate::error::Result;
use crate::state;
use crate::ui;
// similar v2 has no Histogram variant; Patience anchors on unique lines (same intent)
use similar::{Algorithm, ChangeTag, TextDiff};
use std::path::Path;

pub fn run(path: &Path, target: Option<crate::config::AgentTarget>) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let Some(gen_state) = state::load_state(&root)? else {
        ui::info("No previous generation. Run `strata generate` first.");
        return Ok(());
    };

    let scan = crate::scanner::scan_project(&root, &config)?;
    let resolved_target =
        target.unwrap_or_else(|| config.targets.active.first().copied().unwrap_or_default());
    let files = super::generate::generate_all(&root, &config, &scan, resolved_target)?;

    let mut modified = Vec::new();
    let mut unchanged = Vec::new();

    for (rel_path, content) in &files {
        let new_hash = state::hash_content(content);
        match gen_state.files.get(rel_path) {
            Some(file_state) if file_state.content_hash == new_hash => {
                unchanged.push(rel_path.as_str());
            }
            _ => {
                let reason = detect_change_reason(&gen_state, rel_path, &root, &config);
                modified.push((rel_path.clone(), content.clone(), reason));
            }
        }
    }

    if modified.is_empty() {
        ui::success("All generated files are up to date.");
        return Ok(());
    }

    for (rel_path, new_content, reason) in &modified {
        let suffix = reason
            .as_ref()
            .map_or(String::new(), |r| format!(" (sources changed: {r})"));
        let action_style = console::Style::new().yellow();
        let path_style = console::Style::new().dim();
        println!(
            "  {} {}{}",
            action_style.apply_to("modified"),
            path_style.apply_to(rel_path.as_str()),
            path_style.apply_to(&suffix)
        );

        let disk_content = std::fs::read_to_string(root.join(rel_path)).unwrap_or_default();
        print_file_diff(&disk_content, new_content);
    }

    for path in &unchanged {
        let action_style = console::Style::new().dim();
        println!("  {} {path}", action_style.apply_to("unchanged"));
    }

    println!();
    ui::info(&format!(
        "{} file(s) would change. Run `strata generate` to update.",
        modified.len()
    ));

    Ok(())
}

fn print_file_diff(old: &str, new: &str) {
    let diff = TextDiff::configure()
        .algorithm(Algorithm::Patience)
        .diff_lines(old, new);

    let add_style = console::Style::new().green();
    let del_style = console::Style::new().red();
    let ctx_style = console::Style::new().dim();

    for group in diff.grouped_ops(3) {
        for op in group {
            for change in diff.iter_changes(&op) {
                let line = change.value().trim_end_matches('\n');
                match change.tag() {
                    ChangeTag::Insert => println!("  {}", add_style.apply_to(format!("+{line}"))),
                    ChangeTag::Delete => println!("  {}", del_style.apply_to(format!("-{line}"))),
                    ChangeTag::Equal => println!("  {}", ctx_style.apply_to(format!(" {line}"))),
                }
            }
        }
    }
}

/// Try to identify what sources changed for a modified file.
fn detect_change_reason(
    gen_state: &state::GenerationState,
    rel_path: &str,
    root: &Path,
    config: &StrataConfig,
) -> Option<String> {
    let file_state = gen_state.files.get(rel_path)?;

    if rel_path == ".strata/context.md" {
        let current = state::compute_context_source_hash(root, config);
        if current != file_state.source_hash {
            return Some("PROJECT.md, RULES.md, or skills".to_string());
        }
    }

    if let Some(domain_dir) = rel_path
        .strip_prefix(".strata/domains/")
        .and_then(|s| s.strip_suffix(".md"))
    {
        let current = state::compute_domain_source_hash(root, domain_dir);
        if current != file_state.source_hash {
            return Some(format!("{domain_dir}/"));
        }
    }

    None
}
