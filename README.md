# Gemini 4のHydrogen、Argon、Carbonを自作の日本語タスクで動かす

Gemini 4系（Hydrogen、Argon、Carbon）と、比較用の3.8 Flash、3.5 Flash-Liteに、自作の日本語タスクを解かせ、正答、応答時間、思考トークン、費用を記録した検証のコードと結果です。

> [!NOTE]
> モデルの生の応答（`results/raw/`）と実行ログは含めていません。採点結果と集計だけを置いています。

## 結果

全条件の集計は [`results/summary.md`](results/summary.md)、1回ごとの採点結果は [`results/graded.jsonl`](results/graded.jsonl) にあります。

支払い計算のバグ修正（バグ8つ、隠しテスト25件、各3回）の結果は次の通りです。

| 条件 | 全テスト通過 | 時間（中央値、秒） | 思考トークン（平均） | 1回の費用（2026年11月14日時点、$） |
| --- | ---: | ---: | ---: | ---: |
| 3.5 Flash-Lite | 0/3 | 3 | 0 | 0.004 |
| 3.8 Flash | 3/3 | 105 | 12,762 | 0.057 |
| Hydrogen low | 3/3 | 17 | 2,347 | 0.032 |
| Hydrogen high（既定値） | 3/3 | 29 | 5,410 | 0.058 |
| Hydrogen xhigh | 3/3 | 96 | 21,316 | 0.177 |
| Argon medium（既定値） | 3/3 | 19 | 0 | 0.023 |
| Carbon medium（既定値） | 3/3 | 120 | 7,344 | 0.092 |
| Carbon high | 3/3 | 235 | 19,650 | 0.218 |

## 実験の条件

- モデル：`gemini-3.5-flash-lite`、`gemini-3.8-flash`、`gemini-4-hydrogen`（low、high、xhigh）、`gemini-4-argon`（medium）、`gemini-4-carbon`（medium、high）
- 呼び出し：Google Gen AI SDK（`google-genai`）の `generate_content`、`max_output_tokens=65536`
- Hydrogen xhighの約25万トークンの日報だけは、同期の呼び出しで回答が空になったため、Interactions APIの `background=True`（`max_output_tokens=262144`）でも実行した（`hydrogen-xhigh-bg`）
- 実行日：2026年11月13日〜14日
- 費用は、使用量（入力、思考、出力のトークン数）と料金ページの単価から計算した。ArgonとCarbonは11月30日まで、3.8 Flashは12月31日までの導入価格と、その後の単価の両方で計算している

## 題材

| 題材 | 内容 | 件数 |
| --- | --- | --- |
| 制約パズル | 社員ごとの出勤曜日、担当、出身地などを日本語の条件文から一意に決める。4人2属性から7人5属性までの4段階。解が一意であることはz3で確認 | 12問 × 2回 |
| 請求書のバグ修正（`bugfix/`） | 消費税の端数処理、20日締め、祝日、12月締め、令和元年の5つのバグ。隠しテスト14件で採点 | 3回 |
| 支払い計算のバグ修正（`bugfix_hard/`） | 振替休日、第n月曜日、国民の休日、源泉徴収（2種類）、支払日の前倒し、年末年始、元号の境界の8つのバグ。隠しテスト25件で採点 | 3回 |
| 長い日報の読解 | 架空の営業部の日報から、案件の最終担当者、ある日付の担当者、見積額の合計、担当者数、取り下げ案件を答える。約2万トークンと約25万トークンの2種類 | 6本 × 1回（各5問） |

バグ修正の題材には、モデルに渡す仕様書とコード（`src/`）、採点用の隠しテスト（`hidden_tests/`）、すべてのバグを直した参照実装（`reference/`）が入っています。

題材に登場する人名、社名、案件、金額はすべて架空のもので、実在の人物や企業とは関係ありません。

## ディレクトリ

```text
puzzles.py          # 制約パズルを生成する（data/puzzles.json）
longdoc.py          # 長い日報と質問を生成する（data/longdoc.json）
run.py              # 全条件で題材を実行し、応答を results/raw/ に保存する
run_background.py   # Hydrogen xhigh を background=True で長い日報に実行する
grade.py            # results/raw/ を採点し、results/graded.jsonl と集計表を出す
bugfix/             # 請求書のバグ修正の題材
bugfix_hard/        # 支払い計算のバグ修正の題材
data/               # 生成したパズルと日報（問題と正解）
results/            # 採点結果と集計
```

## 再現手順

課金が有効なGoogle CloudプロジェクトのAPIキーを `GEMINI_API_KEY` に入れて実行します（ArgonとCarbonは無料枠では使えません）。

```bash
uv sync
uv run python puzzles.py     # data/puzzles.json を作る（同梱のものと同じになる）
uv run python longdoc.py     # data/longdoc.json を作る（同梱のものと同じになる）
uv run python run.py         # 全条件を実行する（既に保存済みの応答は飛ばす）
uv run python run_background.py
uv run python grade.py       # 採点して集計表を出す
```

全条件を実行すると、2026年11月14日時点の単価で約$31かかりました。
`run.py` は `--configs` で条件を絞れます。

## 関連記事

- [Gemini 4のHydrogen、Argon、Carbonを整理して、APIで動かしてみた](https://dev.classmethod.jp/articles/gemini-4-hydrogen-argon-carbon/)

## ライセンス

MITライセンスです。
