"""各モデルに題材を投げ、生の応答と使用量、レイテンシを results/raw/ に保存する。

既に保存済みの (条件, 題材, 試行) は飛ばすので、途中で止めても再実行で続きから走る。
"""

import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from google import genai
from google.genai import errors, types

ROOT = Path(__file__).parent
RAW = ROOT / "results" / "raw"

# (条件名, モデルID, thinking_level。None は既定値)
CONFIGS = [
    ("3.5-flash-lite", "gemini-3.5-flash-lite", None),
    ("3.8-flash", "gemini-3.8-flash", None),
    ("hydrogen-low", "gemini-4-hydrogen", "low"),
    ("hydrogen-high", "gemini-4-hydrogen", "high"),
    ("hydrogen-xhigh", "gemini-4-hydrogen", "xhigh"),
    ("argon-medium", "gemini-4-argon", "medium"),
    ("carbon-medium", "gemini-4-carbon", "medium"),
    ("carbon-high", "gemini-4-carbon", "high"),
]

BUGFIX_TASKS = {
    "bugfix": {
        "dir": "bugfix",
        "files": ["spec.md"] + [f"invoice/{n}" for n in
                                ["__init__.py", "models.py", "tax.py", "calendar_jp.py", "billing.py", "wareki.py"]]
                 + ["tests/test_visible.py"],
        "intro": [
            "以下は社内で使っている請求書計算モジュールと、その仕様書です。",
            "経理部から「請求書の消費税額が手計算と合わないことがある」「支払期日がおかしい請求書がある」という問い合わせがありました。",
        ],
        "package": "invoice",
    },
    "bugfix_hard": {
        "dir": "bugfix_hard",
        "files": ["spec.md"] + [f"payout/{n}" for n in
                                ["__init__.py", "holidays.py", "withholding.py", "schedule.py", "wareki.py", "calc.py"]]
                 + ["tests/test_visible.py"],
        "intro": [
            "以下は、個人の外注先への支払額と支払日を計算するモジュールと、その仕様書です。",
            "経理部から「源泉徴収税額が合わない支払通知書がある」「支払日がずれていることがある」という問い合わせがありました。",
        ],
        "package": "payout",
    },
}


def bugfix_prompt(task: str) -> str:
    t = BUGFIX_TASKS[task]
    src = ROOT / t["dir"] / "src"
    parts = t["intro"] + [
        "仕様書に照らしてコードを確認し、仕様と食い違っている箇所をすべて修正してください。",
        "",
        "修正したファイルは、ファイル全体を次の形式で出力してください。変更しないファイルは出力しないでください。",
        "",
        f"### FILE: {t['package']}/xxx.py",
        "```python",
        "（ファイル全体）",
        "```",
        "",
    ]
    for name in t["files"]:
        lang = "markdown" if name.endswith(".md") else "python"
        parts += [f"### {name}", f"```{lang}", (src / name).read_text().rstrip(), "```", ""]
    return "\n".join(parts)


def tasks(reps_puzzle: int, reps_bugfix: int):
    puzzles = json.loads((ROOT / "data" / "puzzles.json").read_text())
    for pz in puzzles:
        for r in range(reps_puzzle):
            yield f"puzzle-{pz['id']}", r, pz["prompt"]
    for ld in json.loads((ROOT / "data" / "longdoc.json").read_text()):
        yield f"longdoc-{ld['id']}", 0, ld["prompt"]
    for task in BUGFIX_TASKS:
        bp = bugfix_prompt(task)
        for r in range(reps_bugfix):
            yield task, r, bp


def call(client, model, level, prompt):
    cfg = types.GenerateContentConfig(
        max_output_tokens=65536,
        thinking_config=types.ThinkingConfig(thinking_level=level) if level else None,
    )
    for attempt in range(6):
        try:
            t0 = time.perf_counter()
            r = client.models.generate_content(model=model, contents=prompt, config=cfg)
            return r, time.perf_counter() - t0
        except errors.APIError as e:
            if e.code in (429, 500, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt * 5 + random.random() * 5)
                continue
            raise


def run_one(client, cfg, task_id, rep, prompt):
    name, model, level = cfg
    out = RAW / f"{name}__{task_id}__{rep}.json"
    if out.exists():
        return out, "skip"
    r, latency = call(client, model, level, prompt)
    u = r.usage_metadata
    rec = {
        "config": name, "model": model, "thinking_level": level, "task": task_id, "rep": rep,
        "latency_sec": latency,
        "prompt_tokens": u.prompt_token_count or 0,
        "output_tokens": u.candidates_token_count or 0,
        "thought_tokens": u.thoughts_token_count or 0,
        "finish_reason": str(r.candidates[0].finish_reason) if r.candidates else None,
        "model_version": r.model_version,
        "text": r.text or "",
    }
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return out, f"{latency:.1f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="*", help="実行する条件名（省略時は全部）")
    ap.add_argument("--reps-puzzle", type=int, default=2)
    ap.add_argument("--reps-bugfix", type=int, default=3)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, help="動作確認用に件数を絞る")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    client = genai.Client(http_options=types.HttpOptions(timeout=900_000))
    configs = [c for c in CONFIGS if not args.configs or c[0] in args.configs]
    jobs = [(c, *t) for c in configs for t in tasks(args.reps_puzzle, args.reps_bugfix)]
    if args.limit:
        jobs = jobs[: args.limit]
    random.Random(0).shuffle(jobs)  # 同じモデルへの呼び出しが固まらないようにする

    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(run_one, client, *j): j for j in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            c, task_id, rep, _ = futs[f]
            try:
                _, status = f.result()
            except Exception as e:  # noqa: BLE001
                status = f"ERROR {type(e).__name__}: {e}"[:200]
            print(f"[{i}/{len(jobs)}] {c[0]} {task_id} #{rep} {status}", flush=True)


if __name__ == "__main__":
    main()
