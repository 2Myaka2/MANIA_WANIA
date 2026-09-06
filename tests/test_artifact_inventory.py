"""Fixed-value, standard-library tests for the pure inventory contract."""

import builtins
import datetime
import hashlib
import inspect
import io
import json
import os
import subprocess
import sys
import time
import unittest
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from types import ModuleType
from typing import get_args
from unittest.mock import patch

import mania
from mania import artifact_inventory as models
from mania.artifact_inventory import ArtifactInventory, ArtifactInventoryEntry

ENTRY_KEYS = [
    "artifact_id",
    "direction",
    "role",
    "path",
    "format",
    "byte_size",
    "sha256",
    "condition",
]
ROOT_KEYS = [
    "schema_version",
    "kind",
    "run_id",
    "workflow",
    "inventory_path",
    "checksum_mode",
    "artifact_count",
    "input_artifact_count",
    "output_artifact_count",
    "artifacts",
]
DIGEST = "0123456789abcdef" * 4


def entry(**changes):
    values = dict(
        artifact_id="input:sample-1",
        direction="input",
        role="declared_input",
        path="inputs/sample.bin",
        format="bin",
        byte_size=3,
        sha256=None,
    )
    values.update(changes)
    return ArtifactInventoryEntry(**values)


def inventory(**changes):
    values = dict(
        run_id="run-001",
        workflow="preprocessing",
        inventory_path="artifact_inventory.json",
        checksum_mode="none",
        artifacts=(entry(),),
    )
    values.update(changes)
    return ArtifactInventory(**values)


def forbidden(*args, **kwargs):
    raise AssertionError("External observation is forbidden")


