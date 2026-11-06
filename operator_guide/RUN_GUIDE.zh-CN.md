# GapTrail Memory v0.35 运行与复现指南

本指南对应 `query_document_block_graph` 图 V4 发布。文档补充不更改参评实现、运行归档、模型、参数或评测数据。以下安装与合成请求用于独立复现环境，不能用来覆盖已参评实例。

本仓库公开方法版本为 v0.35；固定源码与文件身份见发布清单。

## 1. 固定版本与文件校验

| 项目 | 固定值 |
| --- | --- |
| 源码提交 | `8b39b233b7d0d6046ba7aab58abc009c25347ab0` |
| 发布路径 | `releases/graph-v4-m05` |
| 运行入口 | `m05_graph_entry:app` |
| 归档 SHA256 | `fe62b9e5203c3556fc46de6b3034dc7e6d75fe797c4fa83369b77821aec3a619` |
| 图协议 SHA256 | `8b314bc69c6ec48006abd42c0155602c29132b865298272c71ddb43367c33fdd` |
| 运行文件清单 | `M05_MANIFEST.json` 中的 `files_sha256` |

克隆并固定源码，按照 README 校验、解压归档和安装发布目录中的依赖。Git 文本展示可能规范化换行，不能跳过解压直接以文本副本通过字节哈希校验。

在解压后的发布目录可单独核验 manifest：

```bash
python - <<'PY'
import hashlib, json
from pathlib import Path
root = Path.cwd()
manifest = json.loads((root / 'M05_MANIFEST.json').read_text())
for name, expected in manifest['files_sha256'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
print('verified', len(manifest['files_sha256']), 'files')
PY
```

## 2. 环境与模型配置

使用 Linux、Python 3.12 和发布目录锁定的 Python 依赖。服务不需要 GPU 或生成式模型权重。需要一个可访问的、支持 DashScope 原生 embedding 协议的 HTTPS 服务及有效凭据；请求模型名固定为 `text-embedding-v4`。

| 环境变量 | 用途 / 本版设置 |
| --- | --- |
| `MEMORY_API_KEY` | Add/Search 鉴权密钥，私有保存 |
| `DASHSCOPE_API_KEY` | embedding 服务鉴权密钥，私有保存 |
| `AE_EMBEDDING_URL` | 经确认的 embedding HTTPS 端点，不得在 URL 中包含凭据 |
| `AE_EMBEDDING_BACKEND` | `dashscope` |
| `AE_EMBEDDING_DIMENSIONS` | `1024` |
| `AE_EMBEDDING_BATCH_SIZE` | `10` |
| `AE_EMBEDDING_TIMEOUT` | 默认 `60` 秒，单次上游 HTTP 请求超时，不是端到端 Search 时限 |
| `AE_EMBEDDING_MAX_ATTEMPTS` | 默认 `3`；只对代码声明的可重试故障重试 |
| `AE_EMBEDDING_MAX_REQUESTS` | 默认 `0`，无进程内请求数上限，不表示供应商无限配额 |

`m05_graph_entry.py` 在启动时覆盖并固定下列三项，单纯设置其他环境值不能改变它们：

```text
AE_MODE=query_document_block_graph
AE_CONTEXT_CHARS=24000
```

默认分块大小 1,000 字符、重叠 120 字符，混合排序候选数 200，BM25 融合权重 0.7，图选择候选池 80。配置来自冻结源码，不按题目、标签或评测答案调整。

Bash 中可通过隐藏输入注入密钥，避免将实际值放入命令历史：

```bash
read -r -s -p 'Memory API key: ' MEMORY_API_KEY; printf '\n'
read -r -s -p 'Embedding API key: ' DASHSCOPE_API_KEY; printf '\n'
read -r -p 'Embedding HTTPS endpoint: ' AE_EMBEDDING_URL
export MEMORY_API_KEY DASHSCOPE_API_KEY AE_EMBEDDING_URL
export AE_EMBEDDING_BACKEND=dashscope
export AE_EMBEDDING_DIMENSIONS=1024
export AE_EMBEDDING_BATCH_SIZE=10
export AE_EMBEDDING_TIMEOUT=60
export AE_EMBEDDING_MAX_ATTEMPTS=3
export AE_EMBEDDING_MAX_REQUESTS=0
```

生产实例通过私有环境文件或服务管理器注入凭据，限制文件权限，不将其提交到 Git。首次初始化后，数据库记录 embedding 配置身份；不得对已有参评库更换模型、维度或端点后继续检索。

可用于平台模型说明的文字：

> GapTrail Memory v0.35 的文档与查询向量均调用 text-embedding-v4（1024 维）。Add 使用确定性原文分块与持久化，Search 使用向量/BM25 召回和原文块图联合选择；这两个接口均不调用生成式 LLM，不运行 Qwen 或其他生成式模型。最终 Answer/Judge 由 AML 平台执行。早期研究目录不属于本次固定运行入口。

## 3. 启动、数据目录与接口

数据库位置由固定入口 `m05_graph_entry.py` 设置，运行账户须能读写该路径。复现前检查入口中的存储赋值，并只在独立环境准备相应目录。

在解压后的发布目录、已激活虚拟环境且完成环境注入后执行：

```bash
python -m uvicorn m05_graph_entry:app --host 127.0.0.1 --port 18505 --workers 1
```

Health 检查：

