use crate::config::StrataConfig;
use crate::error::{Result, StrataError};
use crate::scanner::specs::{self, SpecStatus};
use crate::templates;
use crate::ui;
use std::fmt::Write as _;
use std::fs;
use std::path::Path;

pub fn run_new(path: &Path, name: &str, session_id: Option<&str>) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let specs_dir = root.join(&config.specs.dir);
    fs::create_dir_all(&specs_dir)?;

    let filename = format!("{name}.md");
    let spec_path = specs_dir.join(&filename);

    if spec_path.exists() {
        return Err(StrataError::SpecAlreadyExists(name.to_string()));
    }

    let sid = session_id.unwrap_or("unknown");
    let date = today_iso();
    let content = templates::render_spec(name, sid, &date);
    fs::write(&spec_path, content)?;

    let rel = spec_path
        .strip_prefix(&root)
        .unwrap_or(&spec_path)
        .to_string_lossy()
        .replace('\\', "/");
    ui::success(&format!("Created spec: {rel}"));

    Ok(())
}

pub fn run_list(path: &Path, status_filter: Option<&str>) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let specs = specs::scan_specs(&root, &config.specs);

    if specs.is_empty() {
        ui::info("No specs found.");
        return Ok(());
    }

    let filter: Option<SpecStatus> = status_filter.and_then(|s| match s {
        "in-progress" => Some(SpecStatus::InProgress),
        "complete" => Some(SpecStatus::Complete),
        "abandoned" => Some(SpecStatus::Abandoned),
        _ => None,
    });

    let filtered: Vec<_> = specs
        .iter()
        .filter(|s| filter.is_none() || s.status == filter)
        .collect();

    if filtered.is_empty() {
        ui::info("No specs match the filter.");
        return Ok(());
    }

    let mut table = String::new();
    let _ = writeln!(table, "{:<30} {:<14} Progress", "Name", "Status");
    let _ = writeln!(table, "{}", "-".repeat(60));

    for spec in &filtered {
        let status_str = match spec.status {
            Some(SpecStatus::InProgress) => "in-progress",
            Some(SpecStatus::Complete) => "complete",
            Some(SpecStatus::Abandoned) => "abandoned",
            None => "unknown",
        };
        let progress = if spec.total_steps > 0 {
            format!("{}/{}", spec.completed_steps, spec.total_steps)
        } else {
            "-".to_string()
        };
        let _ = writeln!(table, "{:<30} {:<14} {}", spec.name, status_str, progress);
    }

    println!("{table}");
    Ok(())
}

pub fn run_status(path: &Path, name: Option<&str>) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let specs = specs::scan_specs(&root, &config.specs);

    let target_specs: Vec<_> = if let Some(name) = name {
        specs.iter().filter(|s| s.name == name).collect()
    } else {
        // Show all in-progress specs
        specs
            .iter()
            .filter(|s| s.status == Some(SpecStatus::InProgress))
            .collect()
    };

    if target_specs.is_empty() {
        ui::info("No matching specs found.");
        return Ok(());
    }

    for spec in target_specs {
        let spec_path = root.join(&spec.path);
        if let Ok(content) = fs::read_to_string(&spec_path) {
            // Extract the >> Current Step section
            let mut in_section = false;
            let mut section = String::new();

            for line in content.lines() {
                if line.contains(">> Current Step") {
                    in_section = true;
                    continue;
                }
                if in_section {
                    if line.starts_with("## ") {
                        break;
                    }
                    if !line.trim().is_empty() || !section.is_empty() {
                        let _ = writeln!(section, "{line}");
                    }
                }
            }

            ui::header(&spec.name);
            if section.trim().is_empty() {
                ui::info("No current step defined.");
            } else {
                println!("{}", section.trim());
            }
        }
    }

    Ok(())
}

pub fn run_complete(path: &Path, name: &str) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;

    let spec_path = root.join(&config.specs.dir).join(format!("{name}.md"));
    if !spec_path.exists() {
        return Err(StrataError::SpecNotFound(name.to_string()));
    }

    let content = fs::read_to_string(&spec_path)?;
    let updated = content
        .replace("Status: `in-progress`", "Status: `complete`")
        .replace("Status: `in_progress`", "Status: `complete`");

    fs::write(&spec_path, updated)?;
    ui::success(&format!("Spec '{name}' marked as complete"));

    Ok(())
}

fn today_iso() -> String {
    // Simple date without chrono dep: use SystemTime
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs());
    // Convert to date components
    let days = now / 86400;
    let (year, month, day) = days_to_ymd(days);
    format!("{year:04}-{month:02}-{day:02}")
}

fn days_to_ymd(mut days: u64) -> (u64, u64, u64) {
    // Algorithm from https://howardhinnant.github.io/date_algorithms.html
    days += 719_468;
    let era = days / 146_097;
    let doe = days - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}
