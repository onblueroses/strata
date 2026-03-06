use crate::config::{AgentTarget, StrataConfig};
use crate::error::Result;
use crate::scanner::ProjectScan;
use crate::ui;
use std::fmt::Write as _;
use std::fs;
use std::path::Path;

const GENERATED_MARKER: &str = "<!-- strata:generated -->";

pub fn run(path: &Path, target: Option<AgentTarget>, install_skills: bool) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let (config, _) = StrataConfig::load(&root)?;
    let scan = crate::scanner::scan_project(&root, &config)?;

    let resolved_target = target.unwrap_or(config.targets.default);

    ui::header("Generating context files");

    // Refresh INDEX.md as part of generation
    super::fix::regenerate_index_md(&root, &scan, &config)?;
    ui::file_action("refresh", "INDEX.md");

    // Ensure output directories exist
    let strata_dir = root.join(".strata");
    fs::create_dir_all(&strata_dir)?;
    let domains_dir = strata_dir.join("domains");
    fs::create_dir_all(&domains_dir)?;

    // Tier 1: Project-level context
    let tier1 = generate_tier1(&scan, &config, &root);
    write_with_marker(&strata_dir.join("context.md"), &tier1)?;
    ui::file_action("generate", ".strata/context.md");

    // Tier 2: Per-domain context
    let tier2_files = generate_tier2(&scan, &config, &root);
    for (domain_name, content) in &tier2_files {
        let filename = format!("{domain_name}.md");
        write_with_marker(&domains_dir.join(&filename), content)?;
        ui::file_action("generate", &format!(".strata/domains/{filename}"));
    }

    // Write agent-specific target file
    if let Some(target_output) = crate::targets::resolve_target(resolved_target) {
        let target_path = root.join(&target_output.path);
        if let Some(parent) = target_path.parent() {
            fs::create_dir_all(parent)?;
        }
        let rendered = crate::targets::render_target(&config.project.name, &tier1, &target_output);
        fs::write(&target_path, rendered)?;
        let rel = target_output.path.to_string_lossy().replace('\\', "/");
        ui::file_action("generate", &rel);
    }

    // Install starter skills if requested
    if install_skills {
        install_starter_skills(&root)?;
    }

    let mut count = 1 + tier2_files.len();
    if crate::targets::resolve_target(resolved_target).is_some() {
        count += 1;
    }

    ui::success(&format!("Generated {count} context file(s)"));

    Ok(())
}

/// Install starter skill templates (review + commit).
fn install_starter_skills(root: &Path) -> Result<()> {
    let skills_dir = root.join("skills");

    let review_dir = skills_dir.join("review");
    let review_path = review_dir.join("SKILL.md");
    if !review_path.exists() {
        fs::create_dir_all(&review_dir)?;
        fs::write(&review_path, crate::templates::render_review_skill())?;
        ui::file_action("create", "skills/review/SKILL.md");
    }

    let commit_dir = skills_dir.join("commit");
    let commit_path = commit_dir.join("SKILL.md");
    if !commit_path.exists() {
        fs::create_dir_all(&commit_dir)?;
        fs::write(&commit_path, crate::templates::render_commit_skill())?;
        ui::file_action("create", "skills/commit/SKILL.md");
    }

    Ok(())
}

/// Generate Tier 1 context: project summary, domain map, skill index.
fn generate_tier1(scan: &ProjectScan, config: &StrataConfig, root: &Path) -> String {
    let mut out = String::new();

    // Project name
    let _ = writeln!(out, "# {}", config.project.name);
    let _ = writeln!(out);

    // Purpose extract from PROJECT.md (first non-empty paragraph after heading)
    let project_md = root.join("PROJECT.md");
    if let Ok(content) = fs::read_to_string(&project_md) {
        let purpose = extract_purpose(&content);
        if !purpose.is_empty() {
            let _ = writeln!(out, "{purpose}");
            let _ = writeln!(out);
        }
    }

    // Domain map
    if !config.project.domains.is_empty() {
        let _ = writeln!(out, "## Domains");
        let _ = writeln!(out);
        for domain in &config.project.domains {
            let dir_name = format!("{}-{}", domain.prefix, domain.name);
            let dir_path = std::path::PathBuf::from(&dir_name);
            let purpose_line = scan
                .domain_rules
                .get(&dir_path)
                .and_then(|r| {
                    let first_line = r.purpose_text.lines().next().unwrap_or_default();
                    if first_line.is_empty() {
                        None
                    } else {
                        Some(first_line.to_string())
                    }
                })
                .unwrap_or_else(|| "*No purpose defined*".to_string());
            let _ = writeln!(out, "- **{dir_name}**: {purpose_line}");
        }
        let _ = writeln!(out);
    }

    // Skill index
    if scan.skills.is_empty() {
        let _ = writeln!(out, "## Skills");
        let _ = writeln!(out);
        let _ = writeln!(out, "No skills configured.");
    } else {
        let _ = writeln!(out, "## Skills");
        let _ = writeln!(out);
        for skill in &scan.skills {
            let fallback = skill.path.to_string_lossy();
            let name = skill.name.as_deref().unwrap_or(&fallback);
            let desc = skill.description.as_deref().unwrap_or("*No description*");
            let _ = writeln!(out, "- **{name}**: {desc}");
        }
    }

    out
}

