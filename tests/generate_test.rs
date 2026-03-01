#![expect(clippy::unwrap_used, reason = "test code - unwrap is acceptable")]
#![expect(clippy::expect_used, reason = "test code - expect is acceptable")]

mod common;

use assert_fs::prelude::*;
use std::fs;

fn setup_project_with_content(dir: &assert_fs::TempDir) {
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "gen-test"

[[project.domains]]
name = "Core"
prefix = "01"

[[project.domains]]
name = "Docs"
prefix = "02"
"#,
        )
        .unwrap();
    dir.child("PROJECT.md")
        .write_str("# Gen Test\n\nThis project tests context generation.\n")
        .unwrap();
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();
    dir.child(".strata").create_dir_all().unwrap();

    // Core domain with RULES.md and a content file
    dir.child("01-Core").create_dir_all().unwrap();
    dir.child("01-Core/RULES.md")
        .write_str(
            "# Rules: Core\n\n## Purpose\nCore business logic and models.\n\n## Boundaries\n- No IO operations.\n",
        )
        .unwrap();
    dir.child("01-Core/models.md")
        .write_str("---\ndescription: Data models and types\n---\n\n# Models\n")
        .unwrap();

    // Docs domain with RULES.md
    dir.child("02-Docs").create_dir_all().unwrap();
    dir.child("02-Docs/RULES.md")
        .write_str(
            "# Rules: Docs\n\n## Purpose\nProject documentation.\n\n## Boundaries\n- Markdown only.\n",
        )
        .unwrap();
}

#[test]
fn test_generate_creates_context_file() {
    let dir = common::temp_project();
    setup_project_with_content(&dir);

    let result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(
        result.status.success(),
        "generate failed: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    // Tier 1: .strata/context.md should exist
    let context_path = dir.child(".strata/context.md");
    assert!(
        context_path.path().exists(),
        ".strata/context.md not created"
    );

    let content = fs::read_to_string(context_path.path()).unwrap();
    assert!(content.contains("gen-test"), "Should contain project name");
    assert!(content.contains("01-Core"), "Should contain Core domain");
    assert!(content.contains("02-Docs"), "Should contain Docs domain");
    assert!(
        content.contains("strata:generated"),
        "Should contain generated marker"
    );
}

#[test]
fn test_generate_creates_domain_files() {
    let dir = common::temp_project();
    setup_project_with_content(&dir);

    let result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(result.status.success());

    // Tier 2: Per-domain files should exist
    let core_ctx = dir.child(".strata/domains/01-Core.md");
    assert!(
        core_ctx.path().exists(),
        ".strata/domains/01-Core.md not created"
    );

    let core_content = fs::read_to_string(core_ctx.path()).unwrap();
    assert!(
        core_content.contains("Purpose"),
        "Domain context should have Purpose section"
    );
    assert!(
        core_content.contains("Core business logic"),
        "Should contain purpose text"
    );

    let docs_ctx = dir.child(".strata/domains/02-Docs.md");
    assert!(
        docs_ctx.path().exists(),
        ".strata/domains/02-Docs.md not created"
    );
}

#[test]
fn test_generate_includes_skills() {
    let dir = common::temp_project();
    setup_project_with_content(&dir);

    // Add a skill
    dir.child("skills/my-skill").create_dir_all().unwrap();
    dir.child("skills/my-skill/SKILL.md")
        .write_str("---\nname: my-skill\ndescription: A test skill\n---\n\n# My Skill\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(result.status.success());

    let content = fs::read_to_string(dir.child(".strata/context.md").path()).unwrap();
    assert!(
        content.contains("my-skill"),
        "Context should include skill name"
    );
    assert!(
        content.contains("A test skill"),
        "Context should include skill description"
    );
}

#[test]
fn test_generate_preserves_human_content() {
    let dir = common::temp_project();
    setup_project_with_content(&dir);

    // First generate
    let result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");
    assert!(result.status.success());

    // Add human content above the marker
    let context_path = dir.child(".strata/context.md").path().to_path_buf();
    let original = fs::read_to_string(&context_path).unwrap();
    let with_human = format!("My custom notes go here.\n\n{original}");
    fs::write(&context_path, &with_human).unwrap();

    // Regenerate
    let result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");
    assert!(result.status.success());

    let updated = fs::read_to_string(&context_path).unwrap();
    assert!(
        updated.contains("My custom notes go here"),
        "Human content should be preserved after regeneration"
    );
}

#[test]
fn test_generate_no_skills_shows_message() {
    let dir = common::temp_project();
    setup_project_with_content(&dir);

    let result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");
    assert!(result.status.success());

    let content = fs::read_to_string(dir.child(".strata/context.md").path()).unwrap();
    assert!(
        content.contains("No skills configured"),
        "Should show no-skills message when no skills/ dir exists"
    );
}
