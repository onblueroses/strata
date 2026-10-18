#!/usr/bin/env python3
"""Decode a hook event and tokenize text; never evaluate shell expressions."""
import io
import json
import re
import shlex
import sys


def dynamic(raw):
    quote = None
    escaped = False
    for char in raw:
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif char == quote:
            quote = None
        elif char in "'\"" and quote is None:
            quote = char
        elif char in "$`" and quote != "'":
            return "1"
    return "0"


def quote_state(raw, quote=None):
    """Scan raw from an open quote (or none); return (open quote, inside a comment)."""
    escaped = comment = False
    for char in raw:
        if comment:
            comment = char != "\n"
        elif escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif char == quote:
            quote = None
        elif char in "'\"" and quote is None:
            quote = char
        elif char == "#" and quote is None:
            comment = True
    return quote, comment


def shell_text(command):
    # A statically quoted heredoc is literal stdin data, not shell commands. Mask
    # only its body for tokenization; preserve positions and the original scan text.
    # The quote state carries across lines: a string opened on an earlier line closes on this
    # one, and judged alone its closing quote read as an opening one (2026-09-30).
    lines = command.splitlines(keepends=True)
    i, carry = 0, None
    while i < len(lines):
        pending = [m for m in re.finditer(r"(?<!<)<<(-?)[ \t]*(['\"])([A-Za-z_][A-Za-z0-9_]*)\2", lines[i])
                   if quote_state(lines[i][:m.start()], carry) == (None, False)]
        carry = quote_state(lines[i], carry)[0]
        i += 1
        for marker in pending:
            found = False
            while i < len(lines):
                line = lines[i]
                delimiter = line.rstrip("\r\n")
                if marker[1]:
                    delimiter = delimiter.lstrip("\t")
                lines[i] = "".join("\n" if c == "\n" else " " for c in line)
                i += 1
                if delimiter == marker[3]:
                    found = True
                    break
            if not found:
                raise ValueError("quoted heredoc has no closing delimiter")
    return "".join(lines)


def main():
    event = json.load(sys.stdin)
    command = event.get("tool_input", {}).get("command", "")
    cwd = event.get("cwd", "")
    session = event.get("session_id", "unknown")
    command = "" if command is None else command
    cwd = "" if cwd is None else cwd
    session = "unknown" if session is None else session
    if any(not isinstance(v, str) or "\0" in v for v in (command, cwd, session)):
        raise ValueError("hook fields must be strings without NUL")
    if len(command.encode()) > 1048576:
        raise ValueError("command exceeds the tokenizer bound")
    stream = io.StringIO(shell_text(command))
    punctuation = ";&|()<>\n"
    lexer = shlex.shlex(stream, posix=True, punctuation_chars=punctuation)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    words = []
    while True:
        # shlex reads one character ahead when a word meets punctuation. Its buffered
        # character belongs to the next token, not the raw quote context of this one.
        start = stream.tell() - len(lexer._pushback_chars)
        word = lexer.get_token()
        if word is None:
            break
        end = stream.tell() - len(lexer._pushback_chars)
        raw = command[start:end]
        operator = bool(word) and all(c in punctuation for c in word) and not any(c in raw for c in "'\"\\")
        flags = int(dynamic(raw)) | (2 if operator else 0)
        words.extend((word, str(flags)))
        if len(words) > 16384:
            raise ValueError("too many command tokens")
    fields = ["privacy-event-v2", str(len(words) // 2), command, cwd, session, *words]
    sys.stdout.buffer.write(("\0".join(fields) + "\0").encode())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, AttributeError, OSError) as error:
        print("privacy event could not be decoded: " + str(error), file=sys.stderr)
        sys.exit(3)
