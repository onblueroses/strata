use std::path::PathBuf;

pub type Result<T> = std::result::Result<T, StrataError>;

#[derive(Debug, thiserror::Error)]
pub enum StrataError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Config error in {path}: {message}")]
    Config { path: PathBuf, message: String },

    #[error("TOML parse error: {0}")]
    TomlParse(#[from] toml::de::Error),

    #[error("TOML serialize error: {0}")]
    TomlSerialize(#[from] toml::ser::Error),

    #[error("Project already initialized at {0}")]
    AlreadyInitialized(PathBuf),

    #[error("Not a strata project (no strata.toml found). Run `strata init` first.")]
    NotAProject,

    #[error("Structural check failed: {0} issue(s) found")]
    CheckFailed(usize),

    #[error("Lint found {errors} error(s) and {warnings} warning(s)")]
    LintFailed { errors: usize, warnings: usize },

    #[error("Not a git repository (no .git directory found)")]
    NotAGitRepo,

    #[error("{0}")]
    General(String),
}

impl From<dialoguer::Error> for StrataError {
    fn from(e: dialoguer::Error) -> Self {
        StrataError::General(format!("Prompt error: {e}"))
    }
}

impl From<walkdir::Error> for StrataError {
    fn from(e: walkdir::Error) -> Self {
        match e.into_io_error() {
            Some(io_err) => StrataError::Io(io_err),
            None => StrataError::General("walkdir error".to_string()),
        }
    }
}
