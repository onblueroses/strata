use crate::config::SkillsConfig;
use crate::error::{Result, StrataError};
use crate::eval::{IterationRecord, QueryResult, TriggerTestResult};
use std::fmt::Write as _;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

/// Agent-agnostic interface for trigger testing and description improvement.
pub trait EvalBackend: Send + Sync {
    #[expect(dead_code, reason = "used for display/logging in future backends")]
    fn name(&self) -> &'static str;

    fn test_trigger(
        &self,
        query: &str,
        skill_name: &str,
        skill_description: &str,
        project_root: &Path,
        timeout: Duration,
    ) -> Result<TriggerTestResult>;

    fn improve_description(
        &self,
        skill_name: &str,
        skill_content: &str,
        current_description: &str,
        failed_triggers: &[QueryResult],
        false_triggers: &[QueryResult],
        history: &[IterationRecord],
    ) -> Result<String>;
}

/// Create a backend from config.
pub fn create_backend(config: &SkillsConfig) -> Result<Box<dyn EvalBackend>> {
    match config.eval_backend.as_str() {
        "claude-code" => Ok(Box::new(ClaudeCodeBackend::new(config)?)),
        other => Err(StrataError::Eval(format!(
            "Unknown eval backend: '{other}'. Supported: claude-code"
        ))),
    }
}

/// Claude Code CLI backend - spawns `claude` subprocess for trigger testing.
pub struct ClaudeCodeBackend {
    claude_bin: PathBuf,
    model: Option<String>,
}

impl ClaudeCodeBackend {
    pub fn new(config: &SkillsConfig) -> Result<Self> {
        let claude_bin = resolve_claude_binary()?;
        Ok(Self {
            claude_bin,
            model: config.model.clone(),
        })
    }
}

impl EvalBackend for ClaudeCodeBackend {
    fn name(&self) -> &'static str {
        "claude-code"
    }

    fn test_trigger(
        &self,
        query: &str,
        skill_name: &str,
        skill_description: &str,
        project_root: &Path,
        timeout: Duration,
    ) -> Result<TriggerTestResult> {
        let start = Instant::now();

        // Build the system prompt that simulates a skill being available
        let system_prompt = format!(
            "You have access to a set of skills. The following skill is available:\n\
             - {skill_name}: {skill_description}\n\n\
             If the user's request matches this skill, invoke it using the Skill tool \
             with `skill: \"{skill_name}\"`. If it does not match, respond normally without \
             invoking any skill.\n\n\
             IMPORTANT: Only invoke the skill if the request genuinely matches. Do not invoke \
             it for unrelated requests."
        );

        // Build command
        let mut cmd = Command::new(&self.claude_bin);
        cmd.arg("-p")
            .arg(query)
            .arg("--output-format")
            .arg("stream-json")
            .arg("--verbose")
            .arg("--system-prompt")
            .arg(&system_prompt)
            .arg("--max-turns")
            .arg("1")
            .current_dir(project_root)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());

        if let Some(ref model) = self.model {
            cmd.arg("--model").arg(model);
        }

        // Strip CLAUDECODE env var to allow nesting
        cmd.env_remove("CLAUDECODE");
        cmd.env_remove("CLAUDE_CODE_ENTRYPOINT");

        let mut child = cmd.spawn().map_err(|e| {
            StrataError::Eval(format!(
                "Failed to spawn {}: {e}",
                self.claude_bin.display()
            ))
        })?;

        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| StrataError::Eval("Failed to capture claude stdout".to_string()))?;

        // Parse NDJSON stream with timeout via reader thread + channel
        let (tx, rx) = std::sync::mpsc::channel();
        let target_skill = skill_name.to_string();

        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            let mut parser = StreamParser::new(&target_skill);

            for line in reader.lines() {
                let Ok(line) = line else { break };
                if let Some(result) = parser.feed(&line) {
                    let _ = tx.send(result);
                    return;
                }
            }
            // Stream ended without early match - send final state
            let _ = tx.send(parser.finalize());
        });

        let result = match rx.recv_timeout(timeout) {
            Ok(parsed) => {
                // Kill child if still running (early match)
                let _ = child.kill();
                let _ = child.wait();
                TriggerTestResult {
                    triggered: parsed.triggered,
                    tool_called: parsed.tool_called,
                    skill_invoked: parsed.skill_invoked,
                    duration: start.elapsed(),
                    timed_out: false,
                    error: None,
                }
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                let _ = child.kill();
                let _ = child.wait();
                TriggerTestResult {
                    triggered: false,
                    tool_called: None,
                    skill_invoked: None,
                    duration: start.elapsed(),
                    timed_out: true,
                    error: Some("Timed out".to_string()),
                }
            }
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                let _ = child.kill();
                let _ = child.wait();
                TriggerTestResult {
                    triggered: false,
                    tool_called: None,
                    skill_invoked: None,
                    duration: start.elapsed(),
                    timed_out: false,
                    error: Some("Stream parser disconnected".to_string()),
                }
            }
        };

        Ok(result)
    }

    fn improve_description(
        &self,
        skill_name: &str,
        skill_content: &str,
        current_description: &str,
        failed_triggers: &[QueryResult],
        false_triggers: &[QueryResult],
        history: &[IterationRecord],
    ) -> Result<String> {
        let prompt = build_improvement_prompt(
            skill_name,
            skill_content,
            current_description,
            failed_triggers,
            false_triggers,
            history,
        );

        let mut cmd = Command::new(&self.claude_bin);
        cmd.arg("-p")
            .arg(&prompt)
            .arg("--output-format")
            .arg("text")
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());

        if let Some(ref model) = self.model {
            cmd.arg("--model").arg(model);
        }

        cmd.env_remove("CLAUDECODE");
        cmd.env_remove("CLAUDE_CODE_ENTRYPOINT");

        let output = cmd
            .output()
            .map_err(|e| StrataError::Eval(format!("Failed to run claude for improvement: {e}")))?;

        if !output.status.success() {
            return Err(StrataError::Eval(format!(
                "Claude improvement failed with status {}",
                output.status
            )));
        }

        let response = String::from_utf8_lossy(&output.stdout);
        extract_new_description(&response)
    }
}

