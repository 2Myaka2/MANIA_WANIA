# Local scientific tests

This directory is the test harness space for local-only scientific checks.
Tests here are collected by default but skipped unless local execution is
explicitly enabled:

```bash
MANIA_RUN_LOCAL_SCIENTIFIC=1 pytest tests/local_scientific
```

Tests that need local real data use `MANIA_LOCAL_REFERENCE_PACKAGE`:

```bash
MANIA_RUN_LOCAL_SCIENTIFIC=1 \
MANIA_LOCAL_REFERENCE_PACKAGE=/path/to/local/package \
pytest tests/local_scientific
```

The reference package remains local. Do not commit real topology, trajectory,
structure, or reference-package data here.

The current smoke tests verify only the harness and markers. They do not load
topology or trajectory files and are not scientific integration tests.
