"""Tests of platform/server, AC-30: importing `nock.server` builds no app.

The criterion is about a fresh interpreter, so the checks run one in a subprocess
(`PROBE_SCRIPT`). The probe makes every read of a file under a `grids/` folder
fail with an error of its own, and records each read it refused. It then imports
`nock.server`, looks for the name `app` in the module, and calls
`production_app()`.

Choices where the spec leaves room:

- The repository's `grids/` holds no file in a checkout, so the probe points
  `GRIDS_DIR` (`nock.catalogue`, and `nock.server` when it keeps a copy of the
  name) at a folder of the test with a `catalogue.json`, which `load_catalogue`
  reads first. The reads that must fail are those under that folder.
- "Fails with that read's error": `load_catalogue` may wrap the error it meets in
  its own, so the probe accepts the error itself or any error that has it in its
  `__cause__` or `__context__` chain.
- A read is a call of `open`, `io.open`, `Path.open`, `Path.read_text` or
  `Path.read_bytes`; a stat of the folder or of the index is not a read.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

PROBE_TIME_LIMIT_SECONDS = 120.0
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# Run with the folder to protect as its first argument. It prints one JSON object.
PROBE_SCRIPT = '''
import builtins
import io
import json
import os
import sys
from pathlib import Path

import nock.catalogue

grids_dir = Path(sys.argv[1]).resolve()
refused_reads = []
injected_errors = []


class GridsReadError(OSError):
    """The error of every read under the protected folder."""


def under_grids(target):
    if not isinstance(target, (str, bytes, os.PathLike)):
        return False
    return Path(os.fsdecode(target)).resolve().is_relative_to(grids_dir)


def refuse_if_under_grids(target):
    if under_grids(target):
        refused_reads.append(os.fsdecode(target))
        error = GridsReadError("grid read refused: " + os.fsdecode(target))
        injected_errors.append(error)
        raise error


real_open = builtins.open
real_path_open = Path.open
real_read_text = Path.read_text
real_read_bytes = Path.read_bytes


def guarded_open(file, *args, **kwargs):
    refuse_if_under_grids(file)
    return real_open(file, *args, **kwargs)


def guarded_path_open(self, *args, **kwargs):
    refuse_if_under_grids(self)
    return real_path_open(self, *args, **kwargs)


def guarded_read_text(self, *args, **kwargs):
    refuse_if_under_grids(self)
    return real_read_text(self, *args, **kwargs)


def guarded_read_bytes(self, *args, **kwargs):
    refuse_if_under_grids(self)
    return real_read_bytes(self, *args, **kwargs)


builtins.open = guarded_open
io.open = guarded_open
Path.open = guarded_path_open
Path.read_text = guarded_read_text
Path.read_bytes = guarded_read_bytes
nock.catalogue.GRIDS_DIR = grids_dir

report = {
    "import_error": None,
    "reads_at_import": [],
    "has_app": None,
    "production_app_error": None,
    "error_is_the_read_error": None,
    "reads_by_production_app": [],
}
try:
    import nock.server
except Exception as error:
    report["import_error"] = type(error).__name__ + ": " + str(error)
    print(json.dumps(report))
    sys.exit(0)

report["reads_at_import"] = list(refused_reads)
report["has_app"] = hasattr(nock.server, "app")
if hasattr(nock.server, "GRIDS_DIR"):
    nock.server.GRIDS_DIR = grids_dir
reads_before = len(refused_reads)
try:
    nock.server.production_app()
except Exception as error:
    report["production_app_error"] = type(error).__name__ + ": " + str(error)
    chain = []
    current = error
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    report["error_is_the_read_error"] = any(
        link in injected_errors for link in chain
    )
report["reads_by_production_app"] = refused_reads[reads_before:]
print(json.dumps(report))
'''


class ProbeReport(NamedTuple):
    """What the probe printed."""

    import_error: str | None
    reads_at_import: list[str]
    has_app: bool | None
    production_app_error: str | None
    error_is_the_read_error: bool | None
    reads_by_production_app: list[str]


@pytest.fixture(scope="module")
def probe_report(tmp_path_factory: pytest.TempPathFactory) -> ProbeReport:
    """Run the probe in a fresh interpreter, once; return its report."""
    grids_dir = tmp_path_factory.mktemp("probe") / "grids"
    grids_dir.mkdir()
    (grids_dir / "catalogue.json").write_text("[]", encoding="utf-8")
    environment = dict(os.environ)
    completed = subprocess.run(
        [sys.executable, "-c", PROBE_SCRIPT, str(grids_dir)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=PROBE_TIME_LIMIT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    fields = json.loads(completed.stdout.strip().splitlines()[-1])
    return ProbeReport(**fields)


def test_ac30_import_succeeds_and_reads_no_file_under_grids(
    probe_report: ProbeReport,
) -> None:
    assert probe_report.import_error is None
    assert probe_report.reads_at_import == []


def test_ac30_the_module_has_no_app_name(probe_report: ProbeReport) -> None:
    assert probe_report.import_error is None
    assert probe_report.has_app is False


def test_ac30_production_app_fails_with_the_error_of_the_failed_read(
    probe_report: ProbeReport,
) -> None:
    assert probe_report.import_error is None
    assert probe_report.production_app_error is not None, "production_app() built"
    assert (
        probe_report.error_is_the_read_error is True
    ), probe_report.production_app_error
    assert len(probe_report.reads_by_production_app) >= 1
