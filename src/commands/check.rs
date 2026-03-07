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
    if root.join("INDEX.md").exists() {
        ui::success("INDEX.md exists");
    } else {
        ui::error("INDEX.md is missing");
        issues += 1;
    }

    // Check 2: PROJECT.md exists
    if root.join("PROJECT.md").exists() {
        ui::success("PROJECT.md exists");
    } else {
        ui::error("PROJECT.md is missing");
        issues += 1;
    }

    // Check 3: Every domain has RULES.md
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

    // Check 4: No dead crosslinks
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

    println!();
    if issues > 0 {
        ui::error(&format!("{issues} issue(s) found"));
        Err(StrataError::CheckFailed(issues))
    } else {
        ui::success("All structural checks passed");
        Ok(())
    }
}
