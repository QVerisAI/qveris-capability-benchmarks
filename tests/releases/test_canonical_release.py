from qveris_bench.releases.canonical import canonical_release_bytes, release_digest


def test_ac2_canonical_release_is_deterministic() -> None:
    first = canonical_release_bytes({"b": [2, 1], "a": {"z": True}})
    second = canonical_release_bytes({"a": {"z": True}, "b": [2, 1]})

    assert first == second
    assert release_digest(first).startswith("sha256:")
