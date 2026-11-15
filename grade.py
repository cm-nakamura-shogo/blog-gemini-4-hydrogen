"""results/raw/ の応答を採点し、results/graded.jsonl と条件ごとの集計表を出す。"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / "results" / "raw"

# 100万トークン当たりの (入力, 出力) 単価。出力には思考トークンを含む。
PRICE_NOW = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.8-flash": (0.75, 3.75),  # 導入価格（2026/12/31まで）
    "gemini-4-hydrogen": (1.50, 7.50),
    "gemini-4-argon": (2.00, 10.00),  # 導入価格（2026/11/30まで）
    "gemini-4-carbon": (2.00, 10.00),  # 導入価格（2026/11/30まで）
}
PRICE_REGULAR = {
    **PRICE_NOW,
    "gemini-3.8-flash": (1.50, 7.50),
    "gemini-4-argon": (4.00, 20.00),
    "gemini-4-carbon": (4.00, 20.00),
}
LEVELS = ["easy", "medium", "hard", "expert"]
ORDER = ["3.5-flash-lite", "3.8-flash", "hydrogen-low", "hydrogen-high", "hydrogen-xhigh", "hydrogen-xhigh-bg",
         "argon-medium", "carbon-medium", "carbon-high"]


def cost(rec, table):
    i, o = table[rec["model"]]
    return (rec["prompt_tokens"] * i + (rec["output_tokens"] + rec["thought_tokens"]) * o) / 1e6


def last_json_block(text):
    blocks = re.findall(r"```json\s*(.*?)```", text, re.S)
    for b in reversed(blocks):
        try:
            return json.loads(b)
        except json.JSONDecodeError:
            continue
    return None


def norm(v):
    return str(v).strip().removesuffix("曜日").removesuffix("曜")


def grade_puzzle(rec, answers):
    ans = answers[rec["task"].removeprefix("puzzle-")]
    got = last_json_block(rec["text"])
    total = sum(len(a) for a in ans.values())
    if not isinstance(got, dict):
        return {"correct": False, "cell_acc": 0.0, "parse_error": True}
    got = {k.removesuffix("さん"): v for k, v in got.items()}
    hit = 0
    for person, attrs in ans.items():
        g = got.get(person) or {}
        if not isinstance(g, dict):
            continue
        hit += sum(norm(g.get(a, "")) == norm(v) for a, v in attrs.items())
    return {"correct": hit == total, "cell_acc": hit / total, "parse_error": False}


def grade_bugfix(rec):
    task_dir = {"bugfix": "bugfix", "bugfix_hard": "bugfix_hard"}[rec["task"]]
    package = {"bugfix": "invoice", "bugfix_hard": "payout"}[rec["task"]]
    files = re.findall(r"### FILE:\s*(\S+)\s*\n```(?:python)?\s*\n(.*?)```", rec["text"], re.S)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "src"
        shutil.copytree(ROOT / task_dir / "src", work)
        for name, body in files:
            name = name.strip("`")
            if not name.startswith(f"{package}/") or ".." in name:
                continue
            (work / name).write_text(body)
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml", f"{tmp}/r.xml",
             str(ROOT / task_dir / "hidden_tests"), str(work / "tests"), "-o", f"pythonpath={work}"],
            capture_output=True, text=True, timeout=120,
        )
        xml = Path(f"{tmp}/r.xml").read_text() if Path(f"{tmp}/r.xml").exists() else ""
    hidden = re.findall(r'<testcase classname="[^"]*test_hidden" name="([^"]+)"[^>]*?(/>|>(.*?)</testcase>)', xml, re.S)
    passed = [n for n, end, body in hidden if end == "/>" or ("<failure" not in body and "<error" not in body)]
    n = {"bugfix": 14, "bugfix_hard": 25}[rec["task"]]  # 収集エラー時も分母を固定する
    return {"hidden_passed": len(passed), "hidden_total": n, "all_pass": len(passed) == n,
            "files_returned": [f for f, _ in files], "passed_tests": passed}


def grade_longdoc(rec, answers):
    ans = answers[rec["task"].removeprefix("longdoc-")]
    got = last_json_block(rec["text"])
    if not isinstance(got, dict):
        return {"ld_score": 0, "ld_detail": {}, "parse_error": True}

    def name(x):
        return str(x).strip().removesuffix("さん")

    def num(x):
        try:
            return int(str(x).replace(",", "").replace("万円", "").replace("人", "").strip())
        except ValueError:
            return None

    detail = {
        "q1": name(got.get("q1")) == ans["q1"],
        "q2": name(got.get("q2")) == ans["q2"],
        "q3": num(got.get("q3")) == ans["q3"],
        "q4": num(got.get("q4")) == ans["q4"],
        "q5": isinstance(got.get("q5"), list) and sorted(str(x).strip() for x in got["q5"]) == ans["q5"],
    }
    return {"ld_score": sum(detail.values()), "ld_detail": detail, "parse_error": False}


def main():
    answers = {p["id"]: p["answer"] for p in json.loads((ROOT / "data" / "puzzles.json").read_text())}
    ld_answers = {x["id"]: x["answer"] for x in json.loads((ROOT / "data" / "longdoc.json").read_text())}
    graded = []
    for path in sorted(RAW.glob("*.json")):
        rec = json.loads(path.read_text())
        if rec["task"].startswith("puzzle-"):
            g = grade_puzzle(rec, answers)
        elif rec["task"].startswith("longdoc-"):
            g = grade_longdoc(rec, ld_answers)
        else:
            g = grade_bugfix(rec)
        graded.append({**{k: v for k, v in rec.items() if k != "text"}, **g,
                       "cost_now": cost(rec, PRICE_NOW), "cost_regular": cost(rec, PRICE_REGULAR)})
    (ROOT / "results" / "graded.jsonl").write_text("\n".join(json.dumps(g, ensure_ascii=False) for g in graded))

    by = defaultdict(list)
    for g in graded:
        by[g["config"]].append(g)
    head = ["条件", "パズル正解"] + LEVELS + ["バグ修正(14件)", "全通過", "難バグ修正(25件)", "全通過", "長文 約2万tok", "長文 約25万tok",
                                         "平均思考トークン", "平均レイテンシ(秒)", "総費用 現在($)", "総費用 通常($)"]
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for c in ORDER:
        rs = by.get(c, [])
        if not rs:
            continue
        pz = [r for r in rs if r["task"].startswith("puzzle-")]
        row = [c, f"{sum(r['correct'] for r in pz)}/{len(pz)}"]
        for level in LEVELS:
            xs = [r for r in pz if f"-{level}-" in r["task"]]
            row.append(f"{sum(r['correct'] for r in xs)}/{len(xs)}" if xs else "-")
        for task in ["bugfix", "bugfix_hard"]:
            bf = [r for r in rs if r["task"] == task]
            row.append(f"{sum(r['hidden_passed'] for r in bf) / len(bf):.1f}" if bf else "-")
            row.append(f"{sum(r['all_pass'] for r in bf)}/{len(bf)}" if bf else "-")
        for size in ["short", "long"]:
            ld = [r for r in rs if r["task"].startswith(f"longdoc-{size}")]
            row.append(f"{sum(r['ld_score'] for r in ld)}/{5 * len(ld)}" if ld else "-")
        row += [f"{sum(r['thought_tokens'] for r in rs) / len(rs):,.0f}",
                f"{sum(r['latency_sec'] for r in rs) / len(rs):.1f}",
                f"{sum(r['cost_now'] for r in rs):.3f}", f"{sum(r['cost_regular'] for r in rs):.3f}"]
        print("| " + " | ".join(row) + " |")

if __name__ == "__main__":
    main()