class ArtifactInventoryTests(unittest.TestCase):
    def test_constants_and_public_boundary(self):
        self.assertEqual(models.ARTIFACT_INVENTORY_FILENAME, "artifact_inventory.json")
        self.assertEqual(models.ARTIFACT_INVENTORY_KIND, "mania_artifact_inventory")
        self.assertEqual(
            models.ARTIFACT_INVENTORY_SCHEMA_VERSION, "mania.artifact_inventory.v0.1"
        )
        self.assertEqual(get_args(models.ArtifactDirection), ("input", "output"))
        self.assertEqual(get_args(models.ArtifactChecksumMode), ("none", "sha256"))
        self.assertEqual(
            models.__all__,
            [
                "ARTIFACT_INVENTORY_FILENAME",
                "ARTIFACT_INVENTORY_KIND",
                "ARTIFACT_INVENTORY_SCHEMA_VERSION",
                "ArtifactChecksumMode",
                "ArtifactDirection",
                "ArtifactInventory",
                "ArtifactInventoryEntry",
            ],
        )
        for name in models.__all__:
            self.assertTrue(hasattr(models, name))
            self.assertFalse(hasattr(mania, name))

    def test_models_are_frozen_and_identity_fields_are_non_init(self):
        for model in (entry(), inventory()):
            with self.subTest(model=type(model).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(model, fields(model)[0].name, "changed")
        for name in ("schema_version", "kind"):
            self.assertFalse(
                next(f for f in fields(ArtifactInventory) if f.name == name).init
            )
            with self.assertRaises(TypeError):
                inventory(**{name: "changed"})

    def test_order_counts_and_json_primitives(self):
        first = entry(direction="output", condition="условие", artifact_id="z:last")
        second = entry(artifact_id="a:first", path="sample.bin")
        model = inventory(artifacts=(first, second))
        payload = model.to_dict()
        self.assertEqual(list(payload), ROOT_KEYS)
        self.assertEqual(list(first.to_dict()), ENTRY_KEYS)
        self.assertEqual(payload["artifacts"], [first.to_dict(), second.to_dict()])
        self.assertEqual(model.artifact_count, 2)
        self.assertEqual(model.input_artifact_count, 1)
        self.assertEqual(model.output_artifact_count, 1)
        self.assertEqual(json.loads(json.dumps(payload, allow_nan=False)), payload)
        self.assertIsNone(payload["artifacts"][0]["sha256"])
        self.assertIsNone(payload["artifacts"][1]["condition"])

        def check(value):
            self.assertIn(type(value), (str, int, type(None), dict, list))
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertIs(type(key), str)
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)

        check(payload)
        payload["artifacts"].clear()
        self.assertEqual(
            model.to_dict()["artifacts"], [first.to_dict(), second.to_dict()]
        )

    def test_valid_entries(self):
        for direction in ("input", "output"):
            for path in ("sample.bin", "inputs/normal/sample.bin"):
                with self.subTest(direction=direction, path=path):
                    value = entry(direction=direction, path=path, condition="normal")
                    self.assertEqual(value.direction, direction)
                    self.assertEqual(value.path, path)
                    self.assertEqual(value.condition, "normal")
        self.assertEqual(
            entry(artifact_id="0.A_z-1:x", format="x.1+json_gz-2").byte_size, 3
        )
        self.assertEqual(entry(byte_size=0).byte_size, 0)
        self.assertEqual(entry(sha256=DIGEST).sha256, DIGEST)

    def test_invalid_entry_values(self):
        invalid = {
            "artifact_id": (
                "",
                " x",
                "x ",
                "-x",
                ":x",
                ".x",
                "_x",
                "é",
                "a/b",
                "a b",
                "x\n",
                1,
                None,
            ),
            "direction": ("INPUT", "other", " input", "", None, True),
            "role": ("", " ", "role ", " role", None, 7),
            "format": ("", "BIN", "é", "a/b", "a:b", "bin ", " bin", "a b", None, 4),
            "byte_size": (-1, True, False, 1.0, "3", None, float("nan"), float("inf")),
            "sha256": (
                DIGEST.upper(),
                "a" * 63,
                "a" * 65,
                "g" * 64,
                " " + DIGEST,
                DIGEST + "\n",
                "",
                b"a" * 64,
                4,
            ),
            "condition": ("", " ", "normal ", " normal", 1),
        }
        for name, values in invalid.items():
            for value in values:
                with self.subTest(field=name, value=value):
                    with self.assertRaises(ValueError):
                        entry(**{name: value})

    def test_invalid_portable_paths(self):
        for value in (
            "",
            " /a",
            "/a",
            "//host/a",
            "C:/a",
            "C:a",
            "a\\b",
            "\\host\\a",
            "https://host/a",
            "file://a",
            ".",
            "..",
            "./a",
            "a/./b",
            "a/../b",
            "a/.",
            "a/..",
            "a//b",
            "a/",
            "a\0b",
            "a ",
            None,
            Path("a"),
        ):
            with self.subTest(path=value):
                with self.assertRaises(ValueError):
                    entry(path=value)

    def test_empty_inventory_and_supported_locations(self):
        for mode in ("none", "sha256"):
            for path in ("artifact_inventory.json", "analysis/artifact_inventory.json"):
                with self.subTest(mode=mode, path=path):
                    model = inventory(
                        artifacts=(), checksum_mode=mode, inventory_path=path
                    )
                    self.assertEqual(model.artifact_count, 0)
                    self.assertEqual(model.input_artifact_count, 0)
                    self.assertEqual(model.output_artifact_count, 0)
                    self.assertEqual(model.to_dict()["artifacts"], [])

    def test_invalid_inventory_values(self):
        invalid = {
            "run_id": ("", " run", "run ", None, 1),
            "workflow": ("", " analysis", "analysis ", None, 1),
            "checksum_mode": ("", "SHA256", "md5", None, True),
            "inventory_path": (
                "other.json",
                "my_artifact_inventory.json",
                "artifact_inventory.json/extra",
                "/artifact_inventory.json",
                "C:artifact_inventory.json",
                "./artifact_inventory.json",
                "analysis//artifact_inventory.json",
                "",
                None,
            ),
            "artifacts": ([], [entry()], ("entry",), (entry(), {}), None),
        }
        for name, values in invalid.items():
            for value in values:
                with self.subTest(field=name, value=value):
                    with self.assertRaises(ValueError):
                        inventory(**{name: value})

    def test_duplicate_ids_and_paths(self):
        for second, message in (
            (entry(path="other.bin"), "IDs"),
            (entry(artifact_id="other"), "paths"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    inventory(artifacts=(entry(), second))

    def test_self_reference(self):
        for path in ("artifact_inventory.json", "analysis/artifact_inventory.json"):
            for item in (entry(path=path), entry(role="artifact_inventory")):
                with self.subTest(path=path, entry=item):
                    with self.assertRaisesRegex(ValueError, "itself"):
                        inventory(inventory_path=path, artifacts=(item,))

    def test_checksum_consistency(self):
        hashed = entry(sha256=DIGEST)
        unhashed = entry(artifact_id="output", path="output.bin")
        self.assertEqual(
            inventory(checksum_mode="sha256", artifacts=(hashed,)).artifacts, (hashed,)
        )
        for mode, items in (
            ("none", (hashed,)),
            ("sha256", (unhashed,)),
            ("none", (hashed, unhashed)),
            ("sha256", (hashed, unhashed)),
        ):
            with self.subTest(mode=mode, items=items):
                with self.assertRaisesRegex(ValueError, "checksums"):
                    inventory(checksum_mode=mode, artifacts=items)

    def test_import_body_construction_and_serialization_are_pure(self):
        # Prepare source outside the guard: Python's import loader must read code.
        code = compile(inspect.getsource(models), models.__file__, "exec")
        fresh = ModuleType("_inventory_purity_probe")
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name in ("datetime", "time", "subprocess", "hashlib", "os"):
                forbidden()
            return original_import(name, *args, **kwargs)

        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {fresh.__name__: fresh}))
            stack.enter_context(patch.object(builtins, "__import__", guarded_import))
            for module, names in (
                (builtins, ("open",)),
                (io, ("open",)),
                (
                    Path,
                    (
                        "open",
                        "stat",
                        "lstat",
                        "exists",
                        "iterdir",
                        "glob",
                        "rglob",
                        "resolve",
                        "read_bytes",
                        "read_text",
                    ),
                ),
                (os, ("open", "stat", "lstat", "listdir", "scandir", "walk", "getenv")),
                (subprocess, ("run", "Popen")),
                (time, ("time", "time_ns", "monotonic", "perf_counter")),
                (datetime, ("datetime", "date")),
                (hashlib, ("sha256",)),
            ):
                for name in names:
                    stack.enter_context(patch.object(module, name, forbidden))
            exec(code, fresh.__dict__)
            item = fresh.ArtifactInventoryEntry(**entry().to_dict())
            model = fresh.ArtifactInventory(
                "run-001", "preprocessing", "artifact_inventory.json", "none", (item,)
            )
            payload = model.to_dict()
            json.dumps(payload, allow_nan=False)
        self.assertEqual(payload, inventory().to_dict())


if __name__ == "__main__":
    unittest.main()
