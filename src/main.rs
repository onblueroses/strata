mod cli;
mod commands;
mod config;
mod error;
mod eval;
mod git;
mod lint;
mod sarif;
mod scanner;
mod state;
mod targets;
mod templates;
mod ui;
mod util;

use clap::Parser;
use cli::{Cli, Command, EvalSetAction, SessionAction, SkillAction, SpecAction};
use std::path::Path;
use std::process;

fn main() {
    miette::set_hook(Box::new(|_| {
        Box::new(
            miette::MietteHandlerOpts::new()
                .terminal_links(true)
                .context_lines(2)
                .build(),
        )
    }))
    .ok();

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
        Command::Diff { path, target } => commands::diff::run(Path::new(&path), target),
        Command::Generate {
            path,
            target,
            skills,
        } => commands::generate::run(Path::new(&path), target, skills),
        Command::Update { path, target } => commands::update::run(Path::new(&path), target),
        Command::Watch {
            path,
            target,
            debounce,
        } => commands::watch::run(Path::new(&path), target, debounce),
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
        Command::Skill { action } => match action {
            SkillAction::Eval {
                name,
                eval_set,
                workers,
                timeout,
                runs_per_query,
                trigger_threshold,
                format,
                description,
            } => commands::skill::run_skill_eval(
                Path::new("."),
                &name,
                &eval_set,
                workers,
                timeout,
                runs_per_query,
                trigger_threshold,
                format,
                description.as_deref(),
            ),
            SkillAction::Optimize {
                name,
                eval_set,
                max_iterations,
                holdout,
                runs_per_query,
                report,
                apply,
            } => commands::skill::run_skill_optimize(
                Path::new("."),
                &name,
                &eval_set,
                max_iterations,
                holdout,
                runs_per_query,
                report,
                apply,
            ),
            SkillAction::EvalSet { action } => match action {
                EvalSetAction::Init { name, output } => {
                    commands::skill::run_eval_set_init(Path::new("."), &name, output.as_deref())
                }
            },
        },
    };

    if let Err(e) = result {
        // Use miette rendering for diagnostic-rich errors, fall back to ui::error
        let report: miette::Report = e.into();
        eprintln!("{report:?}");
        process::exit(1);
    }
}
