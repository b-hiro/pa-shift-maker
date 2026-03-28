import copy

def generate_pa_shift(timetable, members_data, rehearsal_time=15, act_time=30):
    """
    PAシフトを作成する関数（現在のバージョン）
    """
    # 元のデータを破壊しないよう、関数内でコピーを作成して計算する
    members = copy.deepcopy(members_data)
    shift_result = {}

    for band in timetable:
        desk_team = []
        stage_team = []
        desk_score = 0
        stage_score = 0

        # 1. NGの人を除外して、この枠に入れる候補者リストを作成
        available = []
        for m in members:
            if band not in m["ng"]:
                # 優先度ポイントの計算
                priority = -m["count"] * 10 
                if band in m["req"]:
                    priority += 100
                priority += m["skill"]
                
                candidate = m.copy()
                candidate["priority"] = priority
                available.append(candidate)
        
        # 2. 優先度ポイントが高い順に並び替え
        available.sort(key=lambda x: x["priority"], reverse=True)

        # 3. 卓チームを組む（目標：スキル合計5以上）
        remaining = []
        for m in available:
            if desk_score < 5:
                desk_team.append(m)
                desk_score += m["skill"]
            else:
                remaining.append(m)
                
        # 4. ステージチームを組む（目標：スキル合計3以上）
        for m in remaining:
            if stage_score < 3:
                stage_team.append(m)
                stage_score += m["skill"]
        
        # 5. 結果の保存とカウントの更新
        if desk_score >= 5 and stage_score >= 3:
            shift_result[band] = {
                "卓": [m["name"] for m in desk_team], 
                "ステージ": [m["name"] for m in stage_team],
                "リハ時間": rehearsal_time,
                "本番時間": act_time
            }
            assigned_names = [m["name"] for m in desk_team + stage_team]
            for m in members:
                if m["name"] in assigned_names:
                    m["count"] += 1
        else:
            shift_result[band] = {"エラー": "スキル条件を満たすメンバーが足りません！要手動調整"}

    return shift_result, members

# ==========================================
# 実行用ブロック（テストデータ）
# ==========================================
if __name__ == "__main__":
    my_timetable = ["バンドA", "バンドB", "バンドC"]
    
    my_members = [
        {"name": "ベテラン先輩", "skill": 5, "count": 0, "ng": ["バンドA"], "req": ["バンドC"]},
        {"name": "自分", "skill": 5, "count": 0, "ng": ["バンドC"], "req": []},
        {"name": "中堅同期", "skill": 3, "count": 0, "ng": [], "req": ["バンドA"]},
        {"name": "初心者後輩1", "skill": 1, "count": 0, "ng": [], "req": []},
        {"name": "初心者後輩2", "skill": 1, "count": 0, "ng": ["バンドB"], "req": []},
        {"name": "初心者後輩3", "skill": 1, "count": 0, "ng": [], "req": []}
    ]

    result_shift, final_members = generate_pa_shift(my_timetable, my_members)

    print("--- シフト作成結果 ---")
    for band, teams in result_shift.items():
        print(f"【{band}】: {teams}")
        
    print("\n--- 最終的なシフト入数 ---")
    for m in final_members:
        print(f"{m['name']}: {m['count']}回")