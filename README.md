# PA-Shift タイムテーブル・シフト生成ツール

## 🎯 概要

ライブイベントの PA（音響スタッフ）シフトを自動生成するツールです。バンドのリハーサル・本番スケジュールとメンバーのスキル・条件を入力すると、最適なシフト配置を自動計算します。

## 🏗️ アーキテクチャ

```
┌──────────────────────────────────────┐
│     フロントエンド (HTML/JS)          │
│   フロントエンド.html                │
└─────────────┬──────────────────────────┘
              │ HTTP (JSON)
              ↓
┌──────────────────────────────────────┐
│     バックエンド (Python/Flask)       │
│         app.py                       │
├──────────────────────────────────────┤
│  - generate_timetable()              │
│  - generate_pa_shift()               │
│  - API /api/generate-shift           │
└──────────────────────────────────────┘
```

**特徴**:
- **Python を軸**: `app.py` (Flask サーバー) が中核
- **自動反映**: Python に変更があれば HTML に自動的に反映
- **API ベース**: HTML は REST API で Python と通信

## 📋 必要なもの

- Python 3.8 以上
- pip (Python パッケージマネージャー)
- ブラウザ (Chrome/Firefox/Safari)

## 🚀 セットアップ

### 1. 必要なパッケージをインストール

```bash
pip install -r requirements.txt
```

### 2. Python サーバーを起動

```bash
python app.py
```

出力例：
```
🚀 PA-Shift Backend Server starting...
📌 http://localhost:5000 でサーバーが起動しました
🔗 http://localhost:5000/api/health でヘルスチェック
 * Running on http://127.0.0.1:5000
```

### 3. ブラウザで HTML を開く

```
フロントエンド.html をブラウザで開く
```

## 📖 使い方

### ステップ 1️⃣ : タイムテーブル設定

1. **開始時間**: イベント開始時間を設定 (例: 11:30)
2. **リハーサル時間**: リハの長さ（分）(例: 15分)
3. **本番時間**: 本番の長さ（分）(例: 10分)
4. **昼休憩**: 休憩の長さ（分）と、どのバンド後に挿入するか設定
5. **バンド追加**: 出演バンドを順番に追加

### ステップ 2️⃣ : メンバー条件設定

各メンバーについて以下を設定：
- **名前**: メンバーの名前
- **卓スキル** (1-5): ミキサー・卓業務のスキル
- **ステージスキル** (1-5): ステージ機材のスキル
- **出演禁止バンド**: 出演するため、シフトに入れないバンド (カンマ区切り)
- **NG 時間帯**: 入れない時間帯 (カンマ区切り)
- **希望バンド**: 優先的に割り当てたいバンド (カンマ区切り)

### ステップ 3️⃣ : シフト生成・出力

1. **「シフトを生成」ボタン**: Python API にリクエスト送信
2. **結果確認**: タイムテーブルと割り当てを確認
3. **「CSVで出力」**: シフト結果を CSV でダウンロード

## 🔧 API エンドポイント

### POST /api/generate-shift

タイムテーブル生成とシフト割り当てを実行します。

**リクエスト例**:
```json
{
  "start_time": "11:30",
  "bands": ["LUNA SEA(D)", "PK shanpoo", "BUMP(コピー)"],
  "rh_mins": 15,
  "act_mins": 10,
  "break_duration": 60,
  "break_after_band": "PK shanpoo",
  "members": [
    {
      "name": "みらい",
      "skill_desk": 5,
      "skill_stage": 4,
      "count": 0,
      "ng_bands": ["LUNA SEA(D)"],
      "ng_times": [],
      "req_bands": []
    }
  ]
}
```

**レスポンス例**:
```json
{
  "status": "success",
  "timetable": [
    {"time": "11:30-11:45", "type": "rh", "name": "LUNA SEA(D)"},
    {"time": "11:45-11:55", "type": "act", "name": "LUNA SEA(D)"}
  ],
  "shift": {
    "LUNA SEA(D)": {
      "卓": ["先輩A"],
      "ステージ": ["後輩B", "後輩C"]
    }
  },
  "members": [...]
}
```

## 📁 ファイル構成

```
pa-shift/
├── フロントエンド.html      # フロント UI
├── app.py                  # Flask バックエンド
├── proto-type.py           # 参考用（元のスクリプト）
├── requirements.txt        # Python 依存パッケージ
├── pa_shift_test.csv       # テスト用 CSV
└── README.md               # このファイル
```

## 🔄 Python に変更を加えるには

### 例: リハの最大人数を変更

`app.py` の `generate_pa_shift()` 関数内：

```python
for m in available_desk:
    if desk_score < 5:  # ← ここを変更 (例: 6に変更)
        desk_team.append(m)
        desk_score += m["skill_desk"]
```

修正後、Python サーバーを再起動（Ctrl+C で終了後、`python app.py` で再起動）すれば、HTML も自動的に新しいロジックを使用します。

## 💡 トラブルシューティング

###「Python サーバーとの通信に失敗しました」エラー

**原因**: Python サーバーが起動していない

**解決方法**:
```bash
python app.py
```

でサーバーを起動してください。

### port 5000 がすでに使用されている

**解決方法**: `app.py` の最後の行を変更：
```python
app.run(debug=True, port=5001)  # 5001に変更
```

その後、HTML のコード内の URL も変更してください：
```javascript
const response = await fetch('http://localhost:5001/api/generate-shift', {
```

## 📝 ライセンス

このプロジェクトは個人用です。自由に改造・使用できます。