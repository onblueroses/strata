use crate::config::StrataConfig;
use crate::error::{Result, StrataError};
use crate::lint::{LintEngine, Severity};
use crate::ui;
use std::path::Path;

pub fn run(path: &Path, rule: Option<&str>, quiet: bool, format: &str) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;
    let scan = crate::scanner::scan_project(&root, &config)?;

    let engine = LintEngine::new(&config);
    let mut diagnostics = engine.run(&scan, &root, &config);

    // Filter by rule if specified
    if let Some(rule_name) = rule {
        diagnostics.retain(|d| d.rule == rule_name);
    }

    if format == "json" {
        let json = serde_json::to_string_pretty(&diagnostics).unwrap_or_else(|_| "[]".to_string());
        println!("{json}");
    } else if !quiet {
        ui::header("Lint Diagnostics");

        if diagnostics.is_empty() {
            ui::success("No issues found");
            return Ok(());
        }

        for d in &diagnostics {
            let msg = format!("[{}] {}: {}", d.rule, d.location, d.message);
            match d.severity {
                Severity::Error => ui::error(&msg),
                Severity::Warning => ui::warning(&msg),
                Severity::Info => ui::info(&msg),
            }
        }
        println!();
    }

    let errors = diagnostics
        .iter()
        .filter(|d| d.severity == Severity::Error)
        .count();
    let warnings = diagnostics
        .iter()
        .filter(|d| d.severity == Severity::Warning)
        .count();

    if errors > 0 || (config.lint.strict && warnings > 0) {
        Err(StrataError::LintFailed { errors, warnings })
    } else {
        if !quiet && format != "json" {
            if warnings > 0 {
                ui::warning(&format!("{warnings} warning(s)"));
            }
            let infos = diagnostics
                .iter()
                .filter(|d| d.severity == Severity::Info)
                .count();
            if infos > 0 {
                ui::info(&format!("{infos} info(s)"));
            }
        }
        Ok(())
    }
}
