import math

from mania.preprocessing import (
    AROMATIC_PI_MAX_CENTROID_DISTANCE_A,
    AROMATIC_PI_PARALLEL_MAX_ANGLE_DEG,
    AROMATIC_PI_TSHAPED_MAX_ANGLE_DEG,
    AROMATIC_PI_TSHAPED_MIN_ANGLE_DEG,
    CATION_PI_MAX_DISTANCE_A,
    ResidueChemistryCandidate,
    build_aromatic_ring_candidate,
    build_aromatic_ring_geometry,
    build_cation_center_candidate,
    detect_aromatic_pi_geometry,
    detect_cation_pi_distance,
    sign_invariant_normal_angle_deg,
)


def planar_hexagon(
    *,
    z: float = 0.0,
) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (
            math.cos(index * math.pi / 3.0),
            math.sin(index * math.pi / 3.0),
            z,
        )
        for index in range(6)
    )


def rotated_hexagon(
    angle_deg: float,
    *,
    z_offset: float = 4.0,
) -> tuple[tuple[float, float, float], ...]:
    angle = math.radians(angle_deg)
    return tuple(
        (
            x * math.cos(angle),
            y,
            z_offset - x * math.sin(angle),
        )
        for x, y, _ in planar_hexagon()
    )


def test_ring_centroid_and_normal_are_deterministic_and_normalized() -> None:
    first = build_aromatic_ring_geometry(planar_hexagon(z=2.0))
    second = build_aromatic_ring_geometry(planar_hexagon(z=2.0))

    assert first is not None
    assert first == second
    assert all(
        math.isclose(value, expected, abs_tol=1e-12)
        for value, expected in zip(
            first.centroid,
            (0.0, 0.0, 2.0),
            strict=True,
        )
    )
    assert math.isclose(
        math.sqrt(sum(value * value for value in first.normal)),
        1.0,
    )


def test_normal_angle_is_sign_invariant() -> None:
    angle = sign_invariant_normal_angle_deg(
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
    )

    assert angle == 0.0


def test_aromatic_pi_parallel_uses_centroid_distance() -> None:
    first = build_aromatic_ring_geometry(planar_hexagon())
    second = build_aromatic_ring_geometry(planar_hexagon(z=4.0))

    assert first is not None
    assert second is not None
    interaction = detect_aromatic_pi_geometry(first, second)
    assert interaction is not None
    assert interaction.mode == "parallel"
    assert math.isclose(interaction.distance_A, 4.0)
    assert math.isclose(interaction.normal_angle_deg, 0.0)


def test_aromatic_pi_t_shaped_geometry_is_detected() -> None:
    first = build_aromatic_ring_geometry(planar_hexagon())
    second = build_aromatic_ring_geometry(rotated_hexagon(90.0))

    assert first is not None
    assert second is not None
    interaction = detect_aromatic_pi_geometry(first, second)
    assert interaction is not None
    assert interaction.mode == "t_shaped"
    assert math.isclose(interaction.normal_angle_deg, 90.0)


def test_aromatic_pi_outside_angle_is_rejected() -> None:
    first = build_aromatic_ring_geometry(planar_hexagon())
    second = build_aromatic_ring_geometry(rotated_hexagon(45.0))

    assert first is not None
    assert second is not None
    assert detect_aromatic_pi_geometry(first, second) is None


def test_aromatic_pi_outside_notebook_distance_is_rejected() -> None:
    first = build_aromatic_ring_geometry(planar_hexagon())
    second = build_aromatic_ring_geometry(
        planar_hexagon(z=AROMATIC_PI_MAX_CENTROID_DISTANCE_A + 0.1)
    )

    assert first is not None
    assert second is not None
    assert detect_aromatic_pi_geometry(first, second) is None


def test_cation_pi_distance_is_strictly_below_six_angstrom() -> None:
    assert detect_cation_pi_distance((0.0, 0.0, 5.9), (0.0, 0.0, 0.0)) == 5.9
    assert (
        detect_cation_pi_distance(
            (0.0, 0.0, CATION_PI_MAX_DISTANCE_A),
            (0.0, 0.0, 0.0),
        )
        is None
    )


def test_supported_ring_and_cation_helpers_skip_incomplete_candidates() -> None:
    phe = ResidueChemistryCandidate(
        residue_index=0,
        residue_id=10,
        resname="PHE",
        segid="A",
        atom_coordinates=tuple(
            zip(
                ("CG", "CD1", "CD2", "CE1", "CE2", "CZ"),
                planar_hexagon(),
                strict=True,
            )
        ),
    )
    lys = ResidueChemistryCandidate(
        residue_index=1,
        residue_id=11,
        resname="LYS",
        segid="A",
        atom_coordinates=(("NZ", (0.0, 0.0, 5.0)),),
    )
    incomplete = ResidueChemistryCandidate(
        residue_index=2,
        residue_id=12,
        resname="TYR",
        segid="A",
        atom_coordinates=(("CG", (0.0, 0.0, 0.0)),),
    )

    assert build_aromatic_ring_candidate(phe) is not None
    assert build_cation_center_candidate(lys) is not None
    assert build_aromatic_ring_candidate(incomplete) is None


def test_geometry_constants_match_stage_16_10_contract() -> None:
    assert AROMATIC_PI_MAX_CENTROID_DISTANCE_A == 7.0
    assert AROMATIC_PI_PARALLEL_MAX_ANGLE_DEG == 30.0
    assert AROMATIC_PI_TSHAPED_MIN_ANGLE_DEG == 60.0
    assert AROMATIC_PI_TSHAPED_MAX_ANGLE_DEG == 120.0
    assert CATION_PI_MAX_DISTANCE_A == 6.0