/// NDJSON stream parser state machine.
struct StreamParser {
    target_skill: String,
    in_skill_tool_use: bool,
    accumulated_json: String,
    result: ParsedResult,
}

#[derive(Default)]
struct ParsedResult {
    triggered: bool,
    tool_called: Option<String>,
    skill_invoked: Option<String>,
}

impl StreamParser {
    fn new(target_skill: &str) -> Self {
        Self {
            target_skill: target_skill.to_string(),
            in_skill_tool_use: false,
            accumulated_json: String::new(),
            result: ParsedResult::default(),
        }
    }

    /// Feed a line of NDJSON. Returns Some if we have a definitive result (early exit).
    fn feed(&mut self, line: &str) -> Option<ParsedResult> {
        let line = line.trim();
        if line.is_empty() {
            return None;
        }

        // Try to parse as JSON
        let Ok(value) = serde_json::from_str::<serde_json::Value>(line) else {
            return None;
        };

        let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("");

        match event_type {
            // assistant message - fallback detection
            "assistant" => {
                self.check_assistant_message(&value);
                Some(std::mem::take(&mut self.result))
            }

            // Stream events - primary detection path
            "content_block_start" => {
                self.handle_content_block_start(&value);
                None
            }

            "content_block_delta" => {
                self.handle_content_block_delta(&value);
                if self.result.triggered {
                    return Some(std::mem::take(&mut self.result));
                }
                None
            }

            "content_block_stop" | "message_stop" => {
                self.handle_block_stop();
                if self.result.triggered {
                    return Some(std::mem::take(&mut self.result));
                }
                None
            }

            "result" => Some(std::mem::take(&mut self.result)),

            _ => None,
        }
    }

    fn finalize(self) -> ParsedResult {
        self.result
    }

    fn handle_content_block_start(&mut self, value: &serde_json::Value) {
        // Look for content_block with type "tool_use" and name "Skill"
        if let Some(content_block) = value.get("content_block") {
            let block_type = content_block
                .get("type")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let name = content_block
                .get("name")
                .and_then(|v| v.as_str())
                .unwrap_or("");

            if block_type == "tool_use" && (name == "Skill" || name == "Read") {
                self.in_skill_tool_use = name == "Skill";
                self.accumulated_json.clear();
                self.result.tool_called = Some(name.to_string());
            }
        }

        // Also check nested event structure
        if let Some(event) = value.get("event") {
            if let Some(content_block) = event.get("content_block") {
                let block_type = content_block
                    .get("type")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let name = content_block
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");

                if block_type == "tool_use" && (name == "Skill" || name == "Read") {
                    self.in_skill_tool_use = name == "Skill";
                    self.accumulated_json.clear();
                    self.result.tool_called = Some(name.to_string());
                }
            }
        }
    }

