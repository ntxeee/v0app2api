"""v0app2api — Three.js 模型指纹样本管理 API
部署: uvicorn api.app:app --host 0.0.0.0 --port 8900
"""
import json, os, time, hashlib, uuid, re
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="v0app2api", version="1.0.0",
              description="Three.js model fingerprint sample management. Import/export samples, query probes & models.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from .gallery import router as gallery_router
app.include_router(gallery_router)

DATA_DIR = Path(os.environ.get("V0APP2API_DATA", Path(__file__).parent.parent / "data"))
SAMPLES_FILE = DATA_DIR / "samples.jsonl"
PROBES_FILE = DATA_DIR / "probes.json"
MODELS_FILE = DATA_DIR / "models.json"


def load_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def save_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()


# ─── Schemas ───────────────────────────────────────────────────────────────────

class SampleImport(BaseModel):
    provider: str
    modelId: str
    effortTier: str = "high"
    probeId: str
    artifactText: str
    promptSha256: Optional[str] = None
    source: Optional[dict] = None
    strictLabel: Optional[str] = None

class SampleBatchImport(BaseModel):
    samples: List[SampleImport]

class SampleOut(BaseModel):
    sampleId: str
    strictLabel: str
    provider: str
    modelId: str
    effortTier: str
    probeId: str
    artifactText: str
    artifact: dict
    source: dict
    importedAt: str


# ─── Probes & Models ──────────────────────────────────────────────────────────

@app.get("/api/probes", tags=["collection"])
def get_probes():
    """获取所有采集探针（提示词）。每个探针定义一个 Three.js 场景任务。"""
    if not PROBES_FILE.exists():
        return {"probes": []}
    return json.loads(PROBES_FILE.read_text(encoding="utf-8"))


@app.get("/api/models", tags=["collection"])
def get_models():
    """获取目标模型列表。采集时需指定 provider + modelId。"""
    if not MODELS_FILE.exists():
        return {"models": []}
    return json.loads(MODELS_FILE.read_text(encoding="utf-8"))


# ─── Samples CRUD ─────────────────────────────────────────────────────────────

@app.post("/api/samples", tags=["samples"], status_code=201)
def import_samples(batch: SampleBatchImport):
    """批量导入样本。其他 AI 采集完成后调此接口入库。
    
    每个样本需要: provider, modelId, probeId, artifactText (完整 HTML 代码)。
    自动计算 sha256、生成 sampleId、补全 strictLabel。
    重复样本（同 artifactText sha256）自动跳过。
    """
    existing = load_jsonl(SAMPLES_FILE)
    existing_hashes = {r.get("artifact", {}).get("sha256") for r in existing}
    added, skipped = 0, 0
    for s in batch.samples:
        code = s.artifactText.strip()
        if len(code) < 100:
            skipped += 1
            continue
        h = sha256(code)
        if h in existing_hashes:
            skipped += 1
            continue
        label = s.strictLabel or f"{s.provider}:{s.modelId}|{s.effortTier}"
        sample = {
            "sampleId": f"threejs-api-{uuid.uuid4().hex[:12]}",
            "strictLabel": label,
            "provider": s.provider,
            "modelId": s.modelId,
            "effortTier": s.effortTier,
            "probeId": s.probeId,
            "promptSha256": s.promptSha256 or "",
            "artifact": {"byteLength": len(code.encode()), "sha256": h},
            "artifactText": code,
            "source": s.source or {"channel": "api-import", "labelConfirmed": True},
            "importedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        existing.append(sample)
        existing_hashes.add(h)
        added += 1
    save_jsonl(SAMPLES_FILE, existing)
    return {"imported": added, "skipped": skipped, "total": len(existing)}


@app.get("/api/samples", tags=["samples"])
def export_samples(
    provider: Optional[str] = None,
    modelId: Optional[str] = None,
    probeId: Optional[str] = None,
    label: Optional[str] = None,
    limit: int = Query(default=1000, le=10000),
    offset: int = 0,
    include_code: bool = True,
):
    """导出样本。支持按 provider/modelId/probeId/label 过滤。
    
    include_code=false 时只返回元数据（不含 artifactText），用于快速浏览。
    训练指纹库时用 include_code=true 获取完整代码。
    """
    rows = load_jsonl(SAMPLES_FILE)
    if provider:
        rows = [r for r in rows if r.get("provider") == provider]
    if modelId:
        rows = [r for r in rows if r.get("modelId") == modelId]
    if probeId:
        rows = [r for r in rows if r.get("probeId") == probeId]
    if label:
        rows = [r for r in rows if r.get("strictLabel") == label]
    total = len(rows)
    rows = rows[offset:offset + limit]
    if not include_code:
        rows = [{k: v for k, v in r.items() if k != "artifactText"} for r in rows]
    return {"total": total, "offset": offset, "limit": limit, "samples": rows}


@app.get("/api/samples/stats", tags=["samples"])
def sample_stats():
    """样本覆盖统计。每个 label 的样本数、探针覆盖、会话数。
    
    达标条件: ≥12 样本 / ≥3 探针 / ≥3 会话。
    """
    rows = load_jsonl(SAMPLES_FILE)
    from collections import defaultdict
    stats = defaultdict(lambda: {"n": 0, "probes": set(), "sessions": set()})
    for r in rows:
        lab = r.get("strictLabel", "?")
        stats[lab]["n"] += 1
        stats[lab]["probes"].add(r.get("probeId", "?"))
        stats[lab]["sessions"].add(r.get("source", {}).get("sessionKey", "?"))
    result = []
    for lab, s in sorted(stats.items()):
        npass = s["n"] >= 12 and len(s["probes"]) >= 3 and len(s["sessions"]) >= 3
        result.append({"label": lab, "count": s["n"], "probes": len(s["probes"]),
                       "sessions": len(s["sessions"]), "gate": "PASS" if npass else "不足"})
    return {"total_samples": len(rows), "labels": len(result),
            "passing": sum(1 for r in result if r["gate"] == "PASS"), "details": result}


@app.delete("/api/samples/{sample_id}", tags=["samples"])
def delete_sample(sample_id: str):
    """删除指定样本。"""
    rows = load_jsonl(SAMPLES_FILE)
    new = [r for r in rows if r.get("sampleId") != sample_id]
    if len(new) == len(rows):
        raise HTTPException(404, "sample not found")
    save_jsonl(SAMPLES_FILE, new)
    return {"deleted": sample_id, "remaining": len(new)}


@app.get("/api/samples/export/jsonl", tags=["samples"])
def export_jsonl():
    """导出完整 JSONL 文件（用于离线训练）。返回 raw JSONL 文本。"""
    from fastapi.responses import PlainTextResponse
    if not SAMPLES_FILE.exists():
        return PlainTextResponse("", media_type="application/x-ndjson")
    return PlainTextResponse(SAMPLES_FILE.read_text(encoding="utf-8"),
                             media_type="application/x-ndjson",
                             headers={"Content-Disposition": "attachment; filename=samples.jsonl"})


@app.get("/health", tags=["system"])
def health():
    rows = load_jsonl(SAMPLES_FILE)
    return {"ok": True, "samples": len(rows), "version": "1.0.0"}