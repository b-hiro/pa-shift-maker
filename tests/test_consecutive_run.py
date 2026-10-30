"""
連続で入るバンド数の推奨（consecutive_run_target・ソフト制約）のテスト。

ソフト制約なので「厳密に何回ずつになる」ではなく、
- 指定が検証されること
- 指定しない場合は従来どおり（状態に影響しない）であること
- 指定すると、続けて入る回数が推奨に寄ること（統計的に）
- ハード制約（リーダー必須・成立）を壊さないこと
を確認する。
"""

import copy

import pytest

from app import (
    _candidate_quality,
    generate_pa_shift,
    generate_pa_shift_multi_day,
    generate_timetable,
    generate_timetable_multi_day,
    parse_shift_config,
)


def _member(name, skill_desk=3, skill_stage=3):
    return {
        "name": name,
        "skill_desk": skill_desk,
        "skill_stage": skill_stage,
        "count": 0,
        "grade": None,
        "ng_bands": [],
        "ng_times": {},
        "req_bands": [],
    }


def _members():
    # リーダー6人 + アシスタント2人。バンド数に対して人数に余裕があり、休みを入れられる編成
    return [_member(f"L{i}", 3, 3) for i in range(6)] + [_member("A1", 1, 1), _member("A2", 1, 2)]


def _consecutive_stats(shift, target):
    """(連続で入った回数の延べ, 推奨を超えて続けて入った回数) を返す。shift: {band: {卓, ステージ}}"""
    runs = {}
    adjacent = 0
    over = 0
    for team in shift.values():
        working = set(team["卓"]) | set(team["ステージ"])
        for name in list(runs):
            if name not in working:
                del runs[name]
        for name in working:
            runs[name] = runs.get(name, 0) + 1
            if runs[name] > 1:
                adjacent += 1
            if target and runs[name] > target:
                over += 1
    return adjacent, over


@pytest.mark.parametrize("value", [0, -1, "2", 1.5, True])
def test_invalid_consecutive_run_target_is_rejected(value):
    config, error = parse_shift_config({"consecutive_run_target": value})
    assert config is None
    assert "consecutive_run_target" in error


@pytest.mark.parametrize("value", [None, 1, 2, 5])
def test_valid_consecutive_run_target_is_accepted(value):
    config, error = parse_shift_config({"consecutive_run_target": value})
    assert error is None
    assert config["consecutive_run_target"] == value


def test_unset_target_has_no_effect_on_quality():
    members = [{"name": "a", "count": 2, "run_overrun": 0}, {"name": "b", "count": 2}]
    with_overrun_field = _candidate_quality(0, 0, [2, 2], members)
    assert with_overrun_field[4] == 0
    # 超過した案は、他が同じなら悪い案として扱われる
    worse = _candidate_quality(0, 0, [2, 2], [{"name": "a", "count": 2, "run_overrun": 3}, {"name": "b", "count": 2}])
    assert worse > with_overrun_field


def test_target_one_reduces_back_to_back_shifts():
    """推奨1（続けて入らない）にすると、指定なしより続けて入る回数が減る。"""
    bands = [f"B{i}" for i in range(10)]
    timetable = generate_timetable("11:00", bands, 10, 10)
    base = {"desk_max_members": 2, "stage_max_members": 2, "candidate_count": 8}

    def total_adjacent(target):
        total = 0
        for _ in range(6):
            config = {**base, "consecutive_run_target": target}
            shift, _, infeasible = generate_pa_shift(timetable, copy.deepcopy(_members()), day_num=1, config=config)
            assert infeasible == []  # ソフト制約なので成立は損なわれない
            total += _consecutive_stats(shift, target)[0]
        return total

    assert total_adjacent(1) < total_adjacent(None)


def test_target_two_keeps_runs_short_and_feasible():
    """推奨2にすると、3回以上続けて入る回数が指定なしより減り、成立は保たれる。"""
    bands = [f"B{i}" for i in range(12)]
    timetable = generate_timetable("11:00", bands, 10, 10)
    base = {"desk_max_members": 2, "stage_max_members": 2, "candidate_count": 8}

    def total_over_two(target):
        total = 0
        for _ in range(6):
            config = {**base, "consecutive_run_target": target}
            shift, _, infeasible = generate_pa_shift(timetable, copy.deepcopy(_members()), day_num=1, config=config)
            assert infeasible == []
            total += _consecutive_stats(shift, 2)[1]
        return total

    assert total_over_two(2) <= total_over_two(None)


def test_run_is_counted_per_day_in_multi_day():
    """日をまたいだ連続は数えない: 全日程で同じメンバー構成でも、日の最初のバンドは連続0から始まる。"""
    timetable_multi = generate_timetable_multi_day({
        "num_days": 2,
        "days": [
            {"day_number": 1, "start_time": "11:00", "bands": ["A", "B", "C"], "rh_mins": 10, "act_mins": 10},
            {"day_number": 2, "start_time": "11:00", "bands": ["D", "E", "F"], "rh_mins": 10, "act_mins": 10},
        ],
    })
    config = {"desk_max_members": 2, "stage_max_members": 2, "candidate_count": 4, "consecutive_run_target": 2}
    _, members, infeasible_days = generate_pa_shift_multi_day(timetable_multi, _members(), config)
    assert not infeasible_days
    # 1日は3バンドなので、日をまたいで数えていなければ連続の超過は最大でも1日分(3-2=1回)に収まる
    assert all(m["run_overrun"] <= 2 for m in members)