```bash
curl --fail --show-error --max-time 15 http://127.0.0.1:18505/health
```

健康信息应包含 `system=GapTrail Memory`、`version=v0.35`、`search_strategy=query_document_block_graph`、`embedding=text-embedding-v4`、`generative_llm_calls_in_memory_service=0`、`context_chars=24000`。健康响应不是 embedding 供应商可用性或吞吐保证。

应用提供 `/add`、`/search` 和 `/health` 相对路由；访问基址与鉴权由独立运行环境配置。

## 独立环境接口验证

以下合成示例只访问自己的本地实例，需已设置 `MEMORY_API_KEY`。消息是演示数据，不包含评测题目或答案。

```bash
curl --fail --show-error http://127.0.0.1:18505/add \
  -H 'Content-Type: application/json' \
  -H "X-Api-Key: ${MEMORY_API_KEY}" \
  --data-binary '{"request_id":"demo-r1","user_id":"demo-user","session_id":"demo-session-1","messages":[{"role":"user","content":"我偏好乘火车出行。"}]}'
```

预期 Add 返回 HTTP 200：

```json
{
  "success": true,
  "request_id": "demo-r1",
  "user_id": "demo-user",
  "session_id": "demo-session-1"
}
```

保持请求完全相同再发送一次，应返回成功且不重复写入；相同 `user_id/request_id` 改变消息或会话内容，应返回 409。

```bash
curl --fail --show-error http://127.0.0.1:18505/search \
  -H 'Content-Type: application/json' \
  -H "X-Api-Key: ${MEMORY_API_KEY}" \
  --data-binary '{"user_id":"demo-user","query":"我的出行偏好是什么？","top_k":5}'
```

成功响应顶层为 `data` 数组，每项必须有非空字符串 `id` 和 `content`，可有数值 `score` 和时间 `created_at`。结果是检索到的原文证据，返回顺序即优先顺序，最多 5 条；文本可能带 `[user]` 等来源前缀。对未写入数据的另一个 `user_id` 查询，应返回 `{"data": []}`。写入同一用户的另一会话后，可从该用户范围跨会话召回。

`messages[].timestamp` 可省略，提供时为毫秒整数。`options` 如有，位于 Search 顶层且为字符串数组。本实现只支持文本字符串，不以多模态示例推定本版接受内容数组。不要向 Search 传入标准答案、题型标签或人工 evidence。

## 4. 容量、成本和异常

本版使用单 Uvicorn worker；正式 Full 的并发配置为 Add 16 / Search 16、`top_k=100`。这是任务配置，不是无限并发或吞吐承诺。CPU、RAM、SQLite/WAL 磁盘空间和 embedding 配额都影响容量。历史测量不构成最低硬件要求或长期容量保证。

embedding 调用按输入与批次产生费用；encoder 记录进程内请求数和供应商报告的 token 用量，未持久化的计数会在重启后丢失。此处不推算未经核对的 Full 总费用，也不将平台 Answer/Judge 费用算作本服务调用。完整供应商账单应通过私有计费记录核对。

| 状态 | 当前实现的含义 |
| --- | --- |
| 200 | Add 已持久化完成，或 Search 成功返回标准结构 |
| 401 | Add/Search 鉴权失败 |
| 409 | 同一幂等键对应不同写入内容 |
| 422 | 请求结构、文本或参数无效 |
| 503 | embedding 异常等服务错误，响应可含 `Retry-After: 5` |

embedding 客户端对 408、425、429、500、502、503、504 和连接故障执行有限重试。当前 API 将 embedding 错误统一映射为 503；外层 503 **不能直接证明**上游状态也是 503 或一定可重试。冻结实现没有保存供应商错误响应正文，应结合 `embedding_failure reason=...` 日志和平台摘要判断，不将未知 400 原因直接认定为长度问题或内容限制。

排查先读取平台任务状态、日志、文件哈希和数据库元数据，限制请求正文日志及访问范围。涉及参评实现变更或原评测数据不可恢复时，先联系 AML 确认；不得清库后直接续跑、替换模型或调整影响结果的关键配置。不要因核对文档自动重启服务、重发 Full 或删除幂等记录。

## 5. 评测与版本维护

截至 2026-11-04，本次 Textual Full 平台状态为 `succeeded` / `completed`，四个阶段完成，完成项为 9,602。任务使用固定平台数据、Answer/Judge 和原生评分；公开成绩以 AML 审核后的榜单为准，不在本指南公开私有分项结果。

运行归档、manifest 和固定源码提交是复现对象。根目录文档可补充说明，但不得借此覆盖服务器源码、模型、排序策略、预算、用户数据或幂等记录。归档内历史文档和根目录早期研究代码不应作为当前启动入口；早期指南见 `experiments/V2_RUN_GUIDE.zh-CN.md`。

评测记忆只用于对应任务，不用于训练、微调、产品分析、数据集重建或传播。按赛事要求在任务完成后 30 天内删除相关数据；需要延长保留时先取得主办方书面同意。执行删除前应与平台复核/异常处理安排协调，本指南不会自动执行删除。

官方要求核对日期为 2026-11-04：[参赛规则](https://agentmemories.ai/rules)、[API Guide](https://agentmemoryleaderboard.ai/api-guide)、[Documentation](https://agentmemoryleaderboard.ai/docs)。账号材料或主办方个别确认需在对应正式渠道处理；本次提交只补充仓库文档。
