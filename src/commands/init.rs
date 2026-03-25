use crate::config::{
    AgentTarget, ContextConfig, DomainConfig, HooksConfig, LintConfig, MemoryConfig, Preset,
    ProjectConfig, SessionsConfig, SkillsConfig, SpecsConfig, StrataConfig, StructureConfig,
    TargetsConfig,
};
use crate::error::{Result, StrataError};
use crate::templates;
use crate::ui;
use dialoguer::{Input, MultiSelect};
use std::fs;
use std::path::Path;

pub fn run(
    path: &Path,
    name: Option<String>,
    domains: Option<Vec<String>>,
    preset: Preset,
    no_enforce: bool,
) -> Result<()> {
    let path = if path == Path::new(".") {
        std::env::current_dir()?
    } else {
        path.to_path_buf()
    };

    // Check if already initialized
    if path.join("strata.toml").exists() {
        return Err(StrataError::AlreadyInitialized(path));
    }

    // Get project name
    let project_name = match name {
        Some(n) => n,
        None => Input::new().with_prompt("Project name").interact_text()?,
    };

    // Get domains
    let domain_names = match domains {
        Some(d) => d,
        None => prompt_domains()?,
    };

    // Build domain configs with numbered prefixes
    let domain_configs: Vec<DomainConfig> = domain_names
        .iter()
        .enumerate()
        .map(|(i, name)| DomainConfig {
            name: name.clone(),
            prefix: format!("{:02}", i + 1),
        })
        .collect();

    ui::header(&format!("Initializing strata project: {project_name}"));

    // Create directory structure
    create_directories(&path, &domain_configs)?;

    // Build hooks config based on preset
    let enforce = !no_enforce;
    let hooks = match preset {
        Preset::Standard | Preset::Full => HooksConfig {
            session_start: ".strata/hooks/session-start.sh".to_string(),
            session_stop: ".strata/hooks/session-stop.sh".to_string(),
            pre_compact: ".strata/hooks/pre-compact.sh".to_string(),
            enforce,
            ..HooksConfig::default()
        },
        Preset::Minimal => HooksConfig::default(),
    };

    let specs = SpecsConfig::default();
    let sessions = SessionsConfig::default();

    // Generate config
    let config = StrataConfig {
        project: ProjectConfig {
            name: project_name.clone(),
            description: String::new(),
            domains: domain_configs.clone(),
        },
        structure: StructureConfig::default(),
        lint: LintConfig::default(),
        context: ContextConfig::default(),
        memory: MemoryConfig::default(),
        hooks,
        specs,
        sessions,
        targets: TargetsConfig::default(),
        skills: SkillsConfig::default(),
        custom_rules: vec![],
        workspace: crate::config::WorkspaceConfig::default(),
    };
    config.save(&path.join("strata.toml"))?;
    ui::file_action("create", "strata.toml");

    // Generate files from templates
    generate_files(&path, &project_name, &domain_configs, preset)?;

    // Preset-specific scaffolding
    if matches!(preset, Preset::Standard | Preset::Full) {
        scaffold_standard(&path, config.hooks.enforce, &config.targets.active)?;
    }
    if preset == Preset::Full {
        scaffold_full(&path)?;
    }

    ui::success(&format!(
        "Project '{}' initialized ({preset} preset, {} domain(s))",
        project_name,
        domain_configs.len()
    ));

    Ok(())
}

fn prompt_domains() -> Result<Vec<String>> {
    let defaults = vec!["Core", "Docs", "Config", "Scripts", "Tests", "Resources"];

    println!("\nSelect domains (or enter custom ones):");

    let selections = MultiSelect::new().items(&defaults).interact()?;

    let mut selected: Vec<String> = selections
        .iter()
        .map(|&i| defaults[i].to_string())
        .collect();

    // Allow adding custom domains
    loop {
        let custom: String = Input::new()
            .with_prompt("Add custom domain (empty to finish)")
            .allow_empty(true)
            .interact_text()?;

        if custom.is_empty() {
            break;
        }
        selected.push(custom);
    }

    if selected.is_empty() {
        selected = vec!["Core".to_string(), "Docs".to_string()];
        ui::info("No domains selected, using defaults: Core, Docs");
    }

    Ok(selected)
}

