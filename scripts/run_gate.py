#!/usr/bin/env python3
"""Run one verification gate and record what actually happened.

The 2026-10-05 evidence audit of docs/task-evidence/ found that five task
receipts carried `observed_at_utc` values with nothing behind them: round
minutes invented after the fact, three of them contradicted by the runner's own
artifacts. This wrapper removes the opportunity. A gate stamp can only come
from a capture taken at the moment the command was spawned, and there is
deliberately no option to supply one.

    python scripts/run_gate.py --name frontend --out <record>.json -- \\
        npm --prefix app/g6/frontend test

`--out` is optional. Omit it and the record goes to
`docs/evidence/gates/<name>.json`, which git tracks. That default exists because
F003 and F007 wrote their records under `scratch/`, which `.gitignore` covers:
the receipts cited evidence a fresh checkout never sees. `docs/evidence/` is
where AGENTS.md already asks for durable run evidence.

The directory is ACCUMULATED, not per-task: one `docs/evidence/gates/` holds
every task's records, named `<task>-<gate>.json`, so re-running a gate replaces
that gate's record rather than accumulating near-duplicates. A receipt pins the
run it cites by its timestamp, so the newest record for a gate name is the one
a reader should trust.

A record path git would ignore is REFUSED (exit 4) before the gate runs. Running
a gate whose output has nowhere durable to land would produce exactly the
evidence a reviewer cannot check, so the tool declines instead.

`output_tail` is capped at 2 KB for readability. The record says so
(`output_truncated`, `output_chars`), and when the cap bites the complete text
is written to `<record>.log` and named in `output_log`. A run that is NOT
truncated removes any log left by an earlier run under the same name, so a
sidecar file can never be read as evidence for a record that names no log.

OUTPUT IS CAPTURED AS BYTES AND DECODED HERE, never in a `subprocess` reader
thread. `text=True` decodes with the host locale, in a thread whose death
`subprocess` does not report: one undecodable byte produced a CompletedProcess
with empty streams, and the record was written claiming the gate had printed
nothing. A receipt citing that record points at nothing, while looking perfectly
healthy. So the record now distinguishes:

  output_capture   EMPTY when zero bytes arrived, CAPTURED otherwise. EMPTY is
                   therefore a PROVABLE claim that the gate was silent. A capture
                   failure writes no record at all (exit 3), so the two can never
                   be conflated.
  output_bytes     how many bytes actually arrived.
  output_encoding  which codec produced the stored text.
  output_decode_lossy / output_undecodable
                   whether decoding was clean, and how many characters had to be
                   replaced. A lossy decode is disclosed, never smoothed over.

The record uses the same field names the receipts already use for each test
entry: `command`, `cwd`, `exit_code`, `observed_at_utc`,
`observed_at_utc_source`.

This tool runs one command and writes one record. It does not rewire any
existing runner, and the Makefile's blocking set is untouched.

Windows note: a relative executable path containing forward slashes
(`.venv/Scripts/python.exe`) cannot be spawned — CreateProcess resolves it
through PATH, not the working directory, and reports WinError 2. Use
backslashes (`.venv\\Scripts\\python.exe`) or a bare command already on PATH
(`python`). The command is deliberately NOT rewritten to work around this:
silently changing what was asked for would make the record's `command` field
disagree with the operator's intent, which is the class of dishonesty this
tool exists to prevent. A command that cannot be spawned yields no record and
exit 3.

Exit codes: the gate's own exit code is mirrored, so a red gate can never be
mistaken for a green one; 2 for a usage error; 3 when no record could be
written (the command could not be spawned at all).
"""
from __future__ import annotations

import argparse
import json
import locale
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
EXIT_USAGE = 2
EXIT_NO_RECORD = 3
EXIT_IGNORED_RECORD_PATH = 4

REPO_ROOT = Path(__file__).resolve().parents[1]
DURABLE_RECORDS = REPO_ROOT / "docs" / "evidence" / "gates"
TAIL_LIMIT = 2000