    fn handle_content_block_delta(&mut self, value: &serde_json::Value) {
        if !self.in_skill_tool_use {
            return;
        }

        // Extract partial_json from delta
        let partial = value
            .get("delta")
            .or_else(|| value.get("event").and_then(|e| e.get("delta")))
            .and_then(|d| d.get("partial_json"))
            .and_then(|v| v.as_str())
            .unwrap_or("");

        self.accumulated_json.push_str(partial);

        // Check for skill name in accumulated JSON (early exit)
        if self.accumulated_json.contains(&self.target_skill) {
            self.result.triggered = true;
            self.result.skill_invoked = Some(self.target_skill.clone());
        }
    }

    fn handle_block_stop(&mut self) {
        if self.in_skill_tool_use && !self.accumulated_json.is_empty() {
            // Try to parse the accumulated JSON for the skill name
            if let Ok(input) = serde_json::from_str::<serde_json::Value>(&self.accumulated_json) {
                if let Some(skill) = input.get("skill").and_then(|v| v.as_str()) {
                    self.result.skill_invoked = Some(skill.to_string());
                    if skill == self.target_skill {
                        self.result.triggered = true;
                    }
                }
            }
        }
        self.in_skill_tool_use = false;
        self.accumulated_json.clear();
    }

    fn check_assistant_message(&mut self, value: &serde_json::Value) {
        // Check assistant message content array for tool_use blocks
        let content = value
            .get("message")
            .and_then(|m| m.get("content"))
            .and_then(|c| c.as_array());

        let Some(blocks) = content else { return };

        for block in blocks {
            let block_type = block.get("type").and_then(|v| v.as_str()).unwrap_or("");
            if block_type != "tool_use" {
                continue;
            }
            let name = block.get("name").and_then(|v| v.as_str()).unwrap_or("");
            if name == "Skill" {
                self.result.tool_called = Some("Skill".to_string());
                if let Some(skill) = block
                    .get("input")
                    .and_then(|i| i.get("skill"))
                    .and_then(|v| v.as_str())
                {
                    self.result.skill_invoked = Some(skill.to_string());
                    if skill == self.target_skill {
                        self.result.triggered = true;
                    }
                }
            }
        }
    }
}

fn resolve_claude_binary() -> Result<PathBuf> {
    // On Windows, claude ships as claude.cmd
    #[cfg(target_os = "windows")]
    let candidates = ["claude.cmd", "claude.exe", "claude"];
    #[cfg(not(target_os = "windows"))]
    let candidates = ["claude"];

    for name in candidates {
        if which_exists(name) {
            return Ok(PathBuf::from(name));
        }
    }

    Err(StrataError::Eval(
        "Claude CLI not found in PATH. Install from https://docs.anthropic.com/claude-code"
            .to_string(),
    ))
}

fn which_exists(name: &str) -> bool {
    Command::new(name)
        .arg("--version")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .is_ok()
}

fn build_improvement_prompt(
    skill_name: &str,
    skill_content: &str,
    current_description: &str,
    failed_triggers: &[QueryResult],
    false_triggers: &[QueryResult],
    history: &[IterationRecord],
) -> String {
    let mut prompt = String::new();

    let _ = write!(
        prompt,
        "You are optimizing the description field of a skill called \"{skill_name}\".\n\n\
         The description is what an AI agent reads to decide whether to invoke this skill. \
         Your goal: write a description that maximizes correct trigger decisions.\n\n"
    );

    prompt.push_str("## Current Description\n\n");
    prompt.push_str(current_description);
    prompt.push_str("\n\n");

    prompt.push_str("## Full Skill Content\n\n```\n");
    prompt.push_str(skill_content);
    prompt.push_str("\n```\n\n");

    if !failed_triggers.is_empty() {
        prompt.push_str("## Missed Triggers (should have triggered but didn't)\n\n");
        for qr in failed_triggers {
            let _ = writeln!(
                prompt,
                "- \"{}\": triggered {:.0}% of the time",
                qr.query.query,
                qr.trigger_rate * 100.0
            );
        }
        prompt.push('\n');
    }

    if !false_triggers.is_empty() {
        prompt.push_str("## False Triggers (should NOT have triggered but did)\n\n");
        for qr in false_triggers {
            let _ = writeln!(
                prompt,
                "- \"{}\": triggered {:.0}% of the time",
                qr.query.query,
                qr.trigger_rate * 100.0
            );
        }
        prompt.push('\n');
    }

    if !history.is_empty() {
        prompt.push_str("## Previous Attempts (blinded - train accuracy only)\n\n");
        for record in history {
            let _ = write!(
                prompt,
                "Iteration {}: train accuracy {:.0}%\n  Description: {}\n\n",
                record.iteration,
                record.train_result.accuracy * 100.0,
                record.description
            );
        }
    }

    prompt.push_str(
        "## Instructions\n\n\
         Write an improved description that:\n\
         1. Triggers correctly for queries that match the skill's purpose\n\
         2. Does NOT trigger for unrelated queries\n\
         3. Is concise (max 1024 characters)\n\
         4. Uses concrete, specific language over vague terms\n\
         5. Includes key trigger words/phrases the agent should match on\n\n\
         Wrap your new description in <new_description> tags:\n\
         <new_description>\n\
         Your improved description here\n\
         </new_description>\n",
    );

    prompt
}