fn create_directories(root: &Path, domains: &[DomainConfig]) -> Result<()> {
    // Create .strata directory
    fs::create_dir_all(root.join(".strata"))?;
    ui::file_action("create", ".strata/");

    // Create config directory
    fs::create_dir_all(root.join("config"))?;
    ui::file_action("create", "config/");

    // Create archive directory
    fs::create_dir_all(root.join("archive"))?;
    ui::file_action("create", "archive/");

    // Create skills directory
    fs::create_dir_all(root.join("skills"))?;
    ui::file_action("create", "skills/");

    // Create domain directories
    for domain in domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        fs::create_dir_all(root.join(&dir_name))?;
        ui::file_action("create", &format!("{dir_name}/"));
    }

    Ok(())
}

fn generate_files(
    root: &Path,
    project_name: &str,
    domains: &[DomainConfig],
    preset: Preset,
) -> Result<()> {
    // PROJECT.md (Constitution layer)
    let project_md = templates::render_project_md(project_name)?;
    fs::write(root.join("PROJECT.md"), project_md)?;
    ui::file_action("create", "PROJECT.md");

    // INDEX.md (Global Index layer)
    let extra_entries: Vec<(&str, &str)> = if matches!(preset, Preset::Standard | Preset::Full) {
        vec![
            ("MEMORY.md", "Persistent project memory for AI agents"),
            (
                "references/code-quality.md",
                "Code quality principles and anti-patterns",
            ),
            (
                "references/skill-design.md",
                "Skill design and description optimization",
            ),
        ]
    } else {
        vec![]
    };
    let index_md = templates::render_index_md(project_name, domains, &extra_entries)?;
    fs::write(root.join("INDEX.md"), index_md)?;
    ui::file_action("create", "INDEX.md");

    // RULES.md per domain (Domain Boundaries layer)
    for domain in domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        let rules_md = templates::render_rules_md(&domain.name)?;
        fs::write(root.join(&dir_name).join("RULES.md"), rules_md)?;
        ui::file_action("create", &format!("{dir_name}/RULES.md"));
    }

    // Skills README
    let skills_readme = templates::render_skills_readme();
    fs::write(root.join("skills").join("README.md"), skills_readme)?;
    ui::file_action("create", "skills/README.md");

    // Default .gitignore
    let gitignore = templates::render_gitignore();
    let gitignore_path = root.join(".gitignore");
    if !gitignore_path.exists() {
        fs::write(&gitignore_path, gitignore)?;
        ui::file_action("create", ".gitignore");
    }

    Ok(())
}

