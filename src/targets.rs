use crate::config::AgentTarget;
use crate::error::Result;
use crate::scanner::project_type::{Language, ProjectType};
use minijinja::{Environment, context};
use std::path::PathBuf;

const CLAUDE_TMPL: &str = include_str!("../templates/targets/claude.md.tmpl");
const CURSOR_TMPL: &str = include_str!("../templates/targets/cursorrules.tmpl");
const COPILOT_TMPL: &str = include_str!("../templates/targets/copilot.md.tmpl");

/// Describes where and how to write agent-specific output.
pub struct TargetOutput {
    /// Relative path for the output file from project root.
    pub path: PathBuf,
    /// Template name for rendering.
    pub template_name: &'static str,
}

fn build_target_env() -> Result<Environment<'static>> {
    let mut env = Environment::new();
    env.add_template("target/claude.md", CLAUDE_TMPL)?;
    env.add_template("target/cursorrules", CURSOR_TMPL)?;
    env.add_template("target/copilot.md", COPILOT_TMPL)?;
    Ok(env)
}

/// Resolve an agent target to its output configuration.
pub fn resolve_target(target: AgentTarget) -> Option<TargetOutput> {
    match target {
        AgentTarget::Generic => None,
        AgentTarget::Claude => Some(TargetOutput {
            path: PathBuf::from("CLAUDE.md"),
            template_name: "target/claude.md",
        }),
        AgentTarget::Cursor => Some(TargetOutput {
            path: PathBuf::from(".cursorrules"),
            template_name: "target/cursorrules",
        }),
        AgentTarget::Copilot => Some(TargetOutput {
            path: PathBuf::from(".github/copilot-instructions.md"),
            template_name: "target/copilot.md",
        }),
    }
}

/// Build a serializable project type context for templates.
fn project_type_context(pt: &ProjectType) -> Option<minijinja::Value> {
    if pt.language == Language::Unknown {
        return None;
    }
    let frameworks = if pt.frameworks.is_empty() {
        String::new()
    } else {
        pt.frameworks
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(", ")
    };
    Some(context! {
        language => pt.language.to_string(),
        build_tool => pt.build_tool.as_deref(),
        frameworks => if frameworks.is_empty() { None } else { Some(frameworks) },
    })
}

/// Render a target template with project context.
pub fn render_target(
    project_name: &str,
    context_text: &str,
    target: &TargetOutput,
    project_type: &ProjectType,
) -> Result<String> {
    let env = build_target_env()?;
    let tmpl = env.get_template(target.template_name)?;
    let pt_ctx = project_type_context(project_type);
    Ok(tmpl.render(context! {
        project_name,
        context => context_text,
        project_type => pt_ctx,
    })?)
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    #[test]
    fn generic_returns_none() {
        assert!(resolve_target(AgentTarget::Generic).is_none());
    }

    #[test]
    fn claude_target_path() {
        let t = resolve_target(AgentTarget::Claude).unwrap();
        assert_eq!(t.path, PathBuf::from("CLAUDE.md"));
    }

    #[test]
    fn cursor_target_path() {
        let t = resolve_target(AgentTarget::Cursor).unwrap();
        assert_eq!(t.path, PathBuf::from(".cursorrules"));
    }

    #[test]
    fn copilot_target_path() {
        let t = resolve_target(AgentTarget::Copilot).unwrap();
        assert_eq!(t.path, PathBuf::from(".github/copilot-instructions.md"));
    }

    #[test]
    fn render_replaces_placeholders() {
        let t = resolve_target(AgentTarget::Claude).unwrap();
        let pt = ProjectType::unknown();
        let rendered = render_target("my-project", "Some context here", &t, &pt).unwrap();
        assert!(rendered.contains("my-project"));
        assert!(rendered.contains("Some context here"));
    }

    #[test]
    fn render_includes_project_type() {
        let t = resolve_target(AgentTarget::Claude).unwrap();
        let pt = ProjectType {
            language: Language::Rust,
            frameworks: vec![],
            build_tool: Some("Cargo".to_string()),
        };
        let rendered = render_target("test", "ctx", &t, &pt).unwrap();
        assert!(rendered.contains("Rust"));
        assert!(rendered.contains("Cargo"));
    }

    #[test]
    fn render_omits_project_type_when_unknown() {
        let t = resolve_target(AgentTarget::Claude).unwrap();
        let pt = ProjectType::unknown();
        let rendered = render_target("test", "ctx", &t, &pt).unwrap();
        assert!(!rendered.contains("Project Type"));
    }
}
