use crate::cli::OutputFormat;
use crate::config::StrataConfig;
use crate::error::{Result, StrataError};
use crate::lint::{Diagnostic, LintEngine, Severity};
use crate::{sarif, ui};
use std::path::Path;

fn format_location(d: &Diagnostic) -> String {
    match (d.line, d.column) {
        (Some(line), Some(col)) => format!("{}:{line}:{col}", d.location),
        (Some(line), None) => format!("{}:{line}", d.location),
        _ => d.location.clone(),
    }
}

pub fn run(path: &Path, rule: Option<&str>, quiet: bool, format: OutputFormat) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let mut diagnostics: Vec<Diagnostic> = if config.is_workspace() {
        let members = StrataConfig::load_workspace_members(&root, &config)?;
        let mut all = Vec::new();
        for (member_root, member_config) in &members {
            let scan = crate::scanner::scan_project(member_root, member_config)?;
            let engine = LintEngine::new(member_config);
            let member_name = member_root
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("?");
            // Prefix each diagnostic's location with the member name so callers
            // can identify which member produced it across all output formats.
            let member_diags = engine
                .run(&scan, member_root, member_config)
                .into_iter()
                .map(|mut d| {
                    d.location = format!("{member_name}/{}", d.location);
                    d
                });
            all.extend(member_diags);
        }
        all
    } else {
        let scan = crate::scanner::scan_project(&root, &config)?;
        LintEngine::new(&config).run(&scan, &root, &config)
    };

    // Filter by rule if specified
    if let Some(rule_name) = rule {
        diagnostics.retain(|d| d.rule == rule_name);
    }

    match format {
        OutputFormat::Json => {
            let json =
                serde_json::to_string_pretty(&diagnostics).unwrap_or_else(|_| "[]".to_string());
            println!("{json}");
        }
        OutputFormat::Sarif => {
            let sarif_json = sarif::diagnostics_to_sarif(&diagnostics);
            println!("{sarif_json}");
        }
        OutputFormat::Text if !quiet => {
            ui::header("Lint Diagnostics");

            if diagnostics.is_empty() {
                ui::success("No issues found");
                return Ok(());
            }

            for d in &diagnostics {
                let loc = format_location(d);
                let msg = format!("[{}] {loc}: {}", d.rule, d.message);
                match d.severity {
                    Severity::Error => ui::error(&msg),
                    Severity::Warning => ui::warning(&msg),
                    Severity::Info => ui::info(&msg),
                }
            }
            println!();
        }
        OutputFormat::Text => {}
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
        if !quiet && matches!(format, OutputFormat::Text) {
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
