use crate::config::{CustomRuleSpec, StrataConfig};
use crate::error::{Result, StrataError};
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use ignore::overrides::OverrideBuilder;
use std::path::{Path, PathBuf};

pub struct CustomRule {
    spec: CustomRuleSpec,
}

impl CustomRule {
    pub fn new(spec: CustomRuleSpec) -> Self {
        Self { spec }
    }
}

fn severity_from_str(s: &str) -> Severity {
    match s {
        "error" => Severity::Error,
        "info" => Severity::Info,
        _ => Severity::Warning,
    }
}

/// Returns references to files that match the given glob pattern.
fn files_matching_glob<'a>(
    files: &'a [PathBuf],
    root: &Path,
    pattern: &str,
) -> Result<Vec<&'a PathBuf>> {
    let mut ob = OverrideBuilder::new(root);
    ob.add(pattern).map_err(|e| StrataError::InvalidPattern {
        pattern: pattern.to_string(),
        reason: e.to_string(),
    })?;
    let overrides = ob.build().map_err(|e| StrataError::InvalidPattern {
        pattern: pattern.to_string(),
        reason: e.to_string(),
    })?;

    Ok(files
        .iter()
        .filter(|f| overrides.matched(root.join(f), false).is_whitelist())
        .collect())
}

impl std::fmt::Debug for CustomRule {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("CustomRule")
            .field("name", &self.spec.name)
            .finish()
    }
}

impl LintRule for CustomRule {
    fn name(&self) -> &str {
        &self.spec.name
    }

    fn severity(&self) -> Severity {
        severity_from_str(&self.spec.severity)
    }

    fn check(&self, scan: &ProjectScan, root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        match self.run_check(scan, root) {
            Ok(diags) => diags,
            Err(e) => vec![Diagnostic::new(
                self.name(),
                Severity::Warning,
                format!("rule evaluation error: {e}"),
                "(rule configuration)",
            )],
        }
    }
}

impl CustomRule {
    fn run_check(&self, scan: &ProjectScan, root: &Path) -> Result<Vec<Diagnostic>> {
        let sev = self.severity();
        let mut diags = Vec::new();

        match self.spec.check.as_str() {
            "file_exists" => {
                let matches = files_matching_glob(&scan.files, root, &self.spec.glob)?;
                if matches.is_empty() {
                    diags.push(Diagnostic::new(
                        &self.spec.name,
                        sev,
                        &self.spec.message,
                        "(project root)",
                    ));
                }
            }
            "file_missing" => {
                for file in files_matching_glob(&scan.files, root, &self.spec.glob)? {
                    let file_str = file.to_string_lossy().replace('\\', "/");
                    let msg = self.spec.message.replace("{file}", &file_str);
                    diags.push(Diagnostic::new(&self.spec.name, sev, msg, file_str));
                }
            }
            "content_contains" => {
                let pattern = self.spec.pattern.as_deref().unwrap_or("");
                for file in files_matching_glob(&scan.files, root, &self.spec.glob)? {
                    let abs = root.join(file);
                    let Ok(content) = std::fs::read_to_string(&abs) else {
                        continue;
                    };
                    let found = content.contains(pattern);
                    let should_flag = if self.spec.negate { !found } else { found };
                    if should_flag {
                        let file_str = file.to_string_lossy().replace('\\', "/");
                        let msg = self.spec.message.replace("{file}", &file_str);
                        diags.push(Diagnostic::new(&self.spec.name, sev, msg, file_str));
                    }
                }
            }
            "frontmatter_key" => {
                // scan.descriptions tracks the `description` frontmatter key (or first heading).
                // Other key names require re-parsing and are not yet supported.
                let key = self.spec.key.as_deref().unwrap_or("description");
                if key != "description" {
                    diags.push(Diagnostic::new(
                        &self.spec.name,
                        Severity::Warning,
                        format!("frontmatter_key check only supports key=\"description\"; \"{key}\" is not supported"),
                        "(rule configuration)",
                    ));
                    return Ok(diags);
                }
                for file in files_matching_glob(&scan.files, root, &self.spec.glob)? {
                    let has_desc = scan.descriptions.get(file).is_some_and(Option::is_some);
                    if !has_desc {
                        let file_str = file.to_string_lossy().replace('\\', "/");
                        let msg = self.spec.message.replace("{file}", &file_str);
                        diags.push(Diagnostic::new(&self.spec.name, sev, msg, file_str));
                    }
                }
            }
            unknown => {
                diags.push(Diagnostic::new(
                    &self.spec.name,
                    Severity::Warning,
                    format!("unknown check type '{unknown}'"),
                    "(rule configuration)",
                ));
            }
        }

        Ok(diags)
    }
}
