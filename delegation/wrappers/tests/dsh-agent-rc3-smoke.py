#!/usr/bin/env python3
"""Run the installed driver against a loopback Messages endpoint."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
import time


WRAPPER = Path(__file__).resolve().parents[1] / "dsh-agent"
requests = []
delay = 0
tool_probe = False
probe_issued = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        global probe_issued
        assert self.path == "/v1/messages", self.path
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests.append(body)
        time.sleep(delay)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        events = [
            {"type": "message_start", "message": {
                "id": "local-test", "type": "message", "role": "assistant",
                "model": body["model"], "content": [],
                "usage": {"input_tokens": 3, "output_tokens": 0}}},
            {"type": "content_block_start", "index": 0,
             "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0,
             "delta": {"type": "text_delta", "text": "LOCAL_DRIVER_OK"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
             "usage": {"output_tokens": 5}},
            {"type": "message_stop"},
        ]
        if tool_probe and not probe_issued:
            probe_issued = True
            events[1:4] = [
                {"type": "content_block_start", "index": 0,
                 "content_block": {"type": "tool_use", "id": "local-bash",
                                   "name": "bash", "input": {}}},
                {"type": "content_block_delta", "index": 0,
                 "delta": {"type": "input_json_delta", "partial_json": json.dumps({
                     "command": "printf LOCAL_TOOL_OK", "description": "Check the local shell."})}},
                {"type": "content_block_stop", "index": 0},
            ]
            events[-2]["delta"]["stop_reason"] = "tool_use"
        try:
            for event in events:
                self.wfile.write(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
server.daemon_threads = True
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
state = Path.home() / ".local/state/dsh-driver-tests" / f"real-{time.time_ns()}"
state.mkdir(parents=True)
env = dict(os.environ, DEEPSEEK_API_KEY="local-test-key",
           DEEPSEEK_BASE_URL=f"http://127.0.0.1:{server.server_port}",
           HTTP_PROXY="", HTTPS_PROXY="", ALL_PROXY="", NO_PROXY="127.0.0.1")
try:
    for name, args, expected in [
        ("native", [], 0), ("ptc", ["--code"], 0),
        ("bash", [], 0),
        ("timeout", ["--timeout", "5"], 124),
    ]:
        delay = 15 if name == "timeout" else 0
        tool_probe = name == "bash"
        probe_issued = False
        before = len(requests)
        result = subprocess.run([str(WRAPPER), "--read-only", *args,
                                 "Return LOCAL_DRIVER_OK."],
                                cwd=state, env=env, capture_output=True,
                                text=True, timeout=35)
        (state / f"{name}.stdout").write_text(result.stdout)
        (state / f"{name}.stderr").write_text(result.stderr)
        assert result.returncode == expected, (name, result.returncode, result.stderr)
        assert len(requests) > before, (name, "no local model request")
        assert requests[before]["model"] == "deepseek-flash"
        if expected == 0:
            assert result.stdout.strip() == "LOCAL_DRIVER_OK", result.stdout
            assert "session.v4.jsonl.zstd" in result.stderr, result.stderr
            tools = [tool["name"] for tool in requests[before].get("tools", [])]
            assert ("run_code" in tools) == (name == "ptc"), tools
            if tool_probe:
                blocks = [block for message in requests[-1]["messages"]
                          for block in message.get("content", []) if isinstance(block, dict)
                          and block.get("type") == "tool_result"]
                assert any("LOCAL_TOOL_OK" in json.dumps(block.get("content"))
                           and not block.get("is_error") for block in blocks), blocks
        else:
            assert "run killed" in result.stderr
        print(f"PASS installed rc.3 {name}: exit {expected}")
finally:
    server.shutdown()
    server.server_close()
    thread.join()
print(f"Logs: {state}")
