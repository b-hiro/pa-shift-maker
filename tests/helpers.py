"""
シフト生成結果がハード制約を守っているかを検査するヘルパー。

完全一致（この人はこのバンドに必ず入る）ではなく、
「ルールを破っていないか」を見るための関数群。
"""

from app import (
    LEADER_SKILL_LEVEL,
    _band_order_and_times,
    has_time_conflict,
)


def members_by_name(members):
    return {m["name"]: m for m in members}


def feasible_band_names(day_shift, infeasible_bands):
    """成立したバンド名だけを返す（不成立バンドはリーダー不在でもよいので検査対象外）。"""
    infeasible_names = {entry["band"] for entry in (infeasible_bands or [])}
    return [band for band in day_shift.keys() if band not in infeasible_names]


def assert_team_has_leader(team_names, members_map, skill_field, context):
    skills = [members_map[name][skill_field] for name in team_names]
    assert any(skill >= LEADER_SKILL_LEVEL for skill in skills), (
        f"{context}: スキル{LEADER_SKILL_LEVEL}以上のリーダーがいません "
        f"(members={team_names}, skills={skills})"
    )


def assert_no_double_assignment(day_shift, infeasible_bands=None):
    for band in feasible_band_names(day_shift, infeasible_bands):
        teams = day_shift[band]
        desk = set(teams.get("卓", []))
        stage = set(teams.get("ステージ", []))
        overlap = desk & stage
        assert not overlap, f"{band}: 同一人物が卓とステージの両方に入っています {overlap}"


def assert_leaders_present(day_shift, members, infeasible_bands=None):
    members_map = members_by_name(members)
    for band in feasible_band_names(day_shift, infeasible_bands):
        teams = day_shift[band]
        assert_team_has_leader(teams.get("卓", []), members_map, "skill_desk", f"{band}/卓")
        assert_team_has_leader(teams.get("ステージ", []), members_map, "skill_stage", f"{band}/ステージ")


def assert_ng_bands_respected(day_shift, members, timetable, infeasible_bands=None):
    """
    生成ロジックと同じく、出演バンド（ng_bands）本人だけでなく
    前後のバンドにも入れない、という制約を検査する。
    """
    band_order, _ = _band_order_and_times(timetable)
    members_map = members_by_name(members)
    feasible = set(feasible_band_names(day_shift, infeasible_bands))

    for i, band in enumerate(band_order):
        if band not in feasible:
            continue
        prev_band = band_order[i - 1] if i > 0 else None
        next_band = band_order[i + 1] if i < len(band_order) - 1 else None
        assigned = set(day_shift[band].get("卓", [])) | set(day_shift[band].get("ステージ", []))
        for name in assigned:
            ng_bands = set(members_map[name].get("ng_bands") or [])
            # 生成ロジックと同じ: 自分の出演バンド、またはその前後なら配置不可
            if band in ng_bands or (prev_band in ng_bands) or (next_band in ng_bands):
                assert False, (
                    f"{name} は ng_bands={sorted(ng_bands)} なのに {band} に配置されています"
                )


def assert_ng_times_respected(day_shift, members, timetable, day_num, infeasible_bands=None):
    _, band_times = _band_order_and_times(timetable)
    members_map = members_by_name(members)
    for band in feasible_band_names(day_shift, infeasible_bands):
        assigned = set(day_shift[band].get("卓", [])) | set(day_shift[band].get("ステージ", []))
        slots = band_times[band]
        for name in assigned:
            member = members_map[name]
            assert not has_time_conflict(slots, member, day_num), (
                f"{name} は NG時間があるのに {band} ({slots}) に配置されています"
            )


def assert_limits_respected(members, config):
    desk_limit = config.get("desk_limit_per_member")
    stage_limit = config.get("stage_limit_per_member")
    total_limit = config.get("total_limit_per_member")
    for m in members:
        if desk_limit is not None:
            assert m.get("desk_count", 0) <= desk_limit, (
                f"{m['name']}: desk_count={m.get('desk_count')} > desk_limit={desk_limit}"
            )
        if stage_limit is not None:
            assert m.get("stage_count", 0) <= stage_limit, (
                f"{m['name']}: stage_count={m.get('stage_count')} > stage_limit={stage_limit}"
            )
        if total_limit is not None:
            assert m.get("count", 0) <= total_limit, (
                f"{m['name']}: count={m.get('count')} > total_limit={total_limit}"
            )


def count_assignments_in_day_shift(day_shift, infeasible_bands=None):
    """成立バンドだけを対象に、名前ごとの配置回数を数える。"""
    counts = {}
    for band in feasible_band_names(day_shift, infeasible_bands):
        teams = day_shift[band]
        for name in set(teams.get("卓", [])) | set(teams.get("ステージ", [])):
            counts[name] = counts.get(name, 0) + 1
    return counts


def assert_day_shift_constraints(day_shift, members, timetable, config, day_num, infeasible_bands=None):
    assert_leaders_present(day_shift, members, infeasible_bands)
    assert_no_double_assignment(day_shift, infeasible_bands)
    assert_ng_bands_respected(day_shift, members, timetable, infeasible_bands)
    assert_ng_times_respected(day_shift, members, timetable, day_num, infeasible_bands)
    assert_limits_respected(members, config)


def assert_multi_day_constraints(shift_result, members, timetable_multi, config, infeasible_days=None):
    infeasible_days = infeasible_days or {}
    for day_key, day_shift in shift_result.items():
        day_num = int(str(day_key).split("_")[1])
        timetable = timetable_multi[day_key]
        infeasible_bands = infeasible_days.get(day_key, [])
        assert_day_shift_constraints(
            day_shift, members, timetable, config, day_num, infeasible_bands
        )

    # 複数日通算: members の count が、全日程の配置回数合計と一致すること
    totals = {}
    for day_key, day_shift in shift_result.items():
        infeasible_bands = infeasible_days.get(day_key, [])
        day_counts = count_assignments_in_day_shift(day_shift, infeasible_bands)
        for name, n in day_counts.items():
            totals[name] = totals.get(name, 0) + n

    for m in members:
        expected = totals.get(m["name"], 0)
        assert m.get("count", 0) == expected, (
            f"{m['name']}: count={m.get('count')} だが配置合計は {expected}"
        )
        assert m.get("count", 0) == m.get("desk_count", 0) + m.get("stage_count", 0), (
            f"{m['name']}: count != desk_count + stage_count"
        )
