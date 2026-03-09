use crate::config::StrataConfig;
use crate::error::{Result, StrataError};
use crate::scanner::{self, ProjectScan};
use crate::ui;
use std::path::Path;

pub fn run(path: &Path) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    ui::header("Structural Check");

    if config.is_workspace() {
        let members = StrataConfig::load_workspace_members(&root, &config)?;
        let mut any_failed = false;
        for (member_root, member_config) in &members {
            let scan = scanner::scan_project(member_root, member_config)?;
            let issues = count_issues(member_root, member_config, &scan);
            let name = member_root
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("?");
            if issues == 0 {
                ui::success(&format!("[{name}] All checks passed"));
            } else {
                ui::error(&format!("[{name}] {issues} issue(s)"));
                any_failed = true;
            }
        }
        println!();
        return if any_failed {
            Err(StrataError::CheckFailed(1))
        } else {
            Ok(())
        };
    }

    let scan = scanner::scan_project(&root, &config)?;
    let issues = check_verbose(&root, &config, &scan);

    println!();
    if issues > 0 {
        ui::error(&format!("{issues} issue(s) found"));
        Err(StrataError::CheckFailed(issues))
    } else {
        ui::success("All structural checks passed");
        Ok(())
    }
}

/// Run structural checks with per-check output. Returns the issue count.
fn check_verbose(root: &Path, config: &StrataConfig, scan: &ProjectScan) -> usize {
    let mut issues = 0;

    if root.join("INDEX.md").exists() {
        ui::success("INDEX.md exists");
    } else {
        ui::error("INDEX.md is missing");
        issues += 1;
    }

    if root.join("PROJECT.md").exists() {
        ui::success("PROJECT.md exists");
    } else {
        ui::error("PROJECT.md is missing");
        issues += 1;
    }

    for domain in &config.project.domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        let rules_path = root.join(&dir_name).join("RULES.md");
        if rules_path.exists() {
            ui::success(&format!("{dir_name}/RULES.md exists"));
        } else {
            ui::error(&format!("{dir_name}/RULES.md is missing"));
            issues += 1;
        }
    }

    let dead_links = scan.dead_links(config.structure.link_mode);
    if dead_links.is_empty() {
        ui::success("No dead crosslinks");
    } else {
        for (source, target) in &dead_links {
            ui::error(&format!(
                "Dead link: {} -> {}",
                source.display(),
                target.target
            ));
        }
        issues += dead_links.len();
    }

    issues
}

/// Silently count structural issues without printing anything.
fn count_issues(root: &Path, config: &StrataConfig, scan: &ProjectScan) -> usize {
    let mut issues = 0;
    if !root.join("INDEX.md").exists() {
        issues += 1;
    }
    if !root.join("PROJECT.md").exists() {
        issues += 1;
    }
    for domain in &config.project.domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        if !root.join(&dir_name).join("RULES.md").exists() {
            issues += 1;
        }
    }
    issues += scan.dead_links(config.structure.link_mode).len();
    issues
}
