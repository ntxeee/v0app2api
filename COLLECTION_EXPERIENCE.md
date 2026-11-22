# 采集经验总结（从实际 Codespace 采集中提炼）

## 环境：GitHub Codespace

- Codespace 的 GitHub IP 直连 v0.app **不被 Cloudflare 拦截**（无需代理）
- 端口转发格式：`https://<codespace-name>-8787.app.github.dev`
- Playwright chromium 安装需 `--with-deps`（系统依赖）
- 16GB 内存 Codespace，Chrome 每实例 400-600MB

## 内存是硬瓶颈

- 4 worker ≈ 2GB，6 worker ≈ 3GB（仅 Chrome）
- Codespace 还有 VS Code Server + 其他进程占内存
- **workers 不要超过 6**，推荐 4（留余量防 OOM）
- OOM 表现：worker 静默死亡，job 卡 running，无错误日志
- 解决：`maximumConcurrentSubmissions=4`，定期清理 Chrome 僵尸进程

## 并发模型：槽位填充，不是批等待

- plan 授权 N 个同时 in-flight（如 6）
- 每个 job 到达终态（completed/failed）立即释放槽位
- **立刻 POST 下一个 task**，不要等所有 6 个都完成
- 错误做法：发 6 个 → 等全部完成 → 再发 6 个（浪费 50% 时间）
- 正确做法：始终保持 6 个在飞，一个完成就补一个

## 生成时间

- 正常：20-33s（gemini/claude high）
- 长响应：opus-4.8 high 可达 60-90s
- 超时设置：response_timeout ≥ 180s

## SSE 流读取

- `getResponseBody` 对短响应有效
- **长响应（>100KB）必须用 `takeResponseBodyAsStream`**（流式读取）
- 否则报 "No data found for resource" / "Request content was evicted"
- 这是 opus-4.8 high 长代码 capture_failed 的根因

## 入库门禁（gate）

### 必须全部通过才入库：
1. **provenance**: request-id、prompt-SHA256、modelId、effort、effective_model 全匹配
2. **purity**: answer_markdown 中代码块外无多余文本（或可分离）
3. **text_source**: 必须是 `upstream_sse_code_block`（SSE 中提取的围栏代码块）
4. **HTML 结构**: 含 `<html` / `<!doctype`
5. **Three.js 内容**: 含 THREE. 引用

### 常见拒绝原因：
- `answer_markdown_purity_failed`：high 档模型在代码块外附加解释文字（10/12 A 类拒绝都是这个）
- `direct_html`：从 DOM 取的 HTML 不含围栏，purity 校验失败
- `effective_model = "v0 Max"`：模型选择失败，走了默认路由（pre-fix 版本问题）

## failed vs completed

- **failed（upstream_error）不产出可入库文本**
- 只有 completed + gate 全通过才入库
- failed  job 不要重新 POST（automaticPostRetry=false）
- 用 GET 查终态，记录 failure.json，继续下一个

## GET-only 原则

- 查询 job 状态只用 GET `/v1/jobs/{id}`
- **不要对已提交的 job 重新 POST**（会创建重复会话，污染样本）
- 终态判定：status=completed 或 status=failed
- running 状态继续等，不要干预

## 探针提示词

- **一字不改原文发送**
- prompt_sha256 必须与 probe-bank 中定义一致
- 修改提示词 = 改变特征分布 = 污染指纹库
- 7 个探针轮换，每标签 ≥3 个不同探针

## effort 档位

- v0 实际选项：none / low / medium / high / xhigh / max（按模型不同）
- 采集时明确指定 effort（不要留 auto/默认）
- 标签格式：`provider:modelId|effort`
- fast 不是独立型号（同模型速度开关，指纹相同）

## 模型选择

- 必须在 v0 UI 中确认选中了目标模型
- 默认模型是 "v0 Max"（路由模型），不是具体型号
- 如果 effective_model 显示 "v0 Max" → 选择失败 → 不入库
- claude/gpt/grok 倾向创建 artifact 文件（代码不在聊天正文）
- gemini 倾向直接贴代码块

## artifact 处理

- 模型创建 artifact 时，聊天正文只是摘要
- 需从 artifact 预览 iframe / 文件 API 取回完整 HTML
- 取不到完整代码 → 不入库（摘要不是代码）
- text_source 应为 artifact_frame 或 artifact_raw

## 代理相关（Codespace 不需要，其他环境参考）

- v0 匿名配额：每 IP 每轮 3 次
- rate-limit API：`GET /chat/api/rate-limit?scope=anon:probe`
- 中国大陆 IP 被 CF 拦截，需海外出口
- 免费代理大量死节点（404/429/530），需健康检查过滤
- SY trojan 节点从本地连 cf.syjc.xyz 返回 530，从海外服务器连正常
- mihomo load-balance round-robin 轮换出口

## 进程管理

- 用 `pkill -f` 清理（匹配进程名）
- 端口设 public（Codespace 端口转发）
- 不要用会卡住 shell 管道的启动方式
- 后台进程用 setsid + nohup + </dev/null
- 所有 SSH 命令设 timeout

## 数据完整性

- 每个样本独立会话（不同 chat_id）
- import key 去重（同 artifact SHA256 不重复入库）
- hash chain：request → job → response → answer 全链路哈希
- write-once intent：入库后不可修改
- ledger 记录所有操作（posted/completed/failed/rejected）