/// Generate Tier 2 context: per-domain files with purpose, boundaries, and key files.
fn generate_tier2(
    scan: &ProjectScan,
    config: &StrataConfig,
    _root: &Path,
) -> Vec<(String, String)> {
    let budget = (config.context.rules_budget as usize) * 2;

    config
        .project
        .domains
        .iter()
        .map(|domain| {
            let dir_name = format!("{}-{}", domain.prefix, domain.name);
            let dir_path = std::path::PathBuf::from(&dir_name);

            let mut out = String::new();
            let _ = writeln!(out, "# {}", domain.name);
            let _ = writeln!(out);

            // Purpose + Boundaries from RULES.md
            if let Some(rules) = scan.domain_rules.get(&dir_path) {
                if !rules.purpose_text.is_empty() {
                    let _ = writeln!(out, "## Purpose");
                    let _ = writeln!(out);
                    let _ = writeln!(out, "{}", rules.purpose_text);
                    let _ = writeln!(out);
                }
                if !rules.boundaries_text.is_empty() {
                    let _ = writeln!(out, "## Boundaries");
                    let _ = writeln!(out);
                    let _ = writeln!(out, "{}", rules.boundaries_text);
                    let _ = writeln!(out);
                }
            }

            // Key files in this domain with descriptions
            let domain_files: Vec<_> = scan
                .files
                .iter()
                .filter(|f| {
                    let s = f.to_string_lossy();
                    s.starts_with(&dir_name)
                        && f.file_name()
                            .and_then(|n| n.to_str())
                            .is_some_and(|n| n != "RULES.md")
                })
                .collect();

            if !domain_files.is_empty() {
                let _ = writeln!(out, "## Files");
                let _ = writeln!(out);
                for file in &domain_files {
                    let desc = scan
                        .descriptions
                        .get(*file)
                        .and_then(|d| d.as_deref())
                        .unwrap_or("*No description*");
                    let rel = file.to_string_lossy().replace('\\', "/");
                    let _ = writeln!(out, "- `{rel}`: {desc}");
                }
            }

            let content = truncate_to_budget(&out, budget);
            (dir_name, content)
        })
        .collect()
}

/// Extract the first non-empty paragraph after the first heading from PROJECT.md.
/// Truncates to ~200 chars if longer.
fn extract_purpose(content: &str) -> String {
    let mut past_heading = false;
    let mut paragraph = String::new();

    for line in content.lines() {
        let trimmed = line.trim();

        if trimmed.starts_with('#') {
            if past_heading && !paragraph.is_empty() {
                break; // reached next heading after collecting content
            }
            past_heading = true;
            continue;
        }

        if past_heading && !trimmed.is_empty() {
            if !paragraph.is_empty() {
                paragraph.push(' ');
            }
            paragraph.push_str(trimmed);
        } else if past_heading && trimmed.is_empty() && !paragraph.is_empty() {
            break; // end of first paragraph
        }
    }

    if paragraph.len() > 200 {
        let boundary = snap_to_char_floor(&paragraph, 200);
        let truncated = &paragraph[..boundary];
        if let Some(pos) = truncated.rfind(' ') {
            format!("{}...", &paragraph[..pos])
        } else {
            format!("{truncated}...")
        }
    } else {
        paragraph
    }
}

