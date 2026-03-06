use crate::config::AgentTarget;
use std::path::PathBuf;

const CLAUDE_TMPL: &str = include_str!("../templates/targets/claude.md.tmpl");
const CURSOR_TMPL: &str = include_str!("../templates/targets/cursorrules.tmpl");
const COPILOT_TMPL: &str = include_str!("../templates/targets/copilot.md.tmpl");

/// Describes where and how to write agent-specific output.
pub struct TargetOutput {
    /// Relative path for the output file from project root.
    pub path: PathBuf,
    /// Template for wrapping context content.
    pub template: &'static str,
}

/// Resolve an agent target to its output configuration.
pub fn resolve_target(target: AgentTarget) -> Option<TargetOutput> {
    match target {
        AgentTarget::Generic => None, // generic only writes .strata/context.md (default behavior)
        AgentTarget::Claude => Some(TargetOutput {
            path: PathBuf::from("CLAUDE.md"),
            template: CLAUDE_TMPL,
        }),
        AgentTarget::Cursor => Some(TargetOutput {
            path: PathBuf::from(".cursorrules"),
            template: CURSOR_TMPL,
        }),
        AgentTarget::Copilot => Some(TargetOutput {
            path: PathBuf::from(".github/copilot-instructions.md"),
            template: COPILOT_TMPL,
        }),
    }
}

/// Render a target template with project context.
pub fn render_target(project_name: &str, context: &str, target: &TargetOutput) -> String {
    target
        .template
        .replace("{{PROJECT_NAME}}", project_name)
        .replace("{{CONTEXT}}", context)
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
        let rendered = render_target("my-project", "Some context here", &t);
        assert!(rendered.contains("my-project"));
        assert!(rendered.contains("Some context here"));
    }
}
