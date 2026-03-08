use crate::config::DomainConfig;
use crate::error::Result;
use minijinja::{Environment, context};
use std::fmt::Write as _;

const PROJECT_MD_TMPL: &str = include_str!("../templates/PROJECT.md.tmpl");
const INDEX_MD_TMPL: &str = include_str!("../templates/INDEX.md.tmpl");
const RULES_MD_TMPL: &str = include_str!("../templates/RULES.md.tmpl");
const GITIGNORE_TMPL: &str = include_str!("../templates/gitignore.tmpl");
const PRE_COMMIT_TMPL: &str = include_str!("../templates/pre-commit.sh.tmpl");
const SKILLS_README_TMPL: &str = include_str!("../templates/skills-readme.md.tmpl");
const SESSION_START_HOOK_TMPL: &str = include_str!("../templates/hooks/session-start.sh.tmpl");
const SESSION_STOP_HOOK_TMPL: &str = include_str!("../templates/hooks/session-stop.sh.tmpl");
const PRE_COMPACT_HOOK_TMPL: &str = include_str!("../templates/hooks/pre-compact.sh.tmpl");
const SPEC_TMPL: &str = include_str!("../templates/spec.md.tmpl");
const REVIEW_SKILL_TMPL: &str = include_str!("../templates/skills/review.md.tmpl");
const COMMIT_SKILL_TMPL: &str = include_str!("../templates/skills/commit.md.tmpl");
const DEBUG_SKILL_TMPL: &str = include_str!("../templates/skills/debug.md.tmpl");
const TEST_SKILL_TMPL: &str = include_str!("../templates/skills/test.md.tmpl");
const PLAN_SKILL_TMPL: &str = include_str!("../templates/skills/plan.md.tmpl");
const PR_SKILL_TMPL: &str = include_str!("../templates/skills/pr.md.tmpl");
const EXPLORE_SKILL_TMPL: &str = include_str!("../templates/skills/explore.md.tmpl");
const RELEASE_SKILL_TMPL: &str = include_str!("../templates/skills/release.md.tmpl");
const SECURITY_SKILL_TMPL: &str = include_str!("../templates/skills/security.md.tmpl");
const OPTIMIZE_SKILL_TMPL: &str = include_str!("../templates/skills/optimize.md.tmpl");
const MEMORY_STARTER_TMPL: &str = include_str!("../templates/memory.md.tmpl");
const EVAL_SET_TMPL: &str = include_str!("../templates/eval-set.json.tmpl");
const EVAL_REPORT_TMPL: &str = include_str!("../templates/eval-report.html.tmpl");

/// Build a minijinja environment with all dynamic templates registered.
pub fn build_env() -> Result<Environment<'static>> {
    let mut env = Environment::new();
    env.add_template("project.md", PROJECT_MD_TMPL)?;
    env.add_template("index.md", INDEX_MD_TMPL)?;
    env.add_template("rules.md", RULES_MD_TMPL)?;
    env.add_template("spec.md", SPEC_TMPL)?;
    env.add_template("eval-set.json", EVAL_SET_TMPL)?;
    env.add_template("eval-report.html", EVAL_REPORT_TMPL)?;
    Ok(env)
}

pub fn render_project_md(project_name: &str) -> Result<String> {
    let env = build_env()?;
    let tmpl = env.get_template("project.md")?;
    Ok(tmpl.render(context! { project_name })?)
}

pub fn render_index_md(project_name: &str, domains: &[DomainConfig]) -> Result<String> {
    let mut entries = String::new();
    for domain in domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        let _ = writeln!(
            entries,
            "| `{dir_name}/RULES.md` | Domain rules for {} |",
            domain.name
        );
    }

    let env = build_env()?;
    let tmpl = env.get_template("index.md")?;
    Ok(tmpl.render(context! {
        project_name,
        index_entries => entries.trim_end(),
    })?)
}

pub fn render_rules_md(domain_name: &str) -> Result<String> {
    let env = build_env()?;
    let tmpl = env.get_template("rules.md")?;
    Ok(tmpl.render(context! { domain_name })?)
}

pub fn render_gitignore() -> String {
    GITIGNORE_TMPL.to_string()
}

pub fn render_pre_commit() -> String {
    PRE_COMMIT_TMPL.to_string()
}

pub fn render_skills_readme() -> String {
    SKILLS_README_TMPL.to_string()
}

pub fn render_session_start_hook() -> String {
    SESSION_START_HOOK_TMPL.to_string()
}

pub fn render_session_stop_hook() -> String {
    SESSION_STOP_HOOK_TMPL.to_string()
}

pub fn render_pre_compact_hook() -> String {
    PRE_COMPACT_HOOK_TMPL.to_string()
}

pub fn render_spec(name: &str, session_id: &str, date: &str) -> Result<String> {
    let env = build_env()?;
    let tmpl = env.get_template("spec.md")?;
    Ok(tmpl.render(context! {
        spec_name => name,
        session_id,
        date,
        phase_name => "Setup",
    })?)
}

pub fn render_review_skill() -> String {
    REVIEW_SKILL_TMPL.to_string()
}

pub fn render_commit_skill() -> String {
    COMMIT_SKILL_TMPL.to_string()
}

pub fn render_debug_skill() -> String {
    DEBUG_SKILL_TMPL.to_string()
}

pub fn render_test_skill() -> String {
    TEST_SKILL_TMPL.to_string()
}

pub fn render_plan_skill() -> String {
    PLAN_SKILL_TMPL.to_string()
}

pub fn render_pr_skill() -> String {
    PR_SKILL_TMPL.to_string()
}

pub fn render_explore_skill() -> String {
    EXPLORE_SKILL_TMPL.to_string()
}

pub fn render_release_skill() -> String {
    RELEASE_SKILL_TMPL.to_string()
}

pub fn render_security_skill() -> String {
    SECURITY_SKILL_TMPL.to_string()
}

pub fn render_optimize_skill() -> String {
    OPTIMIZE_SKILL_TMPL.to_string()
}

pub fn render_memory_starter() -> String {
    MEMORY_STARTER_TMPL.to_string()
}

pub fn render_eval_set(skill_name: &str) -> Result<String> {
    let env = build_env()?;
    let tmpl = env.get_template("eval-set.json")?;
    Ok(tmpl.render(context! { skill_name })?)
}

pub fn render_eval_report(data_json: &str) -> Result<String> {
    let env = build_env()?;
    let tmpl = env.get_template("eval-report.html")?;
    Ok(tmpl.render(context! { data_json })?)
}
