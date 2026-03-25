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
const VERIFY_SKILL_TMPL: &str = include_str!("../templates/skills/verify.md.tmpl");
const END_SKILL_TMPL: &str = include_str!("../templates/skills/end.md.tmpl");
const PICKUP_SKILL_TMPL: &str = include_str!("../templates/skills/pickup.md.tmpl");
const TIDY_SKILL_TMPL: &str = include_str!("../templates/skills/tidy.md.tmpl");
const RESEARCH_SKILL_TMPL: &str = include_str!("../templates/skills/research.md.tmpl");
const DEPLOY_SKILL_TMPL: &str = include_str!("../templates/skills/deploy.md.tmpl");
const STATUS_SKILL_TMPL: &str = include_str!("../templates/skills/status.md.tmpl");
const GET_TO_WORK_SKILL_TMPL: &str = include_str!("../templates/skills/get-to-work.md.tmpl");
const TRACE_SKILL_TMPL: &str = include_str!("../templates/skills/trace.md.tmpl");
const LEARN_SKILL_TMPL: &str = include_str!("../templates/skills/learn.md.tmpl");
const DEEP_UNDERSTAND_SKILL_TMPL: &str =
    include_str!("../templates/skills/deep-understand.md.tmpl");
const RECONCILE_SKILL_TMPL: &str = include_str!("../templates/skills/reconcile.md.tmpl");
const SHIP_SKILL_TMPL: &str = include_str!("../templates/skills/ship.md.tmpl");
const FRONTEND_DESIGN_SKILL_TMPL: &str =
    include_str!("../templates/skills/frontend-design.md.tmpl");
const REACT_BEST_PRACTICES_SKILL_TMPL: &str =
    include_str!("../templates/skills/react-best-practices.md.tmpl");
const MOBILE_PREVIEW_SKILL_TMPL: &str = include_str!("../templates/skills/mobile-preview.md.tmpl");
const COPYWRITING_SKILL_TMPL: &str = include_str!("../templates/skills/copywriting.md.tmpl");
const N8N_CODE_JS_SKILL_TMPL: &str =
    include_str!("../templates/skills/n8n-code-javascript.md.tmpl");
const N8N_CODE_PY_SKILL_TMPL: &str = include_str!("../templates/skills/n8n-code-python.md.tmpl");
const N8N_EXPR_SKILL_TMPL: &str = include_str!("../templates/skills/n8n-expression-syntax.md.tmpl");
const N8N_WORKFLOW_SKILL_TMPL: &str =
    include_str!("../templates/skills/n8n-workflow-patterns.md.tmpl");
const N8N_VALIDATION_SKILL_TMPL: &str =
    include_str!("../templates/skills/n8n-validation-expert.md.tmpl");
const N8N_NODE_CONFIG_SKILL_TMPL: &str =
    include_str!("../templates/skills/n8n-node-configuration.md.tmpl");
const N8N_MCP_SKILL_TMPL: &str = include_str!("../templates/skills/n8n-mcp-tools-expert.md.tmpl");
const SECURITY_REVIEW_SKILL_TMPL: &str =
    include_str!("../templates/skills/security-review.md.tmpl");
const OBSIDIAN_BASES_SKILL_TMPL: &str = include_str!("../templates/skills/obsidian-bases.md.tmpl");
const OBSIDIAN_CLI_SKILL_TMPL: &str = include_str!("../templates/skills/obsidian-cli.md.tmpl");
const OBSIDIAN_MARKDOWN_SKILL_TMPL: &str =
    include_str!("../templates/skills/obsidian-markdown.md.tmpl");
const JSON_CANVAS_SKILL_TMPL: &str = include_str!("../templates/skills/json-canvas.md.tmpl");
const LATEX_PRESENTATION_SKILL_TMPL: &str =
    include_str!("../templates/skills/latex-presentation.md.tmpl");
const SKILL_CREATOR_SKILL_TMPL: &str = include_str!("../templates/skills/skill-creator.md.tmpl");
const ASK_BETTER_SKILL_TMPL: &str = include_str!("../templates/skills/ask-better.md.tmpl");
const AUTOOPTIMIZE_SKILL_TMPL: &str = include_str!("../templates/skills/autooptimize.md.tmpl");
const CONTEXT_RESUME_SKILL_TMPL: &str = include_str!("../templates/skills/context-resume.md.tmpl");
const CONTEXT_SAVE_SKILL_TMPL: &str = include_str!("../templates/skills/context-save.md.tmpl");
const BROWSER_AUTOMATION_SKILL_TMPL: &str =
    include_str!("../templates/skills/browser-automation.md.tmpl");
