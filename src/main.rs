mod cli;
mod commands;
mod config;
mod error;
mod lint;
mod scanner;
mod targets;
mod templates;
mod ui;

use clap::Parser;
use cli::{Cli, Command, SessionAction, SpecAction};
use std::path::Path;
use std::process;

fn main() {
    let cli = Cli::parse();

    let result = match cli.command {
        Command::Init {
            name,
            domains,
            path,
            preset,
        } => commands::init::run(Path::new(&path), name, domains, preset),
        Command::Check { path } => commands::check::run(Path::new(&path)),
        Command::Lint {
            path,
            rule,
            quiet,
            format,
        } => commands::lint::run(Path::new(&path), rule.as_deref(), quiet, format),
        Command::Fix {
            path,
            dry_run,
            index,
        } => commands::fix::run(Path::new(&path), dry_run, index),
        Command::Generate {
            path,
            target,
            skills,
        } => commands::generate::run(Path::new(&path), target, skills),
        Command::InstallHooks { path } => commands::hooks::run(Path::new(&path)),
        Command::Spec { action } => match action {
            SpecAction::New { name, session } => {
                commands::spec::run_new(Path::new("."), &name, session.as_deref())
            }
            SpecAction::List { status } => {
                commands::spec::run_list(Path::new("."), status.as_deref())
            }
            SpecAction::Status { name } => {
                commands::spec::run_status(Path::new("."), name.as_deref())
            }
            SpecAction::Complete { name } => commands::spec::run_complete(Path::new("."), &name),
        },
        Command::Session { action } => match action {
            SessionAction::Start { name } => {
                commands::session::run_start(Path::new("."), name.as_deref())
            }
            SessionAction::List { limit } => commands::session::run_list(Path::new("."), limit),
            SessionAction::Save { session } => {
                commands::session::run_save(Path::new("."), session.as_deref())
            }
        },
    };

    if let Err(e) = result {
        ui::error(&e.to_string());
        process::exit(1);
    }
}