/// Truncate content to fit within a character budget.
/// Uses 70% head + 10% separator + 20% tail, preserving complete lines.
pub fn truncate_to_budget(content: &str, budget: usize) -> String {
    if content.len() <= budget {
        return content.to_string();
    }

    let original_len = content.len();
    let separator = format!("\n\n...truncated ({original_len} chars, budget {budget})...\n\n");
    let separator_len = separator.len();

    let available = budget.saturating_sub(separator_len);
    let head_budget = (available * 70) / 100;
    let tail_budget = available - head_budget;

    // Take head: find last newline within head_budget (char-boundary safe)
    let head = if head_budget >= content.len() {
        content.to_string()
    } else {
        let safe_end = snap_to_char_floor(content, head_budget);
        let head_slice = &content[..safe_end];
        if let Some(pos) = head_slice.rfind('\n') {
            content[..=pos].to_string()
        } else {
            head_slice.to_string()
        }
    };

    // Take tail: find first newline within last tail_budget chars (char-boundary safe)
    let tail = if tail_budget >= content.len() {
        String::new()
    } else {
        let raw_start = content.len().saturating_sub(tail_budget);
        let safe_start = snap_to_char_ceil(content, raw_start);
        let tail_slice = &content[safe_start..];
        if let Some(pos) = tail_slice.find('\n') {
            tail_slice[pos..].to_string()
        } else {
            tail_slice.to_string()
        }
    };

    format!("{head}{separator}{tail}")
}

/// Write generated content to a file, preserving human content above the marker.
fn write_with_marker(path: &Path, generated: &str) -> Result<()> {
    let content = if path.exists() {
        let existing = fs::read_to_string(path)?;
        if let Some(pos) = existing.find(GENERATED_MARKER) {
            // Preserve human content above the marker
            let human_part = &existing[..pos];
            format!("{human_part}{GENERATED_MARKER}\n\n{generated}")
        } else {
            // No marker found - prepend marker, treat everything as generated
            format!("{GENERATED_MARKER}\n\n{generated}")
        }
    } else {
        format!("{GENERATED_MARKER}\n\n{generated}")
    };

    fs::write(path, content)?;
    Ok(())
}

/// Find the largest index <= `pos` that falls on a UTF-8 char boundary.
fn snap_to_char_floor(s: &str, pos: usize) -> usize {
    let pos = pos.min(s.len());
    let mut i = pos;
    while i > 0 && !s.is_char_boundary(i) {
        i -= 1;
    }
    i
}

/// Find the smallest index >= `pos` that falls on a UTF-8 char boundary.
fn snap_to_char_ceil(s: &str, pos: usize) -> usize {
    let pos = pos.min(s.len());
    let mut i = pos;
    while i < s.len() && !s.is_char_boundary(i) {
        i += 1;
    }
    i
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    #[test]
    fn test_truncate_under_budget() {
        let content = "Short content";
        let result = truncate_to_budget(content, 100);
        assert_eq!(result, content);
    }

    #[test]
    fn test_truncate_over_budget() {
        // Build content that's clearly over budget
        use std::fmt::Write;
        let mut lines = String::new();
        for i in 1..=20 {
            let _ = writeln!(lines, "Line {i}: some content here");
        }
        assert!(lines.len() > 200, "Test content should be >200 chars");

        let result = truncate_to_budget(&lines, 200);
        assert!(
            result.contains("truncated"),
            "Should have truncation marker"
        );
        // Head content preserved
        assert!(result.contains("Line 1"), "Should preserve head content");
        // Tail content preserved
        assert!(result.contains("Line 20"), "Should preserve tail content");
    }

    #[test]
    fn test_extract_purpose_short() {
        let content = "# My Project\n\nThis is the purpose.\n\n## Details\n";
        let result = extract_purpose(content);
        assert_eq!(result, "This is the purpose.");
    }

    #[test]
    fn test_extract_purpose_long() {
        let long_text = "x ".repeat(150); // 300 chars
        let content = format!("# My Project\n\n{long_text}\n\n## Details\n");
        let result = extract_purpose(&content);
        assert!(result.len() <= 210, "Should truncate: {}", result.len());
        assert!(result.ends_with("..."));
    }

    #[test]
    fn test_write_with_marker_preserves_human_content() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.md");

        // Write initial generated content
        write_with_marker(&path, "Generated V1\n").unwrap();
        let content = fs::read_to_string(&path).unwrap();
        assert!(content.contains(GENERATED_MARKER));
        assert!(content.contains("Generated V1"));

        // Simulate human adding content above marker
        let with_human = format!("Human notes here.\n\n{content}");
        fs::write(&path, &with_human).unwrap();

        // Regenerate
        write_with_marker(&path, "Generated V2\n").unwrap();
        let updated = fs::read_to_string(&path).unwrap();
        assert!(updated.contains("Human notes here."), "Human content lost");
        assert!(updated.contains("Generated V2"), "New content missing");
        assert!(
            !updated.contains("Generated V1"),
            "Old content should be replaced"
        );
    }
}
