"""Tests for scripts/run_gate.py — the timestamped gate wrapper.

The 2026-10-05 evidence audit found that receipts across five tasks carried
`observed_at_utc` values with no source behind them: round minutes, sometimes
contradicted by the runner's own artifacts. This wrapper exists so a receipt can
only ever carry a stamp that was captured at execution time.

These tests drive the real command line in a subprocess. Unit-testing the
internal helpers would prove nothing about whether a timestamp can be forged
from the outside, which is the whole point of the tool.
"""
from __future__ import annotations

import ast
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_GATE = ROOT / "scripts" / "run_gate.py"


def date_u() -> datetime:
    """A real `date -u` capture, independent of the tool under test."""
    out = subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return datetime.strptime(out, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUN_GATE), *args], capture_output=True, text=True
    )


class RunGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "record.json"
        self.addCleanup(self.tmp.cleanup)

    def read(self) -> dict:
        return json.loads(self.out.read_text(encoding="utf-8"))

    # ---- the three properties the audit demanded ----------------------

    def test_timestamp_is_a_real_capture_not_a_rounded_value(self):
        """The stamp must fall inside a `date -u` bracket taken around the run."""
        before = date_u()
        proc = run_gate(
            "--name", "sleepy",
            "--out", str(self.out),
            "--", sys.executable, "-c", "import time; time.sleep(2)",
        )
        after = date_u()
        self.assertEqual(proc.returncode, 0, proc.stderr)

        stamp = datetime.strptime(
            self.read()["observed_at_utc"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        self.assertGreaterEqual(stamp, before, "stamp predates the bracket")
        self.assertLessEqual(stamp, after, "stamp postdates the bracket")
        # A rounded value would sit exactly on a :00 boundary for a 2s sleep.
        self.assertNotEqual(
            stamp.second, 0, "stamp landed exactly on a minute boundary — looks rounded"
        )

    def test_a_failing_gate_records_its_real_exit_code(self):
        """Non-zero must be reported honestly, not smoothed into success."""
        proc = run_gate(
            "--name", "deliberately-red",
            "--out", str(self.out),
            "--", sys.executable, "-c", "import sys; sys.exit(3)",
        )
        record = self.read()
        self.assertEqual(record["exit_code"], 3)
        self.assertFalse(record["ok"])
        # The tool must not report success for a red gate either.
        self.assertNotEqual(proc.returncode, 0)

    def test_a_gate_that_never_ran_produces_no_record(self):
        """A command that cannot be spawned must leave no evidence behind."""
        self.assertFalse(self.out.exists())
        proc = run_gate(
            "--name", "ghost",
            "--out", str(self.out),
            "--", "definitely-not-a-real-executable-xyz",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.out.exists(), "a record was written for a gate that never ran")

    # ---- a timestamp may never be supplied ----------------------------

    def test_a_timestamp_cannot_be_injected(self):
        for flag in ("--observed-at-utc", "--timestamp", "--at", "--time"):
            with self.subTest(flag=flag):
                out = Path(self.tmp.name) / f"{flag}.json"
                proc = run_gate(
                    "--name", "forged",
                    "--out", str(out),
                    flag, "2026-10-05T00:00:00Z",
                    "--", sys.executable, "-c", "print('x')",
                )
                self.assertNotEqual(proc.returncode, 0, f"{flag} was accepted")
                self.assertFalse(out.exists(), f"{flag} produced a record")

    def test_record_declares_where_its_timestamp_came_from(self):
        run_gate(
            "--name", "sourced",
            "--out", str(self.out),
            "--", sys.executable, "-c", "print('hello-from-gate')",
        )
        source = self.read()["observed_at_utc_source"]
        self.assertIn("date -u", source)
        self.assertNotIn("UNAVAILABLE", source)
        self.assertNotIn("DERIVED", source)

    # ---- record shape ------------------------------------------------

    def test_record_shape_matches_the_receipts(self):
        run_gate(
            "--name", "shaped",
            "--out", str(self.out),
            "--", sys.executable, "-c", "print('MARKER-4711')",
        )
        record = self.read()
        for key in ("gate", "command", "cwd", "exit_code", "ok",
                    "observed_at_utc", "observed_at_utc_source"):
            self.assertIn(key, record)
        # `command`, `cwd`, `exit_code` and the two timestamp fields are the
        # names the receipts already use for each test entry.
        receipt_keys = set(json.loads(
            (ROOT / "docs/task-evidence/F004-receipt.json").read_text(encoding="utf-8")
        )["tests"][0])
        for key in ("command", "cwd", "exit_code", "observed_at_utc", "observed_at_utc_source"):
            self.assertIn(key, receipt_keys, f"receipts do not use {key}")

    def test_summary_quotes_the_command_output_verbatim(self):
        run_gate(
            "--name", "echoing",
            "--out", str(self.out),
            "--", sys.executable, "-c", "print('MARKER-4711')",
        )
        record = self.read()
        self.assertIn("MARKER-4711", record["output_tail"])
        self.assertIn("MARKER-4711", record["summary"])

    def test_existing_runners_are_left_alone(self):
        """The wrapper must not rewire anything that already works.

        Checked against the parsed CODE, not the raw text: the module docstring
        legitimately *mentions* the Makefile and the runners to say it leaves
        them alone, and a substring search over the file would flag that prose
        as if it were a rewire.
        """
        tree = ast.parse(RUN_GATE.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                body = getattr(node, "body", [])
                if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant
                ) and isinstance(body[0].value.value, str):
                    docstrings.add(id(body[0].value))

        code_strings = [
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings
        ]
        imports = [
            (a.name if isinstance(n, ast.Import) else n.module or "")
            for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
            for a in n.names
        ]
        haystack = " ".join(code_strings + imports)
        for runner in ("local-tester", "e2e_ui", "Makefile", "vitest", "pytest"):
            self.assertNotIn(
                runner, haystack,
                f"{runner} appears in executable code; this tool must not rewire it",
            )

    def test_recorded_command_can_be_rerun_verbatim(self):
        """`command` must round-trip: quoting that loses an argument turns the
        record into something you cannot reproduce."""
        run_gate(
            "--name", "spaces",
            "--out", str(self.out),
            "--", sys.executable, "-c", "print('MARKER-4711')",
        )
        record = self.read()
        self.assertEqual(record["argv"][0], sys.executable)
        self.assertEqual(shlex.split(record["command"]), record["argv"])

    def test_a_silent_gate_is_recorded_honestly(self):
        """No output is not an error, and must not be dressed up as one."""
        run_gate(
            "--name", "silent",
            "--out", str(self.out),
            "--", sys.executable, "-c", "pass",
        )
        record = self.read()
        self.assertEqual(record["exit_code"], 0)
        self.assertTrue(record["ok"])
        self.assertEqual(record["summary"], "(no output)")
        self.assertEqual(record["output_tail"], "")

    def test_a_missing_command_is_still_a_usage_error(self):
        """--out became optional (records default to docs/evidence/gates/), but
        "no command to run" is still a refusal, not a silent success."""
        proc = run_gate("--name", "nowhere")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("command", proc.stderr.lower())


DURABLE_DIR = ROOT / "docs" / "evidence" / "gates"
IGNORED_DIR = ROOT / "scratch"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


class DurableRecordTests(unittest.TestCase):
    """A gate's record must outlive the process AND the working tree.

    F007 wrote its records to `scratch/gates/`, which `.gitignore` covers, so
    F003's and F007's receipts cite evidence a fresh checkout never sees. These
    tests pin the durability contract: the record lands in a versioned
    directory, the tool refuses a path git would ignore, and a gate that fails
    or never runs leaves nothing a reviewer could misread.
    """

    def setUp(self):
        # A unique name per test, so a default-path record from one test can
        # never be mistaken for another's.
        self.name = f"durability-{self.id().rsplit('.', 1)[-1]}-{os.getpid()}"
        self.record = DURABLE_DIR / f"{self.name}.json"
        for path in (self.record, DURABLE_DIR / f"{self.name}.log"):
            self.addCleanup(path.unlink, True)

    def read(self, path: Path | None = None) -> dict:
        return json.loads((path or self.record).read_text(encoding="utf-8"))

    # ---- the record is versioned, not scratch ------------------------

    def test_default_record_lands_where_git_would_keep_it(self):
        """No --out: the record goes to docs/evidence/gates/<name>.json and
        git can see it — untracked-but-listed, never ignored."""
        proc = run_gate("--name", self.name, "--",
                        sys.executable, "-c", "print('DURABLE-MARKER')")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.record.exists(), f"expected {self.record}")
        self.assertIn("DURABLE-MARKER", self.read()["output_tail"])

        # survives git check-ignore: exit 1 means "not ignored"
        ignored = git("check-ignore", "-q", "--", str(self.record))
        self.assertEqual(ignored.returncode, 1,
                         f"record is gitignored (check-ignore said: "
                         f"{git('check-ignore', '-v', '--', str(self.record)).stdout.strip()})")
        # and a reviewer running git status sees it
        listing = git("status", "--porcelain", "--", str(self.record))
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertIn(self.name, listing.stdout, "record is invisible to git status")

    def test_default_record_never_depends_on_the_ignored_scratch_tree(self):
        """Assert the record really exists first, so this cannot pass vacuously."""
        proc = run_gate("--name", self.name, "--", sys.executable, "-c", "print('x')")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.record.exists())
        self.assertNotIn(IGNORED_DIR.name, self.record.parts)
        self.assertEqual(self.record.parent, DURABLE_DIR)

    def test_the_record_shape_the_receipts_carry_is_unchanged(self):
        """Durability is additive: every field receipts already read survives."""
        run_gate("--name", self.name, "--", sys.executable, "-c", "print('x')")
        record = self.read()
        for key in ("gate", "command", "argv", "cwd", "exit_code", "ok",
                    "observed_at_utc", "observed_at_utc_source", "timestamp_status",
                    "summary", "output_tail"):
            self.assertIn(key, record)

    # ---- the negative cases ------------------------------------------

    def test_an_ignored_record_path_is_refused_and_writes_nothing(self):
        """Pointing the record at scratch/ is the bug this fixes: refuse it."""
        ignored_out = IGNORED_DIR / "gates" / f"{self.name}.json"
        proc = run_gate("--name", self.name, "--out", str(ignored_out), "--",
                        sys.executable, "-c", "print('x')")
        self.assertNotEqual(proc.returncode, 0, "an ignored record path was accepted")
        self.assertFalse(ignored_out.exists(), "a record was written to an ignored path")
        self.assertIn("ignore", proc.stderr.lower())

    def test_an_ignored_path_is_refused_before_the_gate_ever_runs(self):
        """Not merely "no record was written" - the child must never execute.

        The existing refusal test proves the absence of a record. This proves the
        ordering: a gate that would have written a sentinel must not have run at
        all, because the refusal happens before the spawn.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sentinel = Path(tmp.name) / "ran-anyway.txt"
        ignored_out = IGNORED_DIR / "gates" / f"{self.name}.json"
        proc = run_gate("--name", self.name, "--out", str(ignored_out), "--",
                        sys.executable, "-c",
                        f"open({str(sentinel)!r}, 'w').write('x')")
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(sentinel.exists(),
                         "the gate ran even though its record path was refused")

    def test_a_failing_gate_records_its_real_failure_in_the_durable_tree(self):
        """A red gate must still leave an honest record — never a green one."""
        proc = run_gate("--name", self.name, "--",
                        sys.executable, "-c", "import sys; sys.exit(7)")
        self.assertEqual(proc.returncode, 7, proc.stderr)
        record = self.read()
        self.assertEqual(record["exit_code"], 7)
        self.assertFalse(record["ok"])

    def test_a_gate_that_never_ran_leaves_no_durable_record(self):
        proc = run_gate("--name", self.name, "--", "definitely-not-a-real-executable-xyz")
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.record.exists(), "a record was written for a gate that never ran")
        self.assertFalse((DURABLE_DIR / f"{self.name}.log").exists(),
                         "an output log was written for a gate that never ran")

    # ---- the truncated tail must not imply completeness ---------------

    def test_long_output_is_marked_truncated_and_kept_in_full_beside_the_record(self):
        """`output_tail` caps at 2 KB. The record must say so, and the text the
        cap dropped must still be readable beside it."""
        run_gate("--name", self.name, "--", sys.executable, "-c",
                 "print('HEAD-OF-OUTPUT'); print('z' * 5000); print('TAIL-OF-OUTPUT')")
        record = self.read()
        tail = record["output_tail"]
        self.assertLessEqual(len(tail), 2000)
        self.assertTrue(record["output_truncated"],
                        "a capped tail was presented without saying it was capped")
        self.assertGreater(record["output_chars"], len(tail),
                           "output_chars must count the real output, not the capped tail")
        # this is the text the cap dropped, so it must NOT be in the tail ...
        self.assertNotIn("HEAD-OF-OUTPUT", tail)
        # ... and it must be readable next to the record.
        log = DURABLE_DIR / f"{self.name}.log"
        full = log.read_text(encoding="utf-8")
        self.assertIn("HEAD-OF-OUTPUT", full)
        self.assertIn("TAIL-OF-OUTPUT", full)
        self.assertEqual(record["output_log"],
                         str(log.relative_to(ROOT)).replace(chr(92), "/"))

    def test_short_output_needs_no_sidecar_log(self):
        run_gate("--name", self.name, "--", sys.executable, "-c", "print('short')")
        record = self.read()
        self.assertFalse(record["output_truncated"])
        self.assertIsNone(record["output_log"])
        self.assertFalse((DURABLE_DIR / f"{self.name}.log").exists())


# 0x9D is a UTF-8 continuation byte AND undefined in cp1252, so it is undecodable
# under EITHER codec. That makes it the portable reproducer: the bug reproduces on
# a UTF-8 host and on this cp1252 host alike. Built from byte values, with no
# backslash escapes, so the child program cannot be mangled in transit.
UNDECODABLE_BYTE = 0x9D

BAD_BYTE_CHILD = (
    "import sys;"
    "b = sys.stdout.buffer;"
    "b.write(b'BEFORE-MARKER' + bytes([10]));"
    f"b.write(bytes([{UNDECODABLE_BYTE}]));"
    "b.write(b'AFTER-MARKER' + bytes([10]));"
    "b.flush()"
)

ARROW = chr(0x2192)  # non-ASCII, so a wrong codec shows up as mojibake
MIXED_STREAM_CHILD = (
    "import sys;"
    "o = sys.stdout.buffer; e = sys.stderr.buffer;"
    f"o.write(('ARROW ' + chr(0x2192) + ' 4711 passed').encode('utf-8') + bytes([10]));"
    "e.write(b'STDERR-MARKER' + bytes([10]));"
    f"e.write(bytes([{UNDECODABLE_BYTE}]));"
    "e.write(b'TAIL-MARKER' + bytes([10]));"
    "o.flush(); e.flush()"
)


class CaptureRobustnessTests(unittest.TestCase):
    """A record must never claim a gate was silent when capture actually failed.

    The defect this pins: `subprocess.run(..., text=True)` decodes in a reader
    THREAD using the host locale. One undecodable byte kills that thread, and
    `subprocess` still returns a CompletedProcess whose streams are empty - so
    the record was written claiming "no output" for a gate that printed plenty.
    A receipt citing such a record points at nothing at all.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "record.json"
        self.addCleanup(self.tmp.cleanup)

    def read(self) -> dict:
        return json.loads(self.out.read_text(encoding="utf-8"))

    def run_child(self, name: str, source: str) -> dict:
        proc = run_gate("--name", name, "--out", str(self.out), "--",
                        sys.executable, "-c", source)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return self.read()

    def test_the_reproducer_byte_is_undecodable_in_both_codecs(self):
        """If this ever stops being true the reproducer is not portable, and the
        tests below would pass on a UTF-8 CI host for the wrong reason."""
        raw = bytes([UNDECODABLE_BYTE])
        for encoding in ("utf-8", "cp1252"):
            with self.subTest(encoding=encoding):
                with self.assertRaises(UnicodeDecodeError):
                    raw.decode(encoding)

    def test_undecodable_output_still_produces_the_real_text(self):
        """The whole point: a bad byte must not cost us the evidence."""
        record = self.run_child("badbyte", BAD_BYTE_CHILD)
        self.assertIn("BEFORE-MARKER", record["output_tail"],
                      "output before the undecodable byte was lost")
        self.assertIn("AFTER-MARKER", record["output_tail"],
                      "output after the undecodable byte was lost")
        self.assertGreater(record["output_chars"], 0)
        self.assertNotEqual(record["summary"], "(no output)")

    def test_printed_nothing_and_capture_failed_are_not_the_same_fact(self):
        """A record that says EMPTY must mean zero bytes really arrived."""
        silent = self.run_child("silent", "pass")
        noisy = self.run_child("badbyte", BAD_BYTE_CHILD)
        self.assertEqual(silent["output_capture"], "EMPTY")
        self.assertEqual(silent["output_chars"], 0)
        # The gate that DID print must not be filed beside the silent one.
        self.assertEqual(noisy["output_capture"], "CAPTURED")
        self.assertGreater(noisy["output_chars"], 0)

    def test_the_record_declares_the_encoding_that_produced_its_text(self):
        clean = self.run_child("clean", "print('hello')")
        self.assertEqual(clean["output_encoding"], "utf-8")
        self.assertFalse(clean["output_decode_lossy"])
        self.assertEqual(clean["output_undecodable"], 0)

        lossy = self.run_child("badbyte", BAD_BYTE_CHILD)
        self.assertTrue(lossy["output_decode_lossy"],
                        "a lossy decode was not disclosed")
        self.assertGreaterEqual(lossy["output_undecodable"], 1)
        self.assertNotEqual(lossy["output_encoding"], "utf-8")

    def test_bytes_and_characters_are_both_counted(self):
        """output_chars alone cannot be reconciled without the byte count."""
        record = self.run_child("ascii", "print('MARKER-4711')")
        self.assertEqual(record["output_bytes"], record["output_chars"],
                         "an all-ASCII gate must have equal byte and char counts")
        self.assertEqual(record["output_tail"].strip(), "MARKER-4711")

    def test_the_gate_exit_code_is_mirrored_under_a_narrow_console(self):
        """Regression, and it was found by running this suite the wrong way.

        A lossy decode put U+FFFD in the summary; printing it to a cp1252 console
        raised UnicodeEncodeError AFTER the record was written, so the wrapper
        exited 1 instead of the gate's own code. PYTHONIOENCODING is pinned so
        this cannot pass vacuously on a UTF-8 test host.
        """
        child = BAD_BYTE_CHILD.replace("b.flush()", "b.flush(); sys.exit(4)")
        env = dict(os.environ)
        env.pop("PYTHONUTF8", None)
        env["PYTHONIOENCODING"] = "cp1252"
        proc = subprocess.run(
            [sys.executable, str(RUN_GATE), "--name", "narrow", "--out", str(self.out),
             "--", sys.executable, "-c", child],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(proc.returncode, 4,
                         f"wrapper did not mirror the gate's exit code: {proc.stderr[-400:]}")
        self.assertEqual(self.read()["exit_code"], 4)

    def test_a_bad_byte_in_one_stream_does_not_corrupt_the_other(self):
        """Measured, not assumed: decoding stdout+stderr as one blob let stderr's
        single bad byte push stdout's good UTF-8 through the fallback codec, and
        the arrow came out as mojibake."""
        record = self.run_child("mixed", MIXED_STREAM_CHILD)
        self.assertIn(ARROW, record["output_tail"],
                      "clean stdout was corrupted by the other stream's bad byte")
        self.assertIn("STDERR-MARKER", record["output_tail"])
        self.assertIn("TAIL-MARKER", record["output_tail"])
        self.assertEqual(record["output_encoding"], "mixed",
                         "two different codecs must be reported as mixed, not as one")
        self.assertEqual(record["output_undecodable"], 1)

    def test_a_stale_sidecar_log_is_removed_when_a_later_run_is_shorter(self):
        """A log left beside a record that names no log is a misleading artifact."""
        log = self.out.with_suffix(".log")
        run_gate("--name", "stale", "--out", str(self.out), "--", sys.executable, "-c",
                 "print('HEAD-OF-OUTPUT'); print('z' * 5000); print('TAIL-OF-OUTPUT')")
        self.assertTrue(log.exists(), "the long run should have written a sidecar log")
        self.assertIsNotNone(self.read()["output_log"])

        run_gate("--name", "stale", "--out", str(self.out), "--",
                 sys.executable, "-c", "print('short')")
        record = self.read()
        self.assertFalse(record["output_truncated"])
        self.assertIsNone(record["output_log"])
        self.assertFalse(log.exists(),
                         "a stale log survived and would be read as this run's evidence")


GATE_RECORD_KEYS = {"gate", "argv", "command", "timestamp_status", "output_chars"}


class GateRecordAuditTests(unittest.TestCase):
    """The records already on disk must not contradict themselves.

    A record is a pointer. If it points at output it does not have, or at a log
    nobody can open, then every receipt citing it points at nothing while still
    looking healthy - the exact failure this wrapper exists to prevent.
    """

    def records(self):
        for path in sorted(DURABLE_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if GATE_RECORD_KEYS <= set(data):
                yield path, data

    def test_no_record_claims_truncation_without_readable_output(self):
        seen = 0
        for path, record in self.records():
            seen += 1
            with self.subTest(record=path.name):
                if record["output_truncated"]:
                    self.assertIsNotNone(record["output_log"],
                                         "truncated, yet no log is named")
                    self.assertTrue((ROOT / record["output_log"]).exists(),
                                    f"{record['output_log']} is named but missing on disk")
                if record["output_chars"] > 0:
                    self.assertNotEqual(record["output_tail"], "",
                                        "record counts characters but stores no text")
        self.assertGreater(seen, 0, "no gate records found; the audit proved nothing")

    def test_a_log_attached_outside_the_cap_must_declare_itself(self):
        """A log beside a record that was never truncated is not the tool's doing.

        One such record exists (U001 attached its transcript by hand). It must say
        so, so a reviewer is not left assuming the cap produced it.
        """
        for path, record in self.records():
            if record["output_log"] and not record["output_truncated"]:
                with self.subTest(record=path.name):
                    self.assertIn("record_note", record,
                                  "attaches a log without declaring why")
                    self.assertTrue((ROOT / record["output_log"]).exists())


if __name__ == "__main__":
    unittest.main()