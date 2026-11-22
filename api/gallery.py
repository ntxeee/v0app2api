"""样本库展示页面 — 挂在 API 根路径"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import json
from pathlib import Path

router = APIRouter()
DATA_DIR = Path(__file__).parent.parent / "data"

@router.get("/", response_class=HTMLResponse)
def gallery():
    samples_file = DATA_DIR / "samples.jsonl"
    rows = []
    if samples_file.exists():
        rows = [json.loads(l) for l in samples_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    from collections import defaultdict
    stats = defaultdict(lambda: {"n": 0, "probes": set()})
    for r in rows:
        lab = r.get("strictLabel", "?")
        stats[lab]["n"] += 1
        stats[lab]["probes"].add(r.get("probeId", "?"))
    labels = sorted(stats.items(), key=lambda x: -x[1]["n"])
    total = len(rows)
    passing = sum(1 for _, s in labels if s["n"] >= 12 and len(s["probes"]) >= 3)

    rows_html = ""
    for lab, s in labels:
        gate = "✅" if s["n"] >= 12 and len(s["probes"]) >= 3 else "⚠️"
        rows_html += f"<tr><td>{gate}</td><td><code>{lab}</code></td><td>{s['n']}</td><td>{len(s['probes'])}</td></tr>\n"

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
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1.5rem;min-width:150px}}
.card .num{{font-size:2rem;font-weight:bold;color:#58a6ff}}
.card .label{{color:#8b949e;font-size:.85rem}}
table{{width:100%;border-collapse:collapse;background:#161b22;border-radius:8px;overflow:hidden}}
th,td{{padding:.6rem 1rem;text-align:left;border-bottom:1px solid #21262d}}
th{{background:#1c2128;color:#8b949e;font-size:.8rem;text-transform:uppercase}}
code{{background:#1c2128;padding:.2rem .4rem;border-radius:4px;font-size:.85rem}}
a{{color:#58a6ff;text-decoration:none}}
.links{{margin-top:2rem;display:flex;gap:1rem;flex-wrap:wrap}}
.links a{{background:#21262d;padding:.5rem 1rem;border-radius:6px;border:1px solid #30363d}}
.links a:hover{{border-color:#58a6ff}}
</style>
</head>
<body>
<h1>🧬 Three.js 模型指纹样本库</h1>
<p class="subtitle">v0app2api — 通过 v0.app 采集各 AI 模型生成的 Three.js 代码指纹</p>
<div class="cards">
<div class="card"><div class="num">{total}</div><div class="label">总样本</div></div>
<div class="card"><div class="num">{len(labels)}</div><div class="label">模型标签</div></div>
<div class="card"><div class="num">{passing}</div><div class="label">达标 (≥12样本/3探针)</div></div>
<div class="card"><div class="num">7</div><div class="label">采集探针</div></div>
</div>
<table>
<tr><th>状态</th><th>标签</th><th>样本数</th><th>探针覆盖</th></tr>
{rows_html}
</table>
<div class="links">
<a href="/docs">📖 API 文档 (Swagger)</a>
<a href="/api/probes">🎯 采集探针</a>
<a href="/api/models">🤖 目标模型</a>
<a href="/api/samples?include_code=false&limit=50">📋 样本浏览</a>
<a href="/api/samples/export/jsonl">⬇️ 导出 JSONL</a>
<a href="/api/samples/stats">📊 覆盖统计</a>
<a href="https://github.com/ntxeee/v0app2api">💻 GitHub</a>
</div>
</body>
</html>"""