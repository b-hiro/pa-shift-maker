"""
シフト生成のハード制約を pytest で固定する。

完全一致ではなく「生成結果が制約を満たすか」「リーダー不足時に不成立になるか」を見る。
ランダム性があるので、成功ケースは複数回回して守られることを確認する。
"""

import copy

import pytest

from app import (
    generate_pa_shift,
    generate_pa_shift_multi_day,
    generate_timetable,
    generate_timetable_multi_day,
)
from tests.helpers import (
    assert_day_shift_constraints,
    assert_multi_day_constraints,
    count_assignments_in_day_shift,
)


def _member(name, skill_desk=3, skill_stage=3, ng_bands=None, ng_times=None, grade=None):
    return {
        "name": name,
        "skill_desk": skill_desk,
        "skill_stage": skill_stage,
        "count": 0,
        "grade": grade,
        "ng_bands": ng_bands or [],
        "ng_times": ng_times or {},
        "req_bands": [],
    }


def _base_members():
    """リーダー多め + アシスタント少し、の小さな編成。"""
    return [
        _member("L1", 3, 3),
        _member("L2", 3, 3),
        _member("L3", 3, 3),
        _member("L4", 3, 3),
        _member("A1", 1, 1),
        _member("A2", 1, 2),
    ]


@pytest.fixture
def base_config():
    return {
        "desk_max_members": 2,
        "stage_max_members": 2,
        "candidate_count": 8,
    }


def test_feasible_shift_keeps_hard_constraints(base_config):
    """成立するシフトでは、リーダー必須・二重配置禁止・回数上限を守る。"""
    bands = ["BandA", "BandB", "BandC", "BandD"]
    timetable = generate_timetable("11:00", bands, 10, 10)
    config = {
        **base_config,
        "total_limit_per_member": 3,
        "desk_limit_per_member": 3,
        "stage_limit_per_member": 3,
    }

    # ランダム揺れがあるので複数回確認する
    for _ in range(5):
        members = _base_members()
        day_shift, updated, infeasible = generate_pa_shift(
            timetable, copy.deepcopy(members), day_num=1, config=config
        )
        assert infeasible == []
        assert_day_shift_constraints(day_shift, updated, timetable, config, day_num=1, infeasible_bands=[])


def test_ng_band_and_adjacent_not_assigned(base_config):
    """出演バンド本人とその前後のバンドには入らない。"""
    bands = ["BandA", "BandB", "BandC"]
    timetable = generate_timetable("11:00", bands, 10, 10)
    members = _base_members()
    # L1 は BandB 出演 → BandA/B/C すべて配置不可になるはず
    members[0]["ng_bands"] = ["BandB"]

    for _ in range(5):
        day_shift, updated, infeasible = generate_pa_shift(
            timetable, copy.deepcopy(members), day_num=1, config=base_config
        )
        assert infeasible == []
        assert_day_shift_constraints(
            day_shift, updated, timetable, base_config, day_num=1, infeasible_bands=[]
        )
        for band, teams in day_shift.items():
            assigned = set(teams["卓"]) | set(teams["ステージ"])
            assert "L1" not in assigned, f"L1 が {band} に入っている"


def test_ng_times_not_assigned(base_config):
    """NG時間に重なるバンドには入らない。"""
    bands = ["BandA", "BandB", "BandC"]
    # 11:00-11:10 rh / 11:10-11:20 act → BandA
    # 11:20-11:30 rh / 11:30-11:40 act → BandB
    timetable = generate_timetable("11:00", bands, 10, 10)
    members = _base_members()
    # BandA の時間帯全体を NG にする
    members[0]["ng_times"] = {"day_1": ["11:00-11:20"]}

    for _ in range(5):
        day_shift, updated, infeasible = generate_pa_shift(
            timetable, copy.deepcopy(members), day_num=1, config=base_config
        )
        assert infeasible == []
        assert_day_shift_constraints(
            day_shift, updated, timetable, base_config, day_num=1, infeasible_bands=[]
        )
        assigned_a = set(day_shift["BandA"]["卓"]) | set(day_shift["BandA"]["ステージ"])
        assert "L1" not in assigned_a


