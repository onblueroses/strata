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

/// The kind of assertion to run against an LLM output.
///
/// Deterministic kinds (`Contains`, `NotContains`, `Regex`) are evaluated inline
/// without any LLM call. `LlmJudge` triggers a judge subprocess.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "PascalCase")]
pub enum AssertionKind {
    /// Output must contain this substring.
    Contains(String),
    /// Output must not contain this substring.
    NotContains(String),
    /// Output must match this regex pattern.
    Regex(String),
    /// Output must satisfy this natural-language criterion (evaluated by an LLM judge).
    LlmJudge(String),
}

/// A single assertion against an LLM output, with an optional weight for
/// pass-threshold scoring.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Assertion {
    pub kind: AssertionKind,
    /// Contribution weight for pass-threshold scoring. Defaults to 1.0.
    #[serde(default = "default_assertion_weight")]
    pub weight: f64,
}

fn default_assertion_weight() -> f64 {
    1.0
}

/// Acceptable range for a stochastic benchmark metric.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BenchmarkBand {
    /// Hard floor — fail below this.
    pub min: f64,
    /// Goal value.
    pub target: f64,
    /// Acceptable deviation from target before flagging degradation.
    pub tolerance: f64,
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
    /// Assertions to evaluate against the output.
    /// Deterministic kinds are free; `LlmJudge` triggers a subprocess.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub assertions: Vec<Assertion>,
    /// Optional band for stochastic benchmark metrics.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub benchmark_band: Option<BenchmarkBand>,
    /// Fraction of weighted assertions that must pass (0.0..=1.0).
    /// Defaults to 1.0 (all assertions must pass) when absent.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pass_threshold: Option<f64>,
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

/// Result of a single LLM judge assertion against an output.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SemanticResult {
    /// The natural-language criterion that was judged.
    pub predicate: String,
    /// Whether the output satisfied the criterion.
    pub passed: bool,
    /// Judge's explanation (first-class output, not discarded).
    pub justification: String,
    /// How long the judge call took.
    pub duration: Duration,
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
    /// Semantic judge results, if any `LlmJudge` assertions were evaluated.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub semantic_results: Vec<SemanticResult>,
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

