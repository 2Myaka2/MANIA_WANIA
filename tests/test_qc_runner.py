import builtins
import json
import os
from pathlib import Path
from typing import NoReturn

import pytest

from mania.qc.runner import (
    QC_LEVELS,
    QCMessage,
    build_empty_qc_report,
    build_skeleton_qc_report,
    format_qc_report_summary,
    make_qc_message,
    qc_report_to_dict,
)

EXPECTED_QC_REPORT_KEYS = {"passed", "messages"}
EXPECTED_QC_MESSAGE_KEYS = {"code", "level", "message"}


def fail_filesystem_access(*args: object, **kwargs: object) -> NoReturn:
    raise AssertionError("QC helpers must not inspect or write files")


def test_qc_levels_are_stable() -> None:
    assert QC_LEVELS == ("info", "warning", "error")


def test_make_qc_message_returns_qc_message() -> None:
    message = make_qc_message(
        code="QC_TEST_001",
        level="warning",
        message="Example QC message.",
    )

    assert isinstance(message, QCMessage)
    assert message.code == "QC_TEST_001"
    assert message.level == "warning"
    assert message.message == "Example QC message."


def test_make_qc_message_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="Unknown QC level"):
        make_qc_message(
            code="QC_TEST_002",
            level="critical",
            message="Invalid QC level.",
        )


def test_build_empty_qc_report_returns_passing_report_with_no_messages() -> None:
    report = build_empty_qc_report()

    assert report.passed is True
    assert report.messages == ()


def test_build_skeleton_qc_report_returns_passing_report() -> None:
    report = build_skeleton_qc_report()

    assert report.passed is True


def test_build_skeleton_qc_report_includes_one_info_message() -> None:
    report = build_skeleton_qc_report()

    assert len(report.messages) == 1
    assert report.messages[0].level == "info"
    assert report.messages[0].message == "QC checks are not implemented yet."


def test_build_skeleton_qc_report_uses_stable_code() -> None:
    report = build_skeleton_qc_report()

    assert report.messages[0].code == "QC_SKEL_001"


def test_qc_report_to_dict_returns_basic_json_types() -> None:
    report_dict = qc_report_to_dict(build_skeleton_qc_report())

    assert set(report_dict) == EXPECTED_QC_REPORT_KEYS
    assert isinstance(report_dict["passed"], bool)
    assert isinstance(report_dict["messages"], list)

    message_dict = report_dict["messages"][0]
    assert isinstance(message_dict, dict)
    assert set(message_dict) == EXPECTED_QC_MESSAGE_KEYS
    assert isinstance(message_dict["code"], str)
    assert isinstance(message_dict["level"], str)
    assert isinstance(message_dict["message"], str)


def test_qc_report_to_dict_can_be_json_dumped() -> None:
    report_dict = qc_report_to_dict(build_skeleton_qc_report())

    assert json.dumps(report_dict)


def test_qc_report_to_dict_converts_messages_to_list_of_dictionaries() -> None:
    report_dict = qc_report_to_dict(build_skeleton_qc_report())

    assert report_dict["messages"] == [
        {
            "code": "QC_SKEL_001",
            "level": "info",
            "message": "QC checks are not implemented yet.",
        }
    ]


def test_format_qc_report_summary_contains_expected_fields() -> None:
    summary = format_qc_report_summary(build_skeleton_qc_report())

    assert "MANIA QC report skeleton" in summary
    assert "Passed: true" in summary
    assert "Messages: 1" in summary
    assert "QC_SKEL_001" in summary


def test_format_qc_report_summary_uses_stable_line_order() -> None:
    summary = format_qc_report_summary(build_skeleton_qc_report())

    assert summary.splitlines() == [
        "MANIA QC report skeleton",
        "Passed: true",
        "Messages: 1",
        "[info] QC_SKEL_001: QC checks are not implemented yet.",
    ]


def test_format_qc_report_summary_handles_empty_report() -> None:
    summary = format_qc_report_summary(build_empty_qc_report())

    assert summary.splitlines() == [
        "MANIA QC report skeleton",
        "Passed: true",
        "Messages: 0",
    ]


def test_module_does_not_inspect_or_write_to_filesystem(monkeypatch) -> None:
    monkeypatch.setattr(builtins, "open", fail_filesystem_access)
    monkeypatch.setattr(os.path, "exists", fail_filesystem_access)
    monkeypatch.setattr(os, "makedirs", fail_filesystem_access)
    monkeypatch.setattr(Path, "exists", fail_filesystem_access)
    monkeypatch.setattr(Path, "mkdir", fail_filesystem_access)
    monkeypatch.setattr(Path, "read_text", fail_filesystem_access)
    monkeypatch.setattr(Path, "write_text", fail_filesystem_access)

    message = make_qc_message(
        code="QC_TEST_003",
        level="error",
        message="Example error message.",
    )
    empty_report = build_empty_qc_report()
    skeleton_report = build_skeleton_qc_report()
    report_dict = qc_report_to_dict(skeleton_report)
    summary = format_qc_report_summary(skeleton_report)

    assert isinstance(message, QCMessage)
    assert empty_report.messages == ()
    assert report_dict["passed"] is True
    assert summary.startswith("MANIA QC report skeleton")
