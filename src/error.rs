use std::path::PathBuf;

pub type Result<T> = std::result::Result<T, StrataError>;

#[derive(Debug, thiserror::Error, miette::Diagnostic)]
pub enum StrataError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Config error in {path}: {message}")]
    #[diagnostic(code(strata::config))]
    Config { path: PathBuf, message: String },

    #[error("TOML parse error: {0}")]
    TomlParse(#[from] toml::de::Error),

    #[error("TOML serialize error: {0}")]
    TomlSerialize(#[from] toml::ser::Error),

    #[error("Project already initialized at {0}")]
    AlreadyInitialized(PathBuf),

    #[error("Not a strata project (no strata.toml found). Run `strata init` first.")]
    #[diagnostic(help("Run `strata init` to create a new project in this directory"))]
    NotAProject,

    #[error("Structural check failed: {0} issue(s) found")]
    #[diagnostic(code(strata::check))]
    CheckFailed(usize),

    #[error("Lint found {errors} error(s) and {warnings} warning(s)")]
    #[diagnostic(code(strata::lint))]
    LintFailed { errors: usize, warnings: usize },

    #[error("Not a git repository (no .git directory found)")]
    NotAGitRepo,

    #[error("Eval: {0}")]
    Eval(String),

    #[error("Subprocess `{command}` exited with {status}")]
    #[expect(dead_code, reason = "available for backend implementations")]
    Subprocess { command: String, status: i32 },

    #[error("Subprocess `{command}` timed out after {timeout_secs}s")]
    #[expect(dead_code, reason = "available for backend implementations")]
    Timeout { command: String, timeout_secs: u64 },

    #[error("Spec '{0}' already exists")]
    SpecAlreadyExists(String),

    #[error("Spec '{0}' not found")]
    SpecNotFound(String),

    #[error("No active session. Start one with `strata session start` or pass --session.")]
    #[diagnostic(help("Run `strata session start` to begin a new session"))]
    NoActiveSession,

    #[error("Invalid ignore pattern '{pattern}': {reason}")]
    InvalidPattern { pattern: String, reason: String },

    #[error("Walk error: {0}")]
    WalkError(String),

    #[error("Template error: {0}")]
    Template(String),

    #[error("{0}")]
    General(String),
}

impl From<serde_json::Error> for StrataError {
    fn from(e: serde_json::Error) -> Self {
        StrataError::General(format!("JSON error: {e}"))
    }
}

impl From<minijinja::Error> for StrataError {
    fn from(e: minijinja::Error) -> Self {
        StrataError::Template(e.to_string())
    }
}

impl From<dialoguer::Error> for StrataError {
    fn from(e: dialoguer::Error) -> Self {
        StrataError::General(format!("Prompt error: {e}"))
    }
}

impl From<notify::Error> for StrataError {
    fn from(e: notify::Error) -> Self {
        StrataError::General(format!("Watch error: {e}"))
    }
}
