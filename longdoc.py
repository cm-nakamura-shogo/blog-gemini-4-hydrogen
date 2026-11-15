"""日本語の合成日報（長文）と、その中の案件の履歴をたどる質問を生成する。

案件の引き継ぎ、差し戻し、訂正、見積額の改定、取り下げを日報の中に散らばらせ、
正解はシミュレーションした状態から機械的に求める。
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

PEOPLE = ["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
          "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水"]
CLIENTS = ["北辰精機", "東海ロジテック", "みなと食品", "青葉化成", "白鷺電装", "大和テキスタイル", "瀬戸内マリン", "常盤メディカル"]

NOISE = [
    "午前は社内の定例会議に出席。来期の営業方針について共有があった。",
    "{client}の担当者と電話で打ち合わせ。次回の訪問日程を調整した。",
    "移動中に経費精算を済ませた。交通費の領収書を一部紛失していたので総務に相談した。",
    "{client}向けの提案資料を作成中。図表の差し替えに時間がかかった。",
    "新人の{p}さんの同行営業。商談の進め方について帰りの電車で振り返りをした。",
    "午後は展示会の準備。ブースの備品リストを最終確認した。",
    "{case}の件で{p}さんから相談を受けた。仕様の確認だけで、担当は変わらない。",
    "{case}について{client}から問い合わせがあり、回答期限を確認した。",
    "{case}を{p}さんに引き継ぐ方向で課長と調整中。まだ確定ではない。",
    "来月から{case}を{p}さんに引き継ぐかもしれないと課長から話があった。正式な決定はまだ。",
    "{case}の見積額を見直すよう{client}から打診があった。金額はまだ変えていない。",
    "週次の数字を入力した。今月は目標に対してやや遅れている。",
    "{client}の工場見学に同行。生産ラインの改善事例を聞けて参考になった。",
    "社内研修（情報セキュリティ）を受講。確認テストは満点だった。",
    "午後は在宅で見積書の様式を整理した。古いテンプレートを削除した。",
    "{p}さんが休みのため、{case}の客先対応を一日だけ代行した。担当の変更ではない。",
]


def business_days(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def fmt_date(d):
    return f"{d.year}年{d.month}月{d.day}日"


def man(x):
    return f"{x:,}万円"


def generate(seed, n_days, noise_per_day, n_cases=24, events_per_case=9):
    rng = random.Random(seed)
    days = business_days(date(2026, 4, 1), n_days)
    cases = [f"K-{100 + i}" for i in range(n_cases)]

    # 案件ごとにイベントの日付を決める（作成日 + 後続イベント）
    owner_hist = {c: [] for c in cases}  # [(日付, 担当者)] 訂正を反映済み
    state = {}
    entries = {d: [] for d in days}  # 日付 -> [(書き手, 本文)]

    plans = []
    for c in cases:
        create_i = rng.randrange(0, n_days // 4)
        later = sorted(rng.sample(range(create_i + 1, n_days - 2), events_per_case))
        plans.append((create_i, "create", c))
        plans += [(i, "event", c) for i in later]
    plans.sort(key=lambda x: (x[0], x[2]))

    created = {}  # 案件 -> 作成日
    pending_correction = []  # (訂正を書く日のindex, 案件, 誤記した担当, 正しい担当, 引き継いだ人)
    corrected_days = set()
    for i, kind, c in plans:
        d = days[i]
        if kind == "create":
            owner = rng.choice(PEOPLE)
            amount = rng.randrange(8, 60) * 10
            client = rng.choice(CLIENTS)
            state[c] = {"owner": owner, "amount": amount, "client": client, "active": True, "returned": False}
            owner_hist[c].append((d, owner))
            created[c] = d
            entries[d].append((owner, f"{client}から新規の引き合いがあり、案件{c}として登録した。見積額は{man(amount)}で、担当は私（{owner}）。"))
            continue
        s = state[c]
        if not s["active"]:
            continue
        cur = s["owner"]
        r = rng.random()
        prev_owners = [o for _, o in owner_hist[c][:-1]]
        if r < 0.40:  # 引き継ぎ
            new = rng.choice([p for p in PEOPLE if p != cur])
            phr = rng.choice([
                f"本日付で案件{c}を{new}さんに引き継いだ。",
                f"{c}は今日から{new}さんの担当になった。引き継ぎ資料を共有済み。",
                f"課長の指示で、{c}の担当を{new}さんに交代した。",
                f"{c}を{new}さんへ移管した。客先にも連絡済み。",
            ])
            # 一定確率で誤記し、翌営業日に訂正する
            if rng.random() < 0.25 and i + 1 < n_days and i + 1 not in corrected_days:
                wrong = rng.choice([p for p in PEOPLE if p not in (cur, new)])
                phr = phr.replace(f"{new}さん", f"{wrong}さん")
                pending_correction.append((i + 1, c, wrong, new, cur))
                corrected_days.add(i + 1)
            entries[d].append((cur, phr))
            s["owner"] = new
            s["returned"] = False
            owner_hist[c].append((d, new))
        elif r < 0.52 and prev_owners and prev_owners[-1] != cur and not s["returned"]:  # 差し戻し（連続はしない）
            back = prev_owners[-1]
            entries[d].append((cur, f"{c}は先方の要望で、前任者に担当を差し戻した。"))
            s["owner"] = back
            s["returned"] = True
            owner_hist[c].append((d, back))
        elif r < 0.75:  # 見積額の改定（絶対額）
            new_amt = rng.randrange(8, 60) * 10
            entries[d].append((cur, f"{c}の見積額を{man(s['amount'])}から{man(new_amt)}に改定した。"))
            s["amount"] = new_amt
        elif r < 0.97:  # 値引き（差額のみ）
            disc = rng.choice([10, 20, 30, 50])
            if s["amount"] - disc <= 0:
                continue
            entries[d].append((cur, f"{c}は競合対策として{man(disc)}値引きすることで合意した。"))
            s["amount"] -= disc
        else:  # 取り下げ
            entries[d].append((cur, f"{c}は先方の予算凍結により取り下げとなった。"))
            s["active"] = False

    for ci, c, wrong, right, writer in pending_correction:
        entries[days[ci]].append((writer, f"前営業日の日報の訂正：{c}の引き継ぎ先は{wrong}さんではなく{right}さんです。"))

    # ノイズを足す
    for d in days:
        for _ in range(noise_per_day):
            live = [c for c in cases if created[c] <= d]
            t = rng.choice(NOISE).format(client=rng.choice(CLIENTS), p=rng.choice(PEOPLE),
                                         case=rng.choice(live) if live else cases[0])
            entries[d].append((rng.choice(PEOPLE), t))

    # 日報として書き出す（書き手ごとにまとめる）
    lines = []
    for d in days:
        lines.append(f"## {fmt_date(d)}（{'月火水木金'[d.weekday()]}）")
        by = {}
        for w, t in entries[d]:
            by.setdefault(w, []).append(t)
        writers = list(by)
        rng.shuffle(writers)
        for w in writers:
            lines.append(f"### {w}")
            lines += [f"- {t}" for t in by[w]]
        lines.append("")
    doc = "\n".join(lines)

    # 質問と正解
    def owner_on(c, d):
        o = None
        for hd, ho in owner_hist[c]:
            if hd <= d:
                o = ho
        return o

    long_cases = sorted(cases, key=lambda c: -len(owner_hist[c]))
    q1c = long_cases[0]
    q2c = long_cases[1]
    q2d = rng.choice([d for d in days[n_days // 3: 2 * n_days // 3]])
    q3client = max(CLIENTS, key=lambda cl: sum(1 for c in cases if state[c]["client"] == cl))
    q4c = long_cases[2]
    questions = {
        "q1": f"案件{q1c}の、最後の日報の時点での担当者は誰ですか。",
        "q2": f"{fmt_date(q2d)}の業務終了時点で、案件{q2c}の担当者は誰でしたか。",
        "q3": f"取引先「{q3client}」の案件のうち、最後の日報の時点で取り下げられていないものについて、見積額の合計は何万円ですか。",
        "q4": f"案件{q4c}を一度でも担当したことのある人は、何人いますか（最初の担当者を含む）。",
        "q5": "最後の日報の時点で取り下げられている案件の案件番号をすべて挙げてください。",
    }
    answers = {
        "q1": state[q1c]["owner"],
        "q2": owner_on(q2c, q2d),
        "q3": sum(state[c]["amount"] for c in cases if state[c]["client"] == q3client and state[c]["active"]),
        "q4": len({o for _, o in owner_hist[q4c]}),
        "q5": sorted(c for c in cases if not state[c]["active"]),
    }
    return doc, questions, answers


def render_prompt(doc, questions):
    head = [
        "以下は、ある会社の営業部の日報です。各日付の下に、書いた人ごとの記載があります。",
        "日報を読んで、最後の質問に答えてください。",
        "",
        "注意：",
        "- 「調整中」「予定」「かもしれない」などの記載は、担当の変更として扱わないでください。",
        "- 一時的な代行や相談は、担当の変更ではありません。",
        "- 訂正の記載がある場合は、訂正後の内容が正しいものとします。",
        "- 「前任者」は、その時点の担当者の直前にその案件を担当していた人を指します。",
        "",
        "---",
        "",
    ]
    tail = ["", "---", "", "質問："] + [f"{k}. {v}" for k, v in questions.items()] + [
        "",
        "回答の最後に、次の形式のJSONを ```json ブロックで1つだけ出力してください。",
        '{"q1": "人名（さん付けなし）", "q2": "人名（さん付けなし）", "q3": 数値（万円単位の整数）, "q4": 数値, "q5": ["K-xxx", ...]}',
    ]
    return "\n".join(head) + doc + "\n".join(tail)


if __name__ == "__main__":
    out = []
    for size, n_days, noise in [("short", 60, 8), ("long", 240, 40)]:
        for seed in range(3):
            doc, qs, ans = generate(seed, n_days, noise)
            out.append({"id": f"{size}-{seed}", "size": size, "prompt": render_prompt(doc, qs), "answer": ans,
                        "chars": len(doc)})
            print(size, seed, len(doc), "字", ans)
    Path("data").mkdir(exist_ok=True)
    Path("data/longdoc.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
