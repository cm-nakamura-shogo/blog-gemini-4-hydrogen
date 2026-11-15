"""日本語の制約パズルを生成する。

隠れた正解を先に決め、正解に対して真になる条件をランダムに追加していき、
z3 で解が一意になった時点で止める。最後に、外しても一意性が保たれる条件を削って最小化する。
"""

import json
import random
from pathlib import Path

import z3

PEOPLE = ["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本"]
DAYS = ["月", "火", "水", "木", "金", "土", "日"]
ATTRS = {
    "担当": ["受付", "経理", "倉庫", "営業", "総務", "企画", "広報"],
    "出身": ["北海道", "宮城", "東京", "愛知", "大阪", "福岡", "広島"],
    "飲み物": ["緑茶", "紅茶", "コーヒー", "水", "ココア", "麦茶", "牛乳"],
    "趣味": ["将棋", "釣り", "登山", "読書", "料理", "写真", "囲碁"],
}

# 難易度ごとの (人数, 曜日以外に使う属性の数)
LEVELS = {"easy": (4, 1), "medium": (5, 2), "hard": (6, 3), "expert": (7, 4)}


def build(n, attr_names):
    """属性ごとの z3 変数。曜日は順序を持つ属性として扱う。"""
    names = ["曜日"] + attr_names
    v = {a: [z3.Int(f"{a}_{p}") for p in range(n)] for a in names}
    base = []
    for a in names:
        base += [z3.And(x >= 0, x < n) for x in v[a]]
        base.append(z3.Distinct(v[a]))
    return names, v, base


def day_of(v, ref, n):
    """参照（人物 or 属性値）の曜日を表す z3 式。"""
    kind, a, x = ref
    if kind == "p":
        return v["曜日"][x]
    expr = z3.IntVal(-1)
    for p in range(n):
        expr = z3.If(v[a][p] == x, v["曜日"][p], expr)
    return expr


def holds(v, ref, a2, x2, n):
    """参照が属性 a2 = x2 を持つことを表す z3 式。"""
    kind, a, x = ref
    if kind == "p":
        return v[a2][x] == x2
    return z3.Or([z3.And(v[a][p] == x, v[a2][p] == x2) for p in range(n)])


def ref_text(ref):
    kind, a, x = ref
    if kind == "p":
        return f"{PEOPLE[x]}さん"
    if a == "曜日":
        return f"{DAYS[x]}曜に出勤する人"
    if a == "担当":
        return f"{ATTRS[a][x]}担当の人"
    if a == "出身":
        return f"{ATTRS[a][x]}出身の人"
    if a == "趣味":
        return f"趣味が{ATTRS[a][x]}の人"
    return f"{ATTRS[a][x]}が好きな人"


def val_text(a, x):
    if a == "曜日":
        return f"{DAYS[x]}曜に出勤する"
    if a == "担当":
        return f"{ATTRS[a][x]}担当である"
    if a == "出身":
        return f"{ATTRS[a][x]}出身である"
    if a == "趣味":
        return f"趣味が{ATTRS[a][x]}である"
    return f"{ATTRS[a][x]}が好きである"


def neg_text(a, x):
    if a == "曜日":
        return f"{DAYS[x]}曜には出勤しない"
    if a == "担当":
        return f"{ATTRS[a][x]}担当ではない"
    if a == "出身":
        return f"{ATTRS[a][x]}出身ではない"
    if a == "趣味":
        return f"趣味が{ATTRS[a][x]}ではない"
    return f"{ATTRS[a][x]}は好きではない"


def random_ref(rng, names, sol, n):
    if rng.random() < 0.35:
        return ("p", None, rng.randrange(n))
    a = rng.choice(names[1:]) if len(names) > 1 and rng.random() < 0.85 else "曜日"
    return ("a", a, rng.randrange(n))


def person_of(ref, sol, n):
    kind, a, x = ref
    if kind == "p":
        return x
    return next(p for p in range(n) if sol[a][p] == x)


