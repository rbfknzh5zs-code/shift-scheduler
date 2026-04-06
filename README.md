# Shift Scheduler + Shift Portal

店舗向けのシフト作成ツールです。以下の2つで運用します。

- `shift_portal.py`: スタッフ入力フォーム + 管理カレンダー + CSV出力
- `shift_scheduler.py`: 最適化でシフト作成（CSV/XLSX出力）

## 1. セットアップ

```bash
cd /Users/macbookpro/shift-scheduler
./.venv/bin/pip install -r requirements.txt
```

## 2. フォームシステム起動

```bash
cd /Users/macbookpro/shift-scheduler
./.venv/bin/python shift_portal.py
```

- トップ: `http://localhost:5050/`
- スタッフ入力: `http://localhost:5050/form?year=2026&month=5&name=田中%20太郎`
- 管理カレンダー: `http://localhost:5050/admin?year=2026&month=5`

## 3. 入力仕様（スタッフ側）

日付ごとに以下を入力します。

- `出勤可` + `開始時刻/終了時刻`
- `申請休`
- `契約休`
- `有給`
- 月次コメント

## 4. 管理者運用

管理カレンダーで全員分の月次回答を確認し、CSVを出力します。

- `requests.csv`:
  - `申請休` -> `priority=希望`
  - `契約休 / 有給` -> `priority=必須`
- `availability.csv`:
  - `出勤可` の時間帯を日別で出力

## 5. シフト自動作成（時間帯制約付き）

`shift_scheduler.py` は `--daily-availability` を受け取れます。

```bash
cd /Users/macbookpro/shift-scheduler
./.venv/bin/python shift_scheduler.py \
  --year 2026 \
  --month 5 \
  --requests sample_data/requests.csv \
  --daily-availability sample_data/availability.csv \
  --format both
```

## 6. LINE配布（LIFF）について

この実装は「LINEで開けるフォーム」に流用しやすい構成です。

- LINEメッセージで `/form?year=YYYY&month=MM&name=スタッフ名` を配布
- 次段階でLIFF認証（LINEユーザーIDとスタッフ紐づけ）を追加可能

## 7. Vercel公開

```bash
cd /Users/macbookpro/shift-scheduler
vercel --prod --yes
```

- `vercel.json` と `api/index.py` を使ってFlaskアプリを公開
- Vercel上ではDB保存先が `/tmp/shift_portal.db` になるため、データは永続化されません
