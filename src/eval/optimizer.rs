use crate::error::Result;
use crate::eval::backend::EvalBackend;
use crate::eval::runner::run_eval;
use crate::eval::{EvalQuery, EvalResult, IterationRecord, OptimizeResult, split_eval_set};
use crate::ui;
use std::path::Path;
use std::time::Duration;

/// Run the full optimization loop: eval baseline, then iterate improve+eval.
#[expect(
    clippy::too_many_arguments,
    reason = "optimization loop with many parameters"
)]
#[expect(
    clippy::too_many_lines,
    reason = "sequential loop logic reads better as one function"
)]
pub fn run_optimize_loop(
    backend: &dyn EvalBackend,
    skill_name: &str,
    original_description: &str,
    skill_content: &str,
    queries: &[EvalQuery],
    project_root: &Path,
    workers: u32,
    timeout: Duration,
    runs_per_query: u32,
    trigger_threshold: f64,
    holdout: f64,
    max_iterations: u32,
) -> Result<OptimizeResult> {
    // Deterministic train/test split
    let seed = compute_seed(skill_name, queries.len());
    let (train_set, test_set) = split_eval_set(queries, holdout, seed);

    ui::info(&format!(
        "Split: {} train, {} test queries",
        train_set.len(),
        test_set.len()
    ));

    // Baseline eval on test set
    ui::header("Baseline evaluation");
    let baseline_test = run_eval(
        backend,
        skill_name,
        original_description,
        skill_content,
        &test_set,
        project_root,
        workers,
        timeout,
        runs_per_query,
        trigger_threshold,
    )?;
    ui::info(&format!(
        "Baseline test accuracy: {:.0}%",
        baseline_test.accuracy * 100.0
    ));

    let mut iterations: Vec<IterationRecord> = Vec::new();
    let mut current_description = original_description.to_string();
    let mut best_description = original_description.to_string();
    let mut best_test_accuracy = baseline_test.accuracy;
    let mut best_iteration = 0u32;

    for iter in 1..=max_iterations {
        ui::header(&format!("Iteration {iter}/{max_iterations}"));

        // Eval on train set with current description
        let train_result = run_eval(
            backend,
            skill_name,
            &current_description,
            skill_content,
            &train_set,
            project_root,
            workers,
            timeout,
            runs_per_query,
            trigger_threshold,
        )?;

        ui::info(&format!(
            "Train accuracy: {:.0}%",
            train_result.accuracy * 100.0
        ));

        // Collect failures for improvement prompt
        let failed_triggers: Vec<_> = train_result
            .results
            .iter()
            .filter(|r| !r.passed && r.query.should_trigger)
            .cloned()
            .collect();

        let false_triggers: Vec<_> = train_result
            .results
            .iter()
            .filter(|r| !r.passed && !r.query.should_trigger)
            .cloned()
            .collect();

        // Build blinded history: train results only, test data blanked to prevent overfitting
        let blinded_history: Vec<IterationRecord> = iterations
            .iter()
            .map(|rec| IterationRecord {
                iteration: rec.iteration,
                description: rec.description.clone(),
                train_result: rec.train_result.clone(),
                test_result: EvalResult {
                    skill_name: String::new(),
                    description: String::new(),
                    results: Vec::new(),
                    total_queries: 0,
                    passed_queries: 0,
                    accuracy: 0.0,
                    duration: Duration::ZERO,
                },
            })
            .collect();

        // Ask backend to improve description
        ui::info("Generating improved description...");
        let new_description = backend.improve_description(
            skill_name,
            skill_content,
            &current_description,
            &failed_triggers,
            &false_triggers,
            &blinded_history,
        )?;

        ui::info(&format!(
            "New description ({} chars): {}",
            new_description.len(),
            truncate_display(&new_description, 80)
        ));

        // Eval new description on test set (blinded from improvement)
        let test_result = run_eval(
            backend,
            skill_name,
            &new_description,
            skill_content,
            &test_set,
            project_root,
            workers,
            timeout,
            runs_per_query,
            trigger_threshold,
        )?;

        ui::info(&format!(
            "Test accuracy: {:.0}%",
            test_result.accuracy * 100.0
        ));

        iterations.push(IterationRecord {
            iteration: iter,
            description: new_description.clone(),
            train_result,
            test_result: test_result.clone(),
        });

        // Track best by test accuracy
        if test_result.accuracy > best_test_accuracy {
            best_test_accuracy = test_result.accuracy;
            best_description.clone_from(&new_description);
            best_iteration = iter;
            ui::success(&format!(
                "New best! Test accuracy: {:.0}%",
                best_test_accuracy * 100.0
            ));
        }

        // Early exit if perfect
        if (test_result.accuracy - 1.0).abs() < f64::EPSILON {
            ui::success("Perfect test accuracy - stopping early");
            break;
        }

        current_description = new_description;
    }

    Ok(OptimizeResult {
        skill_name: skill_name.to_string(),
        original_description: original_description.to_string(),
        best_description,
        best_iteration,
        iterations,
        baseline_test,
    })
}

/// Compute a deterministic seed from skill name and query count.
fn compute_seed(skill_name: &str, query_count: usize) -> u64 {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325; // FNV offset basis
    for byte in skill_name.bytes() {
        hash ^= u64::from(byte);
        hash = hash.wrapping_mul(0x0100_0000_01b3); // FNV prime
    }
    hash ^= query_count as u64;
    hash
}

fn truncate_display(s: &str, max: usize) -> String {
    let single_line: String = s.chars().map(|c| if c == '\n' { ' ' } else { c }).collect();
    if single_line.len() <= max {
        single_line
    } else {
        format!("{}...", &single_line[..max])
    }
}
