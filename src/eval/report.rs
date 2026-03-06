use crate::error::{Result, StrataError};
use crate::eval::OptimizeResult;
use std::path::Path;

const REPORT_TEMPLATE: &str = include_str!("../../templates/eval-report.html.tmpl");

/// Generate an HTML report from optimization results.
pub fn generate_report(result: &OptimizeResult, output_path: &Path) -> Result<()> {
    let data_json = serde_json::to_string(result)
        .map_err(|e| StrataError::Eval(format!("Failed to serialize report data: {e}")))?;

    let html = REPORT_TEMPLATE.replace("{{DATA_JSON}}", &data_json);

    if let Some(parent) = output_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    std::fs::write(output_path, html)?;
    Ok(())
}
