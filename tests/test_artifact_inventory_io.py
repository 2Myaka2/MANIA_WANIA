"""Deterministic file, streaming, and atomic-publication tests using small fixtures."""

import ast
import builtins
import datetime
import hashlib
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path, PurePath
from types import SimpleNamespace
from unittest.mock import Mock, patch

import mania
from mania import artifact_inventory_io as inventory_io
from mania.artifact_inventory import ArtifactInventory, ArtifactInventoryEntry
from mania.artifact_inventory_io import (
    ARTIFACT_INVENTORY_DEFAULT_HASH_CHUNK_SIZE,
    ArtifactInventoryBuildError,
    ArtifactInventoryFileSpec,
    ArtifactInventoryWriteResult,
    build_artifact_inventory,
    stream_file_sha256,
    write_artifact_inventory,
)


def forbidden(*args, **kwargs):
    raise AssertionError("Undeclared I/O or runtime collection")


def file_spec(local_path, **changes):
    values = dict(
        artifact_id="input:sample",
        direction="input",
        role="declared_input",
        local_path=local_path,
        path="inputs/sample.bin",
        format="custom+binary",
        condition="normal",
    )
    values.update(changes)
    return ArtifactInventoryFileSpec(**values)


def build(specs, **changes):
    values = dict(
        run_id="run-001",
        workflow="preprocessing",
        inventory_path="artifact_inventory.json",
        file_specs=specs,
    )
    values.update(changes)
    return build_artifact_inventory(**values)


@contextmanager
def no_discovery():
    with ExitStack() as stack:
        for module, names in (
            (Path, ("iterdir", "glob", "rglob", "resolve")),
            (os, ("listdir", "scandir", "walk", "getenv")),
            (subprocess, ("run", "Popen")),
            (time, ("time", "time_ns", "monotonic", "perf_counter")),
            (datetime, ("datetime", "date")),
        ):
            for name in names:
                stack.enter_context(patch.object(module, name, forbidden))
        yield


class ArtifactInventoryIOTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source.bin"
        self.source.write_bytes(b"abc")
        self.spec = file_spec(self.source)
        self.model = build((self.spec,))

    def test_public_boundary(self):
        self.assertEqual(ARTIFACT_INVENTORY_DEFAULT_HASH_CHUNK_SIZE, 1024 * 1024)
        self.assertEqual(
            inventory_io.__all__,
            [
                "ARTIFACT_INVENTORY_DEFAULT_HASH_CHUNK_SIZE",
                "ArtifactInventoryBuildError",
                "ArtifactInventoryFileSpec",
                "ArtifactInventoryWriteResult",
                "build_artifact_inventory",
                "stream_file_sha256",
                "write_artifact_inventory",
            ],
        )
        self.assertTrue(issubclass(ArtifactInventoryBuildError, ValueError))
        for name in inventory_io.__all__:
            self.assertTrue(hasattr(inventory_io, name))
            self.assertFalse(hasattr(mania, name))

    def test_file_spec_frozen_and_execution_paths(self):
        for path in (self.source, Path("relative/missing.bin")):
            with self.subTest(path=path):
                spec = file_spec(path)
                self.assertIs(spec.local_path, path)
                self.assertFalse(hasattr(spec, "to_dict"))
                with self.assertRaises(FrozenInstanceError):
                    spec.path = "changed.bin"

    def test_file_spec_rejects_non_exact_paths(self):
        class CustomPath(type(Path())):
            pass

        for value in (str(self.source), PurePath("file"), None, 3, CustomPath("file")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "exact Path"):
                    file_spec(value)

    def test_file_spec_metadata_validation_matches_entry(self):
        for name, value in (
            ("artifact_id", "a/b"),
            ("direction", "both"),
            ("role", " padded "),
            ("path", "../sample.bin"),
            ("format", "BIN"),
            ("condition", ""),
        ):
            with self.subTest(field=name):
                with self.assertRaises(ValueError) as spec_error:
                    file_spec(self.source, **{name: value})
                values = self.model.artifacts[0].to_dict()
                values[name] = value
                with self.assertRaises(ValueError) as entry_error:
                    ArtifactInventoryEntry(**values)
                self.assertEqual(str(spec_error.exception), str(entry_error.exception))

    def test_file_spec_construction_does_not_inspect_files(self):
        with no_discovery(), ExitStack() as stack:
            for module, names in (
                (Path, ("stat", "lstat", "exists", "open")),
                (os, ("stat", "lstat", "open")),
                (builtins, ("open",)),
                (io, ("open",)),
            ):
                for name in names:
                    stack.enter_context(patch.object(module, name, forbidden))
            spec = file_spec(Path("missing.bin"))
        self.assertEqual(spec.local_path, Path("missing.bin"))

    def test_default_mode_uses_only_exact_metadata_and_preserves_order(self):
        other = self.root / "other.xtc"
        other.write_bytes(b"\x00\xff\x01\x02\x03")
        specs = (
            file_spec(
                other,
                artifact_id="z:output",
                direction="output",
                role="result",
                path="normal/result.data",
                format="explicit",
                condition="условие",
            ),
            self.spec,
        )
        stat_paths = []
        real_stat = Path.stat

        def exact_stat(path, *args, **kwargs):
            stat_paths.append(path)
            return real_stat(path, *args, **kwargs)

        with no_discovery(), ExitStack() as stack:
            stack.enter_context(patch.object(Path, "stat", exact_stat))
            for module, names in (
                (
                    Path,
                    ("open", "read_bytes", "read_text", "write_bytes", "write_text"),
                ),
                (builtins, ("open",)),
                (io, ("open",)),
                (os, ("open", "read")),
                (inventory_io, ("stream_file_sha256",)),
                (hashlib, ("sha256",)),
            ):
                for name in names:
                    stack.enter_context(patch.object(module, name, forbidden))
            model = build(specs)
        self.assertEqual(stat_paths, [other, self.source])
        self.assertEqual([e.byte_size for e in model.artifacts], [5, 3])
        self.assertEqual([e.sha256 for e in model.artifacts], [None, None])
        for spec, item in zip(specs, model.artifacts, strict=True):
            for name in (
                "artifact_id",
                "direction",
                "role",
                "path",
                "format",
                "condition",
            ):
                self.assertEqual(getattr(spec, name), getattr(item, name))
        self.assertEqual(model.input_artifact_count, 1)
        self.assertEqual(model.output_artifact_count, 1)
        self.assertEqual(model.checksum_mode, "none")
        self.assertNotIn(str(self.root), json.dumps(model.to_dict()))
        self.assertEqual(set(self.root.iterdir()), {self.source, other})
        self.assertEqual(specs[0].format, "explicit")

    def test_empty_builder_has_no_file_access(self):
        with (
            patch.object(Path, "stat", forbidden),
            patch.object(Path, "open", forbidden),
        ):
            for mode in ("none", "sha256"):
                self.assertEqual(build((), checksum_mode=mode).artifacts, ())

    def test_builder_accepts_symlink_without_resolving_or_leaking_target(self):
        link = self.root / "link.bin"
        link.symlink_to(self.source)
        with no_discovery():
            for mode in ("none", "sha256"):
                result = build((file_spec(link),), checksum_mode=mode)
                self.assertEqual(result.artifacts[0].byte_size, 3)
                self.assertEqual(result.artifacts[0].path, "inputs/sample.bin")
                self.assertNotIn(str(self.source), json.dumps(result.to_dict()))

    def test_known_sha256_digests(self):
        cases = (
            (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
            (
                b"abc",
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            ),
            (
                bytes(range(256)),
                "40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880",
            ),
        )
        for content, expected in cases:
            with self.subTest(size=len(content)):
                self.source.write_bytes(content)
                self.assertEqual(stream_file_sha256(self.source), expected)
                model = build((self.spec,), checksum_mode="sha256")
                self.assertEqual(model.artifacts[0].sha256, expected)
                self.assertRegex(expected, r"^[0-9a-f]{64}$")
                self.assertEqual(model.artifacts[0].byte_size, len(content))

    def test_sha256_builder_hashes_every_spec_without_writing(self):
        other = self.root / "other.bin"
        other.write_bytes(b"\xff\x00")
        specs = (self.spec, file_spec(other, artifact_id="second", path="second.bin"))
        original = tuple(specs)
        with (
            no_discovery(),
            patch.object(
                inventory_io, "stream_file_sha256", wraps=stream_file_sha256
            ) as hasher,
            patch.object(Path, "write_text", forbidden),
        ):
            result = build(specs, checksum_mode="sha256")
        self.assertEqual(
            [call.args[0] for call in hasher.call_args_list], [self.source, other]
        )
        self.assertEqual(
            [item.sha256 for item in result.artifacts],
            [
                hashlib.sha256(b"abc").hexdigest(),
                hashlib.sha256(b"\xff\x00").hexdigest(),
            ],
        )
        self.assertEqual(specs, original)
        self.assertEqual(set(self.root.iterdir()), {self.source, other})

    def test_reads_are_bounded_and_stream_larger_than_one_chunk(self):
        for chunk_size in (7, ARTIFACT_INVENTORY_DEFAULT_HASH_CHUNK_SIZE):
            with self.subTest(chunk_size=chunk_size):
                content = b"\x00\xff" * (chunk_size + 2)
                self.source.write_bytes(content)
                reads = []
                real_open = Path.open

                @contextmanager
                def checked_open(
                    path,
                    mode,
                    *,
                    real_open=real_open,
                    chunk_size=chunk_size,
                    reads=reads,
                ):
                    self.assertEqual(mode, "rb")
                    with real_open(path, mode) as stream:

                        def read(size):
                            self.assertGreater(size, 0)
                            self.assertLessEqual(size, chunk_size)
                            data = stream.read(size)
                            reads.append((size, len(data)))
                            return data

                        yield Mock(read=read, fileno=stream.fileno)

                with (
                    patch.object(Path, "open", checked_open),
                    patch.object(Path, "read_bytes", forbidden),
                ):
                    digest = stream_file_sha256(self.source, chunk_size=chunk_size)
                self.assertEqual(digest, hashlib.sha256(content).hexdigest())
                self.assertGreater(len(reads), 2)
                self.assertEqual(sum(length for _, length in reads), len(content))
                self.assertTrue(all(length < len(content) for _, length in reads))
                self.assertEqual(reads[-1][1], 0)

    def test_invalid_hash_arguments_before_open(self):
        with patch.object(Path, "open", forbidden):
            for size in (0, -1, True, False, 1.5, "3", None):
                with self.subTest(size=size):
                    with self.assertRaisesRegex(ValueError, "positive integer"):
                        stream_file_sha256(self.source, chunk_size=size)
            for path in (str(self.source), PurePath("file"), None):
                with self.subTest(path=path):
                    with self.assertRaisesRegex(ValueError, "exact Path"):
                        stream_file_sha256(path)

    def test_hash_propagates_file_errors(self):
        with self.assertRaises(FileNotFoundError):
            stream_file_sha256(self.root / "missing.bin")
        with patch.object(Path, "open", side_effect=PermissionError("private path")):
            with self.assertRaises(PermissionError):
                stream_file_sha256(self.source)

    def test_hash_supports_stream_without_file_descriptor(self):
        with patch.object(Path, "open", return_value=io.BytesIO(b"abc")):
            self.assertEqual(
                stream_file_sha256(self.source), hashlib.sha256(b"abc").hexdigest()
            )

    def test_hash_detects_mutated_size_or_timestamp(self):
        real_open = Path.open
        for mutation in ("size", "timestamp"):
            self.source.write_bytes(b"abcdef")

            @contextmanager
            def mutating_open(path, mode, *, mutation=mutation):
                with real_open(path, mode) as stream:
                    initial = path.stat()
                    mutated = False

                    def read(size):
                        nonlocal mutated
                        data = stream.read(size)
                        if not mutated:
                            mutated = True
                            if mutation == "size":
                                with real_open(path, "ab") as writer:
                                    writer.write(b"changed")
                            else:
                                os.utime(
                                    path,
                                    ns=(
                                        initial.st_atime_ns,
                                        initial.st_mtime_ns + 10**9,
                                    ),
                                )
                        return data

                    yield Mock(read=read, fileno=stream.fileno)

            with (
                self.subTest(mutation=mutation),
                patch.object(Path, "open", mutating_open),
            ):
                with self.assertRaisesRegex(
                    ValueError, "^File changed during SHA256 hashing\\.$"
                ):
                    stream_file_sha256(self.source, chunk_size=2)
                with self.assertRaises(ArtifactInventoryBuildError):
                    build((self.spec,), checksum_mode="sha256")

    def test_hash_rejects_byte_count_inconsistent_with_descriptor_size(self):
        real_open = Path.open

        @contextmanager
        def short_read(path, mode):
            with real_open(path, mode) as stream:
                yield Mock(read=Mock(side_effect=[b"a", b""]), fileno=stream.fileno)

        with patch.object(Path, "open", short_read):
            with self.assertRaisesRegex(ValueError, "File changed"):
                stream_file_sha256(self.source)
            with self.assertRaises(ArtifactInventoryBuildError):
                build((self.spec,), checksum_mode="sha256")

    def test_builder_checks_size_around_hashing(self):
        def mutate(path):
            path.write_bytes(b"longer")
            return hashlib.sha256(b"longer").hexdigest()

        with patch.object(inventory_io, "stream_file_sha256", mutate):
            with self.assertRaisesRegex(ArtifactInventoryBuildError, "Could not hash"):
                build((self.spec,), checksum_mode="sha256")

    def test_builder_validates_complete_metadata_set_before_file_access(self):
        cases = (
            {"run_id": ""},
            {"workflow": " padded "},
            {"checksum_mode": "md5"},
            {"inventory_path": "../artifact_inventory.json"},
            {"file_specs": [self.spec]},
            {"file_specs": (object(),)},
            {"file_specs": (self.spec, replace(self.spec, path="other.bin"))},
            {"file_specs": (self.spec, replace(self.spec, artifact_id="other"))},
            {
                "file_specs": (
                    self.spec,
                    replace(
                        self.spec, artifact_id="self", path="artifact_inventory.json"
                    ),
                )
            },
            {"file_specs": (replace(self.spec, role="artifact_inventory"),)},
        )
        with (
            patch.object(Path, "stat", forbidden),
            patch.object(Path, "open", forbidden),
        ):
            for changes in cases:
                with self.subTest(changes=changes):
                    with self.assertRaises(ValueError):
                        values = {"file_specs": (self.spec,)} | changes
                        build(values.pop("file_specs"), **values)

    def test_missing_directory_and_non_regular_files_fail(self):
        paths = [self.root / "missing.bin", self.root]
        if hasattr(os, "mkfifo"):
            fifo = self.root / "fifo"
            os.mkfifo(fifo)
            paths.append(fifo)
        for path in paths:
            for mode in ("none", "sha256"):
                with (
                    self.subTest(path=path, mode=mode),
                    patch.object(Path, "open", forbidden),
                ):
                    with self.assertRaises(ArtifactInventoryBuildError) as caught:
                        build((file_spec(path),), checksum_mode=mode)
                    self.assertNotIn(str(self.root), str(caught.exception))
                    self.assertIn("input:sample", str(caught.exception))

    def test_inspection_and_open_errors_are_sanitized(self):
        for operation, mode, expected in (
            ("stat", "none", "Could not inspect artifact 'input:sample'."),
            ("open", "sha256", "Could not hash artifact 'input:sample'."),
        ):
            with (
                self.subTest(operation=operation),
                patch.object(
                    Path,
                    operation,
                    side_effect=PermissionError(f"secret {self.source}"),
                ),
            ):
                with self.assertRaises(ArtifactInventoryBuildError) as caught:
                    build((self.spec,), checksum_mode=mode)
                self.assertEqual(str(caught.exception), expected)
                self.assertTrue(caught.exception.__suppress_context__)

    def test_hash_failure_is_all_or_nothing_and_stops_processing(self):
        specs = tuple(
            replace(self.spec, artifact_id=f"file:{i}", path=f"{i}.bin")
            for i in range(3)
        )
        with patch.object(
            inventory_io,
            "stream_file_sha256",
            side_effect=[
                hashlib.sha256(b"abc").hexdigest(),
                OSError(f"private {self.source}"),
            ],
        ) as hasher:
            with self.assertRaisesRegex(ArtifactInventoryBuildError, "file:1"):
                build(specs, checksum_mode="sha256")
        self.assertEqual(hasher.call_count, 2)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_writer_result_is_frozen_ordered_and_json_safe(self):
        for written, error in ((True, None), (False, "Filesystem write failed.")):
            with self.subTest(written=written):
                result = ArtifactInventoryWriteResult(self.source, written, error)
                self.assertEqual(result.passed, written)
                self.assertEqual(
                    list(result.to_dict()),
                    ["output_path", "written", "error", "passed"],
                )
                self.assertEqual(result.to_dict()["output_path"], str(self.source))
                json.dumps(result.to_dict(), allow_nan=False)
                with self.assertRaises(FrozenInstanceError):
                    result.written = False

    def test_writer_result_validation(self):
        for path, written, error in (
            ("file", True, None),
            (self.source, 1, None),
            (self.source, "yes", None),
            (self.source, True, "error"),
            (self.source, False, None),
            (self.source, False, ""),
            (self.source, False, " padded "),
            (self.source, False, 1),
        ):
            with self.subTest(written=written, error=error):
                with self.assertRaises(ValueError):
                    ArtifactInventoryWriteResult(path, written, error)

    def test_writer_utf8_order_layout_and_single_newline(self):
        for location in ("artifact_inventory.json", "analysis/artifact_inventory.json"):
            with self.subTest(location=location):
                model = replace(
                    self.model,
                    inventory_path=location,
                    artifacts=(
                        replace(
                            self.model.artifacts[0],
                            role="результат",
                            condition="условие",
                        ),
                    ),
                )
                before = model.to_dict()
                output = self.root / "nested" / "output"
                result = write_artifact_inventory(model, str(output))
                self.assertTrue(result.passed)
                self.assertEqual(result.output_path, output / location)
                text = result.output_path.read_bytes().decode("utf-8")
                self.assertEqual(
                    text,
                    json.dumps(
                        before,
                        indent=2,
                        sort_keys=False,
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                    + "\n",
                )
                payload = json.loads(text)
                self.assertEqual(list(payload), list(before))
                self.assertEqual(
                    list(payload["artifacts"][0]), list(before["artifacts"][0])
                )
                self.assertIn('\n  "schema_version":', text)
                self.assertIn("результат", text)
                self.assertTrue(text.endswith("\n"))
                self.assertFalse(text.endswith("\n\n"))
                self.assertEqual(before, model.to_dict())
                self.assertEqual(
                    list(result.output_path.parent.iterdir()), [result.output_path]
                )

    def test_writer_preserves_existing_target_without_overwrite(self):
        target = self.root / self.model.inventory_path
        target.write_bytes(b"original\x00\xff")
        result = write_artifact_inventory(self.model, self.root)
        self.assertEqual(result.error, "Target already exists.")
        self.assertFalse(result.passed)
        self.assertEqual(target.read_bytes(), b"original\x00\xff")
        self.assertEqual(set(self.root.iterdir()), {self.source, target})

    def test_atomic_publication_sees_only_complete_same_directory_json(self):
        target = self.root / self.model.inventory_path
        for overwrite in (False, True):
            operation = "replace" if overwrite else "link"
            publish = getattr(os, operation)
            if overwrite:
                target.write_bytes(b"original")
            calls = []

            def inspect_publication(
                source,
                destination,
                *,
                overwrite=overwrite,
                publish=publish,
                calls=calls,
            ):
                self.assertEqual(source.parent, target.parent)
                self.assertNotEqual(source, target)
                self.assertEqual(destination, target)
                self.assertEqual(json.loads(source.read_text()), self.model.to_dict())
                if overwrite:
                    self.assertEqual(target.read_bytes(), b"original")
                else:
                    self.assertFalse(target.exists())
                publish(source, destination)
                calls.append(destination)

            with (
                self.subTest(overwrite=overwrite),
                patch.object(os, operation, inspect_publication),
            ):
                result = write_artifact_inventory(
                    self.model, self.root, overwrite=overwrite
                )
            self.assertTrue(result.passed)
            self.assertEqual(calls, [target])
            self.assertEqual(json.loads(target.read_text()), self.model.to_dict())
            self.assertEqual(set(self.root.iterdir()), {self.source, target})

    def test_concurrent_target_is_not_clobbered(self):
        target = self.root / self.model.inventory_path
        real_link = os.link

        def racing_link(source, destination):
            target.write_bytes(b"concurrent")
            real_link(source, destination)

        with patch.object(os, "link", racing_link):
            result = write_artifact_inventory(self.model, self.root)
        self.assertEqual(result.error, "Target already exists.")
        self.assertEqual(target.read_bytes(), b"concurrent")
        self.assertEqual(set(self.root.iterdir()), {self.source, target})

    def test_dangling_target_symlink_counts_as_existing(self):
        target = self.root / self.model.inventory_path
        target.symlink_to(self.root / "absent")
        result = write_artifact_inventory(self.model, self.root)
        self.assertEqual(result.error, "Target already exists.")
        self.assertTrue(target.is_symlink())

    def test_output_root_or_target_parent_file_fails(self):
        for output, location in (
            (self.source, "artifact_inventory.json"),
            (self.root, "source.bin/artifact_inventory.json"),
        ):
            with self.subTest(location=location):
                result = write_artifact_inventory(
                    replace(self.model, inventory_path=location), output
                )
                self.assertFalse(result.passed)
                self.assertIsNotNone(result.error)
                self.assertEqual(self.source.read_bytes(), b"abc")
                self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_writer_rejects_invalid_arguments(self):
        class SubInventory(ArtifactInventory):
            pass

        subclass = SubInventory(
            "run", "analysis", "artifact_inventory.json", "none", ()
        )
        for value in (None, {}, subclass):
            with self.subTest(inventory=value):
                with self.assertRaisesRegex(ValueError, "exact ArtifactInventory"):
                    write_artifact_inventory(value, self.root)
        for output in ("", None, 3):
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    write_artifact_inventory(self.model, output)
        for overwrite in (0, 1, "yes", None):
            with self.subTest(overwrite=overwrite):
                with self.assertRaisesRegex(ValueError, "bool"):
                    write_artifact_inventory(self.model, self.root, overwrite=overwrite)

    def test_serialization_failures_leave_no_partial_file(self):
        target = self.root / self.model.inventory_path
        for existing in (False, True):
            if existing:
                target.write_bytes(b"original")
            for invalid in (float("nan"), float("inf"), {1}, b"bytes", Path("local")):
                with (
                    self.subTest(existing=existing, invalid=invalid),
                    patch.object(
                        ArtifactInventory, "to_dict", return_value={"invalid": invalid}
                    ),
                ):
                    result = write_artifact_inventory(
                        self.model, self.root, overwrite=existing
                    )
                self.assertEqual(result.error, "JSON serialization failed.")
                self.assertEqual(target.exists(), existing)
                if existing:
                    self.assertEqual(target.read_bytes(), b"original")
                expected = {self.source, target} if existing else {self.source}
                self.assertEqual(set(self.root.iterdir()), expected)

    def test_filesystem_failures_clean_temporary_files_and_preserve_target(self):
        real_temporary = tempfile.NamedTemporaryFile
        target = self.root / self.model.inventory_path

        @contextmanager
        def broken_writer(**kwargs):
            with real_temporary(**kwargs) as stream:

                def fail_write(payload):
                    stream.write(payload[:8])
                    raise OSError(f"private {target}")

                yield SimpleNamespace(name=stream.name, write=fail_write)

        for operation in ("mkdir", "temporary", "write", "link", "replace"):
            overwrite = operation == "replace"
            if overwrite:
                target.write_bytes(b"original")
            with self.subTest(operation=operation), ExitStack() as stack:
                error = OSError(f"private {target}")
                if operation == "mkdir":
                    stack.enter_context(patch.object(Path, "mkdir", side_effect=error))
                elif operation == "temporary":
                    stack.enter_context(
                        patch.object(tempfile, "NamedTemporaryFile", side_effect=error)
                    )
                elif operation == "write":
                    stack.enter_context(
                        patch.object(tempfile, "NamedTemporaryFile", broken_writer)
                    )
                else:
                    stack.enter_context(patch.object(os, operation, side_effect=error))
                result = write_artifact_inventory(
                    self.model, self.root, overwrite=overwrite
                )
            self.assertEqual(result.error, "Filesystem write failed.")
            self.assertEqual(target.exists(), overwrite)
            if overwrite:
                self.assertEqual(target.read_bytes(), b"original")
            expected = {self.source, target} if overwrite else {self.source}
            self.assertEqual(set(self.root.iterdir()), expected)

    def test_cleanup_error_is_reported_deterministically(self):
        with patch.object(Path, "unlink", side_effect=PermissionError("private path")):
            result = write_artifact_inventory(self.model, self.root)
        self.assertEqual(result.error, "Temporary file cleanup failed.")
        self.assertFalse(result.passed)
        self.assertEqual(
            json.loads(result.output_path.read_text()), self.model.to_dict()
        )
        # TemporaryDirectory owns cleanup after the injected permission failure ends.

    def test_writer_ignores_unrelated_files_without_hashing_scanning_git_or_clock(self):
        sentinels = {
            "run_provenance.json": b'{"kind":"mania_run_provenance"}\n',
            "mania_manifest.json": b'{"existing":"manifest"}\n',
            "extended_metrics.json": b'{"existing":"metrics"}\n',
            "run_meta.json": b'{"existing":"legacy"}\n',
            "nodes.csv": b"resid,resname,condition\n1,ALA,normal\n",
            "graph.json": b'{"nodes":[],"edges":[]}\n',
            "old.bin": b"unrelated\x00\xff",
        }
        for name, content in sentinels.items():
            (self.root / name).write_bytes(content)
        before = self.model.to_dict()
        with (
            no_discovery(),
            patch.object(inventory_io, "stream_file_sha256", forbidden),
            patch.object(hashlib, "sha256", forbidden),
            patch.object(Path, "read_bytes", forbidden),
            patch.object(Path, "read_text", forbidden),
        ):
            result = write_artifact_inventory(self.model, self.root)
        self.assertTrue(result.passed)
        self.assertEqual(self.model.to_dict(), before)
        self.assertEqual(json.loads(result.output_path.read_text()), before)
        for name, content in sentinels.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        self.assertEqual(
            set(path.name for path in self.root.iterdir()),
            set(sentinels) | {"source.bin", "artifact_inventory.json"},
        )
        self.assertNotIn(
            "artifact_inventory.json", [e.path for e in self.model.artifacts]
        )
        self.assertFalse((self.root / "checksums.sha256").exists())

    def test_existing_contract_and_dependency_boundaries(self):
        from mania import artifact_inventory, constants
        from mania.export.run_meta import RunMeta

        forbidden_fields = {
            "sha256",
            "byte_size",
            "checksum_mode",
            "artifact_inventory",
        }
        self.assertFalse(
            forbidden_fields.intersection(field.name for field in fields(RunMeta))
        )
        for columns in constants.ARTIFACT_COLUMNS.values():
            self.assertFalse(forbidden_fields.intersection(columns))
        self.assertFalse(forbidden_fields.intersection(constants.GRAPH_REQUIRED_KEYS))
        self.assertNotIn("artifact_inventory.json", constants.ARTIFACT_COLUMNS)
        for module in (artifact_inventory, inventory_io):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imports = [node.module]
                for name in imports:
                    self.assertTrue(
                        name == "mania.artifact_inventory"
                        or name.split(".")[0] in sys.stdlib_module_names
                    )
        contract = (
            Path(__file__).parents[1] / "docs/artifact_inventory_contract.md"
        ).read_text()
        for name in (
            "run_provenance.json",
            "mania_manifest.json",
            "extended_metrics.json",
            "RunMeta",
        ):
            self.assertIn(name, contract)
        self.assertIn("None replaces another", contract)
        self.assertIn("no scientific row, schema, value", contract)


if __name__ == "__main__":
    unittest.main()
