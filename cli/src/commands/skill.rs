use crate::config::StrataConfig;
use crate::error::{Result, StrataError};
use crate::eval::backend::create_backend;
use crate::eval::optimizer::run_optimize_loop;
use crate::eval::report::generate_report;
use crate::eval::runner::run_eval;
use crate::eval::{self, OutputFormat};
use crate::scanner::skills;
use crate::templates;
use crate::ui;
use std::fs;
use std::path::Path;
use std::time::Duration;

#[expect(
    clippy::too_many_arguments,
    reason = "CLI handler with many optional overrides"
)]
pub fn run_skill_eval(
    path: &Path,
    name: &str,
    eval_set_path: &str,
    workers: Option<u32>,
    timeout: Option<u64>,
    runs_per_query: Option<u32>,
    trigger_threshold: Option<f64>,
    format: OutputFormat,
    description_override: Option<&str>,
) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let description = resolve_description(&root, name, description_override)?;
    let queries = eval::load_eval_set(Path::new(eval_set_path))?;
    let skill_content = read_skill_content(&root, name)?;

    let backend = create_backend(&config.skills)?;
    let workers = workers.unwrap_or(config.skills.eval_workers);
    let timeout = Duration::from_secs(timeout.unwrap_or(config.skills.eval_timeout));
    let runs = runs_per_query.unwrap_or(config.skills.runs_per_query);
    let threshold = trigger_threshold.unwrap_or(config.skills.trigger_threshold);

    let result = run_eval(
        backend.as_ref(),
        name,
        &description,
        &skill_content,
        &queries,
        &root,
        workers,
        timeout,
        runs,
        threshold,
    )?;

    match format {
        OutputFormat::Text => print_eval_text(&result),
        OutputFormat::Json => {
            let json = serde_json::to_string_pretty(&result)
                .map_err(|e| StrataError::Eval(format!("Failed to serialize result: {e}")))?;
            println!("{json}");
        }
    }

    if result.passed_queries < result.total_queries {
        return Err(StrataError::Eval(format!(
            "{}/{} queries failed",
            result.total_queries - result.passed_queries,
            result.total_queries
        )));
    }

    Ok(())
}

#[expect(
    clippy::too_many_arguments,
    reason = "CLI handler with many optional overrides"
)]
pub fn run_skill_optimize(
    path: &Path,
    name: &str,
    eval_set_path: &str,
    max_iterations: Option<u32>,
    holdout: Option<f64>,
    runs_per_query: Option<u32>,
    report: bool,
    apply: bool,
) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let description = resolve_description(&root, name, None)?;
    let queries = eval::load_eval_set(Path::new(eval_set_path))?;
    let skill_content = read_skill_content(&root, name)?;

    let backend = create_backend(&config.skills)?;
    let max_iter = max_iterations.unwrap_or(config.skills.max_iterations);
    let holdout_frac = holdout.unwrap_or(config.skills.holdout);
    let runs = runs_per_query.unwrap_or(config.skills.runs_per_query);
    let timeout = Duration::from_secs(config.skills.eval_timeout);
    let threshold = config.skills.trigger_threshold;
    let workers = config.skills.eval_workers;

    let result = run_optimize_loop(
        backend.as_ref(),
        name,
        &description,
        &skill_content,
        &queries,
        &root,
        workers,
        timeout,
        runs,
        threshold,
        holdout_frac,
        max_iter,
    )?;

    // Print summary
    ui::header("Optimization complete");
    println!(
        "  Best iteration: {} (test accuracy: {:.0}%)",
        result.best_iteration,
        result
            .iterations
            .iter()
            .find(|i| i.iteration == result.best_iteration)
            .map_or(0.0, |i| i.test_result.accuracy * 100.0)
    );
    println!(
        "  Baseline test accuracy: {:.0}%",
        result.baseline_test.accuracy * 100.0
    );
    println!();
    ui::header("Best description");
    println!("{}", result.best_description);

    if report {
        let report_path = root.join(format!(".strata/eval-report-{name}.html"));
        generate_report(&result, &report_path)?;
        ui::success(&format!("Report written to {}", report_path.display()));
        open_in_browser(&report_path);
    }

    if apply {
        apply_description(&root, name, &result.best_description)?;
        ui::success("Applied best description to SKILL.md");
    }

    Ok(())
}

pub fn run_eval_set_init(path: &Path, name: &str, output: Option<&str>) -> Result<()> {
    let root = StrataConfig::find_root(path)?;

    let out_path = if let Some(o) = output {
        root.join(o)
    } else {
        root.join(format!("skills/{name}/eval-set.json"))
    };

    if out_path.exists() {
        return Err(StrataError::Eval(format!(
            "Eval set already exists at {}",
            out_path.display()
        )));
    }

    if let Some(parent) = out_path.parent() {
        fs::create_dir_all(parent)?;
    }

    let content = templates::render_eval_set(name)?;
    fs::write(&out_path, content)?;

    let rel = out_path
        .strip_prefix(&root)
        .unwrap_or(&out_path)
        .to_string_lossy()
        .replace('\\', "/");
    ui::success(&format!("Created eval set: {rel}"));

    Ok(())
}