/// Scaffold standard preset: hooks, starter skills, MEMORY.md.
fn scaffold_standard(root: &Path, enforce_hooks: bool, targets: &[AgentTarget]) -> Result<()> {
    // Hooks directory with 3 scripts
    let hooks_dir = root.join(".strata").join("hooks");
    fs::create_dir_all(&hooks_dir)?;
    ui::file_action("create", ".strata/hooks/");

    fs::write(
        hooks_dir.join("session-start.sh"),
        templates::render_session_start_hook(),
    )?;
    ui::file_action("create", ".strata/hooks/session-start.sh");

    fs::write(
        hooks_dir.join("session-stop.sh"),
        templates::render_session_stop_hook(enforce_hooks)?,
    )?;
    ui::file_action("create", ".strata/hooks/session-stop.sh");

    fs::write(
        hooks_dir.join("pre-compact.sh"),
        templates::render_pre_compact_hook(),
    )?;
    ui::file_action("create", ".strata/hooks/pre-compact.sh");

    // Agent-specific hook wiring
    if targets.contains(&AgentTarget::ClaudeCode) {
        let claude_dir = root.join(".claude");
        fs::create_dir_all(&claude_dir)?;
        let settings_path = claude_dir.join("settings.json");
        if !settings_path.exists() {
            fs::write(&settings_path, templates::render_claude_code_settings())?;
            ui::file_action("create", ".claude/settings.json");
        }
    }

    // Core skills via registry
    for name in templates::core_skills() {
        if let Some(content) = templates::render_skill(name) {
            let skill_dir = root.join("skills").join(name);
            fs::create_dir_all(&skill_dir)?;
            fs::write(skill_dir.join("SKILL.md"), content)?;
            ui::file_action("create", &format!("skills/{name}/SKILL.md"));
        }
    }

    // MEMORY.md starter
    let memory_path = root.join("MEMORY.md");
    if !memory_path.exists() {
        fs::write(&memory_path, templates::render_memory_starter())?;
        ui::file_action("create", "MEMORY.md");
    }

    // Reference docs
    let refs_dir = root.join("references");
    fs::create_dir_all(&refs_dir)?;
    ui::file_action("create", "references/");

    fs::write(
        refs_dir.join("code-quality.md"),
        templates::render_code_quality_reference(),
    )?;
    ui::file_action("create", "references/code-quality.md");

    fs::write(
        refs_dir.join("skill-design.md"),
        templates::render_skill_design_reference(),
    )?;
    ui::file_action("create", "references/skill-design.md");

    Ok(())
}

/// Scaffold full preset additions: specs dir, sessions dir, domain skills.
fn scaffold_full(root: &Path) -> Result<()> {
    let specs_dir = root.join(".strata").join("specs");
    fs::create_dir_all(&specs_dir)?;
    ui::file_action("create", ".strata/specs/");

    let sessions_dir = root.join(".strata").join("sessions");
    fs::create_dir_all(&sessions_dir)?;
    ui::file_action("create", ".strata/sessions/");

    // Getting started reference doc
    let refs_dir = root.join("references");
    let getting_started_path = refs_dir.join("getting-started.md");
    if !getting_started_path.exists() {
        fs::write(
            &getting_started_path,
            templates::render_getting_started_reference(),
        )?;
        ui::file_action("create", "references/getting-started.md");
    }

    // Meta skills (opt-in tooling)
    for name in templates::meta_skills() {
        if let Some(content) = templates::render_skill(name) {
            let skill_dir = root.join("skills").join(name);
            fs::create_dir_all(&skill_dir)?;
            fs::write(skill_dir.join("SKILL.md"), content)?;
            ui::file_action("create", &format!("skills/{name}/SKILL.md"));
        }
    }

    // Detect project type and install matching domain skills
    let project_type = crate::scanner::project_type::detect_project_type(root, &[]);
    let domains = domains_for_project_type(&project_type);

    for domain in domains {
        for name in templates::domain_skills(domain) {
            if let Some(content) = templates::render_skill(name) {
                let skill_dir = root.join("skills").join(name);
                fs::create_dir_all(&skill_dir)?;
                fs::write(skill_dir.join("SKILL.md"), content)?;
                ui::file_action("create", &format!("skills/{name}/SKILL.md"));
            }
        }
    }

    Ok(())
}

/// Map detected project type to domain skill categories.
fn domains_for_project_type(pt: &crate::scanner::project_type::ProjectType) -> Vec<&'static str> {
    use crate::scanner::project_type::{Framework, Language};

    let mut domains = Vec::new();

    // Frontend domain: JS/TS projects with frontend frameworks
    let has_frontend_framework = pt.frameworks.iter().any(|f| {
        matches!(
            f,
            Framework::Nextjs | Framework::React | Framework::Vue | Framework::Svelte
        )
    });
    if has_frontend_framework {
        domains.push("frontend");
    }

    // Security domain: always useful for non-unknown projects
    if pt.language != Language::Unknown {
        domains.push("security");
    }

    domains
}
