# 接力采集指南

## 样本库 API

```
BASE_URL = https://detail-fondly-chosen.ngrok-free.dev
```

| 操作 | 方法 | 路径 |
|------|------|------|
| 采集探针（提示词） | GET | /api/probes |
| 目标模型列表 | GET | /api/models |
| 导入样本 | POST | /api/samples |
| 导出全量 JSONL | GET | /api/samples/export/jsonl |
| 覆盖统计 | GET | /api/samples/stats |
| API 文档 | GET | /docs |

## 采集目标

在 v0.app（或其他能调用目标模型的平台）上，用指定探针提示词让模型生成 Three.js 代码，收集完整 HTML 产物。

**达标条件（每个标签）：≥12 样本 / ≥3 个不同探针 / ≥3 个独立会话**

## 当前缺口（优先采集）

| 标签 | 现有 | 需补 |
|------|------|------|
| anthropic:claude-fable-5.2\|high | 7 | 5 |
| anthropic:claude-opus-5\|high | 10 | 2 |
| anthropic:claude-opus-5.5\|high | 9 | 3 |
| anthropic:claude-opus-5.5-fast\|high | 11 | 1 |
| anthropic:claude-opus-5-fast\|high | 6 | 6 |
| google:gemini-3.5-flash-lite\|high | 10 | 2 |
| google:gemini-4-carbon\|high | 7 | 5 |
| google:gemini-4-hydrogen\|high | 11 | 1 |
| openai:gpt-5.6-luna\|high | 10 | 2 |
| openai:gpt-5.6-luna-fast\|high | 11 | 1 |
| openai:gpt-5.6-sol\|high | 11 | 1 |
| openai:gpt-5.6-terra\|high | 10 | 2 |
| openai:gpt-5.6-terra-fast\|high | 11 | 1 |
| openai:gpt-6-astra\|high | 11 | 1 |
| openai:gpt-6-sol\|high | 10 | 2 |
| spacexai:grok-4.5\|high | 8 | 4 |
| spacexai:grok-4.6\|high | 7 | 5 |
| spacexai:grok-4.7\|high | 3 | 9（且探针覆盖不足） |
| spacexai:grok-build-0.1\|high | 9 | 3 |
| google:gemini-3.5-flash-lite\|high | 1 | 11（且探针覆盖不足） |
| google:gemini-4-carbon\|high | 2 | 10（且探针覆盖不足） |

## 采集注意事项

### 必须遵守

1. **不要修改探针提示词。** 原文发送，一字不改。修改会改变代码特征分布，污染指纹库。
2. **每个样本必须来自独立会话。** 不同 chat_id / session。同一会话里多次生成只算一个会话。
3. **每个标签至少覆盖 3 个不同探针。** 7 个探针 (T3D-01~07) 轮换使用。
4. **收集完整 HTML 文档。** 不是片段，不是摘要。必须是 `<!DOCTYPE html><html>...</html>` 完整结构。
5. **确认模型身份。** 必须确认实际生成代码的模型与标签一致（看平台显示的模型名/配置）。
6. **effort 档位对应标签后缀。** `|high` 表示 thinking/reasoning effort = high；`|high` 表示默认/自动。

### 质量要求

- artifactText 必须含 `<html` 或 `<!doctype`（完整 HTML）
- artifactText 必须含 Three.js 相关代码（`THREE.` 或 `three` 模块引用）
- 代码长度通常 10KB~80KB（太短可能是摘要不是代码）
- 不要收集纯文本回复/解释/摘要——只要代码产物

### 关于 artifact

部分模型（claude/gpt/grok）会把代码写进 artifact 文件而非贴在聊天里。这时：
- 聊天正文只是摘要（"Created a single HTML file..."），**不是代码**
- 需要从 artifact 预览/下载/文件 API 取回完整 HTML
- 如果取不到完整代码，**不要入库**（会污染）

### 关于配额

- v0.app 匿名：每 IP 每轮 3 次（`GET /chat/api/rate-limit?scope=anon:probe` 可查）
- 需要多 IP 轮换或等待配额重置
- 需要海外 IP（中国大陆直连被拦截）

### 关于反自动化

- v0.app 会检测浏览器自动化（CDP/DevTools Protocol），检测到后禁用页面交互
- 如遇此问题，需自行解决（反检测浏览器、OS 级输入、或换平台）
- 本指南不限定具体技术方案，采集者自行选择

## 入库格式

```json
POST /api/samples
{
  "samples": [{
    "provider": "anthropic",
    "modelId": "claude-sonnet-5",
    "effortTier": "high",
    "probeId": "T3D-03",
    "artifactText": "<!DOCTYPE html><html>...完整代码...</html>",
    "source": {
      "channel": "你的采集渠道标识",
      "sessionKey": "唯一会话ID（如 chat-sha256:xxx）",
      "labelConfirmed": true
    }
  }]
}
```

- `strictLabel` 自动生成（provider:modelId|effortTier），也可手动指定
- 同代码 SHA256 自动去重
- 返回 `{"imported": N, "skipped": N, "total": N}`

## 探针说明

7 个探针定义不同 Three.js 场景（GET /api/probes 获取完整提示词）：

| ID | 场景 |
|----|------|
| T3D-01 | 低多边形动态温室 |
| T3D-02 | 深海观测无人机 |
| T3D-03 | 等距微型工厂 |
| T3D-04 | 粒子星云 |
| T3D-05 | 机械臂装配线 |
| T3D-06 | 地形生成器 |
| T3D-07 | 光影雕塑 |

所有探针要求：单文件 HTML、Three.js CDN、OrbitControls、无外部资源/模型/纹理。

## 指纹训练（采集完成后）

- 特征提取引擎: `collector/threejs-fingerprint-core.js`（Node.js，纯静态分析）
- 训练脚本: `collector/train_char.py`（Python，TF-IDF + SVD + SVC）
- 当前精度: ~75%（session-grouped holdout top-1）
- 目标: ≥80%
- 提升路径: 补样本 → 补 grok/meta 标签 → 特征工程 → 分类器调优

## 最终产出

采集完成后应产出一份总文档，包含：
- 各标签最终样本数 / 探针覆盖 / 会话数
- 采集渠道、时间、方法记录
- 识别精度评估结果（训练后）
- 未达标标签及原因说明