#![expect(clippy::unwrap_used, reason = "test code - unwrap is acceptable")]
#![expect(clippy::expect_used, reason = "test code - expect is acceptable")]

mod common;

use assert_fs::prelude::*;
use std::fs;

/// End-to-end test: init -> add content -> add skill -> generate -> lint -> fix --index -> verify
#[test]
fn test_memory_system_workflow() {
    let dir = common::temp_project();
    let bin = common::strata_bin();

    // Step 1: Init project
    let result = std::process::Command::new(&bin)
        .args([
            "init",
            "--name",
            "memory-e2e",
            "--domains",
            "Core,Docs",
            "--path",
        ])
        .arg(dir.path())
        .output()
        .expect("init failed");
    assert!(
        result.status.success(),
        "init: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    // Verify skills directory was created
    assert!(
        dir.child("skills").path().exists(),
        "skills/ directory should be created by init"
    );
    assert!(
        dir.child("skills/README.md").path().exists(),
        "skills/README.md should be created by init"
    );

    // Step 2: Add content files with descriptions
    dir.child("01-Core/models.md")
        .write_str("---\ndescription: Data models\n---\n\n# Models\n\nModel definitions.\n")
        .unwrap();
    dir.child("01-Core/utils.md")
        .write_str("# Utilities\n\nHelper functions.\n")
        .unwrap();
    dir.child("02-Docs/guide.md")
        .write_str("---\ndescription: User guide\n---\n\n# Guide\n")
        .unwrap();

    // Step 3: Create a skill
    dir.child("skills/my-skill").create_dir_all().unwrap();
    dir.child("skills/my-skill/SKILL.md")
        .write_str(
            "---\nname: my-skill\ndescription: A test skill for e2e\ntrigger: when testing\n---\n\n# My Skill\n\nDo the thing.\n",
        )
        .unwrap();

    // Step 4: Generate context files
    let result = std::process::Command::new(&bin)
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("generate failed");
    assert!(
        result.status.success(),
        "generate: {}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );

    // Verify .strata/context.md
    let context = fs::read_to_string(dir.child(".strata/context.md").path()).unwrap();
    assert!(
        context.contains("memory-e2e"),
        "Should contain project name"
    );
    assert!(context.contains("01-Core"), "Should contain Core domain");
    assert!(context.contains("02-Docs"), "Should contain Docs domain");
    assert!(context.contains("my-skill"), "Should contain skill name");
    assert!(
        context.contains("A test skill for e2e"),
        "Should contain skill description"
    );

    // Verify .strata/domains/01-Core.md
    let core_ctx = fs::read_to_string(dir.child(".strata/domains/01-Core.md").path()).unwrap();
    assert!(
        core_ctx.contains("Purpose"),
        "Domain context should have Purpose"
    );
    assert!(
        core_ctx.contains("models.md"),
        "Domain context should list files"
    );

    // Verify INDEX.md was refreshed (generate calls fix --index internally)
    let index = fs::read_to_string(dir.child("INDEX.md").path()).unwrap();
    assert!(
        index.contains("01-Core/models.md"),
        "INDEX.md should contain models.md"
    );
    assert!(
        index.contains("Data models"),
        "INDEX.md should have frontmatter description"
    );

    // Step 5: Lint should pass (no errors)
    let result = std::process::Command::new(&bin)
        .args(["lint"])
        .current_dir(dir.path())
        .output()
        .expect("lint failed");
    assert!(
        result.status.success(),
        "lint should pass: {}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );

    // Step 6: Make PROJECT.md oversized and verify context-budget fires
    let big_content = "# memory-e2e\n\n".to_string() + &"x".repeat(3500);
    dir.child("PROJECT.md").write_str(&big_content).unwrap();

    let result = std::process::Command::new(&bin)
        .args(["lint", "--rule", "context-budget"])
        .current_dir(dir.path())
        .output()
        .expect("lint failed");

    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(
        stdout.contains("context-budget"),
        "Oversized PROJECT.md should trigger context-budget warning: {stdout}"
    );

    // Step 7: fix --index produces sorted INDEX.md
    let result = std::process::Command::new(&bin)
        .args(["fix", "--index"])
        .current_dir(dir.path())
        .output()
        .expect("fix --index failed");
    assert!(
        result.status.success(),
        "fix --index: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    let index = fs::read_to_string(dir.child("INDEX.md").path()).unwrap();
    // Verify sorting: 01-Core files should come before 02-Docs files
    let core_pos = index.find("01-Core");
    let docs_pos = index.find("02-Docs");
    if let (Some(c), Some(d)) = (core_pos, docs_pos) {
        assert!(c < d, "Core should appear before Docs in sorted INDEX.md");
    }
}
