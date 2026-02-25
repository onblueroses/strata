mod cli;
mod commands;
mod config;
mod error;
mod lint;
mod scanner;
mod templates;
mod ui;

use clap::Parser;
use cli::{Cli, Command};
use std::path::Path;
use std::process;

fn main() {
    let cli = Cli::parse();

    let result = match cli.command {
        Command::Init {
            name,
            domains,
            path,
        } => commands::init::run(Path::new(&path), name, domains),
        Command::Check { path } => commands::check::run(Path::new(&path)),
        Command::Lint {
            path,
            rule,
            quiet,
            format,
        } => commands::lint::run(Path::new(&path), rule.as_deref(), quiet, &format),
        Command::Fix { path, dry_run } => commands::fix::run(Path::new(&path), dry_run),
        Command::InstallHooks { path } => commands::hooks::run(Path::new(&path)),
    };

    if let Err(e) = result {
        ui::error(&e.to_string());
        process::exit(1);
    }
}
