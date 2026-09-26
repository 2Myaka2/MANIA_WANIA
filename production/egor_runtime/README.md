# Tracked Egor runtime authority

This is the small runtime subset of the reviewed Egor handoff. The authority,
controls, templates and catalog were copied byte-for-byte from the accepted
`e3f69331f95a` handoff. `HANDOFF_FILES.sha256` inventories this subset. No delivery
archive, historical directory, prepared coordinates or old outputs are needed.

The retained manifest contains historical packaging/checkpoint fields. Those
fields, and provenance paths inside immutable controls, are historical records,
never runtime paths. Runtime selection reads only the explicit catalog, rows,
systems, source inventory, shared toppar, PBC protocol and per-replica templates.
The catalog copy matches `production/dataset_v1` exactly; catalog updates must
also update the templates through a separately reviewed authority change.

`source_inventory.json` defines the exact source/run mapping. Its `egor/` prefix
is a logical mount: the launcher's first argument supplies that directory.
Paths below it are literal, including the two reviewed delivered r1 DCD names
that differ from the CONF/OUT declarations. No recursive filename search or
scientific inference occurs. Missing inputs are reported by trajectory and path.

The launcher creates a private hard-link view under `EGOR_DATA_DIR/.mania_egor/`,
copies these small controls unchanged, and uses the existing preparation tool.
Hard links retain the raw bytes without duplicating their storage. The input
directory must be writable and its selected files must support hard links onto
that filesystem. Source symlinks escaping the input directory are rejected.
The original sources are checked again before confirmation and each production
run; replacing a source cannot leave an unnoticed stale hard-link snapshot.

The technical manifest is used only by the advanced acceptance-test option.
Normal operation always selects all nine production trajectories at 5–100 ns.