def test_total_limit_not_exceeded(base_config):
    """絶対上限 total_limit_per_member を超えない。"""
    bands = ["B1", "B2", "B3", "B4", "B5"]
    timetable = generate_timetable("10:00", bands, 10, 10)
    config = {**base_config, "total_limit_per_member": 2, "candidate_count": 12}

    for _ in range(5):
        day_shift, updated, infeasible = generate_pa_shift(
            timetable, copy.deepcopy(_base_members()), day_num=1, config=config
        )
        # 上限がきついと一部不成立もあり得るが、成立分・member count は上限内
        assert_day_shift_constraints(
            day_shift, updated, timetable, config, day_num=1, infeasible_bands=infeasible
        )
        for m in updated:
            assert m["count"] <= 2


def test_no_leaders_makes_bands_infeasible(base_config):
    """リーダー候補が誰もいない場合、正しく不成立になる。"""
    bands = ["BandA", "BandB"]
    timetable = generate_timetable("11:00", bands, 10, 10)
    members = [
        _member("A1", 1, 1),
        _member("A2", 1, 1),
        _member("A3", 2, 2),
    ]

    day_shift, updated, infeasible = generate_pa_shift(
        timetable, members, day_num=1, config=base_config
    )
    assert len(infeasible) == 2
    infeasible_names = {entry["band"] for entry in infeasible}
    assert infeasible_names == {"BandA", "BandB"}
    for entry in infeasible:
        assert entry["desk_has_leader"] is False or entry["stage_has_leader"] is False
        assert "リーダー" in entry["reason"]


def test_multi_day_counts_are_cumulative(base_config):
    """複数日でも配置回数が通算され、制約も日をまたいで守られる。"""
    timetable_multi = generate_timetable_multi_day(
        {
            "num_days": 2,
            "days": [
                {
                    "day_number": 1,
                    "start_time": "11:00",
                    "bands": ["D1B1", "D1B2", "D1B3"],
                    "rh_mins": 10,
                    "act_mins": 10,
                },
                {
                    "day_number": 2,
                    "start_time": "12:00",
                    "bands": ["D2B1", "D2B2"],
                    "rh_mins": 10,
                    "act_mins": 10,
                },
            ],
        }
    )
    config = {**base_config, "total_limit_per_member": 4}

    for _ in range(5):
        shift_result, updated, infeasible_days = generate_pa_shift_multi_day(
            timetable_multi, copy.deepcopy(_base_members()), config=config
        )
        assert infeasible_days == {}
        assert_multi_day_constraints(
            shift_result, updated, timetable_multi, config, infeasible_days={}
        )

        # 通算: 全日の配置数を足すと count になる（helper側でも見ているが明示）
        totals = {}
        for day_key, day_shift in shift_result.items():
            for name, n in count_assignments_in_day_shift(day_shift).items():
                totals[name] = totals.get(name, 0) + n
        for m in updated:
            assert m["count"] == totals.get(m["name"], 0)


def _multi_day_timetable(num_days, bands_per_day):
    return generate_timetable_multi_day(
        {
            "num_days": num_days,
            "days": [
                {
                    "day_number": d,
                    "start_time": "11:00",
                    "bands": [f"D{d}B{i}" for i in range(1, bands_per_day + 1)],
                    "rh_mins": 10,
                    "act_mins": 10,
                }
                for d in range(1, num_days + 1)
            ],
        }
    )


def _days_worked(shift_result, name):
    days = set()
    for day_key, day_shift in shift_result.items():
        for teams in day_shift.values():
            if name in teams["卓"] or name in teams["ステージ"]:
                days.add(day_key)
    return days


