# GapTrail Memory

**沿缺失关系补查，循原文证据返回。** GapTrail Memory 是一个本地运行的记忆检索服务：先检索原文，再由本地规划器判断缺少哪些关系，最多补查两次。笔记保存原文编号，最终返回原始来源片段，供调用平台生成答案。

这是研究候选 v2 的独立运行封装，版本 `0.1.0`。本地配对结果尚未通过永久回归门槛，不能据此宣称优于对照或达到官方分数。完整结果见 [研究记录](research/RESULTS.md)，运行步骤见 [中文运行指南](RUN_GUIDE.zh-CN.md)。

## 工作方式

1. `/add` 保存用户原始消息及会话、角色和时间，使用 CPU BGE 建立原生索引。
2. `/search` 执行原版 `query_document_evidence` 检索。
3. 本地 Qwen 规划器判断缺失关系，执行 `search` 或 `finish`，最多三次规划调用、两次额外查询。查询输入上限 4096 token，输出上限 512 token。
4. 后续证据可以替换旧笔记。finish 的支持引用必须是原文子串；这一检查保证字面来源，不能保证语义充分。
5. 保护原版前两条结果，在其后插入最多四条、总计不超过 4000 字符的新原文，最终保持 24000 字符和最多 100 条结果的预算。

单个长文占主要内容或初始结果已覆盖全部来源时直接返回原版结果。规划仅使用查询、原始历史和来源元数据。服务不执行最终 Answer/Judge，不接受标准答案、题型或人工 evidence 字段。

## 快速开始

需要 Python 3.11+、本地 BGE-small-en-v1.5 目录、Qwen3.5-4B tokenizer、Q4_K_M GGUF，以及支持该模型的 llama.cpp。实验使用 llama.cpp `b11146`。模型权重不在仓库内。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/run_local.py --llama-server "C:/models/llama-server.exe" --gguf "C:/models/Qwen3.5-4B-Q4_K_M.gguf" --bge "C:/models/bge-small-en-v1.5" --tokenizer "C:/models/qwen-tokenizer" --no-auth
```

该命令仅绑定本机：模型端口 18405，记忆 API 端口 8000。`--no-auth` 适用于本地试用；需要服务认证时，在终端设置 `MEMORY_API_KEY` 并去掉该参数。按 Ctrl+C 会停止本次启动的两个进程，并按所有权 nonce 释放 GPU 锁。

## 接口

```http
POST /add
Content-Type: application/json

{"request_id":"demo-1","user_id":"demo","session_id":"s1","messages":[{"role":"user","content":"My laboratory sample is teal."}]}
```

```http
POST /search
Content-Type: application/json

{"user_id":"demo","query":"What color is my laboratory sample?","top_k":5}
```

Search 返回 `{"data":[...]}`，其中是带原文内容的检索结果。`GET /health` 返回服务信息。认证开启时，Add/Search 携带 `X-API-Key` 或 `Authorization: Bearer ...`。

## 结果与成本

固定公开历史样本：六数据集、每个 split 每数据集 12 题，共 144 题、288 条有效臂评分。development 为 43.06% → 43.06%；holdout 为 43.06% → 44.44%；胜/负/平为 1/0/143。development 没有严格提高，因此永久门槛未通过。holdout 曾在 v1 中暴露，不是新的盲测；更大的 48 题 development 筛选未执行。

共 119 次额外查询、238 次规划调用；32 题实际模型输入变化；1 题标注 packed-input 覆盖提高；无已观察到的逐题答案/覆盖回退。平均 Search 延迟从 0.179 秒升至 3.677 秒。研究全部使用本地模型，付费 API 成本为 0，但消耗本地时间与 token。没有提交 Smoke/Full 或晋升 incumbent。

独立 API 封装通过合成 CPU 测试；上述准确率来自冻结研究管线，不是对新封装再次运行基准后的成绩。

## 仓库内容

- `gaptrail/planner.py`：与冻结 v2 逐字节一致的规划器。
- `adaptive_evidence/`：逐字节保留的原文检索依赖模块。
- `gaptrail/api.py`、`runtime.py`：独立 API 和仅允许本机地址的模型调用适配。
- `scripts/run_local.py`：原子锁、进程所有权和启动清理。
- `tests/`：合成 CPU 测试，不依赖数据集、GPU 或下载模型。
- `research/`：聚合结果、成本和复现边界；`SOURCE_MANIFEST.json` 记录来源哈希。

数据集、历史消息、模型答案、评审回执、数据库、模型权重、运行日志和认证文件保留在本地，均不作为发布文件。`data/` 与 `.runtime/` 用于运行时数据，已忽略。

## 许可

MIT，保留依赖源码的版权声明。来源和封装边界见 [PROVENANCE.md](PROVENANCE.md)。

## 发布状态

本仓库对应 v2 研究封装，不等同于线上 v0.35/v7 部署。Full 尚未提交；当前规划候选没有完成有效官方 Smoke。来源披露的补充说明由维护者确认后添加，已有依赖归属和许可仍保留。
