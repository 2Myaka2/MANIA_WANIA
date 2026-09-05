import importlib
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from unittest.mock import Mock

import pytest

from mania import _version, software_identity

SHA = "0123456789abcdef" * 2 + "01234567"


def git_result(
    stdout: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["git"], returncode, stdout=stdout, stderr="")


@pytest.fixture
def source_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "mania checkout"
    module_path = root / "src" / "mania" / "software_identity.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    (root / ".git").mkdir()
    monkeypatch.setattr(software_identity, "__file__", str(module_path))
    return root


@pytest.fixture
def git_run(source_checkout: Path, monkeypatch: pytest.MonkeyPatch) -> Mock:
    run = Mock(
        side_effect=[
            git_result(f"{source_checkout}\n"),
            git_result(f"{SHA}\n"),
            git_result(),
        ]
    )
    monkeypatch.setattr(subprocess, "run", run)
    return run


def assert_unavailable(identity: software_identity.SoftwareIdentity) -> None:
    assert identity.commit_sha is None
    assert identity.commit_source == "unavailable"
    assert identity.working_tree_status == "unavailable"


@pytest.mark.parametrize("sha", [None, SHA])
def test_identity_is_immutable_and_json_safe(sha: str | None) -> None:
    identity = software_identity.SoftwareIdentity(
        software_name="MANIA",
        distribution_name="mania-wania",
        version="0.1.0",
        commit_sha=sha,
        commit_source="unavailable" if sha is None else "git_checkout",
        working_tree_status="unavailable" if sha is None else "clean",
    )
    expected = {
        "software_name": "MANIA",
        "distribution_name": "mania-wania",
        "version": "0.1.0",
        "commit_sha": sha,
        "commit_source": "unavailable" if sha is None else "git_checkout",
        "working_tree_status": "unavailable" if sha is None else "clean",
    }

    assert {field.name for field in fields(identity)} == set(expected)
    assert identity.to_dict() == expected
    assert json.loads(json.dumps(identity.to_dict())) == expected
    with pytest.raises(FrozenInstanceError):
        identity.version = "changed"  # type: ignore[misc]
    exported = identity.to_dict()
    exported["version"] = "changed"
    assert identity.version == "0.1.0"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("", "clean"),
        ("M  tracked.py\n", "dirty"),
        (" M tracked.py\n", "dirty"),
        ("?? new.py\n", "dirty"),
    ],
    ids=["clean", "staged", "unstaged", "untracked"],
)
def test_verified_checkout_state(
    source_checkout: Path,
    git_run: Mock,
    status: str,
    expected: str,
) -> None:
    git_run.side_effect = [
        git_result(f"{source_checkout}\n"),
        git_result(f"{SHA}\n"),
        git_result(status),
    ]

    identity = software_identity.get_software_identity()

    assert identity.software_name == software_identity.SOFTWARE_NAME == "MANIA"
    assert identity.distribution_name == software_identity.DISTRIBUTION_NAME
    assert identity.distribution_name == "mania-wania"
    assert identity.version == _version.__version__
    assert identity.commit_sha == SHA
    assert identity.commit_source == "git_checkout"
    assert identity.working_tree_status == expected
    status_args = git_run.call_args.args[0]
    assert "--porcelain=v1" in status_args
    assert "--untracked-files=all" in status_args


def test_git_file_metadata_is_supported(source_checkout: Path, git_run: Mock) -> None:
    metadata = source_checkout / ".git"
    metadata.rmdir()
    metadata.write_text("gitdir: ../metadata/worktrees/mania\n", encoding="utf-8")

    assert software_identity.get_software_identity().commit_sha == SHA
    assert git_run.call_count == 3


@pytest.mark.parametrize(
    "relative_path",
    [
        ".venv/lib/python3.11/site-packages/mania/software_identity.py",
        "mania/software_identity.py",
        "src/another/software_identity.py",
    ],
)
def test_layout_mismatch_under_git_repository_is_unavailable(
    source_checkout: Path,
    git_run: Mock,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
) -> None:
    installed_module = source_checkout / relative_path
    installed_module.parent.mkdir(parents=True)
    installed_module.touch()
    monkeypatch.setattr(software_identity, "__file__", str(installed_module))

    assert_unavailable(software_identity.get_software_identity())
    git_run.assert_not_called()


def test_missing_git_metadata_is_unavailable(
    source_checkout: Path, git_run: Mock
) -> None:
    (source_checkout / ".git").rmdir()

    assert_unavailable(software_identity.get_software_identity())
    git_run.assert_not_called()


