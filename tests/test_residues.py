import mania.residues as residues


def test_normalize_resname_strips_spaces_and_uppercases() -> None:
    assert residues.normalize_resname(" lip ") == "LIP"


def test_normalize_resname_blank_string_returns_empty_string() -> None:
    assert residues.normalize_resname("   ") == ""


def test_placeholder_registries_are_empty_frozensets() -> None:
    assert residues.LIPID_RESIDUES == frozenset()
    assert residues.GLYCAN_RESIDUES == frozenset()
    assert residues.GLYCOLIPID_RESIDUES == frozenset()

    assert isinstance(residues.LIPID_RESIDUES, frozenset)
    assert isinstance(residues.GLYCAN_RESIDUES, frozenset)
    assert isinstance(residues.GLYCOLIPID_RESIDUES, frozenset)


def test_derived_sets_are_empty_frozensets_by_default() -> None:
    assert residues.ALL_LIPIDS == frozenset()
    assert residues.ALL_GLYCANS == frozenset()
    assert residues.ALL_GLYCOLIPIDS == frozenset()

    assert isinstance(residues.ALL_LIPIDS, frozenset)
    assert isinstance(residues.ALL_GLYCANS, frozenset)
    assert isinstance(residues.ALL_GLYCOLIPIDS, frozenset)


def test_lipid_classification_uses_lipid_registry(monkeypatch) -> None:
    monkeypatch.setattr(residues, "LIPID_RESIDUES", frozenset({"LIP"}))

    assert residues.is_lipid_residue("LIP")
    assert residues.classify_nonprotein_residue("LIP") == "lipid"


def test_glycan_classification_uses_glycan_registry(monkeypatch) -> None:
    monkeypatch.setattr(residues, "GLYCAN_RESIDUES", frozenset({"GLY"}))

    assert residues.is_glycan_residue("GLY")
    assert residues.classify_nonprotein_residue("GLY") == "glycan"


def test_glycolipid_classification_uses_glycolipid_registry(monkeypatch) -> None:
    monkeypatch.setattr(residues, "GLYCOLIPID_RESIDUES", frozenset({"GLIP"}))

    assert residues.is_glycolipid_residue("GLIP")
    assert residues.classify_nonprotein_residue("GLIP") == "glycolipid"


def test_glycolipid_priority_wins_for_overlapping_registries(monkeypatch) -> None:
    monkeypatch.setattr(residues, "LIPID_RESIDUES", frozenset({"BOTH"}))
    monkeypatch.setattr(residues, "GLYCAN_RESIDUES", frozenset({"BOTH"}))
    monkeypatch.setattr(residues, "GLYCOLIPID_RESIDUES", frozenset({"BOTH"}))

    assert residues.classify_nonprotein_residue("BOTH") == "glycolipid"


def test_unknown_residue_returns_none() -> None:
    assert residues.classify_nonprotein_residue("UNKNOWN") is None


def test_classification_is_case_insensitive_and_strips_spaces(monkeypatch) -> None:
    monkeypatch.setattr(residues, "LIPID_RESIDUES", frozenset({"LIP"}))

    assert residues.classify_nonprotein_residue(" lip ") == "lipid"


def test_edge_type_protein_glycolipid_constant() -> None:
    assert residues.EDGE_TYPE_PROTEIN_GLYCOLIPID == "protein_glycolipid"
