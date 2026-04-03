use crate::cli::Cli;
use crate::error::Result;
use clap::CommandFactory;
use clap_complete::Shell;

// Consistent return type with all other command runners; no fallible operations here.
#[expect(
    clippy::unnecessary_wraps,
    reason = "all command runners return Result for uniform dispatch in main"
)]
pub fn run(shell: Shell) -> Result<()> {
    let mut cmd = Cli::command();
    clap_complete::generate(shell, &mut cmd, "strata", &mut std::io::stdout());
    Ok(())
}
