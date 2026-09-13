# shift-scheduler

店舗向けのシフト作成ツール。スタッフが勤務希望を入力するWebフォームと、最適化でシフトを自動作成するスクリプトの2つからなる。

**このリポジトリは公開（public）。** スタッフの実名・連絡先・APIキーなどをコミットしない。`sample_data/` は架空の名前だけにする。

## 記述スタイル
- 日本語で回答すること
- コミットメッセージは日本語
- 不要なコメントは書かない
- 挨拶・前置き・段階報告・絵文字は書かない。結論ファースト

## 技術スタック
- Python / Flask / SQLite
- シフト最適化: PuLP / Excel出力: openpyxl / 祝日: jpholiday
- デプロイ: Vercel（`vercel.json` → `api/index.py`。本番 https://shift-scheduler-lilac.vercel.app）

## ファイル
| ファイル | 役割 |
|---|---|
| `shift_portal.py` | Flaskアプリ。スタッフ入力フォーム、管理カレンダー、CSV出力 |
| `shift_scheduler.py` | 最適化でシフトを作成し、CSV / XLSX を出力 |
| `api/index.py` | Vercel用の入口（`shift_portal.py` を読み込む） |
| `api/requirements.txt` | Vercel用の依存（Flaskのみ） |
| `templates/` / `static/` | 画面のHTML・CSS・JS |
| `sample_data/` | 入力CSVのサンプル |

## コマンド
| 用途 | コマンド |
|---|---|
| 依存インストール | `python -m venv .venv && .venv/bin/pip install -r requirements.txt` |
| 構文チェック | `python -m py_compile shift_portal.py shift_scheduler.py api/index.py` |
| シフト作成 | `.venv/bin/python shift_scheduler.py --year 2026 --month 5 --format both`（数秒で終わる。出力 `shift_output_*.csv/.xlsx` はGit管理外） |
| フォーム起動 | `.venv/bin/python shift_portal.py`（http://localhost:5050。ローカルのみ） |

## 変更後に必ずやること
1. 構文チェックを通す
2. `shift_scheduler.py` を変えたら、上の「シフト作成」を実行して正常終了を確認する

## 注意
- Vercel 上では DB が `/tmp/shift_portal.db` になり、データは永続化されない
- `shift_portal.py` に Flask 以外のライブラリを読み込ませる場合は、`api/requirements.txt` にも追加する。追加しないと Vercel で起動しない

## クラウド環境での禁止事項
Claude Code on the web や Codex のクラウド環境で作業しているときは、終了しないコマンドを実行しない。セッションが止まる。

- `shift_portal.py` の起動（Flaskサーバーは終了しない）
- `tail -f`、`watch` など

クラウド内の `localhost` は利用者のブラウザから開けない。Claude Code のクラウド環境では環境変数 `CLAUDE_CODE_REMOTE` が `true` になる。

## 見た目の確認
- ローカル: `shift_portal.py` を起動し、Google Chrome で http://localhost:5050 を開く
- クラウド: 作業ブランチ（main以外）にpushすると、Vercel がプレビューを作る。そのURLを利用者に伝え、main にマージする前に利用者のPCやスマホのブラウザで確認してもらう

pushの数分後に、プレビューの状態とURLを取得する。

```bash
id=$(gh api "repos/rbfknzh5zs-code/shift-scheduler/deployments?sha=$(git rev-parse HEAD)" --jq '.[0].id')
[ -n "$id" ] && gh api "repos/rbfknzh5zs-code/shift-scheduler/deployments/$id/statuses" --jq '.[0] | "\(.state) \(.target_url)"'
```

- `success`: URLを利用者に伝える
- `pending` / `in_progress`: 1〜2分待って再実行する
- `failure` / `error`、または数分待っても何も出ない: コミット作者（下記）を確認する。解決しなければブランチ名を伝え、ローカルでの確認を依頼する

プレビューは Vercel Authentication で保護されているので、Vercel にログインしたブラウザで開くよう利用者に伝える。

## コミット作者（Vercel）
Vercel は、プロジェクトへのアクセス権がない作者のコミットをデプロイしない（`Git author ... must have access to the project on Vercel`）。コミット前に作者を確認し、違えば設定する。

```bash
git config user.name; git config user.email
git config user.name rbfknzh5zs-code
git config user.email 250702757+rbfknzh5zs-code@users.noreply.github.com
```
