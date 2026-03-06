use crate::config::{AgentTarget, Preset};
use crate::eval::OutputFormat as EvalOutputFormat;
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

        /// Preset tier: minimal (structure only), standard (+hooks, skills, memory), full (+specs, sessions)
        #[arg(long, default_value_t = Preset::Minimal)]
        preset: Preset,
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

        /// Regenerate INDEX.md from project files
        #[arg(long)]
        index: bool,
    },

    /// Generate context files for AI agent consumption
    Generate {
        /// Project directory (defaults to current directory)
        #[arg(default_value = ".")]
        path: String,

        /// Target agent format
        #[arg(long)]
        target: Option<AgentTarget>,

        /// Install starter skill templates
        #[arg(long)]
        skills: bool,
    },

    /// Install git pre-commit hooks for drift prevention
    InstallHooks {
        /// Project directory (defaults to current directory)
        #[arg(default_value = ".")]
        path: String,
    },

    /// Manage implementation specs
    Spec {
        #[command(subcommand)]
        action: SpecAction,
    },

    /// Manage agent sessions
    Session {
        #[command(subcommand)]
        action: SessionAction,
    },

    /// Skill evaluation and optimization
    Skill {
        #[command(subcommand)]
        action: SkillAction,
    },
}

#[derive(Subcommand)]
pub enum SpecAction {
    /// Create a new spec from template
    New {
        /// Spec name (used as filename)
        name: String,

        /// Session ID to assign ownership
        #[arg(long)]
        session: Option<String>,
    },

    /// List all specs
    List {
        /// Filter by status (in-progress, complete, abandoned)
        #[arg(long)]
        status: Option<String>,
    },

    /// Show current step of active specs
    Status {
        /// Spec name (shows all in-progress if omitted)
        name: Option<String>,
    },

    /// Mark a spec as complete
    Complete {
        /// Spec name
        name: String,
    },
}

#[derive(Subcommand)]
pub enum SkillAction {
    /// Test whether a skill triggers correctly against an eval set
    Eval {
        /// Skill name (directory under skills/)
        name: String,

        /// Path to eval set JSON file
        #[arg(long)]
        eval_set: String,

        /// Number of parallel workers
        #[arg(long)]
        workers: Option<u32>,

        /// Timeout per query in seconds
        #[arg(long)]
        timeout: Option<u64>,

        /// Number of runs per query
        #[arg(long)]
        runs_per_query: Option<u32>,

        /// Minimum trigger rate for positive queries
        #[arg(long)]
        trigger_threshold: Option<f64>,

        /// Output format
        #[arg(long, default_value_t = EvalOutputFormat::Text)]
        format: EvalOutputFormat,

        /// Override skill description (instead of reading from SKILL.md)
        #[arg(long)]
        description: Option<String>,
    },

    /// Iteratively optimize a skill's description for better triggering
    Optimize {
        /// Skill name (directory under skills/)
        name: String,

        /// Path to eval set JSON file
        #[arg(long)]
        eval_set: String,

        /// Maximum optimization iterations
        #[arg(long)]
        max_iterations: Option<u32>,

        /// Fraction of eval set held out for testing
        #[arg(long)]
        holdout: Option<f64>,

        /// Runs per query (higher = more stable signal)
        #[arg(long)]
        runs_per_query: Option<u32>,

        /// Generate HTML report
        #[arg(long)]
        report: bool,

        /// Apply best description to SKILL.md
        #[arg(long)]
        apply: bool,
    },

    /// Manage eval sets
    EvalSet {
        #[command(subcommand)]
        action: EvalSetAction,
    },
}

#[derive(Subcommand)]
pub enum EvalSetAction {
    /// Create a starter eval set with placeholder queries
    Init {
        /// Skill name to create eval set for
        name: String,

        /// Output path (defaults to skills/<name>/eval-set.json)
        #[arg(long)]
        output: Option<String>,
    },
}

#[derive(Subcommand)]
pub enum SessionAction {
    /// Start a new session
    Start {
        /// Descriptive session name
        #[arg(long)]
        name: Option<String>,
    },

    /// List recent sessions
    List {
        /// Max sessions to show
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },

    /// Save context for the current session
    Save {
        /// Session ID (uses current session if omitted)
        #[arg(long)]
        session: Option<String>,
    },
}
