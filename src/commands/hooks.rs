use crate::error::{Result, StrataError};
use crate::templates;
use crate::ui;
use std::fs;
use std::path::Path;

pub fn run(path: &Path) -> Result<()> {
    let root = crate::config::StrataConfig::find_root(path)?;
    let git_dir = root.join(".git");

    if !git_dir.exists() {
        return Err(StrataError::NotAGitRepo);
    }

    let hooks_dir = git_dir.join("hooks");
    fs::create_dir_all(&hooks_dir)?;

    let hook_path = hooks_dir.join("pre-commit");
    let content = templates::render_pre_commit();

    fs::write(&hook_path, content)?;

    // Make executable on Unix
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&hook_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&hook_path, perms)?;
    }

    ui::success("Installed pre-commit hook at .git/hooks/pre-commit");
    ui::info("The hook will run `strata check` before each commit");

    Ok(())
}
