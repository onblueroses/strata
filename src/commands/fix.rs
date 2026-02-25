use crate::config::StrataConfig;
use crate::error::Result;
use crate::scanner;
use crate::templates;
use crate::ui;
use std::fmt::Write as _;
use std::fs;
use std::path::Path;

pub fn run(path: &Path, dry_run: bool) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;
    let scan = scanner::scan_project(&root, &config)?;

    if dry_run {
        ui::header("Fix (dry run)");
    } else {
        ui::header("Fix");
    }

    let mut fixes = 0;

    // Fix 1: Add unindexed files to INDEX.md
    let unindexed = scan.unindexed_files(&root);
    if !unindexed.is_empty() {
        if dry_run {
            for file in &unindexed {
                ui::info(&format!("Would add to INDEX.md: {}", file.display()));
            }
        } else {
            append_to_index(&root, &unindexed)?;
            for file in &unindexed {
                ui::success(&format!("Added to INDEX.md: {}", file.display()));
            }
        }
        fixes += unindexed.len();
    }

    // Fix 2: Generate missing RULES.md stubs
    for domain in &config.project.domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        let rules_path = root.join(&dir_name).join("RULES.md");
        if !rules_path.exists() {
            if dry_run {
                ui::info(&format!("Would create {dir_name}/RULES.md"));
            } else {
                // Ensure domain directory exists
                fs::create_dir_all(root.join(&dir_name))?;
                let content = templates::render_rules_md(&domain.name);
                fs::write(&rules_path, content)?;
                ui::success(&format!("Created {dir_name}/RULES.md"));
            }
            fixes += 1;
        }
    }

    // Fix 3: Remove dead links
    let dead_links = scan.dead_links();
    if !dead_links.is_empty() {
        if dry_run {
            for (source, target) in &dead_links {
                ui::info(&format!(
                    "Would remove dead link in {}: {}",
                    source.display(),
                    target
                ));
            }
        } else {
            for (source, target) in &dead_links {
                remove_link_from_file(&root.join(source), target)?;
                ui::success(&format!(
                    "Removed dead link in {}: {}",
                    source.display(),
                    target
                ));
            }
        }
        fixes += dead_links.len();
    }

    println!();
    if fixes == 0 {
        ui::success("Nothing to fix");
    } else if dry_run {
        ui::info(&format!("{fixes} fix(es) would be applied"));
    } else {
        ui::success(&format!("{fixes} fix(es) applied"));
    }

    Ok(())
}

fn append_to_index(root: &Path, files: &[std::path::PathBuf]) -> Result<()> {
    let index_path = root.join("INDEX.md");
    let mut content = if index_path.exists() {
        fs::read_to_string(&index_path)?
    } else {
        String::from("# Index\n\n| File | Description |\n|------|-------------|\n")
    };

    for file in files {
        let relative = file
            .strip_prefix(root)
            .unwrap_or(file)
            .to_string_lossy()
            .replace('\\', "/");
        let _ = writeln!(content, "| `{relative}` | *TODO: add description* |");
    }

    fs::write(&index_path, content)?;
    Ok(())
}

fn remove_link_from_file(file: &Path, target: &str) -> Result<()> {
    let content = fs::read_to_string(file)?;
    let line_ending = if content.contains("\r\n") {
        "\r\n"
    } else {
        "\n"
    };

    // Remove [[wiki-link]] style
    let wiki_pattern = format!("[[{target}]]");
    let content = content.replace(&wiki_pattern, "");

    // Remove [text](target) style
    let needle = format!("]({target})");
    let lines: Vec<String> = content
        .lines()
        .map(|line| {
            if line.contains(&needle) {
                remove_md_links(line, target)
            } else {
                line.to_string()
            }
        })
        .collect();

    let mut output = lines.join(line_ending);
    if content.ends_with('\n') || content.ends_with("\r\n") {
        output.push_str(line_ending);
    }

    fs::write(file, output)?;
    Ok(())
}

fn remove_md_links(line: &str, target: &str) -> String {
    let needle = format!("]({target})");
    let mut result = line.to_string();

    while let Some(close_bracket) = result.find(&needle) {
        let before = &result[..close_bracket];
        if let Some(open_bracket) = before.rfind('[') {
            let end = close_bracket + needle.len();
            result = format!("{}{}", &result[..open_bracket], &result[end..]);
        } else {
            break;
        }
    }

    result
}
