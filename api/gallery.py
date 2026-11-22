"""样本库展示页 — 显示全部目标模型覆盖状态"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import json
from pathlib import Path
from collections import defaultdict

router = APIRouter()
DATA_DIR = Path(__file__).parent.parent / "data"

@router.get("/", response_class=HTMLResponse)
def gallery():
    samples_file = DATA_DIR / "samples.jsonl"
    models_file = DATA_DIR / "models.json"
    rows = []
    if samples_file.exists():
        rows = [json.loads(l) for l in samples_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    models = []
    if models_file.exists():
        models = json.loads(models_file.read_text(encoding="utf-8")).get("models", [])

    # count samples per label
    stats = defaultdict(lambda: {"n": 0, "probes": set(), "sessions": set()})
    for r in rows:
        lab = r.get("strictLabel", "?")
        stats[lab]["n"] += 1
        stats[lab]["probes"].add(r.get("probeId", "?"))
        stats[lab]["sessions"].add(r.get("source", {}).get("sessionKey", "?"))

    # build full target matrix: each model × effort tiers
    efforts = ["high", "low"]
    targets = []
    for m in models:
        for eff in efforts:
            lab = f"{m['provider']}:{m['modelId']}|{eff}"
            s = stats.get(lab, {"n": 0, "probes": set(), "sessions": set()})
            ready = s["n"] >= 12 and len(s["probes"]) >= 3 and len(s["sessions"]) >= 3
            targets.append({"label": lab, "n": s["n"], "probes": len(s["probes"]),
                            "sessions": len(s["sessions"]), "ready": ready})

    total = len(rows)
    ready_count = sum(1 for t in targets if t["ready"])
    has_samples = sum(1 for t in targets if t["n"] > 0)

    rows_html = ""
    for t in sorted(targets, key=lambda x: (-x["ready"], -x["n"], x["label"])):
        icon = "✅" if t["ready"] else ("🔶" if t["n"] > 0 else "⬜")
        need = max(0, 12 - t["n"])
        probe_note = f'{t["probes"]}/3' if t["probes"] < 3 else str(t["probes"])
        rows_html += f'<tr><td>{icon}</td><td><code>{t["label"]}</code></td><td>{t["n"]}</td><td>{probe_note}</td><td>{t["sessions"]}</td><td>{"—" if t["ready"] else f"+{need}"}</td></tr>\n'

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Three.js 模型指纹样本库</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d1117;color:#c9d1d9;padding:2rem}}
h1{{color:#58a6ff;margin-bottom:.5rem}}
.subtitle{{color:#8b949e;margin-bottom:2rem}}
.cards{{display:flex;gap:1rem;margin-bottom:2rem;flex-wrap:wrap}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1.5rem;min-width:140px}}
.card .num{{font-size:2rem;font-weight:bold;color:#58a6ff}}
.card .label{{color:#8b949e;font-size:.85rem}}
table{{width:100%;border-collapse:collapse;background:#161b22;border-radius:8px;overflow:hidden;font-size:.9rem}}
th,td{{padding:.5rem .8rem;text-align:left;border-bottom:1px solid #21262d}}
th{{background:#1c2128;color:#8b949e;font-size:.75rem;text-transform:uppercase}}
code{{background:#1c2128;padding:.15rem .4rem;border-radius:4px;font-size:.8rem}}
a{{color:#58a6ff;text-decoration:none}}
.links{{margin-top:2rem;display:flex;gap:1rem;flex-wrap:wrap}}
.links a{{background:#21262d;padding:.5rem 1rem;border-radius:6px;border:1px solid #30363d}}
.links a:hover{{border-color:#58a6ff}}
.legend{{color:#8b949e;font-size:.8rem;margin-bottom:1rem}}
</style>
</head>
<body>
<h1>Three.js 模型指纹样本库</h1>
<p class="subtitle">v0app2api — 采集各 AI 模型生成的 Three.js 代码，训练指纹识别器</p>
<div class="cards">
<div class="card"><div class="num">{total}</div><div class="label">总样本</div></div>
<div class="card"><div class="num">{len(models)}</div><div class="label">目标模型</div></div>
<div class="card"><div class="num">{len(targets)}</div><div class="label">目标标签 (模型×档位)</div></div>
<div class="card"><div class="num">{ready_count}</div><div class="label">达标</div></div>
<div class="card"><div class="num">{has_samples}</div><div class="label">有样本</div></div>
</div>
<p class="legend">✅ 达标 (≥12样本/≥3探针/≥3会话) &nbsp; 🔶 有样本未达标 &nbsp; ⬜ 未采集 &nbsp; 档位: high / low</p>
<table>
<tr><th></th><th>标签</th><th>样本</th><th>探针</th><th>会话</th><th>需补</th></tr>
{rows_html}
</table>
<div class="links">
<a href="/docs">API 文档</a>
<a href="/api/probes">采集探针</a>
<a href="/api/models">目标模型</a>
<a href="/api/samples?include_code=false&limit=50">样本浏览</a>
<a href="/api/samples/export/jsonl">导出 JSONL</a>
<a href="/api/samples/stats">覆盖统计</a>
<a href="https://github.com/ntxeee/v0app2api">GitHub</a>
</div>
</body>
</html>"""