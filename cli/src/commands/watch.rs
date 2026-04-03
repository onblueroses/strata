use crate::config::{AgentTarget, StrataConfig};
use crate::error::Result;
use crate::lint::{LintEngine, Severity};
use crate::state;
use crate::ui;
use notify::{Event, EventKind, RecursiveMode, Watcher};
use std::path::Path;
use std::sync::mpsc;
use std::time::{Duration, Instant};

pub fn run(path: &Path, target: Option<AgentTarget>, debounce_ms: u64) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let resolved_target = target
        .or_else(|| {
            state::load_state(&root)
                .ok()
                .flatten()
                .and_then(|s| parse_target(&s.target))
        })
        .unwrap_or_else(|| config.targets.active.first().copied().unwrap_or_default());

    ui::header("Watching for changes");
    ui::info(&format!(
        "Target: {resolved_target}, debounce: {debounce_ms}ms"
    ));
    ui::info("Press Ctrl+C to stop.\n");

    let (tx, rx) = mpsc::channel::<notify::Result<Event>>();

    let mut watcher = notify::recommended_watcher(tx)?;
    watcher.watch(&root, RecursiveMode::Recursive)?;

    let debounce = Duration::from_millis(debounce_ms);
    let mut last_event: Option<Instant> = None;
    let mut pending = false;

    loop {
        match rx.recv_timeout(Duration::from_millis(50)) {
            Ok(Ok(event)) => {
                if is_relevant_event(&event, &root, &config) {
                    last_event = Some(Instant::now());
                    pending = true;
                }
            }
            Ok(Err(e)) => {
                ui::warning(&format!("Watch error: {e}"));
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {}
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                break;
            }
        }

        if pending {
            if let Some(last) = last_event {
                if last.elapsed() >= debounce {
                    pending = false;
                    last_event = None;
                    process_changes(&root, resolved_target);
                }
            }
        }
    }

    Ok(())
}

/// Filter events: only Create/Modify/Remove on relevant files, excluding .strata/ and .git/.
fn is_relevant_event(event: &Event, root: &Path, config: &StrataConfig) -> bool {
    match event.kind {
        EventKind::Create(_) | EventKind::Modify(_) | EventKind::Remove(_) => {}
        _ => return false,
    }

    event.paths.iter().any(|p| {
        let Ok(rel) = p.strip_prefix(root) else {
            return false;
        };

        let rel_str = rel.to_string_lossy();

        // Skip .strata/ and .git/ to prevent infinite loops
        if rel_str.starts_with(".strata") || rel_str.starts_with(".git") {
            return false;
        }

        // Skip ignored directories
        for ignore in &config.structure.ignore {
            if rel_str.starts_with(ignore.as_str()) {
                return false;
            }
        }

        // Check extension if file has one
        if let Some(ext) = p.extension().and_then(|e| e.to_str()) {
            config.structure.scan_extensions.iter().any(|e| e == ext) || ext == "toml" // strata.toml changes
        } else {
            // Directories or extensionless files - accept
            true
        }
    })
}

/// Full regeneration cycle: reload config, scan, generate, write changed, lint.
fn process_changes(root: &Path, target: AgentTarget) {
    let Ok((config, config_path)) = StrataConfig::load(root) else {
        ui::error("Failed to load strata.toml");
        return;
    };

    let Ok(scan) = crate::scanner::scan_project(root, &config) else {
        ui::error("Failed to scan project");
        return;
    };

    // Refresh INDEX.md
    if let Err(e) = super::fix::regenerate_index_md(root, &scan, &config) {
        ui::warning(&format!("Failed to refresh INDEX.md: {e}"));
    }

    let Ok(files) = super::generate::generate_all(root, &config, &scan, target) else {
        ui::error("Failed to generate context");
        return;
    };

    let prev_state = state::load_state(root).ok().flatten();
    let (updated, _unchanged) = match write_changed(root, &files, prev_state.as_ref()) {
        Ok(counts) => counts,
        Err(e) => {
            ui::error(&format!("Failed to write files: {e}"));
            return;
        }
    };

    // Save new state
    let git_commit = crate::git::head_commit(root);
    let gen_state =
        state::build_generation_state(root, &config, &config_path, &files, target, git_commit);
    let _ = state::save_state(root, &gen_state);

    // Run lint, report only errors and warnings
    let engine = LintEngine::new(&config);
    let diagnostics = engine.run(&scan, root, &config);
    let actionable: Vec<_> = diagnostics
        .iter()
        .filter(|d| matches!(d.severity, Severity::Error | Severity::Warning))
        .collect();

    if updated > 0 || !actionable.is_empty() {
        if updated > 0 {
            ui::success(&format!("Updated {updated} file(s)"));
        }
        for diag in &actionable {
            let prefix = match diag.severity {
                Severity::Error => "error",
                Severity::Warning => "warn",
                Severity::Info => "info",
            };
            println!("  [{prefix}] {}: {}", diag.rule, diag.message);
        }
    }
}

