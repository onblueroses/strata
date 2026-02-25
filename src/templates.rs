use crate::config::DomainConfig;

const PROJECT_MD_TMPL: &str = include_str!("../templates/PROJECT.md.tmpl");
const INDEX_MD_TMPL: &str = include_str!("../templates/INDEX.md.tmpl");
const RULES_MD_TMPL: &str = include_str!("../templates/RULES.md.tmpl");
const GITIGNORE_TMPL: &str = include_str!("../templates/gitignore.tmpl");
const PRE_COMMIT_TMPL: &str = include_str!("../templates/pre-commit.sh.tmpl");

pub fn render_project_md(project_name: &str) -> String {
    PROJECT_MD_TMPL.replace("{{PROJECT_NAME}}", project_name)
}

pub fn render_index_md(project_name: &str, domains: &[DomainConfig]) -> String {
    let mut entries = String::new();
    for domain in domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        entries.push_str(&format!(
            "| `{}/RULES.md` | Domain rules for {} |\n",
            dir_name, domain.name
        ));
    }

    INDEX_MD_TMPL
        .replace("{{PROJECT_NAME}}", project_name)
        .replace("{{INDEX_ENTRIES}}", entries.trim_end())
}

pub fn render_rules_md(domain_name: &str) -> String {
    RULES_MD_TMPL.replace("{{DOMAIN_NAME}}", domain_name)
}

pub fn render_gitignore() -> String {
    GITIGNORE_TMPL.to_string()
}

pub fn render_pre_commit() -> String {
    PRE_COMMIT_TMPL.to_string()
}
