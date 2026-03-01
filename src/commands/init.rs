use crate::config::{
    ContextConfig, DomainConfig, LintConfig, ProjectConfig, StrataConfig, StructureConfig,
};
use crate::error::{Result, StrataError};
use crate::templates;
use crate::ui;
use dialoguer::{Input, MultiSelect};
use std::fs;
use std::path::Path;

pub fn run(path: &Path, name: Option<String>, domains: Option<Vec<String>>) -> Result<()> {
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
    };
    config.save(&path.join("strata.toml"))?;
    ui::file_action("create", "strata.toml");

    // Generate files from templates
    generate_files(&path, &project_name, &domain_configs)?;

    ui::success(&format!(
        "Project '{}' initialized with {} domain(s)",
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

fn generate_files(root: &Path, project_name: &str, domains: &[DomainConfig]) -> Result<()> {
    // PROJECT.md (Constitution layer)
    let project_md = templates::render_project_md(project_name);
    fs::write(root.join("PROJECT.md"), project_md)?;
    ui::file_action("create", "PROJECT.md");

    // INDEX.md (Global Index layer)
    let index_md = templates::render_index_md(project_name, domains);
    fs::write(root.join("INDEX.md"), index_md)?;
    ui::file_action("create", "INDEX.md");

    // RULES.md per domain (Domain Boundaries layer)
    for domain in domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        let rules_md = templates::render_rules_md(&domain.name);
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
