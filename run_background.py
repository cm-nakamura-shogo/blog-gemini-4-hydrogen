"""Hydrogen xhigh を background=True（ロングデコード）で長文の題材に実行する。

同期呼び出しでは max_output_tokens の上限 65,536 に思考トークンだけで達して回答が空になったため、
Interactions API の background 実行で上限を広げて再実行する。
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from google import genai

ROOT = Path(__file__).parent
RAW = ROOT / "results" / "raw"
CONFIG = "hydrogen-xhigh-bg"
MODEL = "gemini-4-hydrogen"
MAX_OUTPUT = 262_144


def to_dict(x):
    if hasattr(x, "model_dump"):
        return x.model_dump(mode="json", exclude_none=True)
    return x


def run_one(client, ld):
    task = f"longdoc-{ld['id']}"
    out = RAW / f"{CONFIG}__{task}__0.json"
    if out.exists():
        return task, "skip"
    t0 = time.perf_counter()
    job = client.interactions.create(
        model=MODEL,
        input=ld["prompt"],
        background=True,
        generation_config={"max_output_tokens": MAX_OUTPUT, "thinking_level": "xhigh"},
    )
    while job.status in ("in_progress", "queued"):
        time.sleep(5)
        job = client.interactions.get(id=job.id)
    latency = time.perf_counter() - t0
    text = "".join(
        c.text for step in (job.steps or []) if step.type == "model_output"
        for c in (step.content or []) if c.type == "text"
    )
    usage = to_dict(job.usage) or {}
    rec = {
        "config": CONFIG, "model": MODEL, "thinking_level": "xhigh", "task": task, "rep": 0,
        "latency_sec": latency,
        "prompt_tokens": usage.get("total_input_tokens") or usage.get("input_tokens") or 0,
        "output_tokens": usage.get("total_output_tokens") or usage.get("output_tokens") or 0,
        "thought_tokens": usage.get("total_thought_tokens") or usage.get("thought_tokens") or 0,
        "finish_reason": job.status,
        "model_version": MODEL,
        "usage_raw": usage,
        "text": text,
    }
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return task, f"{job.status} {latency:.0f}s usage={usage}"


def main():
    client = genai.Client()
    lds = [x for x in json.loads((ROOT / "data" / "longdoc.json").read_text()) if x["size"] == "long"]
    with ThreadPoolExecutor(3) as ex:
        for task, status in ex.map(lambda ld: run_one(client, ld), lds):
            print(task, status, flush=True)


if __name__ == "__main__":
    main()
