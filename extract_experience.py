import sqlite3, json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
db = os.path.expanduser("~/.local/share/opencode/opencode.db")
con = sqlite3.connect(db)

sessions = ["ses_e2042fcc1ffeYgSrwUGtOiTlNS", "ses_e11f9b559ffe0wEZxtLOgdbdmu"]
keywords = ["采集", "collect", "v0proxy", "codespace", "指纹", "fingerprint", "样本", "sample",
            "失败", "fail", "错误", "error", "成功", "success", "入库", "import",
            "prompt", "探针", "probe", "artifact", "SSE", "stream", "配额", "quota",
            "代理", "proxy", "出口", "exit", "模型", "model", "effort", "thinking",
            "教训", "注意", "坑", "bug", "fix", "解决", "方案"]

for sid in sessions:
    print("=" * 60)
    print("SESSION:", sid)
    rows = con.execute("SELECT data FROM part WHERE session_id=? ORDER BY rowid", (sid,)).fetchall()
    
    relevant = []
    for (d,) in rows:
        try:
            j = json.loads(d)
        except Exception:
            continue
        if j.get("type") != "text":
            continue
        txt = j.get("text", "")
        if len(txt) < 80:
            continue
        score = sum(1 for k in keywords if k in txt.lower())
        if score >= 4:
            relevant.append((score, txt))
    
    relevant.sort(key=lambda x: -x[0])
    for score, txt in relevant[:20]:
        print(f"\n--- [score={score}] ---")
        print(txt[:800])
    
    print(f"\n(total relevant: {len(relevant)})")

con.close()