use clap::{Parser, Subcommand};

#[derive(Debug, Clone, Copy, clap::ValueEnum)]
pub enum OutputFormat {
    Text,
    Json,
}

impl std::fmt::Display for OutputFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            OutputFormat::Text => write!(f, "text"),
            OutputFormat::Json => write!(f, "json"),
        }
    }
}

#[derive(Parser)]
#[command(
    name = "strata",
    about = "Scaffold and validate AI-navigable project structures",
    version,
    propagate_version = true
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand)]
pub enum Command {
    /// Initialize a new strata project with the five-layer architecture
    Init {
        /// Project name (skip interactive prompt)
        #[arg(long)]
        name: Option<String>,

        /// Comma-separated domain names (skip interactive prompt)
        #[arg(long, value_delimiter = ',')]
        domains: Option<Vec<String>>,

        /// Directory to initialize in (defaults to current directory)
        #[arg(long, default_value = ".")]
        path: String,
    },

    /// Check structural integrity (pass/fail)
    Check {
        /// Project directory (defaults to current directory)
        #[arg(default_value = ".")]
        path: String,
    },

    /// Run quality diagnostics with severity levels
    Lint {
        /// Project directory (defaults to current directory)
        #[arg(default_value = ".")]
        path: String,

        /// Only run a specific rule
        #[arg(long)]
        rule: Option<String>,

        /// Suppress output, only set exit code
        #[arg(long)]
        quiet: bool,

        /// Output format (text or json)
        #[arg(long, default_value_t = OutputFormat::Text)]
        format: OutputFormat,
    },

    /// Auto-repair common structural issues
    Fix {
        /// Project directory (defaults to current directory)
        #[arg(default_value = ".")]
        path: String,

        /// Show what would be fixed without making changes
        #[arg(long)]
        dry_run: bool,
    },

    /// Install git pre-commit hooks for drift prevention
    InstallHooks {
        /// Project directory (defaults to current directory)
        #[arg(default_value = ".")]
        path: String,
    },
}
