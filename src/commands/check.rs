use crate::config::StrataConfig;
use crate::error::{Result, StrataError};
use crate::scanner;
use crate::ui;
use std::path::Path;

pub fn run(path: &Path) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;
    let scan = scanner::scan_project(&root, &config)?;

    ui::header("Structural Check");

    let mut issues = 0;

    // Check 1: INDEX.md exists
    if !root.join("INDEX.md").exists() {
        ui::error("INDEX.md is missing");
        issues += 1;
    } else {
        ui::success("INDEX.md exists");
    }

    // Check 2: PROJECT.md exists
    if !root.join("PROJECT.md").exists() {
        ui::error("PROJECT.md is missing");
        issues += 1;
    } else {
        ui::success("PROJECT.md exists");
    }

    // Check 3: Every domain has RULES.md
    for domain in &config.project.domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        let rules_path = root.join(&dir_name).join("RULES.md");
        if !rules_path.exists() {
            ui::error(&format!("{}/RULES.md is missing", dir_name));
            issues += 1;
        } else {
            ui::success(&format!("{}/RULES.md exists", dir_name));
        }
    }

    // Check 4: No dead crosslinks
    let dead_links = scan.dead_links();
    if !dead_links.is_empty() {
        for (source, target) in &dead_links {
            ui::error(&format!("Dead link: {} -> {}", source.display(), target));
        }
        issues += dead_links.len();
    } else {
        ui::success("No dead crosslinks");
    }

    println!();
    if issues > 0 {
        ui::error(&format!("{} issue(s) found", issues));
        Err(StrataError::CheckFailed(issues))
    } else {
        ui::success("All structural checks passed");
        Ok(())
    }
}
