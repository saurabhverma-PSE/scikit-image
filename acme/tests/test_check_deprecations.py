"""Focused tests for the deprecation-governance checker.

Repositories created here are temporary. The real checkout, including
``poc/first-contribution-workflow`` and the ACME-142 feature branch, is only
read.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REAL_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REAL_ROOT / "acme" / "tools" / "check_deprecations.py"
ACME_142_HEAD = "cursor/acme-142-threshold-triangle-n-bins-07bf"
INTEGRATION_BASE = "poc/first-contribution-workflow"

VERSION_PY = '''\
"""Package version."""

__version__ = "0.27.0rc2.dev0"
'''


def _todo(sections: dict[str, str]) -> str:
    parts = ["Release manager notes.", ""]
    for version, body in sections.items():
        heading = f"Version {version}"
        parts.extend([heading, "-" * len(heading), body.rstrip(), ""])
    return "\n".join(parts)


def _run_checker(repo: Path, base_ref: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--base-ref", base_ref],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


class TemporaryRepo:
    """Small Git repository used as a checker fixture."""

    def __init__(self, path: Path) -> None:
        self.path = path
        completed = _git(path, "init", "-b", "main")
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)

    def write(self, relative: str, text: str) -> None:
        destination = self.path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> None:
        add = _git(self.path, "add", "-A")
        if add.returncode != 0:
            raise AssertionError(add.stderr)
        completed = _git(
            self.path,
            "-c",
            "user.email=dev@example.com",
            "-c",
            "user.name=Acme Dev",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            message,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)

    def branch(self, name: str) -> None:
        completed = _git(self.path, "branch", name)
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)


def _seed(repo: TemporaryRepo, todo: str, *modules: tuple[str, str]) -> None:
    repo.write("src/skimage/__init__.py", VERSION_PY)
    repo.write("TODO.txt", todo)
    for path, source in modules:
        repo.write(path, source)
    repo.commit("base")
    repo.branch("baseline")


def _passing_todo() -> str:
    return _todo(
        {
            "0.29": (
                "* Remove all traces of deprecated parameter `nbins` in\n"
                "  `skimage.filters.threshold_triangle`."
            )
        }
    )


@pytest.fixture
def repo(tmp_path: Path) -> TemporaryRepo:
    return TemporaryRepo(tmp_path)


def test_passing_decorator(repo: TemporaryRepo) -> None:
    path = "src/_skimage2/filters/thresholding.py"
    _seed(
        repo,
        _passing_todo(),
        (path, "def threshold_triangle(image):\n    return image\n"),
    )
    repo.write(
        path,
        '''\
@deprecate_parameter("nbins", new_name="n_bins", start_version="0.27", stop_version="0.29")
def threshold_triangle(image, nbins=None, *, n_bins=256):
    return n_bins
''',
    )
    repo.commit("add deprecation")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "deprecation governance check passed" in completed.stdout


def test_multiline_decorator_passes(repo: TemporaryRepo) -> None:
    path = "src/_skimage2/filters/thresholding.py"
    _seed(
        repo,
        _passing_todo(),
        (path, "def threshold_triangle(image):\n    return image\n"),
    )
    repo.write(
        path,
        '''\
@deprecate_parameter(
    deprecated_name="nbins",
    new_name="n_bins",
    start_version="0.27",
    stop_version="0.29",
)
def threshold_triangle(image, nbins=None, *, n_bins=256):
    """Triangle threshold."""
    return n_bins
''',
    )
    repo.commit("add multiline deprecation")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_wrong_start_version_reports_location(repo: TemporaryRepo) -> None:
    path = "src/skimage/filters/thresholding.py"
    _seed(
        repo,
        _passing_todo(),
        (path, "def threshold_triangle(image):\n    return image\n"),
    )
    repo.write(
        path,
        '''\
"""Public threshold."""
@deprecate_parameter(
    "nbins",
    new_name="n_bins",
    start_version="0.26",
    stop_version="0.29",
)
def threshold_triangle(image):
    return image
''',
    )
    repo.commit("wrong start")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode != 0
    assert (
        f"{path}:2: parameter 'nbins': start_version '0.26' does not match "
        "the repository version 0.27"
    ) in completed.stdout


def test_missing_todo_section(repo: TemporaryRepo) -> None:
    path = "src/_skimage2/filters/thresholding.py"
    _seed(repo, _todo({"0.28": "* Remove `num_threads`."}), (path, "x = 1\n"))
    repo.write(
        path,
        '''\
@deprecate_parameter("nbins", start_version="0.27", stop_version="0.30")
def threshold_triangle(image):
    return image
''',
    )
    repo.commit("missing section")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode != 0
    assert "parameter 'nbins'" in completed.stdout
    assert (
        "stop_version '0.30' has no matching 'Version 0.30' section" in completed.stdout
    )
    assert f"{path}:1:" in completed.stdout


def test_todo_section_must_mention_parameter_in_backticks(repo: TemporaryRepo) -> None:
    path = "src/_skimage2/filters/thresholding.py"
    _seed(
        repo,
        _todo({"0.29": "* Remove the nbins parameter from threshold_triangle."}),
        (path, "x = 1\n"),
    )
    repo.write(
        path,
        '''\
@deprecate_parameter("nbins", start_version="0.27", stop_version="0.29")
def threshold_triangle(image):
    return image
''',
    )
    repo.commit("todo without backticks")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode != 0
    assert "parameter 'nbins'" in completed.stdout
    assert "does not mention `nbins` in backticks" in completed.stdout


def test_dynamic_start_version_fails(repo: TemporaryRepo) -> None:
    path = "src/_skimage2/filters/thresholding.py"
    _seed(repo, _passing_todo(), (path, "x = 1\n"))
    repo.write(
        path,
        '''\
START_VERSION = "0.27"

@deprecate_parameter("nbins", start_version=START_VERSION, stop_version="0.29")
def threshold_triangle(image):
    return image
''',
    )
    repo.commit("dynamic start")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode != 0
    assert f"{path}:3: parameter 'nbins':" in completed.stdout
    assert "start_version is unsupported or dynamically computed" in completed.stdout


def test_dynamic_parameter_name_fails(repo: TemporaryRepo) -> None:
    path = "src/_skimage2/filters/thresholding.py"
    _seed(repo, _passing_todo(), (path, "x = 1\n"))
    repo.write(
        path,
        '''\
name = "nbins"

@deprecate_parameter(name, start_version="0.27", stop_version="0.29")
def threshold_triangle(image):
    return image
''',
    )
    repo.commit("dynamic name")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode != 0
    assert f"{path}:3: parameter <unknown>:" in completed.stdout
    assert (
        "deprecated parameter name is unsupported or dynamically computed"
        in completed.stdout
    )


def test_unchanged_legacy_decorator_in_modified_file_is_ignored(
    repo: TemporaryRepo,
) -> None:
    path = "src/_skimage2/restoration/_rolling_ball.py"
    legacy = '''\
@deprecate_parameter("num_threads", new_name="workers", start_version="0.26", stop_version="0.28")
def rolling_ball(image, num_threads=None, *, workers=None):
    return image
'''
    _seed(repo, _todo({"0.28": "* Remove something else."}), (path, legacy))
    repo.write(
        path,
        legacy
        + '''\

def helper(image):
    return image
''',
    )
    repo.commit("touch legacy module")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_modified_legacy_decorator_is_checked(repo: TemporaryRepo) -> None:
    path = "src/_skimage2/restoration/_rolling_ball.py"
    _seed(
        repo,
        _todo({"0.28": "* Unrelated."}),
        (
            path,
            '''\
@deprecate_parameter("num_threads", start_version="0.26", stop_version="0.28")
def rolling_ball():
    return 0
''',
        ),
    )
    repo.write(
        path,
        '''\
@deprecate_parameter("num_threads", start_version="0.26", stop_version="0.30")
def rolling_ball():
    return 0
''',
    )
    repo.commit("change stop version")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode != 0
    assert "parameter 'num_threads'" in completed.stdout
    assert "start_version '0.26'" in completed.stdout


def test_legacy_decorator_in_untouched_file_is_ignored(repo: TemporaryRepo) -> None:
    legacy = "src/_skimage2/restoration/_cycle_spin.py"
    added = "src/_skimage2/filters/thresholding.py"
    _seed(
        repo,
        _passing_todo(),
        (
            legacy,
            '''\
@deprecate_parameter("num_workers", start_version="0.10", stop_version="0.12")
def cycle_spin(x):
    return x
''',
        ),
        (added, "def threshold_triangle(image):\n    return image\n"),
    )
    repo.write(
        added,
        '''\
@deprecate_parameter("nbins", new_name="n_bins", start_version="0.27", stop_version="0.29")
def threshold_triangle(image, *, n_bins=256):
    return n_bins
''',
    )
    repo.commit("add governed deprecation")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "num_workers" not in completed.stdout


def test_renamed_file_does_not_flag_unchanged_legacy_decorator(
    repo: TemporaryRepo,
) -> None:
    source = "src/_skimage2/restoration/old_name.py"
    destination = "src/_skimage2/restoration/new_name.py"
    legacy = '''\
@deprecate_parameter("num_threads", start_version="0.26", stop_version="0.28")
def rolling_ball():
    return 0
'''
    _seed(repo, _todo({"0.28": "* Unrelated."}), (source, legacy))
    move = _git(repo.path, "mv", source, destination)
    assert move.returncode == 0, move.stderr
    repo.commit("rename module")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_both_package_trees_are_inspected(repo: TemporaryRepo) -> None:
    skimage = "src/skimage/filters/thresholding.py"
    skimage2 = "src/_skimage2/filters/thresholding.py"
    bad = '''\
@deprecate_parameter("nbins", start_version="0.20", stop_version="0.29")
def threshold_triangle():
    return 0
'''
    _seed(
        repo,
        _passing_todo(),
        (skimage, "x = 1\n"),
        (skimage2, "x = 1\n"),
    )
    repo.write(skimage, bad)
    repo.write(skimage2, bad)
    repo.commit("bad decorators in both trees")

    completed = _run_checker(repo.path, "baseline")

    assert completed.returncode != 0
    assert f"{skimage}:1: parameter 'nbins':" in completed.stdout
    assert f"{skimage2}:1: parameter 'nbins':" in completed.stdout


def test_missing_base_ref_is_an_inspection_failure(repo: TemporaryRepo) -> None:
    _seed(repo, _passing_todo(), ("src/_skimage2/filters/thresholding.py", "x = 1\n"))

    completed = _run_checker(repo.path, "does-not-exist")

    assert completed.returncode != 0
    assert "unable to inspect diff" in completed.stdout
    assert "deprecation governance check failed" in completed.stdout


def test_acme_142_passes_against_integration_branch(tmp_path: Path) -> None:
    """Copy ACME-142 and the integration branch into a throwaway repository."""
    head_ok = _git(REAL_ROOT, "rev-parse", "--verify", "--quiet", ACME_142_HEAD)
    base_ok = _git(REAL_ROOT, "rev-parse", "--verify", "--quiet", INTEGRATION_BASE)
    if head_ok.returncode != 0 or base_ok.returncode != 0:
        pytest.fail(
            "ACME-142 demonstration needs local refs "
            f"{ACME_142_HEAD!r} and {INTEGRATION_BASE!r}"
        )

    changed = _git(
        REAL_ROOT,
        "diff",
        "--name-only",
        f"{INTEGRATION_BASE}...{ACME_142_HEAD}",
    )
    assert changed.returncode == 0, changed.stderr
    paths = set(changed.stdout.splitlines())
    paths.update(["src/skimage/__init__.py", "TODO.txt"])

    repo = TemporaryRepo(tmp_path)
    _materialize(repo, INTEGRATION_BASE, paths)
    repo.commit("integration branch snapshot")
    repo.branch(INTEGRATION_BASE)
    _materialize(repo, ACME_142_HEAD, paths)
    repo.commit("acme-142 snapshot")

    target = repo.path / "src/_skimage2/filters/thresholding.py"
    source = target.read_text(encoding="utf-8")
    assert "@deprecate_parameter(" in source
    assert "start_version='0.27'" in source
    assert "`nbins`" in (repo.path / "TODO.txt").read_text(encoding="utf-8")

    completed = _run_checker(repo.path, INTEGRATION_BASE)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "deprecation governance check passed" in completed.stdout

    # The same snapshot must fail if the new decorator's start version drifts,
    # which shows the pass above inspected this decorator rather than an empty diff.
    target.write_text(source.replace("start_version='0.27'", "start_version='0.26'", 1))
    repo.commit("drift start version")
    failed = _run_checker(repo.path, INTEGRATION_BASE)
    assert failed.returncode != 0
    assert "parameter 'nbins'" in failed.stdout
    assert "start_version '0.26'" in failed.stdout


def _materialize(repo: TemporaryRepo, ref: str, paths: set[str]) -> None:
    for relative in sorted(paths):
        shown = subprocess.run(
            ["git", "-C", str(REAL_ROOT), "show", f"{ref}:{relative}"],
            capture_output=True,
            check=False,
        )
        if shown.returncode != 0:
            continue
        destination = repo.path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(shown.stdout)