def test_target_days_gathers_member_into_few_days(base_config):
    """出勤日数の目安（ソフト）を指定した人は、人手に余裕があれば目安の日数に収まる。"""
    timetable_multi = _multi_day_timetable(num_days=5, bands_per_day=4)
    members = _base_members() + [_member("L5", 3, 3), _member("L6", 3, 3)]
    members[0]["target_days"] = 2  # L1 は5日のうち2日にまとめたい
    config = {**base_config, "candidate_count": 12}

    for _ in range(5):
        shift_result, updated, infeasible_days = generate_pa_shift_multi_day(
            timetable_multi, copy.deepcopy(members), config=config
        )
        assert infeasible_days == {}
        assert_multi_day_constraints(
            shift_result, updated, timetable_multi, config, infeasible_days={}
        )
        worked = _days_worked(shift_result, "L1")
        assert len(worked) <= 2, f"L1 が {sorted(worked)} の{len(worked)}日に散らばっている"
        l1 = next(m for m in updated if m["name"] == "L1")
        assert sorted(l1["worked_days"]) == sorted(int(k.split("_")[1]) for k in worked)


def test_target_days_is_soft_and_does_not_break_feasibility(base_config):
    """目安はソフト制約: 他に候補がいない日は、目安を超えてでも成立を優先する。"""
    timetable_multi = _multi_day_timetable(num_days=3, bands_per_day=2)
    all_day_ng = ["00:00-23:59"]
    # 2・3日目はリーダーが L1 と もう1人しかいない。L1 は1日にまとめたいが、成立を優先して入る
    members = [
        _member("L1", 3, 3),
        _member("L2", 3, 3),
        _member("L3", 3, 3, ng_times={"day_2": all_day_ng, "day_3": all_day_ng}),
        _member("A1", 1, 1),
    ]
    members[0]["target_days"] = 1

    for _ in range(5):
        shift_result, updated, infeasible_days = generate_pa_shift_multi_day(
            timetable_multi, copy.deepcopy(members), config=base_config
        )
        assert infeasible_days == {}, "目安を理由に不成立になってはいけない（ソフト制約）"
        assert_multi_day_constraints(
            shift_result, updated, timetable_multi, base_config, infeasible_days={}
        )
        assert len(_days_worked(shift_result, "L1")) >= 2


def test_quality_prefers_lower_shortage_risk():
    """複数案の比較では、不成立の次に不足リスク（リーダー1人綱渡り）が低い案を選ぶ。"""
    from app import _candidate_quality

    members = [{"name": "L1", "count": 3}, {"name": "L2", "count": 1}]
    safe = _candidate_quality(0, 0, [2, 2], members)
    risky = _candidate_quality(0, 3, [2, 2], members)
    infeasible = _candidate_quality(1, 0, [2, 2], members)
    assert safe < risky < infeasible

    # 公平さ（回数のばらつき）より不足リスクを優先する
    even_but_risky = _candidate_quality(0, 2, [2, 2], [{"name": "a", "count": 2}, {"name": "b", "count": 2}])
    uneven_but_safe = _candidate_quality(0, 0, [2, 2], [{"name": "a", "count": 5}, {"name": "b", "count": 0}])
    assert uneven_but_safe < even_but_risky


def test_quality_ignores_target_days_members_in_fairness():
    """出勤日数を絞った人の回数は、全員均等という評価に含めない。"""
    from app import _candidate_quality

    with_focus = [
        {"name": "a", "count": 4},
        {"name": "b", "count": 4},
        {"name": "f", "count": 1, "target_days": 1, "worked_days": [1]},
    ]
    without_focus = [{"name": "a", "count": 4}, {"name": "b", "count": 4}]
    assert _candidate_quality(0, 0, [2], with_focus)[-1] == _candidate_quality(0, 0, [2], without_focus)[-1]


def test_invalid_target_days_is_rejected():
    from app import validate_members

    base = {"name": "X", "skill_desk": 3, "skill_stage": 3, "count": 0}
    assert validate_members([{**base, "target_days": 2}]) is None
    assert validate_members([{**base, "target_days": None}]) is None
    for bad in (0, -1, 1.5, "2", True):
        assert "target_days" in validate_members([{**base, "target_days": bad}])