@pytest.mark.parametrize("command_index", [0, 1], ids=["top-level", "commit"])
@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("git missing"),
        subprocess.TimeoutExpired(["git"], 2),
        PermissionError("git denied"),
        subprocess.SubprocessError("git error"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid output"),
        git_result(returncode=1),
    ],
    ids=["missing-git", "timeout", "os-error", "subprocess-error", "decode", "nonzero"],
)
def test_git_failure_is_unavailable(
    source_checkout: Path,
    git_run: Mock,
    command_index: int,
    failure: Exception | subprocess.CompletedProcess[str],
) -> None:
    git_run.side_effect = [git_result(f"{source_checkout}\n")][:command_index] + [
        failure
    ]

    assert_unavailable(software_identity.get_software_identity())
    assert git_run.call_count == command_index + 1


@pytest.mark.parametrize(
    "output",
    ["", ".\n", "/another/repository\n", "/bad\0path\n", "/one\n/two\n"],
)
def test_invalid_top_level_is_unavailable(git_run: Mock, output: str) -> None:
    git_run.side_effect = [git_result(output)]

    assert_unavailable(software_identity.get_software_identity())
    assert git_run.call_count == 1


@pytest.mark.parametrize(
    "failure", [OSError("path denied"), RuntimeError("symlink loop")]
)
def test_module_path_errors_are_unavailable(
    git_run: Mock,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    monkeypatch.setattr(Path, "resolve", Mock(side_effect=failure))

    assert_unavailable(software_identity.get_software_identity())
    git_run.assert_not_called()


@pytest.mark.parametrize(
    "sha", ["", "abcdef0", "g" * 40, "a" * 39, "a" * 41, "a" * 64, SHA + "\nextra"]
)
def test_invalid_commit_is_rejected(
    source_checkout: Path, git_run: Mock, sha: str
) -> None:
    git_run.side_effect = [git_result(f"{source_checkout}\n"), git_result(sha + "\n")]

    assert_unavailable(software_identity.get_software_identity())
    assert git_run.call_count == 2


def test_uppercase_commit_is_normalized(source_checkout: Path, git_run: Mock) -> None:
    git_run.side_effect = [
        git_result(f"{source_checkout}\n"),
        git_result(SHA.upper() + "\n"),
        git_result(),
    ]

    assert software_identity.get_software_identity().commit_sha == SHA


@pytest.mark.parametrize(
    "failure",
    [
        git_result(returncode=1),
        FileNotFoundError("git missing"),
        subprocess.TimeoutExpired(["git"], 2),
        OSError("status failed"),
    ],
    ids=["nonzero", "missing-git", "timeout", "os-error"],
)
def test_failed_status_preserves_commit(
    source_checkout: Path,
    git_run: Mock,
    failure: Exception | subprocess.CompletedProcess[str],
) -> None:
    git_run.side_effect = [
        git_result(f"{source_checkout}\n"),
        git_result(f"{SHA}\n"),
        failure,
    ]

    identity = software_identity.get_software_identity()

    assert identity.commit_sha == SHA
    assert identity.commit_source == "git_checkout"
    assert identity.working_tree_status == "unavailable"


def test_git_uses_module_checkout_with_bounded_argument_list_calls(
    source_checkout: Path,
    git_run: Mock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_repository = tmp_path / "other-repository"
    (other_repository / ".git").mkdir(parents=True)
    monkeypatch.chdir(other_repository)
    monkeypatch.setenv("GIT_DIR", str(other_repository / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other_repository))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other_repository / "custom-index"))

    assert software_identity.get_software_identity().commit_sha == SHA

    for call in git_run.call_args_list:
        assert isinstance(call.args[0], list)
        assert call.args[0][0] == "git"
        assert call.kwargs["cwd"] == source_checkout
        assert 0 < call.kwargs["timeout"] <= 5
        assert not call.kwargs.get("shell", False)
        assert not any(key.startswith("GIT_") for key in call.kwargs["env"])


def test_version_comes_from_version_module(
    source_checkout: Path,
    git_run: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_version, "__version__", "test-version")
    assert software_identity.get_software_identity().version == "test-version"

    (source_checkout / ".git").rmdir()
    identity = software_identity.get_software_identity()
    assert identity.version == "test-version"
    assert_unavailable(identity)


@pytest.mark.parametrize(
    "module", ["mania", "mania._version", "mania.software_identity", "mania.cli"]
)
def test_fresh_import_does_not_invoke_git(module: str) -> None:
    script = """
import importlib
import subprocess
import sys
from unittest.mock import patch

with patch.object(subprocess, "Popen", side_effect=AssertionError("process launched")):
    importlib.import_module(sys.argv[1])
"""
    result = subprocess.run(
        [sys.executable, "-c", script, module],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_reload_does_not_invoke_git(monkeypatch: pytest.MonkeyPatch) -> None:
    popen = Mock(side_effect=AssertionError("unexpected subprocess"))
    monkeypatch.setattr(subprocess, "Popen", popen)

    importlib.reload(software_identity)

    popen.assert_not_called()
