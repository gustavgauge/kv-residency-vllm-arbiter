from kv_vllm_arbiter.materialization import (
    evaluate_leading_prefix,
    leading_prefix_length,
)


def test_many_surviving_blocks_do_not_materialize_missing_leading_prefix() -> None:
    evaluation = evaluate_leading_prefix(range(1, 61), required_blocks=60)

    assert evaluation.surviving_blocks == 60
    assert evaluation.leading_blocks == 0
    assert not evaluation.materialized


def test_contiguous_leading_prefix_materializes_at_threshold() -> None:
    evaluation = evaluate_leading_prefix(range(60), required_blocks=60)

    assert evaluation.surviving_blocks == 60
    assert evaluation.leading_blocks == 60
    assert evaluation.materialized


def test_losing_leading_block_breaks_previously_materialized_claim() -> None:
    before = evaluate_leading_prefix(range(70), required_blocks=60)
    after = evaluate_leading_prefix(range(1, 70), required_blocks=60)

    assert before.materialized
    assert not after.materialized


def test_losing_tail_above_threshold_does_not_break_claim() -> None:
    before = evaluate_leading_prefix(range(70), required_blocks=60)
    after = evaluate_leading_prefix(range(69), required_blocks=60)

    assert before.materialized
    assert after.materialized


def test_leading_prefix_length_ignores_tail_fragments() -> None:
    assert leading_prefix_length([0, 1, 2, 8, 9, 10]) == 3