const VISUALIZE_SKILL_TMPL: &str = include_str!("../templates/skills/visualize.md.tmpl");
const GETTING_STARTED_REF_TMPL: &str =
    include_str!("../templates/references/getting-started.md.tmpl");
const CODE_QUALITY_REF_TMPL: &str = include_str!("../templates/references/code-quality.md.tmpl");
const SKILL_DESIGN_REF_TMPL: &str = include_str!("../templates/references/skill-design.md.tmpl");
const MEMORY_STARTER_TMPL: &str = include_str!("../templates/memory.md.tmpl");
const CLAUDE_CODE_SETTINGS_TMPL: &str =
    include_str!("../templates/hooks/claude-code-settings.json.tmpl");
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

pub fn render_index_md(
    project_name: &str,
    domains: &[DomainConfig],
    extra_entries: &[(&str, &str)],
) -> Result<String> {
    let mut entries = String::new();
    for domain in domains {
        let dir_name = format!("{}-{}", domain.prefix, domain.name);
        let _ = writeln!(
            entries,
            "| `{dir_name}/RULES.md` | Domain rules for {} |",
            domain.name
        );
    }
    for (path, desc) in extra_entries {
        let _ = writeln!(entries, "| `{path}` | {desc} |");
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

pub fn render_pre_commit(enforce: bool) -> Result<String> {
    let mut env = Environment::new();
    env.add_template("pre-commit.sh", PRE_COMMIT_TMPL)?;
    let tmpl = env.get_template("pre-commit.sh")?;
    Ok(tmpl.render(context! { enforce })?)
}

pub fn render_skills_readme() -> String {
    SKILLS_README_TMPL.to_string()
}

pub fn render_session_start_hook() -> String {
    SESSION_START_HOOK_TMPL.to_string()
}

pub fn render_session_stop_hook(enforce: bool) -> Result<String> {
    let mut env = Environment::new();
    env.add_template("session-stop.sh", SESSION_STOP_HOOK_TMPL)?;
    let tmpl = env.get_template("session-stop.sh")?;
    Ok(tmpl.render(context! { enforce })?)
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

/// Skill registry: render a skill template by name.
/// Returns `None` if the skill name is not recognized.
pub fn render_skill(name: &str) -> Option<String> {
    let content = match name {
        "review" => REVIEW_SKILL_TMPL,
        "commit" => COMMIT_SKILL_TMPL,
        "debug" => DEBUG_SKILL_TMPL,
        "test" => TEST_SKILL_TMPL,
        "plan" => PLAN_SKILL_TMPL,
        "pr" => PR_SKILL_TMPL,
        "explore" => EXPLORE_SKILL_TMPL,
        "release" => RELEASE_SKILL_TMPL,
        "security" => SECURITY_SKILL_TMPL,
        "optimize" => OPTIMIZE_SKILL_TMPL,
        "verify" => VERIFY_SKILL_TMPL,
        "end" => END_SKILL_TMPL,
        "pickup" => PICKUP_SKILL_TMPL,
        "tidy" => TIDY_SKILL_TMPL,
        "research" => RESEARCH_SKILL_TMPL,
        "deploy" => DEPLOY_SKILL_TMPL,
        "status" => STATUS_SKILL_TMPL,
        "get-to-work" => GET_TO_WORK_SKILL_TMPL,
        "trace" => TRACE_SKILL_TMPL,
        "learn" => LEARN_SKILL_TMPL,
        "deep-understand" => DEEP_UNDERSTAND_SKILL_TMPL,
        "reconcile" => RECONCILE_SKILL_TMPL,
        "ship" => SHIP_SKILL_TMPL,
        "frontend-design" => FRONTEND_DESIGN_SKILL_TMPL,
        "react-best-practices" => REACT_BEST_PRACTICES_SKILL_TMPL,
        "mobile-preview" => MOBILE_PREVIEW_SKILL_TMPL,
        "copywriting" => COPYWRITING_SKILL_TMPL,
        "n8n-code-javascript" => N8N_CODE_JS_SKILL_TMPL,
        "n8n-code-python" => N8N_CODE_PY_SKILL_TMPL,
        "n8n-expression-syntax" => N8N_EXPR_SKILL_TMPL,
        "n8n-workflow-patterns" => N8N_WORKFLOW_SKILL_TMPL,
        "n8n-validation-expert" => N8N_VALIDATION_SKILL_TMPL,
        "n8n-node-configuration" => N8N_NODE_CONFIG_SKILL_TMPL,
        "n8n-mcp-tools-expert" => N8N_MCP_SKILL_TMPL,
        "security-review" => SECURITY_REVIEW_SKILL_TMPL,
        "obsidian-bases" => OBSIDIAN_BASES_SKILL_TMPL,
        "obsidian-cli" => OBSIDIAN_CLI_SKILL_TMPL,
        "obsidian-markdown" => OBSIDIAN_MARKDOWN_SKILL_TMPL,
        "json-canvas" => JSON_CANVAS_SKILL_TMPL,
        "latex-presentation" => LATEX_PRESENTATION_SKILL_TMPL,
        "skill-creator" => SKILL_CREATOR_SKILL_TMPL,
        "ask-better" => ASK_BETTER_SKILL_TMPL,
        "autooptimize" => AUTOOPTIMIZE_SKILL_TMPL,
        "context-resume" => CONTEXT_RESUME_SKILL_TMPL,
        "context-save" => CONTEXT_SAVE_SKILL_TMPL,
        "browser-automation" => BROWSER_AUTOMATION_SKILL_TMPL,
        "visualize" => VISUALIZE_SKILL_TMPL,
        _ => return None,
    };
    Some(content.to_string())
}

/// List all registered skill names (core + domain).
#[expect(
    dead_code,
    reason = "Available for validation tests and Phase 6 test coverage"
)]
pub fn registered_skills() -> &'static [&'static str] {
    &[
        "review",
        "commit",
        "debug",
        "test",
        "plan",
        "pr",
        "explore",
        "release",
        "security",
        "optimize",
        "verify",
        "end",
        "pickup",
        "tidy",
        "research",
        "deploy",
        "status",
        "get-to-work",
        "trace",
        "learn",
        "deep-understand",
        "reconcile",
        "ship",
        "frontend-design",
        "react-best-practices",
        "mobile-preview",
        "copywriting",
        "n8n-code-javascript",
        "n8n-code-python",
        "n8n-expression-syntax",
        "n8n-workflow-patterns",
        "n8n-validation-expert",
        "n8n-node-configuration",
        "n8n-mcp-tools-expert",
        "security-review",
        "obsidian-bases",
        "obsidian-cli",
        "obsidian-markdown",
        "json-canvas",
        "latex-presentation",
        "skill-creator",
        "ask-better",
        "autooptimize",
        "context-resume",
        "context-save",
        "browser-automation",
        "visualize",
    ]
}

