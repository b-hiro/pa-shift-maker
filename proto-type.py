import copy
import csv
from datetime import datetime, timedelta

def generate_timetable(start_time_str, band_list, rh_mins, act_mins, break_info=None):
    """
    開始時間とバンドリストから、タイムテーブルを自動生成する関数
    """
    timetable = []
    # 文字列の時間を、計算できる「時計データ」に変換
    current_time = datetime.strptime(start_time_str, "%H:%M")

    for band in band_list:
        # 1. リハの時間を計算して追加
        rh_start = current_time.strftime("%H:%M")
        current_time += timedelta(minutes=rh_mins) # リハの分数だけ時間を進める
        rh_end = current_time.strftime("%H:%M")
        timetable.append({"time": f"{rh_start}-{rh_end}", "type": "rh", "name": band})

        # 2. 本番の時間を計算して追加
        act_start = current_time.strftime("%H:%M")
        current_time += timedelta(minutes=act_mins) # 本番の分数だけ時間を進める
        act_end = current_time.strftime("%H:%M")
        timetable.append({"time": f"{act_start}-{act_end}", "type": "act", "name": band})

        # 3. お昼休みの判定（もし指定されていて、今のバンドが終わった直後なら）
        if break_info and break_info.get("after_band") == band:
            break_start = current_time.strftime("%H:%M")
            current_time += timedelta(minutes=break_info["duration"]) # 休憩の分数だけ進める
            break_end = current_time.strftime("%H:%M")
            timetable.append({"time": f"{break_start}-{break_end}", "type": "break", "name": "昼休憩"})

    return timetable

def generate_pa_shift(timetable, members_data):
    """
    PAシフトを作成する関数（v2：リハ・本番セット化＆インターバル制約対応）
    """
    members = copy.deepcopy(members_data)
    shift_result = {}

    # 1. タイムテーブルから「シフト対象のバンド」と「前後の順番」を整理する
    band_times = {} # {"バンド名": ["リハ時間", "本番時間"]}
    band_order = [] # 前後関係を把握するためのリスト
    
    for entry in timetable:
        if entry["type"] == "break":
            continue # 休憩はシフト計算から除外
        
        b_name = entry["name"]
        if b_name not in band_times:
            band_times[b_name] = []
            band_order.append(b_name)
        band_times[b_name].append(entry["time"])

    # 2. バンドごとにシフトを計算（ここでリハと本番が1セットとして扱われます）
    for i, band in enumerate(band_order):
        desk_team = []
        stage_team = []
        desk_score = 0
        stage_score = 0

        # --- 新仕様：前後のバンドを取得 ---
        prev_band = band_order[i-1] if i > 0 else None
        next_band = band_order[i+1] if i < len(band_order)-1 else None

        # 卓チーム編成
        available_desk = []
        for m in members:
            # NG判定①：自分が出演するバンド、またはその「前後」ならシフト不可
            if band in m["ng_bands"] or prev_band in m["ng_bands"] or next_band in m["ng_bands"]:
                continue
            
            # NG判定②：LINEで指定されたNG時間に被っているか
            time_conflict = False
            for t in band_times[band]: # リハと本番の時間、両方をチェック
                if t in m["ng_times"]:
                    time_conflict = True
                    break
            if time_conflict:
                continue

            # 卓優先度計算
            priority_desk = -m["count"] * 10
            if band in m.get("req_bands", []):
                priority_desk += 100
            priority_desk += m["skill_desk"]
            
            candidate = m.copy()
            candidate["priority_desk"] = priority_desk
            available_desk.append(candidate)

        available_desk.sort(key=lambda x: x["priority_desk"], reverse=True)

        for m in available_desk:
            if desk_score < 5:
                desk_team.append(m)
                desk_score += m["skill_desk"]
        
        # ステージチーム編成
        available_stage = []
        for m in members:
            if m in desk_team:  # すでに卓に割り当てられたメンバーは除く
                continue
            # NG判定①：自分が出演するバンド、またはその「前後」ならシフト不可
            if band in m["ng_bands"] or prev_band in m["ng_bands"] or next_band in m["ng_bands"]:
                continue
            
            # NG判定②：LINEで指定されたNG時間に被っているか
            time_conflict = False
            for t in band_times[band]: # リハと本番の時間、両方をチェック
                if t in m["ng_times"]:
                    time_conflict = True
                    break
            if time_conflict:
                continue

            # ステージ優先度計算
            priority_stage = -m["count"] * 10
            if band in m.get("req_bands", []):
                priority_stage += 100
            priority_stage += m["skill_stage"]
            
            candidate = m.copy()
            candidate["priority_stage"] = priority_stage
            available_stage.append(candidate)

        available_stage.sort(key=lambda x: x["priority_stage"], reverse=True)

        for m in available_stage:
            if stage_score < 3:
                stage_team.append(m)
                stage_score += m["skill_stage"]
        
        # 3. 結果の保存とカウント更新（2枠セットで1カウント）
        shift_result[band] = {
            "卓": [m["name"] for m in desk_team], 
            "ステージ": [m["name"] for m in stage_team]
        }
        
        assigned_names = [m["name"] for m in desk_team + stage_team]
        for m in members:
            if m["name"] in assigned_names:
                m["count"] += 1

    return shift_result, members

