# v0app2api — Three.js 模型指纹样本管理 API

通过 v0.app 匿名采集各 AI 模型生成的 Three.js 代码，建立指纹样本库，用于训练模型识别器。

## 🌐 在线 API（可直接调用）

```
https://detail-fondly-chosen.ngrok-free.dev
```

- 展示页: https://detail-fondly-chosen.ngrok-free.dev/
- Swagger: https://detail-fondly-chosen.ngrok-free.dev/docs
- 导入样本: `POST /api/samples`
- 导出训练: `GET /api/samples/export/jsonl`
- 覆盖统计: `GET /api/samples/stats`

**接力采集请先读 [HANDOFF.md](./HANDOFF.md)**

## 快速开始

```bash
pip install -r requirements.txt
uvicorn api.app:app --host 0.0.0.0 --port 8900
```

API 文档: `http://HOST:8900/docs` (Swagger UI)

## API 端点

### 采集配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/probes` | 获取 7 个采集探针（Three.js 场景提示词） |
| GET | `/api/models` | 获取 29 个目标模型（provider/modelId/apiModel） |

### 样本管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/samples` | 批量导入样本 |
| GET | `/api/samples` | 导出/查询样本（支持过滤） |
| GET | `/api/samples/stats` | 覆盖统计（每 label 样本数/探针/会话） |
| GET | `/api/samples/export/jsonl` | 下载完整 JSONL（离线训练用） |
| DELETE | `/api/samples/{id}` | 删除样本 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |

## 导入样本

```bash
curl -X POST http://HOST:8900/api/samples \
  -H "Content-Type: application/json" \
  -d '{
    "samples": [{
      "provider": "google",
      "modelId": "gemini-3.6-flash",
      "effortTier": "high",
      "probeId": "T3D-01",
      "artifactText": "<!DOCTYPE html><html>...完整 Three.js HTML...</html>",
      "source": {"channel": "my-collector", "sessionKey": "unique-session-id"}
    }]
  }'
```

**必填字段:**
- `provider`: 模型提供商 (anthropic/google/openai/spacexai/meta)
- `modelId`: 模型 ID
- `probeId`: 探针 ID (T3D-01 ~ T3D-07)
- `artifactText`: 模型生成的完整 HTML 代码（必须含 `<html>` 和 Three.js）

**可选字段:**
- `effortTier`: 推理档位 (默认 "high")
- `promptSha256`: 提示词 SHA256
- `source`: 来源元数据 (channel, sessionKey, labelConfirmed 等)
- `strictLabel`: 精确标签 (默认自动生成 "provider:modelId|effortTier")

**去重:** 同 artifactText SHA256 自动跳过。

## 导出样本（训练用）

```bash
# 全量 JSONL 下载
curl http://HOST:8900/api/samples/export/jsonl -o samples.jsonl

# 按模型过滤
curl "http://HOST:8900/api/samples?provider=google&modelId=gemini-3.6-flash&include_code=true"

# 只看元数据（不含代码）
curl "http://HOST:8900/api/samples?include_code=false&limit=100"

# 覆盖统计
curl http://HOST:8900/api/samples/stats
```

## 采集探针说明

7 个探针 (T3D-01 ~ T3D-07)，每个定义不同的 Three.js 场景：
- T3D-01: 低多边形动态温室
- T3D-02: 深海观测无人机
- T3D-03: 等距微型工厂
- T3D-04: 粒子星云
- T3D-05: 机械臂装配线
- T3D-06: 地形生成器
- T3D-07: 光影雕塑

所有探针要求: 单文件 HTML、Three.js CDN、OrbitControls、无外部资源。

## 采集方法

通过 v0.app 匿名会话（或其他能调用目标模型的平台）采集：
1. 选择目标模型
2. 发送探针提示词（GET /api/probes）
3. 等待生成完成
4. 提取完整 HTML 代码产物
5. POST /api/samples 入库

**详细注意事项见 [HANDOFF.md](./HANDOFF.md)**

## 指纹训练

样本库达标条件: 每 label ≥12 样本 / ≥3 探针 / ≥3 会话。

推荐特征: char_wb 3-5gram TF-IDF + 结构特征 → SVD150 + SVC-RBF(C=100)
当前最优: session-grouped holdout top-1 ≈ 75%

## 部署

```bash
# FI 服务器
ssh root@fi-hel03.altare.global -p 25194
bash deploy.sh
# 服务运行在 :8900
```

### 公网访问（ngrok 固定域名）

trycloudflare 免费隧道每次重启 URL 会变。用 ngrok 固定：

```bash
# 1. 注册 ngrok: https://dashboard.ngrok.com/signup
# 2. 安装
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | tee /etc/apt/trusted.gpg.d/ngrok.asc
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | tee /etc/apt/sources.list.d/ngrok.list
apt update && apt install ngrok

# 3. 绑定 authtoken（dashboard 里拿）
ngrok config add-authtoken YOUR_TOKEN

# 4. 申请固定域名（dashboard → Domains → 免费 1 个）
# 假设拿到: your-name.ngrok-free.app

# 5. 启动固定隧道
ngrok http --domain=your-name.ngrok-free.app 8900

# 6. 后台运行
nohup ngrok http --domain=your-name.ngrok-free.app 8900 > /tmp/ngrok.log 2>&1 &
```

固定后 API 地址: `https://your-name.ngrok-free.app`

### 当前公网地址

`https://detail-fondly-chosen.ngrok-free.dev`（ngrok 隧道，进程存活期间固定）

## 项目结构

```
v0app2api/
├── api/app.py          # FastAPI 主服务
├── data/
│   ├── probes.json     # 7 个采集探针
│   ├── models.json     # 29 个目标模型
│   └── samples.jsonl   # 样本库 (397 条)
├── collector/          # 采集模块文档
├── deploy.sh           # 一键部署脚本
├── requirements.txt
└── README.md
```