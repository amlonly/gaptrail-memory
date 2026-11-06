# GapTrail Memory v0.35

图发布物的验证入口与历史规划实验的使用范围，见[工作区说明](operator_guide/GRAPH_WORKSPACE.md)。

GapTrail Memory 是用于 Agent Memory Challenge 文本记忆赛道的 Add/Search 服务。当前发布采用**原文块图与联合证据选择**：先用向量与词项检索召回候选，再补齐标题、列表引导段等原文结构依赖，在长度和条数限制内选择证据。

Add/Search 使用 `text-embedding-v4`，不调用生成式语言模型。Search 返回带来源身份的记忆片段；最终回答和评分由 AML 平台统一执行。

本仓库公开方法版本为 v0.35；固定源码与文件身份见下方发布记录。

## 参评版本与源码

| 项目 | 内容 |
| --- | --- |
| 系统 / 版本 | GapTrail Memory / v0.35 |
| 参评赛道 | Textual，开源方法榜 |
| 检索模式 | `query_document_block_graph` |
| Full 源码固定提交 | [`8b39b233b7d0d6046ba7aab58abc009c25347ab0`](https://github.com/amlonly/gaptrail-memory/tree/8b39b233b7d0d6046ba7aab58abc009c25347ab0) |
| 当前运行代码 | [releases/graph-v4-m05](releases/graph-v4-m05) |
| 启动入口 | `m05_graph_entry:app` |
| 文件身份 | [M05_MANIFEST.json](releases/graph-v4-m05/M05_MANIFEST.json)，41 个运行文件的 SHA256 |
| 逐字节运行归档 | [frozen-runtime.tar.gz](releases/graph-v4-m05/frozen-runtime.tar.gz) |
| 依赖锁定 | [requirements.txt](releases/graph-v4-m05/requirements.txt) |
| 完整运行说明 | [RUN_GUIDE.zh-CN.md](operator_guide/RUN_GUIDE.zh-CN.md) |

运行归档 SHA256：

```text
fe62b9e5203c3556fc46de6b3034dc7e6d75fe797c4fa83369b77821aec3a619
```

Git 的文本换行规范化可能改变文件字节。复现时必须先校验并解压运行归档，再启动服务；入口会校验冻结文件哈希。后续 README 和运行指南补充不改变参评源码或归档。

## 方法流程

1. **同步写入。** 按 `user_id` 保存原始消息、角色、会话、时间和来源偏移；默认以 1,000 字符分块、120 字符重叠，调用 embedding 后将原文与向量写入 SQLite。事务完成且后续可检索后才返回 HTTP 200。
2. **用户内召回。** 在同一 `user_id` 的所有会话中，结合向量相似度和 BM25 排序。选择题的 `options` 仅作为对称的低权重检索视图，不选择答案，也不写入记忆。
3. **原文块图。** 从候选对应的原文中识别标题、段落、列表和代码围栏；图边表示标题层级、列表引导段等布局依赖，节点保留原始字符范围。
4. **联合证据选择。** 对前 80 个候选构建依赖闭包，合并同一来源的重叠区间，按排序收益、查询词覆盖及新增字符成本选择证据。总预算为 24,000 字符，条数不超过 `top_k`。长文档路径或块闭包无法容纳时，沿用冻结的证据打包路径。
5. **返回原文。** 每条结果包含稳定 `id`、原文片段及角色/时间前缀，可附 `score`、`created_at`。分数表达证据顺序，不是答案置信度。服务不生成当前问题的最终答案。

| 代码 | 职责 |
| --- | --- |
| [m05_graph_entry.py](releases/graph-v4-m05/m05_graph_entry.py) | 文件校验，固定模式、预算和独立数据路径，提供健康信息 |
| [api.py](releases/graph-v4-m05/adaptive_evidence/api.py) | 鉴权、请求校验、同步 Add、Search 和错误响应 |
| [core.py](releases/graph-v4-m05/adaptive_evidence/core.py) | 持久化、幂等、用户隔离、分块与混合召回 |
| [block_graph.py](releases/graph-v4-m05/adaptive_evidence/block_graph.py) | 原文块解析及布局依赖 |
| [block_selection.py](releases/graph-v4-m05/adaptive_evidence/block_selection.py) | 依赖闭包、区间合并和联合预算选择 |
| [remote_encoder.py](releases/graph-v4-m05/adaptive_evidence/remote_encoder.py) | embedding 请求、向量校验和上游错误处理 |

## 模型与运行依赖

| 环节 | 模型或实现 | 执行位置 |
| --- | --- | --- |
| Add 分块、抽取 | 确定性原文处理；无生成式 LLM、无摘要模型 | 参赛服务 CPU |
| 文档 / 查询 embedding | `text-embedding-v4`，1,024 维，L2 归一化 | 配置的 DashScope 协议 HTTPS 服务 |
| Search 排序与图选择 | NumPy、BM25、原文块图；无生成式 LLM | 参赛服务 CPU |
| Answer / Judge | AML 平台统一配置 | AML 平台 |

本版 Add/Search 不使用 Qwen、其他生成式模型或本地模型权重。历史研究目录中的模型配置不属于本次运行入口。服务不要求 GPU，需联网访问配置的 embedding 服务；费用取决于实际输入、调用次数和供应商计费，不含参赛服务侧的生成式 LLM 费用。

运行环境为 Linux、Python 3.12、SQLite；Python 依赖使用发布目录锁定的版本。完整配置和容量限制见[运行指南](operator_guide/RUN_GUIDE.zh-CN.md)。

## 快速启动

以下步骤用于**独立复现环境**。已有参评实例不应为核对文档执行重新安装、覆盖、清库或重启。

```bash
git clone https://github.com/amlonly/gaptrail-memory.git
cd gaptrail-memory
git checkout 8b39b233b7d0d6046ba7aab58abc009c25347ab0

python3.12 -m venv .venv-graph
source .venv-graph/bin/activate
cd releases/graph-v4-m05
sha256sum -c frozen-runtime.sha256
tar -xzf frozen-runtime.tar.gz
python -m pip install -r requirements.txt

# 先按 m05_graph_entry.py 中的固定存储配置准备可写目录。

# 按运行指南在当前环境注入私有服务密钥和 embedding 配置后启动。
python -m uvicorn m05_graph_entry:app --host 127.0.0.1 --port 18505 --workers 1
```

必须配置 `MEMORY_API_KEY`、`DASHSCOPE_API_KEY`、`AE_EMBEDDING_URL`。仅克隆源码不会获得凭据；不要将其写入仓库、请求 URL 或截图。本地示例使用回环地址与端口 18505；访问基址由运行环境配置。

## Add/Search 契约

本版实现 Textual 的字符串消息和查询；不声明支持多模态内容数组或 Coding 赛道。

| 接口 | 输入 / 行为 |
| --- | --- |
| `POST /add` | `request_id`、`user_id`、`session_id`、`messages`；消息包含 `role`、`content`，可附毫秒整数 `timestamp` |
| `POST /search` | `user_id`、`query`、`top_k`，可附顶层 `options`；`top_k` 为 1–100 的整数 |
| `GET /health` | 返回服务身份、检索模式、embedding 模型及证据预算；不写入记忆 |
| 鉴权 | Add/Search 使用 `X-Api-Key`；Health 无需认证 |
| 幂等 | 以 `(user_id, request_id)` 去重；同逻辑请求重试不重复写入，不同内容复用同一键返回 409 |
| 隔离 | 不跨 `user_id` 检索；同用户不同 `session_id` 可以互相召回 |
| 返回 | 顶层为有序 `data` 数组，条数不超过本次 `top_k`；无可返回证据时为 `{"data": []}` |

Search 结构示例（合成数据，仅展示字段）：

```json
{
  "data": [
    {
      "id": "stable-source-span-id",
      "content": "[user] 我偏好乘火车出行。",
      "score": 1.0
    }
  ]
}
```

完整合成请求、鉴权示例和错误码见[运行指南](operator_guide/RUN_GUIDE.zh-CN.md#独立环境接口验证)。接入字段以 [AML API Guide](https://agentmemoryleaderboard.ai/api-guide) 和 [Documentation](https://agentmemoryleaderboard.ai/docs) 为准。

## 评测状态与验证范围

截至 2026-11-04，所提交 Textual Full 的平台回执为 `succeeded` / `completed`，Add、Search、Answer、Eval 均完成，完成项为 9,602。Full 配置为 Add 并发 16、Search 并发 16、`top_k=100`。私有任务完成不等于公榜已审核发布；正式成绩及发布状态以 AML 为准。

提交前曾完成用户隔离、跨会话、写后可见、幂等冲突、空结果和 `top_k` 等合成接口检查。合成检查不替代准确率评估；早期本地实验及其他账号的 Smoke 不能作为本版 Full 分数或收益证明。

本仓库只分发源码和运行说明，不分发评测记忆、题目、答案、私有成绩明细、模型权重、数据库或凭据。评测数据仅用于对应任务，按赛事要求在任务完成后 30 天内处理删除；如需延长，须先取得主办方书面同意。该政策不是自动清库脚本，也不授权中断审核或覆盖幂等记录。

## 仓库范围与许可

`releases/graph-v4-m05/` 是本次参评代码；根目录 `legacy/query_planner_v2/gaptrail/`、`legacy/query_planner_v2/scripts/`、`legacy/query_planner_v2/adaptive_evidence/` 和 `experiments/` 保留早期 v2 研究资料，其启动方式和成绩不用于当前发布。冻结归档内的旧说明保留归档时状态，当前操作步骤以本 README 和根目录运行指南为准。

许可为 MIT，见 [LICENSE](LICENSE)。依赖许可、版权通知及发布文件对应关系见 [PROVENANCE.md](PROVENANCE.md)。使用问题可通过 [GitHub Issues](https://github.com/amlonly/gaptrail-memory/issues) 反馈，请勿附带密钥或评测正文。
