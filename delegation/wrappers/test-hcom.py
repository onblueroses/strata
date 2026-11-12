#!/usr/bin/env python3
"""Exercise the long-run mode with a scripted hcom process."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent
STUB = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
root = pathlib.Path(os.environ['RIG'])
a = sys.argv[1:]
with (root/'calls').open('a') as f: f.write(json.dumps(a)+'\n')
mode = os.environ.get('SCENARIO', 'success')
assert os.environ.get('TERM') != 'dumb'
if a[0] == 'codex':
    if mode == 'launch-failed':
        print(json.dumps({'names': [], 'failed': 1}))
        sys.exit(1)
    print(json.dumps({'names': ['delegate-test'], 'failed': 0}))
    sys.exit(2 if mode == 'launch-pending' else 0)
if a[0] == 'kill':
    sys.exit(1 if mode == 'cleanup-failed' else 0)
if a[0] == 'term':
    if mode == 'screen-failed':
        print('PTY unavailable', file=sys.stderr)
        sys.exit(1)
    lines = []
    if mode == 'trust': lines = ['Trust this folder?', 'enter continue · esc back']
    if mode == 'modal': lines = ['Review startup hooks', 'enter continue · esc back']
    if mode == 'delayed-start': lines = ['Waiting for startup', 'MCP startup: waiting']
    if mode == 'completed-trust': lines = ['Trust this folder?']
    if mode in ('undelivered', 'no-transcript'): lines = ['To get started, describe a task or try one of these commands:']
    if mode == 'loading': lines = ['>_ OpenAI Codex (v0.167.2)', 'GPT-6-Luna default · Context 0% used']
    print(json.dumps({'lines':lines, 'ready':mode in ('undelivered', 'no-transcript', 'startup-race', 'delayed-start', 'loading'), 'prompt_empty':True}))
    sys.exit(0)
if a[0] != 'list': sys.exit(7)
countfile = root/'count'
count = int(countfile.read_text()) + 1 if countfile.exists() else 1
countfile.write_text(str(count))
path = root/'rollout.jsonl'
started = {'type':'event_msg','payload':{'type':'task_started'}}
final = {'type':'event_msg','payload':{'type':'task_complete','last_agent_message': 'ANSWER with hit your usage limit for GPT- quoted'}}
status = 'active'
if count == 1:
    path.write_text('')
    status = 'listening'
elif count == 2:
    path.write_text('' if mode == 'undelivered' else json.dumps(started)+'\n')
    if mode not in ('hang', 'blocked', 'dead', 'quota', 'error', 'empty', 'partial'):
        with path.open('a') as f: f.write(json.dumps(final)+'\n')
elif mode == 'partial' and count == 3:
    with path.open('a') as f: f.write(json.dumps(final)[:30])
elif mode == 'partial' and count == 4:
    with path.open('a') as f: f.write(json.dumps(final)[30:]+'\n')
elif mode == 'empty':
    final['payload']['last_agent_message'] = ''
    with path.open('a') as f: f.write(json.dumps(final)+'\n')
if count >= 3 and mode not in ('hang', 'partial'): status = 'listening'
if mode == 'partial' and count >= 4: status = 'listening'
if count >= 2 and mode in ('blocked', 'dead', 'quota'): status = 'blocked' if mode == 'blocked' else 'inactive'
if count == 2 and mode == 'error':
    with path.open('a') as f: f.write(json.dumps({'type':'event_msg','payload':{'type':'error','message':'model_not_found'}})+'\n')
log = root/'pty.log'
log.write_text("ERROR: You've hit your usage limit. Try later." if mode == 'quota' else '')
if mode == 'no-transcript':
    status = 'listening'
    path = ''
if mode in ('delayed-start', 'loading'):
    status = 'listening'
    path.write_text('' if count < 3 else json.dumps(started)+'\n'+json.dumps(final)+'\n')
if mode == 'completed-trust':
    status = 'listening'
    path.write_text(json.dumps(started)+'\n'+json.dumps(final)+'\n')
session = None if mode == 'loading' and count < 3 else 'test-session'
print(json.dumps({'status': status, 'session_id':session, 'transcript_path':str(path), 'background_log_file':str(log)}))
'''


class HcomMode(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.bin = self.root/'bin'
        self.bin.mkdir()
        stub = self.bin/'hcom'
        stub.write_text(STUB)
        stub.chmod(0o700)
        codex = self.bin/'codex'
        codex.write_text('#!/bin/sh\necho "Unexpected real exec path" >&2\nexit 91\n')
        codex.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.bin)+':'+os.environ['PATH'],
                        HOME=str(self.root), RIG=str(self.root), TERM='dumb',
                        DELEGATE_CACHE_DIR=str(self.root/'cache'))
        telemetry = self.root/'.local/bin'
        telemetry.mkdir(parents=True)
        (telemetry/'telemetry-emit').write_text('printf "%s\\n" "$3" >> "$RIG/telemetry"\n')
        self.env['DELEGATE_TELEMETRY_EMITTER'] = str(telemetry/'telemetry-emit')

    def tearDown(self):
        # Retain fixtures for failure diagnosis and follow the local deletion convention.
        archive = Path.home()/'to-delete'
        archive.mkdir(exist_ok=True)
        target = archive/self.root.name
        self.root.rename(target)
        with (archive/'manifest.txt').open('a') as out:
            out.write(f'{target.name} | {self.root} | {time.strftime("%Y-%m-%d")} | long-run test fixtures\n')

    def invoke(self, wrapper, scenario='success', extra=()):
        self.env['SCENARIO'] = scenario
        return subprocess.run(['bash',str(ROOT/wrapper),'--hcom',*extra,'probe'],
                              capture_output=True, text=True, env=self.env)

    def calls(self):
        return [json.loads(line) for line in (self.root/'calls').read_text().splitlines()]

    def test_success_and_arguments(self):
        for wrapper in ('codex-strong', 'codex-fast'):
            with self.subTest(wrapper=wrapper):
                result = self.invoke(wrapper, extra=('--model','gpt-6-luna','--reasoning','high',
                    '--sandbox','workspace-write','--web-search','off','--service-tier','default','--cwd',str(self.root)))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), 'ANSWER with hit your usage limit for GPT- quoted')
                self.assertIn('hcom: delegate-test', result.stderr)
                launch = next(c for c in reversed(self.calls()) if c[0] == 'codex')
                for expected in ('--headless','--go','--hcom-prompt','gpt-6-luna',
                                 'model_reasoning_effort=high','tools.web_search=false',
                                 'workspace-write','features.plugins=false','service_tier=default',
                                 'model_provider="openai"'):
                    self.assertIn(expected, launch)
                self.assertEqual(launch[launch.index('--dir')+1], str(self.root))
                self.assertFalse(any(arg.startswith('projects=') for arg in launch))
                self.assertNotIn('exec', launch)
                self.assertNotIn('--json', launch[launch.index('--')+1:])
                self.assertEqual(self.calls()[-1], ['kill','delegate-test','--json'])
                self.assertEqual(json.loads((self.root/'telemetry').read_text().splitlines()[-1])['status'], 'success')
                (self.root/'count').write_text('0')

    def test_startup_attention_and_undelivered_prompt(self):
        for mode, message in [('trust','folder trust'), ('modal','startup attention'),
                              ('undelivered','without starting'), ('no-transcript','without starting'),
                              ('screen-failed','PTY unavailable')]:
            with self.subTest(mode=mode):
                result = self.invoke('codex-fast', mode)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, '')
                self.assertIn(message, result.stderr)
                self.assertEqual(self.calls()[-1], ['kill','delegate-test','--json'])
                (self.root/'count').write_text('0')
                # A fresh cache per case keeps earlier failures from opening the breaker.
                self.env['DELEGATE_CACHE_DIR'] = str(self.root/f'cache-{mode}')

    def test_rollout_appears_after_ready_screen(self):
        for mode in ('startup-race', 'delayed-start', 'loading', 'completed-trust'):
            with self.subTest(mode=mode):
                result = self.invoke('codex-fast', mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('ANSWER', result.stdout)
                (self.root/'count').write_text('0')

    def test_saved_trust_refusal_does_not_launch(self):
        config = self.root/'.codex/config.toml'
        config.parent.mkdir()
        config.write_text('projects={' + json.dumps(str(self.root))
                          + '={trust_level="untrusted"}}')
        self.env['CODEX_HOME'] = str(config.parent)
        result = self.invoke('codex-fast', extra=('--cwd', str(self.root)))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('trust was refused', result.stderr)
        self.assertFalse((self.root/'calls').exists())
        self.assertIn('untrusted', config.read_text())

    def test_implicit_directory_does_not_add_trust(self):
        result = self.invoke('codex-fast')
        self.assertEqual(result.returncode, 0, result.stderr)
        launch = self.calls()[0]
        self.assertNotIn('--dir', launch)
        self.assertFalse(any(arg.startswith('projects=') for arg in launch))

    def test_dotted_and_quoted_directory(self):
        directory = self.root/'folder.with."quotes"'
        directory.mkdir()
        result = self.invoke('codex-fast', extra=('--cwd', str(directory)))
        self.assertEqual(result.returncode, 0, result.stderr)
        launch = self.calls()[0]
        self.assertEqual(launch[launch.index('--dir')+1], str(directory))

    def test_relative_directory_uses_canonical_codex_path(self):
        directory = self.root/'relative-folder'
        directory.mkdir()
        relative = os.path.relpath(directory)
        result = self.invoke('codex-fast', extra=('--cwd', relative))
        self.assertEqual(result.returncode, 0, result.stderr)
        launch = self.calls()[0]
        self.assertEqual(launch[launch.index('--dir')+1], str(directory))
        self.assertEqual(launch[launch.index('-C')+1], str(directory))

    def test_partial_rollout_and_pending_launch(self):
        for mode in ('partial','launch-pending'):
            with self.subTest(mode=mode):
                result = self.invoke('codex-fast', mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('ANSWER', result.stdout)
                (self.root/'count').write_text('0')

    def test_failures(self):
        for mode, expected in (('launch-failed',2),('blocked',2),('dead',2),('quota',3),('error',2),('empty',5)):
            with self.subTest(mode=mode):
                result = self.invoke('codex-strong', mode)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(result.stdout, '')
                self.assertEqual(self.calls()[-1][0], 'kill')
                (self.root/'count').write_text('0')
                # A fresh cache per case tests classification without accumulated breaker state.
                self.env['DELEGATE_CACHE_DIR'] = str(self.root/f'cache-{mode}')

    def test_cleanup_failure_is_an_error(self):
        result = self.invoke('codex-fast', 'cleanup-failed')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertIn('cleanup failed', result.stderr)

    def test_cache_is_disabled(self):
        result = self.invoke('codex-fast', extra=('--cache','rw'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any(call[0] == 'codex' for call in self.calls()))
        self.assertEqual(list((self.root/'cache').glob('*.txt')), [])

    def test_breaker_rejects_before_launch(self):
        import hashlib
        cache = self.root/'cache'
        cache.mkdir()
        model = hashlib.sha256(b'gpt-6-sol').hexdigest()
        (cache/f'breaker-codex-strong-{model}.open-until').write_text(str(int(time.time())+60))
        result = self.invoke('codex-strong', extra=('--model','gpt-6-sol'))
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertFalse((self.root/'calls').exists())

    def test_timeout_cleans_up(self):
        result = self.invoke('codex-fast','hang',('--timeout','3'))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.calls()[-1], ['kill','delegate-test','--json'])
        record = json.loads((self.root/'telemetry').read_text().splitlines()[-1])
        self.assertEqual(record['failure_cause'], 'timeout')

    def test_interrupt_cleans_up(self):
        self.env['SCENARIO'] = 'hang'
        process = subprocess.Popen(['bash',str(ROOT/'codex-fast'),'--hcom','probe'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        while not (self.root/'count').exists() and process.poll() is None:
            time.sleep(.01)
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate()
        self.assertEqual(process.returncode, 130, stderr)
        self.assertEqual(stdout, '')
        self.assertEqual(self.calls()[-1], ['kill','delegate-test','--json'])

    def test_unsupported_flags_do_not_launch(self):
        for flag in (('--raw',),('--resume','last')):
            result = self.invoke('codex-fast',extra=flag)
            self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root/'calls').exists())


if __name__ == '__main__':
    unittest.main()