def _console_safe() -> None:
    """Stop the tool's own reporting from depending on the host's codec.

    A lossy decode can legitimately put U+FFFD in `summary`. Printing that to a
    cp1252 console raises UnicodeEncodeError AFTER the record was already
    written, so the wrapper died with the wrong exit code and stopped mirroring
    the gate. Reporting must never be the thing that fails.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def decode_capture(*streams: bytes) -> tuple[str, str, int]:
    """Decode each captured stream on its own, without trusting the host locale.

    Returns (text, encoding, undecodable).

    UTF-8 is tried strictly first because that is what every runner in this
    repository emits, and a strict decode is also the proof that those bytes
    arrived whole. A stream that fails falls back to the locale encoding with
    replacement, and the record then names the codec and counts what it had to
    invent. A record must never imply clean text it did not get.

    Decoding per stream rather than on stdout+stderr concatenated is deliberate:
    concatenating first lets one bad byte in stderr push the other stream's
    perfectly good UTF-8 through the fallback codec, turning real output into
    mojibake. That was measured, not assumed.
    """
    texts: list[str] = []
    encodings: list[str] = []
    undecodable = 0
    for raw in streams:
        if not raw:
            continue
        try:
            texts.append(raw.decode("utf-8"))
            encodings.append("utf-8")
        except UnicodeDecodeError:
            fallback = locale.getencoding() or "utf-8"
            text = raw.decode(fallback, errors="replace")
            texts.append(text)
            encodings.append(fallback)
            undecodable += text.count("�")
    if not encodings:
        label = "none"
    elif len(set(encodings)) == 1:
        label = encodings[0]
    else:
        label = "mixed"
    return "".join(texts), label, undecodable


def capture_utc() -> tuple[str, str]:
    """Return (stamp, source) captured now, never supplied from outside.

    `date -u` is used so the recorded value is the same observable the audit
    checked receipts against. If it is unavailable the fallback is recorded as
    such rather than presented as a `date -u` capture.
    """
    try:
        out = subprocess.run(
            ["date", "-u", "+" + STAMP_FORMAT],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if out:
            return out, f"captured by `date -u +{STAMP_FORMAT}` at spawn time"
    except (OSError, subprocess.CalledProcessError):
        pass
    now = datetime.now(timezone.utc).strftime(STAMP_FORMAT)
    return now, "captured by datetime.now(timezone.utc) at spawn time (`date -u` unavailable)"


def is_gitignored(path: Path) -> bool | None:
    """True when git would ignore `path`; None when git cannot answer.

    Asking git is the only honest test. Reading .gitignore by hand would miss
    nested .gitignore files and any global/exclude rules.
    """
    proc = subprocess.run(
        ["git", "check-ignore", "-q", "--", str(path)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode == 0:
        return True
    # 1 = "not ignored". Anything else means git could not answer (not a work
    # tree, git missing); the record then says UNVERIFIED rather than claiming
    # a check that never happened.
    return False if proc.returncode == 1 else None


def repo_relative(path: Path) -> str:
    """A path a receipt can cite: repo-relative, forward slashes."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def summarise(text: str) -> str:
    """A short, honest digest of real output — never an invented verdict."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "(no output)"
    for line in reversed(lines):
        if any(token in line for token in ("passed", "failed", "error", "OK", "match", "built")):
            return line[:200]
    return lines[-1][:200]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one verification gate and write a machine-readable record.",
    )
    parser.add_argument("--name", required=True, help="gate name recorded in the record")
    parser.add_argument("--out", type=Path, default=None,
                        help="record path; default docs/evidence/gates/<name>.json")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="-- followed by the command to run")
    _console_safe()
    args = parser.parse_args(argv)

    argv_command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not argv_command:
        parser.error("no command given; pass it after --")

    # Decide where the record lands, and refuse before running anything: a gate
    # whose output has nowhere durable to go is evidence nobody can check.
    out = args.out if args.out is not None else DURABLE_RECORDS / f"{args.name}.json"
    ignored = is_gitignored(out.resolve())
    if ignored:
        print(
            f"NO RECORD: {out} is git-ignored, so no reviewer could read this"
            f" gate's evidence. Write it somewhere git tracks (default:"
            f" {repo_relative(DURABLE_RECORDS)}).",
            file=sys.stderr,
        )
        return EXIT_IGNORED_RECORD_PATH

    # Stamp immediately before the spawn, so the value describes this run.
    stamp, source = capture_utc()

    try:
        # No text=True: decoding happens here, so it cannot fail silently in a
        # reader thread that subprocess never checks.
        completed = subprocess.run(argv_command, capture_output=True)
    except (OSError, ValueError) as exc:
        # Nothing ran, so nothing may be recorded. An invented exit code here
        # would be exactly the failure this tool exists to prevent.
        print(f"NO RECORD: could not run {argv_command!r}: {exc}", file=sys.stderr)
        return EXIT_NO_RECORD

    out_bytes, err_bytes = completed.stdout or b"", completed.stderr or b""
    combined, encoding, undecodable = decode_capture(out_bytes, err_bytes)
    stripped = combined.strip()
    tail = stripped[-TAIL_LIMIT:]
    truncated = len(tail) < len(stripped)
    log_path = out.with_suffix(".log")
    record = {
        "gate": args.name,
        # shlex.join quotes only what needs quoting, so a simple command reads
        # exactly as typed while `-k "a and b"` stays re-parseable. A record you
        # cannot faithfully re-run is not evidence. `argv` remains authoritative.
        "command": shlex.join(argv_command),
        "argv": argv_command,
        "cwd": str(Path.cwd()),
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
        "observed_at_utc": stamp,
        "observed_at_utc_source": source,
        "timestamp_status": "CAPTURED",
        "summary": summarise(combined),
        # The tail is a convenience, not the evidence: say how long the
        # real output was, and whether the cap dropped anything.
        "output_tail": tail,
        "output_chars": len(combined),
        "output_truncated": truncated,
        # EMPTY is now a provable statement that the gate printed nothing,
        # because capture is byte-exact. A capture failure writes no record.
        "output_capture": "EMPTY" if not (out_bytes or err_bytes) else "CAPTURED",
        "output_bytes": len(out_bytes) + len(err_bytes),
        "output_encoding": encoding,
        "output_decode_lossy": undecodable > 0,
        "output_undecodable": undecodable,
        "output_log": repo_relative(log_path) if truncated else None,
        "durability": ("UNVERIFIED: git check-ignore could not answer"
                       if ignored is None else "VERSIONED"),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    # Sidecar FIRST. A record names its log, so the log has to exist before the
    # record does; written the other way round, a failure in between leaves a
    # record citing a file nobody can open.
    if truncated:
        log_path.write_text(combined, encoding="utf-8")
    elif log_path.exists():
        # Left over from an earlier, longer run of this same gate. A reviewer
        # would read it as this run's evidence, and it is not.
        log_path.unlink()
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{args.name}: exit {completed.returncode} — {record['summary']}")
    print(f"recorded at {stamp} -> {repo_relative(out)}")
    # Mirror the gate so a red gate never reads as success.
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
