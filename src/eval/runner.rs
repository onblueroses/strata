use crate::error::Result;
use crate::eval::backend::EvalBackend;
use crate::eval::{EvalQuery, EvalResult, QueryResult};
use crate::ui;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::mpsc;
use std::time::{Duration, Instant};

/// Run evaluation of all queries against a skill.
#[expect(
    clippy::too_many_arguments,
    reason = "eval runner with many tuning parameters"
)]
pub fn run_eval(
    backend: &dyn EvalBackend,
    skill_name: &str,
    description: &str,
    _skill_content: &str,
    queries: &[EvalQuery],
    project_root: &Path,
    workers: u32,
    timeout: Duration,
    runs_per_query: u32,
    trigger_threshold: f64,
) -> Result<EvalResult> {
    let start = Instant::now();
    let total_work = queries.len() * runs_per_query as usize;
    let completed = AtomicUsize::new(0);

    // Build work items: (query_index, run_index)
    let work: Vec<(usize, u32)> = queries
        .iter()
        .enumerate()
        .flat_map(|(qi, _)| (0..runs_per_query).map(move |ri| (qi, ri)))
        .collect();

    // Use channel as work queue, wrapped in Mutex for sharing across threads
    let (tx, rx) = mpsc::channel();
    for item in &work {
        let _ = tx.send(*item);
    }
    drop(tx);
    let rx = std::sync::Mutex::new(rx);

    // Collect results: Vec<Vec<TriggerTestResult>> indexed by query
    let results_mutex = std::sync::Mutex::new(vec![Vec::new(); queries.len()]);

    let workers = (workers as usize).min(total_work);

    std::thread::scope(|s| {
        for _ in 0..workers {
            s.spawn(|| {
                loop {
                    let item = {
                        let lock = rx.lock();
                        match lock {
                            Ok(guard) => match guard.recv() {
                                Ok(item) => item,
                                Err(_) => break,
                            },
                            Err(_) => break,
                        }
                    };
                    let (qi, _ri) = item;
                    let query = &queries[qi];
                    let result = backend.test_trigger(
                        &query.query,
                        skill_name,
                        description,
                        project_root,
                        timeout,
                    );

                    match result {
                        Ok(trigger_result) => {
                            if let Ok(mut results) = results_mutex.lock() {
                                results[qi].push(trigger_result);
                            }
                        }
                        Err(e) => {
                            let err_result = crate::eval::TriggerTestResult {
                                triggered: false,
                                tool_called: None,
                                skill_invoked: None,
                                duration: Duration::ZERO,
                                timed_out: false,
                                error: Some(e.to_string()),
                            };
                            if let Ok(mut results) = results_mutex.lock() {
                                results[qi].push(err_result);
                            }
                        }
                    }

                    let done = completed.fetch_add(1, Ordering::Relaxed) + 1;
                    ui::progress(&format!("{done}/{total_work} queries evaluated..."));
                }
            });
        }
    });

    ui::clear_progress();

    // Aggregate results
    let all_runs = results_mutex
        .into_inner()
        .map_err(|e| crate::error::StrataError::Eval(format!("Lock poisoned: {e}")))?;

    let mut query_results = Vec::with_capacity(queries.len());

    for (qi, runs) in all_runs.into_iter().enumerate() {
        let query = &queries[qi];
        let total_runs = runs.len() as u32;
        let trigger_count = runs.iter().filter(|r| r.triggered).count() as u32;
        let trigger_rate = if total_runs > 0 {
            f64::from(trigger_count) / f64::from(total_runs)
        } else {
            0.0
        };

        let passed = if query.should_trigger {
            trigger_rate >= trigger_threshold
        } else {
            trigger_rate < trigger_threshold
        };

        query_results.push(QueryResult {
            query: query.clone(),
            trigger_count,
            total_runs,
            trigger_rate,
            passed,
            runs,
        });
    }

    let total_queries = query_results.len();
    let passed_queries = query_results.iter().filter(|r| r.passed).count();
    let accuracy = if total_queries > 0 {
        passed_queries as f64 / total_queries as f64
    } else {
        0.0
    };

    Ok(EvalResult {
        skill_name: skill_name.to_string(),
        description: description.to_string(),
        results: query_results,
        total_queries,
        passed_queries,
        accuracy,
        duration: start.elapsed(),
        semantic_results: Vec::new(),
    })
}
