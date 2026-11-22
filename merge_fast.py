import json, sys, io
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
f = r"D:\printjiekou\v0app2api\data\samples.jsonl"
rows = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
merged = 0
for r in rows:
    mid = r.get("modelId", "")
    if mid.endswith("-fast"):
        base = mid[:-5]
        r["modelId"] = base
        r["strictLabel"] = r["provider"] + ":" + base + "|" + r.get("effortTier", "high")
        merged += 1
with open(f, "w", encoding="utf-8") as out:
    out.write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
print("merged %d fast samples, total %d" % (merged, len(rows)))
c = Counter(r["strictLabel"] for r in rows)
print("labels:", len(c))
for lab, n in c.most_common():
    print("  %s: %d" % (lab, n))