/// Emit warnings for suspicious `EvalQuery` configurations.
///
/// These are not hard errors — a misconfigured query still runs — but the
/// warnings surface likely mistakes at load time rather than silently producing
/// wrong results.
pub fn validate_eval_query(query: &EvalQuery, index: usize) {
    let label = query
        .category
        .as_deref()
        .unwrap_or(&query.query[..query.query.len().min(40)]);

    if let Some(band) = &query.benchmark_band {
        if band.min > band.target {
            eprintln!(
                "warn: eval query {index} ({label:?}): benchmark_band.min ({}) > target ({}) — likely misconfigured",
                band.min, band.target
            );
        }
        if band.tolerance <= 0.0 {
            eprintln!(
                "warn: eval query {index} ({label:?}): benchmark_band.tolerance ({}) must be > 0",
                band.tolerance
            );
        }
    }

    if !query.assertions.is_empty() && !query.should_trigger {
        eprintln!(
            "warn: eval query {index} ({label:?}): has assertions but should_trigger=false — assertions are only evaluated when the skill fires"
        );
    }

    if let Some(threshold) = query.pass_threshold {
        if threshold <= 0.0 || threshold > 1.0 {
            eprintln!(
                "warn: eval query {index} ({label:?}): pass_threshold ({threshold}) must be in (0.0, 1.0]"
            );
        }
    }
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
    for (i, query) in queries.iter().enumerate() {
        validate_eval_query(query, i);
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
                assertions: Vec::new(),
                benchmark_band: None,
                pass_threshold: None,
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

    #[test]
    fn eval_query_minimal_json_deserializes_with_defaults() {
        let json = r#"[{"query": "review my code", "should_trigger": true}]"#;
        let queries: Vec<EvalQuery> = serde_json::from_str(json).unwrap();
        assert_eq!(queries.len(), 1);
        assert!(queries[0].assertions.is_empty());
        assert!(queries[0].benchmark_band.is_none());
        assert!(queries[0].pass_threshold.is_none());
    }

    #[test]
    fn eval_query_with_contains_assertion() {
        let json = r#"[{
            "query": "write a function",
            "should_trigger": true,
            "assertions": [{"kind": {"Contains": "def "}}]
        }]"#;
        let queries: Vec<EvalQuery> = serde_json::from_str(json).unwrap();
        assert_eq!(queries[0].assertions.len(), 1);
        assert_eq!(
            queries[0].assertions[0].kind,
            AssertionKind::Contains("def ".to_string())
        );
        assert!((queries[0].assertions[0].weight - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn eval_query_with_benchmark_band() {
        let json = r#"[{
            "query": "trigger test",
            "should_trigger": true,
            "benchmark_band": {"min": 0.7, "target": 0.85, "tolerance": 0.05}
        }]"#;
        let queries: Vec<EvalQuery> = serde_json::from_str(json).unwrap();
        let band = queries[0].benchmark_band.as_ref().unwrap();
        assert!((band.min - 0.7).abs() < f64::EPSILON);
        assert!((band.target - 0.85).abs() < f64::EPSILON);
        assert!((band.tolerance - 0.05).abs() < f64::EPSILON);
    }

    #[test]
    fn eval_query_with_pass_threshold_and_llm_judge() {
        let json = r#"[{
            "query": "explain the bug",
            "should_trigger": true,
            "pass_threshold": 0.67,
            "assertions": [
                {"kind": {"NotContains": "I don't know"}, "weight": 2.0},
                {"kind": {"LlmJudge": "identifies a specific cause"}, "weight": 1.0}
            ]
        }]"#;
        let queries: Vec<EvalQuery> = serde_json::from_str(json).unwrap();
        assert!((queries[0].pass_threshold.unwrap() - 0.67).abs() < f64::EPSILON);
        assert_eq!(queries[0].assertions.len(), 2);
        assert_eq!(
            queries[0].assertions[0].kind,
            AssertionKind::NotContains("I don't know".to_string())
        );
        assert!((queries[0].assertions[0].weight - 2.0).abs() < f64::EPSILON);
    }

    #[test]
    fn eval_query_roundtrip_preserves_fields() {
        let original = EvalQuery {
            query: "test query".to_string(),
            should_trigger: true,
            category: Some("direct".to_string()),
            assertions: vec![
                Assertion {
                    kind: AssertionKind::Contains("foo".to_string()),
                    weight: 1.5,
                },
                Assertion {
                    kind: AssertionKind::LlmJudge("is helpful".to_string()),
                    weight: 2.0,
                },
            ],
            benchmark_band: Some(BenchmarkBand {
                min: 0.6,
                target: 0.8,
                tolerance: 0.1,
            }),
            pass_threshold: Some(0.75),
        };

        let json = serde_json::to_string(&original).unwrap();
        let restored: EvalQuery = serde_json::from_str(&json).unwrap();

        assert_eq!(restored.query, original.query);
        assert_eq!(restored.assertions.len(), 2);
        assert_eq!(
            restored.assertions[1].kind,
            AssertionKind::LlmJudge("is helpful".to_string())
        );
        assert!((restored.pass_threshold.unwrap() - 0.75).abs() < f64::EPSILON);
        let band = restored.benchmark_band.unwrap();
        assert!((band.min - 0.6).abs() < f64::EPSILON);
    }

    #[test]
    fn split_eval_set_preserves_new_fields() {
        let queries: Vec<EvalQuery> = (0..10)
            .map(|i| EvalQuery {
                query: format!("query {i}"),
                should_trigger: i % 2 == 0,
                category: None,
                assertions: vec![Assertion {
                    kind: AssertionKind::Contains(format!("token{i}")),
                    weight: 1.0,
                }],
                benchmark_band: Some(BenchmarkBand {
                    min: 0.5,
                    target: 0.8,
                    tolerance: 0.05,
                }),
                pass_threshold: Some(0.75),
            })
            .collect();

        let (train, test) = split_eval_set(&queries, 0.4, 42);

        for q in train.iter().chain(test.iter()) {
            assert_eq!(q.assertions.len(), 1);
            assert!(q.benchmark_band.is_some());
            assert_eq!(q.pass_threshold, Some(0.75));
        }
    }
}
