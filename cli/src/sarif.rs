use crate::lint::{Diagnostic, Severity};
use serde_sarif::sarif::{
    ArtifactLocation, Location, Message, PhysicalLocation, Region, Result as SarifResult,
    ResultLevel, Run, Sarif, Tool, ToolComponent,
};

fn build_location(d: &Diagnostic) -> Location {
    let artifact = ArtifactLocation::builder().uri(&d.location).build();

    let physical = match (d.line, d.column, d.end_line, d.end_column) {
        (Some(line), Some(col), Some(end_line), Some(end_col)) => {
            let region = Region::builder()
                .start_line(i64::from(line))
                .start_column(i64::from(col))
                .end_line(i64::from(end_line))
                .end_column(i64::from(end_col));
            PhysicalLocation::builder()
                .artifact_location(artifact)
                .region(region.build())
                .build()
        }
        (Some(line), Some(col), _, _) => {
            let region = Region::builder()
                .start_line(i64::from(line))
                .start_column(i64::from(col));
            PhysicalLocation::builder()
                .artifact_location(artifact)
                .region(region.build())
                .build()
        }
        (Some(line), None, _, _) => {
            let region = Region::builder().start_line(i64::from(line));
            PhysicalLocation::builder()
                .artifact_location(artifact)
                .region(region.build())
                .build()
        }
        _ => PhysicalLocation::builder()
            .artifact_location(artifact)
            .build(),
    };

    Location::builder().physical_location(physical).build()
}

pub fn diagnostics_to_sarif(diagnostics: &[Diagnostic]) -> String {
    let results: Vec<SarifResult> = diagnostics
        .iter()
        .map(|d| {
            let level = match d.severity {
                Severity::Error => ResultLevel::Error,
                Severity::Warning => ResultLevel::Warning,
                Severity::Info => ResultLevel::Note,
            };

            SarifResult::builder()
                .rule_id(&d.rule)
                .level(level)
                .message(Message::builder().text(&d.message).build())
                .locations(vec![build_location(d)])
                .build()
        })
        .collect();

    let tool = Tool::builder()
        .driver(
            ToolComponent::builder()
                .name("strata")
                .version(env!("CARGO_PKG_VERSION"))
                .information_uri("https://github.com/onblueroses/strata")
                .build(),
        )
        .build();

    let run = Run::builder().tool(tool).results(results).build();

    let sarif = Sarif::builder().version("2.1.0").runs(vec![run]).build();

    serde_json::to_string_pretty(&sarif).unwrap_or_else(|_| "{}".to_string())
}
