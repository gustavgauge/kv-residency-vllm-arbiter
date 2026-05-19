from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "vllm_resident_claim_prototype.patch"


def test_vllm_patch_tracks_logical_positions_for_claim_predicates() -> None:
    patch_text = PATCH.read_text()

    assert "logical_block_positions" in patch_text
    assert "_kv_residency_leading_blocks_survived" in patch_text
    assert "_kv_residency_claim_predicate_fields" in patch_text
    assert "logical_block_position=num_cached_blocks + i" in patch_text


def test_vllm_patch_does_not_use_raw_block_count_as_prefix_predicate() -> None:
    patch_text = PATCH.read_text()

    assert 'len(claim["block_ids"]) >= threshold' not in patch_text
    assert 'len(claim["block_ids"]) < threshold' not in patch_text
    assert 'predicate_fields["predicate_materialized"]' in patch_text
    assert 'predicate_before["predicate_materialized"]' in patch_text
    assert 'predicate_after["predicate_materialized"]' in patch_text
