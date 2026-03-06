pub mod backend;
pub mod optimizer;
pub mod report;
pub mod runner;

use crate::error::{Result, StrataError};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::time::Duration;

/// Output format for eval results.
#[derive(Debug, Clone, Copy, Default, clap::ValueEnum)]
pub enum OutputFormat {
    #[default]
    Text,
    Json,
}

impl std::fmt::Display for OutputFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Text => write!(f, "text"),
            Self::Json => write!(f, "json"),
        }
    }
}

/// A single query in an eval set.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalQuery {
    /// The user prompt to test.
    pub query: String,
    /// Whether this query SHOULD trigger the skill.
    pub should_trigger: bool,
    /// Optional category for grouping in reports.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub category: Option<String>,
}

/// Result of testing a single query once.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerTestResult {
    /// Whether the skill was triggered.
    pub triggered: bool,
    /// Which tool was called (if any).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_called: Option<String>,
    /// The skill name extracted from the tool call (if any).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub skill_invoked: Option<String>,
    /// How long the test took.
    pub duration: Duration,
    /// Whether the test timed out.
    pub timed_out: bool,
    /// Raw error message if the test failed to execute.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

/// Aggregated result for one query across multiple runs.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryResult {
    pub query: EvalQuery,
    /// How many times the skill triggered out of total runs.
    pub trigger_count: u32,
    /// Total number of runs.
    pub total_runs: u32,
    /// Trigger rate (`trigger_count` / `total_runs`).
    pub trigger_rate: f64,
    /// Whether this query passed (respecting threshold and `should_trigger`).
    pub passed: bool,
    /// Individual run results.
    pub runs: Vec<TriggerTestResult>,
}

/// Full eval result across all queries.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalResult {
    pub skill_name: String,
    pub description: String,
    pub results: Vec<QueryResult>,
    pub total_queries: usize,
    pub passed_queries: usize,
    pub accuracy: f64,
    pub duration: Duration,
}

/// Record of one optimization iteration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IterationRecord {
    pub iteration: u32,
    pub description: String,
    pub train_result: EvalResult,
    pub test_result: EvalResult,
}

/// Full optimization result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptimizeResult {
    pub skill_name: String,
    pub original_description: String,
    pub best_description: String,
    pub best_iteration: u32,
    pub iterations: Vec<IterationRecord>,
    pub baseline_test: EvalResult,
}

/// Load and validate an eval set from a JSON file.
pub fn load_eval_set(path: &Path) -> Result<Vec<EvalQuery>> {
    let content = std::fs::read_to_string(path).map_err(|e| {
        StrataError::Eval(format!(
            "Failed to read eval set at {}: {e}",
            path.display()
        ))
    })?;
    let queries: Vec<EvalQuery> = serde_json::from_str(&content).map_err(|e| {
        StrataError::Eval(format!(
            "Failed to parse eval set at {}: {e}",
            path.display()
        ))
    })?;
    if queries.is_empty() {
        return Err(StrataError::Eval("Eval set is empty".to_string()));
    }
    Ok(queries)
}

/// Split eval set into (train, test) using a deterministic LCG-based Fisher-Yates shuffle.
/// `holdout` is the fraction reserved for test (0.0..1.0).
/// `seed` makes the split reproducible.
pub fn split_eval_set(
    queries: &[EvalQuery],
    holdout: f64,
    seed: u64,
) -> (Vec<EvalQuery>, Vec<EvalQuery>) {
    // LCG constants from Numerical Recipes
    const A: u64 = 6_364_136_223_846_793_005;
    const C: u64 = 1_442_695_040_888_963_407;

    let n = queries.len();
    let test_count = ((n as f64) * holdout).round() as usize;
    let test_count = test_count.max(1).min(n - 1);

    // Create index array and shuffle with LCG
    let mut indices: Vec<usize> = (0..n).collect();
    let mut state = seed;

    for i in (1..n).rev() {
        state = state.wrapping_mul(A).wrapping_add(C);
        let j = (state >> 33) as usize % (i + 1);
        indices.swap(i, j);
    }

    let test_indices = &indices[..test_count];
    let train_indices = &indices[test_count..];

    let train: Vec<EvalQuery> = train_indices.iter().map(|&i| queries[i].clone()).collect();
    let test: Vec<EvalQuery> = test_indices.iter().map(|&i| queries[i].clone()).collect();

    (train, test)
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    fn make_queries(n: usize) -> Vec<EvalQuery> {
        (0..n)
            .map(|i| EvalQuery {
                query: format!("query {i}"),
                should_trigger: i % 2 == 0,
                category: None,
            })
            .collect()
    }

    #[test]
    fn split_eval_set_deterministic() {
        let queries = make_queries(10);
        let (train1, test1) = split_eval_set(&queries, 0.4, 42);
        let (train2, test2) = split_eval_set(&queries, 0.4, 42);
        assert_eq!(train1.len(), train2.len());
        assert_eq!(test1.len(), test2.len());
        for (a, b) in train1.iter().zip(&train2) {
            assert_eq!(a.query, b.query);
        }
    }

    #[test]
    fn split_eval_set_coverage() {
        let queries = make_queries(10);
        let (train, test) = split_eval_set(&queries, 0.4, 42);
        assert_eq!(train.len() + test.len(), 10);
        assert_eq!(test.len(), 4);
    }

    #[test]
    fn split_eval_set_different_seeds() {
        let queries = make_queries(20);
        let (train1, _) = split_eval_set(&queries, 0.4, 42);
        let (train2, _) = split_eval_set(&queries, 0.4, 99);
        // Different seeds should (almost certainly) produce different orderings
        let same = train1
            .iter()
            .zip(&train2)
            .filter(|(a, b)| a.query == b.query)
            .count();
        assert!(same < train1.len());
    }

    #[test]
    fn load_eval_set_invalid_json() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("bad.json");
        std::fs::write(&path, "not json").unwrap();
        assert!(load_eval_set(&path).is_err());
    }

    #[test]
    fn load_eval_set_empty() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("empty.json");
        std::fs::write(&path, "[]").unwrap();
        assert!(load_eval_set(&path).is_err());
    }

    #[test]
    fn load_eval_set_valid() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("good.json");
        std::fs::write(&path, r#"[{"query": "test", "should_trigger": true}]"#).unwrap();
        let queries = load_eval_set(&path).unwrap();
        assert_eq!(queries.len(), 1);
        assert!(queries[0].should_trigger);
    }
}