def random_clue(rng, names, v, sol, n):
    """正解に対して真になる条件を1つ作り、(z3式, 日本語文) を返す。"""
    t = rng.choice(["same", "same", "not", "before", "next", "xor", "gap"])
    r1 = random_ref(rng, names, sol, n)
    p1 = person_of(r1, sol, n)
    if t == "same":
        a2 = rng.choice([a for a in names if a != r1[1]])
        x2 = sol[a2][p1]
        return holds(v, r1, a2, x2, n), f"{ref_text(r1)}は{val_text(a2, x2)}。"
    if t == "not":
        a2 = rng.choice([a for a in names if a != r1[1]])
        x2 = rng.choice([x for x in range(n) if x != sol[a2][p1]])
        return z3.Not(holds(v, r1, a2, x2, n)), f"{ref_text(r1)}は{neg_text(a2, x2)}。"
    r2 = random_ref(rng, names, sol, n)
    p2 = person_of(r2, sol, n)
    if p1 == p2 or "曜日" in (r1[1], r2[1]):
        return None
    d1, d2 = sol["曜日"][p1], sol["曜日"][p2]
    e1, e2 = day_of(v, r1, n), day_of(v, r2, n)
    if t == "before":
        if d1 > d2:
            r1, r2, e1, e2 = r2, r1, e2, e1
        return e1 < e2, f"{ref_text(r1)}は、{ref_text(r2)}より前の曜日に出勤する。"
    if t == "next":
        if abs(d1 - d2) != 1:
            return None
        if d1 > d2:
            r1, r2, e1, e2 = r2, r1, e2, e1
        return e2 == e1 + 1, f"{ref_text(r2)}は、{ref_text(r1)}の翌日に出勤する。"
    if t == "gap":
        if abs(d1 - d2) < 2:
            return None
        return z3.Abs(e1 - e2) >= 2, f"{ref_text(r1)}と{ref_text(r2)}の出勤日は、2日以上離れている。"
    if t == "xor":
        a2 = rng.choice([a for a in names if a != r1[1]])
        a3 = rng.choice([a for a in names if a not in (r1[1], a2)] or [a2])
        x2 = sol[a2][p1]
        x3 = rng.choice([x for x in range(n) if x != sol[a3][p1]])
        if rng.random() < 0.5:
            x2, x3, a2, a3 = x3, x2, a3, a2
        return (
            z3.Xor(holds(v, r1, a2, x2, n), holds(v, r1, a3, x3, n)),
            f"{ref_text(r1)}について、「{val_text(a2, x2)}」と「{val_text(a3, x3)}」のうち、"
            "ちょうど一方だけが成り立つ。",
        )
    return None


def count_solutions(base, clues, v, names, limit=2):
    s = z3.Solver()
    s.add(base + clues)
    found = 0
    while found < limit and s.check() == z3.sat:
        m = s.model()
        found += 1
        s.add(z3.Or([x != m[x] for a in names for x in v[a]]))
    return found


def generate(level, seed):
    rng = random.Random(seed)
    n, k = LEVELS[level]
    attr_names = list(ATTRS)[:k]
    names, v, base = build(n, attr_names)
    sol = {a: rng.sample(range(n), n) for a in names}

    clues = []
    while count_solutions(base, [c for c, _ in clues], v, names) > 1:
        c = random_clue(rng, names, v, sol, n)
        if c is not None and c[1] not in [t for _, t in clues]:
            clues.append(c)

    # 冗長な条件を削る
    i = 0
    while i < len(clues):
        trial = clues[:i] + clues[i + 1 :]
        if count_solutions(base, [c for c, _ in trial], v, names) == 1:
            clues = trial
        else:
            i += 1
    rng.shuffle(clues)

    answer = {
        PEOPLE[p]: {
            a: (DAYS[sol[a][p]] if a == "曜日" else ATTRS[a][sol[a][p]]) for a in names
        }
        for p in range(n)
    }
    return {"id": f"{level}-{seed}", "level": level, "prompt": render(n, names, clues), "answer": answer}


def render(n, names, clues):
    lines = [f"ある職場の{n}人（" + "、".join(f"{p}さん" for p in PEOPLE[:n]) + "）について、次のことが分かっています。"]
    lines.append("")
    lines.append(f"- 全員が{'、'.join(DAYS[:n])}のいずれか1日に出勤し、同じ曜日に出勤する人はいない。")
    for a in names[1:]:
        lines.append(f"- {a}は「{'、'.join(ATTRS[a][:n])}」のいずれかで、全員異なる。")
    lines.append("")
    for i, (_, t) in enumerate(clues, 1):
        lines.append(f"{i}. {t}")
    lines.append("")
    example = {"(人名)": {a: "…" for a in names}}
    lines.append(f"各人の{'、'.join(names)}を求めてください。")
    lines.append(
        "回答の最後に、全員分の答えを次の形式のJSONで、```json ブロックに1つだけ出力してください"
        "（人名に「さん」は付けず、曜日は1文字で書く）。"
    )
    lines.append("")
    lines.append(json.dumps(example, ensure_ascii=False) + "  ← 1人分の例。全員分を並べる")
    return "\n".join(lines)


if __name__ == "__main__":
    out = []
    for level in LEVELS:
        for seed in range(3):
            pz = generate(level, seed)
            out.append(pz)
            print(pz["id"], "条件数", pz["prompt"].count("\n") - 4 - len(LEVELS))
    Path("data").mkdir(exist_ok=True)
    Path("data/puzzles.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(out[3]["prompt"])