/// Core skills installed with Standard and Full presets.
pub fn core_skills() -> &'static [&'static str] {
    &[
        "review",
        "commit",
        "debug",
        "test",
        "plan",
        "pr",
        "explore",
        "release",
        "security",
        "optimize",
        "verify",
        "end",
        "pickup",
        "tidy",
        "research",
        "deploy",
        "status",
        "get-to-work",
        "trace",
        "learn",
        "deep-understand",
        "reconcile",
        "ship",
    ]
}

/// Domain skills keyed by domain name.
/// Returns skill names for a given domain.
pub fn domain_skills(domain: &str) -> &'static [&'static str] {
    match domain {
        "frontend" => &[
            "frontend-design",
            "react-best-practices",
            "mobile-preview",
            "copywriting",
        ],
        "n8n" => &[
            "n8n-code-javascript",
            "n8n-code-python",
            "n8n-expression-syntax",
            "n8n-workflow-patterns",
            "n8n-validation-expert",
            "n8n-node-configuration",
            "n8n-mcp-tools-expert",
        ],
        "security" => &["security-review"],
        "obsidian" => &[
            "obsidian-bases",
            "obsidian-cli",
            "obsidian-markdown",
            "json-canvas",
        ],
        "academic" => &["latex-presentation"],
        _ => &[],
    }
}

/// Meta skills installed only with Full preset (opt-in tooling).
pub fn meta_skills() -> &'static [&'static str] {
    &[
        "skill-creator",
        "ask-better",
        "autooptimize",
        "context-resume",
        "context-save",
        "browser-automation",
        "visualize",
    ]
}

/// All domain names that have associated skills.
#[expect(
    dead_code,
    reason = "Available for meta skills and future domain iteration"
)]
pub fn all_domains() -> &'static [&'static str] {
    &["frontend", "n8n", "security", "obsidian", "academic"]
}

pub fn render_code_quality_reference() -> String {
    CODE_QUALITY_REF_TMPL.to_string()
}

pub fn render_skill_design_reference() -> String {
    SKILL_DESIGN_REF_TMPL.to_string()
}

pub fn render_getting_started_reference() -> String {
    GETTING_STARTED_REF_TMPL.to_string()
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

/// Render Claude Code settings.json with hook entries pointing to strata hooks.
pub fn render_claude_code_settings() -> String {
    CLAUDE_CODE_SETTINGS_TMPL.to_string()
}