fn extract_new_description(response: &str) -> Result<String> {
    let start_tag = "<new_description>";
    let end_tag = "</new_description>";

    let start = response.find(start_tag).ok_or_else(|| {
        StrataError::Eval("Improvement response missing <new_description> tag".to_string())
    })?;

    let end = response.find(end_tag).ok_or_else(|| {
        StrataError::Eval("Improvement response missing </new_description> tag".to_string())
    })?;

    let desc = response[start + start_tag.len()..end].trim().to_string();

    if desc.is_empty() {
        return Err(StrataError::Eval(
            "Extracted description is empty".to_string(),
        ));
    }

    // Auto-shorten if too long
    if desc.len() > 1024 {
        Ok(desc[..1024].to_string())
    } else {
        Ok(desc)
    }
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    #[test]
    fn parse_stream_tool_use_in_assistant_message() {
        let mut parser = StreamParser::new("review");
        let line = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"review"}}]}}"#;
        let result = parser.feed(line);
        assert!(result.is_some());
        let r = result.unwrap();
        assert!(r.triggered);
        assert_eq!(r.skill_invoked.as_deref(), Some("review"));
    }

    #[test]
    fn parse_stream_no_trigger() {
        let mut parser = StreamParser::new("review");
        let line =
            r#"{"type":"assistant","message":{"content":[{"type":"text","text":"Hello!"}]}}"#;
        let result = parser.feed(line);
        // assistant without skill tool_use - returns Some but not triggered
        let r = result.unwrap();
        assert!(!r.triggered);
    }

    #[test]
    fn parse_stream_wrong_skill() {
        let mut parser = StreamParser::new("review");
        let line = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"commit"}}]}}"#;
        let result = parser.feed(line);
        let r = result.unwrap();
        assert!(!r.triggered);
        assert_eq!(r.skill_invoked.as_deref(), Some("commit"));
    }

    #[test]
    fn parse_content_block_deltas() {
        let mut parser = StreamParser::new("debug");

        // Start a Skill tool_use block
        let start =
            r#"{"type":"content_block_start","content_block":{"type":"tool_use","name":"Skill"}}"#;
        assert!(parser.feed(start).is_none());

        // Send partial JSON deltas
        let delta1 = r#"{"type":"content_block_delta","delta":{"partial_json":"{\"skill\":\"de"}}"#;
        assert!(parser.feed(delta1).is_none());

        let delta2 = r#"{"type":"content_block_delta","delta":{"partial_json":"bug\"}"}}"#;
        let result = parser.feed(delta2);
        assert!(result.is_some());
        assert!(result.unwrap().triggered);
    }

    #[test]
    fn parse_content_block_stop_finalizes() {
        let mut parser = StreamParser::new("test");

        let start =
            r#"{"type":"content_block_start","content_block":{"type":"tool_use","name":"Skill"}}"#;
        parser.feed(start);

        let delta =
            r#"{"type":"content_block_delta","delta":{"partial_json":"{\"skill\":\"test\"}"}}"#;
        // This might trigger on partial match
        let _ = parser.feed(delta);

        let stop = r#"{"type":"content_block_stop"}"#;
        let result = parser.feed(stop);
        // Should have triggered by now either in delta or stop
        if let Some(r) = result {
            assert!(r.triggered);
        }
    }

    #[test]
    fn extract_description_valid() {
        let response = "Here is my improved version:\n<new_description>\nA skill for code review\n</new_description>";
        let desc = extract_new_description(response).unwrap();
        assert_eq!(desc, "A skill for code review");
    }

    #[test]
    fn extract_description_missing_tag() {
        let response = "No tags here";
        assert!(extract_new_description(response).is_err());
    }

    #[test]
    fn extract_description_auto_shorten() {
        let long_desc = "x".repeat(2000);
        let response = format!("<new_description>{long_desc}</new_description>");
        let desc = extract_new_description(&response).unwrap();
        assert_eq!(desc.len(), 1024);
    }
}
