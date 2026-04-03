use crate::config::StrataConfig;
use crate::error::{Result, StrataError};
use crate::templates;
use crate::ui;
use std::fs;
use std::path::Path;

pub fn run(path: &Path) -> Result<()> {
    let root = StrataConfig::find_root(path)?;
    let git_dir = root.join(".git");

    if !git_dir.exists() {
        return Err(StrataError::NotAGitRepo);
    }

    // Load config to check enforcement setting
    let (config, _) = StrataConfig::load(&root.join("strata.toml"))?;

    let hooks_dir = git_dir.join("hooks");
    fs::create_dir_all(&hooks_dir)?;

    let hook_path = hooks_dir.join("pre-commit");
    let content = templates::render_pre_commit(config.hooks.enforce)?;

    fs::write(&hook_path, content)?;

    // Make executable on Unix
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&hook_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&hook_path, perms)?;
    }

    let mode = if config.hooks.enforce {
        "enforcement enabled"
    } else {
        "warnings only"
    };
    ui::success(&format!(
        "Installed pre-commit hook at .git/hooks/pre-commit ({mode})"
    ));
    ui::info("The hook will run `strata check` and verify review status before each commit");

    Ok(())
}
