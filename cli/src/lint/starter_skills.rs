use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct StarterSkills;

impl LintRule for StarterSkills {
    fn name(&self) -> &'static str {
        "starter-skills"
    }

    fn severity(&self) -> Severity {
        Severity::Info
    }

    fn check(&self, scan: &ProjectScan, root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        // Only fire if hooks are configured (implies standard+ preset) but no skills exist
        let has_hooks = !config.hooks.session_start.is_empty()
            || !config.hooks.session_stop.is_empty()
            || !config.hooks.pre_compact.is_empty();

        if !has_hooks {
            return Vec::new();
        }

        let skills_dir = root.join("skills");
        if !skills_dir.is_dir() || scan.skills.is_empty() {
            return vec![Diagnostic::new(
                self.name(),
                self.severity(),
                "Hooks are configured but no skills are installed. Consider adding starter skills with `strata init --preset standard` or `strata generate --skills`.",
                "skills/",
            )];
        }

        Vec::new()
    }
}