def export_to_csv(timetable, shift_result, filename="pa_shift.csv"):
    """
    作成したシフトをCSVファイルとして保存する関数
    """
    with open(filename, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["時間帯", "種別", "バンド名", "担当（卓）", "担当（ステージ）"])

        for entry in timetable:
            time_str = entry["time"]
            type_str = entry["type"]
            band_name = entry["name"]
            
            if type_str == "break":
                writer.writerow([time_str, type_str, band_name, "", ""])
                continue
            
            assigned = shift_result.get(band_name, {})
            desk = "、".join(assigned.get("卓", []))
            stage = "、".join(assigned.get("ステージ", []))

            writer.writerow([time_str, type_str, band_name, desk, stage])
            
    print(f"CSVファイルを保存しました: {filename}")


# ==========================================
# 実行用ブロック
# ==========================================
if __name__ == "__main__":
    # 出演バンドのリストを定義するだけ！
    live_bands = ["LUNA SEA(D)", "PK shanpoo", "BUMP(コピー)", "アジカン(コピー)"]
    
    # お昼休みの設定（PK shanpooの後に60分）
    lunch_setting = {"after_band": "PK shanpoo", "duration": 60}

    # 関数を呼び出して、タイムテーブルを自動生成！
    # （10:30スタート、リハ15分、本番10分）
    my_timetable = generate_timetable("11:30", live_bands, 15, 10, lunch_setting)

    # --------------------------------------------------

    my_members = [
        # みらいさんはLUNA SEAに出演するため、前後（ここではPK shanpoo）もシフトに入れないはず
        {"name": "みらい", "skill_desk": 5, "skill_stage": 4, "count": 0, "ng_bands": ["LUNA SEA(D)"], "ng_times": [], "req_bands": []},
        {"name": "るい", "skill_desk": 3, "skill_stage": 3, "count": 0, "ng_bands": [], "ng_times": [], "req_bands": []},
        {"name": "先輩A", "skill_desk": 5, "skill_stage": 5, "count": 0, "ng_bands": [], "ng_times": [], "req_bands": []},
        {"name": "後輩B", "skill_desk": 1, "skill_stage": 1, "count": 0, "ng_bands": [], "ng_times": [], "req_bands": []},
        {"name": "後輩C", "skill_desk": 1, "skill_stage": 2, "count": 0, "ng_bands": [], "ng_times": [], "req_bands": []},
    ]

    # 1. シフト計算を実行
    result_shift, final_members = generate_pa_shift(my_timetable, my_members)
    
    # 2. 結果をCSVに出力
    export_to_csv(my_timetable, result_shift, "pa_shift_test.csv")

    # 3. 黒い画面（ターミナル）にも確認用に出力
    print("\n--- メンバーの最終シフト入数 ---")
    for m in final_members:
        print(f"{m['name']}: {m['count']}回")