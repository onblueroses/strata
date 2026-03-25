use crate::config::AgentTarget;
use crate::error::Result;
use crate::scanner::project_type::{Language, ProjectType};
use minijinja::{Environment, context};
use std::path::PathBuf;

const CLAUDE_CODE_TMPL: &str = include_str!("../templates/targets/claude-code.md.tmpl");
const OPENCODE_TMPL: &str = include_str!("../templates/targets/opencode.md.tmpl");
const PI_TMPL: &str = include_str!("../templates/targets/pi.md.tmpl");

/// How a target agent handles hooks.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HookMechanism {
    /// Hooks defined in `.claude/settings.json`.
    SettingsJson,
    /// JS/TS plugin system.
    PluginSystem,
    /// TS extensions.
    Extensions,
}

/// Capabilities and paths for a specific agent target.
#[expect(
    dead_code,
    reason = "skill_dir, config_dir, hook_mechanism used in Phase 2 (enforcement hooks)"
)]
pub struct TargetCapabilities {
    /// Where the agent reads project instructions.
    pub instruction_file: PathBuf,
    /// Where skills are stored for this agent.
    pub skill_dir: PathBuf,
    /// Agent-specific config directory.
    pub config_dir: PathBuf,
    /// How this agent handles hooks.
    pub hook_mechanism: HookMechanism,
}

/// Describes where and how to write agent-specific output.
pub struct TargetOutput {
    /// Relative path for the output file from project root.
    pub path: PathBuf,
    /// Template name for rendering.
    pub template_name: &'static str,
}

fn build_target_env() -> Result<Environment<'static>> {
    let mut env = Environment::new();
    env.add_template("target/claude-code.md", CLAUDE_CODE_TMPL)?;
    env.add_template("target/opencode.md", OPENCODE_TMPL)?;
    env.add_template("target/pi.md", PI_TMPL)?;
    Ok(env)
}

/// Get the capabilities for a given agent target.
pub fn capabilities(target: AgentTarget) -> TargetCapabilities {
    match target {
        AgentTarget::ClaudeCode => TargetCapabilities {
            instruction_file: PathBuf::from("CLAUDE.md"),
            skill_dir: PathBuf::from("skills"),
            config_dir: PathBuf::from(".claude"),
            hook_mechanism: HookMechanism::SettingsJson,
        },
        AgentTarget::OpenCode => TargetCapabilities {
            instruction_file: PathBuf::from("AGENTS.md"),
            skill_dir: PathBuf::from("skills"),
            config_dir: PathBuf::from(".opencode"),
            hook_mechanism: HookMechanism::PluginSystem,
        },
        AgentTarget::Pi => TargetCapabilities {
            instruction_file: PathBuf::from("AGENTS.md"),
            skill_dir: PathBuf::from("skills"),
            config_dir: PathBuf::from(".pi"),
            hook_mechanism: HookMechanism::Extensions,
        },
    }
}

/// Resolve an agent target to its output configuration.
pub fn resolve_target(target: AgentTarget) -> TargetOutput {
    let caps = capabilities(target);
    let template_name = match target {
        AgentTarget::ClaudeCode => "target/claude-code.md",
        AgentTarget::OpenCode => "target/opencode.md",
        AgentTarget::Pi => "target/pi.md",
    };
    TargetOutput {
        path: caps.instruction_file,
        template_name,
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
    fn claude_code_target_path() {
        let t = resolve_target(AgentTarget::ClaudeCode);
        assert_eq!(t.path, PathBuf::from("CLAUDE.md"));
    }

    #[test]
    fn opencode_target_path() {
        let t = resolve_target(AgentTarget::OpenCode);
        assert_eq!(t.path, PathBuf::from("AGENTS.md"));
    }

    #[test]
    fn pi_target_path() {
        let t = resolve_target(AgentTarget::Pi);
        assert_eq!(t.path, PathBuf::from("AGENTS.md"));
    }

    #[test]
    fn claude_code_capabilities() {
        let caps = capabilities(AgentTarget::ClaudeCode);
        assert_eq!(caps.config_dir, PathBuf::from(".claude"));
        assert_eq!(caps.hook_mechanism, HookMechanism::SettingsJson);
    }

    #[test]
    fn opencode_capabilities() {
        let caps = capabilities(AgentTarget::OpenCode);
        assert_eq!(caps.config_dir, PathBuf::from(".opencode"));
        assert_eq!(caps.hook_mechanism, HookMechanism::PluginSystem);
    }

    #[test]
    fn pi_capabilities() {
        let caps = capabilities(AgentTarget::Pi);
        assert_eq!(caps.config_dir, PathBuf::from(".pi"));
        assert_eq!(caps.hook_mechanism, HookMechanism::Extensions);
    }

    #[test]
    fn render_replaces_placeholders() {
        let t = resolve_target(AgentTarget::ClaudeCode);
        let pt = ProjectType::unknown();
        let rendered = render_target("my-project", "Some context here", &t, &pt).unwrap();
        assert!(rendered.contains("my-project"));
        assert!(rendered.contains("Some context here"));
    }

    #[test]
    fn render_includes_project_type() {
        let t = resolve_target(AgentTarget::ClaudeCode);
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
        let t = resolve_target(AgentTarget::ClaudeCode);
        let pt = ProjectType::unknown();
        let rendered = render_target("test", "ctx", &t, &pt).unwrap();
        assert!(!rendered.contains("Project Type"));
    }
}
