"""样本库展示页 — 基于 v0 真实模型数据"""
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
    models_data = {}
    if models_file.exists():
        models_data = json.loads(models_file.read_text(encoding="utf-8"))
    models = models_data.get("models", [])

    stats = defaultdict(lambda: {"n": 0, "probes": set(), "sessions": set()})
    for r in rows:
        lab = r.get("strictLabel", "?")
        stats[lab]["n"] += 1
        stats[lab]["probes"].add(r.get("probeId", "?"))
        stats[lab]["sessions"].add(r.get("source", {}).get("sessionKey", "?"))

    total = len(rows)
    labels_with_samples = len(stats)
    ready_count = sum(1 for s in stats.values() if s["n"] >= 12 and len(s["probes"]) >= 3 and len(s["sessions"]) >= 3)

    # model table: show each model with its effort options and sample count
    model_rows = ""
    for m in sorted(models, key=lambda x: (x["provider"], x["modelId"])):
        mid = m["apiModel"]
        efforts = m.get("effortOptions", [])
        fast = "⚡" if m.get("supportsFast") else ""
        # count samples for this model (any effort)
        n = sum(s["n"] for lab, s in stats.items() if lab.startswith(f"{m['provider']}:{m['modelId']}|"))
        eff_str = ", ".join(efforts) if efforts else "—"
        icon = "✅" if n >= 12 else ("🔶" if n > 0 else "⬜")
        model_rows += f'<tr><td>{icon}</td><td><code>{mid}</code> {fast}</td><td>{m.get("name","")}</td><td>{eff_str}</td><td>{n}</td></tr>\n'

    # label detail table (only labels with samples)
    label_rows = ""
    for lab, s in sorted(stats.items(), key=lambda x: -x[1]["n"]):
        ready = s["n"] >= 12 and len(s["probes"]) >= 3 and len(s["sessions"]) >= 3
        icon = "✅" if ready else "🔶"
        need = max(0, 12 - s["n"])
        label_rows += f'<tr><td>{icon}</td><td><code>{lab}</code></td><td>{s["n"]}</td><td>{len(s["probes"])}/3</td><td>{len(s["sessions"])}</td><td>{"—" if ready else f"+{need}"}</td></tr>\n'

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Three.js 模型指纹样本库</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d1117;color:#c9d1d9;padding:2rem}}
h1{{color:#58a6ff;margin-bottom:.5rem}}
h2{{color:#c9d1d9;margin:2rem 0 1rem;font-size:1.1rem}}
.subtitle{{color:#8b949e;margin-bottom:2rem}}
.cards{{display:flex;gap:1rem;margin-bottom:2rem;flex-wrap:wrap}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1.5rem;min-width:130px}}
.card .num{{font-size:2rem;font-weight:bold;color:#58a6ff}}
.card .label{{color:#8b949e;font-size:.85rem}}
table{{width:100%;border-collapse:collapse;background:#161b22;border-radius:8px;overflow:hidden;font-size:.85rem;margin-bottom:1rem}}
th,td{{padding:.45rem .7rem;text-align:left;border-bottom:1px solid #21262d}}
th{{background:#1c2128;color:#8b949e;font-size:.72rem;text-transform:uppercase}}
code{{background:#1c2128;padding:.1rem .3rem;border-radius:3px;font-size:.78rem}}
a{{color:#58a6ff;text-decoration:none}}
.links{{margin-top:2rem;display:flex;gap:1rem;flex-wrap:wrap}}
.links a{{background:#21262d;padding:.5rem 1rem;border-radius:6px;border:1px solid #30363d}}
.links a:hover{{border-color:#58a6ff}}
.legend{{color:#8b949e;font-size:.8rem;margin-bottom:1rem}}
details{{margin-bottom:1rem}}
summary{{cursor:pointer;color:#58a6ff;font-size:.9rem}}
</style>
</head>
<body>
<h1>Three.js 模型指纹样本库</h1>
<p class="subtitle">数据来源: v0.app gateway-models API (实时) | 样本: {total} 条</p>
<div class="cards">
<div class="card"><div class="num">{total}</div><div class="label">总样本</div></div>
<div class="card"><div class="num">{len(models)}</div><div class="label">v0 可用模型</div></div>
<div class="card"><div class="num">{labels_with_samples}</div><div class="label">已采集标签</div></div>
<div class="card"><div class="num">{ready_count}</div><div class="label">达标 (≥12/3/3)</div></div>
</div>

<h2>已采集标签覆盖</h2>
<p class="legend">✅ 达标 &nbsp; 🔶 未达标 &nbsp; 达标条件: ≥12样本 / ≥3探针 / ≥3会话</p>
<table>
<tr><th></th><th>标签</th><th>样本</th><th>探针</th><th>会话</th><th>需补</th></tr>
{label_rows}
</table>

<details>
<summary>全部 {len(models)} 个 v0 模型（含 effort 选项）</summary>
<p class="legend">⚡ = 有 fast 变体 | effort 选项来自 v0 reasoningOptions</p>
<table>
<tr><th></th><th>模型 ID</th><th>名称</th><th>Effort 选项</th><th>样本数</th></tr>
{model_rows}
</table>
</details>

<div class="links">
<a href="/docs">API 文档</a>
<a href="/api/probes">采集探针</a>
<a href="/api/models">模型 JSON</a>
<a href="/api/samples?include_code=false&limit=50">样本浏览</a>
<a href="/api/samples/export/jsonl">导出 JSONL</a>
<a href="/api/samples/stats">覆盖统计</a>
<a href="https://github.com/ntxeee/v0app2api">GitHub</a>
</div>
</body>
</html>"""