/// Write only changed files (same logic as update command).
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
                std::fs::create_dir_all(parent)?;
            }

            if rel_path.starts_with(".strata/") {
                super::generate::write_with_marker(&abs_path, content)?;
            } else {
                std::fs::write(&abs_path, content)?;
            }
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

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;
    use crate::config::StrataConfig;
    use notify::event::{CreateKind, ModifyKind, RemoveKind};
    use std::path::PathBuf;

    fn test_path(root: &Path, rel: &str) -> PathBuf {
        root.join(rel)
    }

    fn test_config() -> StrataConfig {
        toml::from_str(
            r#"
[project]
name = "test"
"#,
        )
        .unwrap()
    }

    fn make_event(kind: EventKind, paths: Vec<PathBuf>) -> Event {
        Event {
            kind,
            paths,
            attrs: notify::event::EventAttributes::default(),
        }
    }

    #[test]
    fn test_relevant_create_md() {
        let root = PathBuf::from("/project");
        let config = test_config();
        let event = make_event(
            EventKind::Create(CreateKind::File),
            vec![test_path(&root, "PROJECT.md")],
        );
        assert!(is_relevant_event(&event, &root, &config));
    }

    #[test]
    fn test_ignores_strata_dir() {
        let root = PathBuf::from("/project");
        let config = test_config();
        let event = make_event(
            EventKind::Modify(ModifyKind::Data(notify::event::DataChange::Content)),
            vec![test_path(&root, ".strata/state.json")],
        );
        assert!(!is_relevant_event(&event, &root, &config));
    }

    #[test]
    fn test_ignores_git_dir() {
        let root = PathBuf::from("/project");
        let config = test_config();
        let event = make_event(
            EventKind::Modify(ModifyKind::Data(notify::event::DataChange::Content)),
            vec![test_path(&root, ".git/HEAD")],
        );
        assert!(!is_relevant_event(&event, &root, &config));
    }

    #[test]
    fn test_ignores_node_modules() {
        let root = PathBuf::from("/project");
        let config = test_config();
        let event = make_event(
            EventKind::Create(CreateKind::File),
            vec![test_path(&root, "node_modules/foo/index.js")],
        );
        assert!(!is_relevant_event(&event, &root, &config));
    }

    #[test]
    fn test_relevant_toml_change() {
        let root = PathBuf::from("/project");
        let config = test_config();
        let event = make_event(
            EventKind::Modify(ModifyKind::Data(notify::event::DataChange::Content)),
            vec![test_path(&root, "strata.toml")],
        );
        assert!(is_relevant_event(&event, &root, &config));
    }

    #[test]
    fn test_ignores_unsupported_extension() {
        let root = PathBuf::from("/project");
        let config = test_config();
        let event = make_event(
            EventKind::Create(CreateKind::File),
            vec![test_path(&root, "image.png")],
        );
        assert!(!is_relevant_event(&event, &root, &config));
    }

    #[test]
    fn test_relevant_remove_event() {
        let root = PathBuf::from("/project");
        let config = test_config();
        let event = make_event(
            EventKind::Remove(RemoveKind::File),
            vec![test_path(&root, "01-Core/RULES.md")],
        );
        assert!(is_relevant_event(&event, &root, &config));
    }
}