fn resolve_description(root: &Path, name: &str, override_desc: Option<&str>) -> Result<String> {
    if let Some(desc) = override_desc {
        return Ok(desc.to_string());
    }

    let skills = skills::scan_skills(root);
    let skill = skills
        .iter()
        .find(|s| s.name.as_deref() == Some(name))
        .ok_or_else(|| StrataError::Eval(format!("Skill '{name}' not found under skills/")))?;

    skill
        .description
        .clone()
        .ok_or_else(|| StrataError::Eval(format!("Skill '{name}' has no description in SKILL.md")))
}

fn read_skill_content(root: &Path, name: &str) -> Result<String> {
    let skill_path = root.join(format!("skills/{name}/SKILL.md"));
    fs::read_to_string(&skill_path)
        .map_err(|e| StrataError::Eval(format!("Failed to read skills/{name}/SKILL.md: {e}")))
}

fn print_eval_text(result: &eval::EvalResult) {
    ui::header(&format!("Eval: {}", result.skill_name));
    println!(
        "  {}/{} passed ({:.0}%) in {:.1}s",
        result.passed_queries,
        result.total_queries,
        result.accuracy * 100.0,
        result.duration.as_secs_f64()
    );
    // Show reliability metrics when multi-run data is available
    if (result.pass_at_k - result.pass_hat_k).abs() > f64::EPSILON {
        println!(
            "  pass@k: {:.0}% (any run ok)  pass^k: {:.0}% (all runs ok)",
            result.pass_at_k * 100.0,
            result.pass_hat_k * 100.0,
        );
    }
    println!();

    for qr in &result.results {
        let icon = if qr.passed { "  ✓" } else { "  ✗" };
        let expect = if qr.query.should_trigger {
            "should trigger"
        } else {
            "should NOT trigger"
        };
        let rate = format!("{:.0}%", qr.trigger_rate * 100.0);
        println!(
            "{icon} [{rate:>4}] {expect}: {}",
            truncate(&qr.query.query, 60)
        );
    }
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        let end = crate::util::snap_to_char_floor(s, max);
        format!("{}...", &s[..end])
    }
}

fn apply_description(root: &Path, name: &str, description: &str) -> Result<()> {
    let skill_path = root.join(format!("skills/{name}/SKILL.md"));
    let content = fs::read_to_string(&skill_path)?;

    let mut lines: Vec<String> = content.lines().map(String::from).collect();
    let mut in_frontmatter = false;
    let mut desc_start = None;
    let mut desc_end = None;
    let mut fm_end = None;

    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();
        if trimmed == "---" {
            if i == 0 {
                in_frontmatter = true;
                continue;
            } else if in_frontmatter {
                fm_end = Some(i);
                break;
            }
        }
        if in_frontmatter && trimmed.starts_with("description:") {
            desc_start = Some(i);
            // Check for YAML block scalar or multi-line
            desc_end = Some(i);
            // Look ahead for continuation lines (indented)
            for (j, line) in lines.iter().enumerate().skip(i + 1) {
                let next = line.trim();
                if next == "---"
                    || (!next.is_empty() && !line.starts_with("  ") && !line.starts_with('\t'))
                {
                    break;
                }
                desc_end = Some(j);
            }
        }
    }

    if let (Some(start), Some(end)) = (desc_start, desc_end) {
        // Replace description lines with new value using YAML block scalar if multiline
        let new_lines: Vec<String> = if description.contains('\n') {
            let mut v = vec![format!("description: |")];
            for line in description.lines() {
                v.push(format!("  {line}"));
            }
            v
        } else {
            vec![format!("description: \"{description}\"")]
        };

        lines.splice(start..=end, new_lines);
    } else if let Some(fm) = fm_end {
        // No description field found - insert before frontmatter end
        lines.insert(fm, format!("description: \"{description}\""));
    } else {
        return Err(StrataError::Eval(
            "SKILL.md has no YAML frontmatter to update".to_string(),
        ));
    }

    let mut output = lines.join("\n");
    if content.ends_with('\n') && !output.ends_with('\n') {
        output.push('\n');
    }
    fs::write(&skill_path, output)?;
    Ok(())
}

fn open_in_browser(path: &Path) {
    let path_str = path.to_string_lossy();
    #[cfg(target_os = "windows")]
    let _ = std::process::Command::new("cmd")
        .args(["/c", "start", "", &path_str])
        .spawn();
    #[cfg(target_os = "macos")]
    let _ = std::process::Command::new("open").arg(&*path_str).spawn();
    #[cfg(target_os = "linux")]
    let _ = std::process::Command::new("xdg-open")
        .arg(&*path_str)
        .spawn();
}
