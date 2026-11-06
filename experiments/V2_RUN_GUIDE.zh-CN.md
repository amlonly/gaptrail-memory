# 历史 v2 研究指南

本文件仅描述旧 v2/Qwen 本地研究，不是当前图 V4 的部署或 Full 运行指南。当前版本见仓库根目录 RUN_GUIDE.zh-CN.md。

# GapTrail Memory 运行指南

## 1. 准备资源

使用 Python 3.11 或更高版本。准备四个本地路径：llama.cpp `llama-server` 可执行文件；Qwen3.5-4B 的 `Q4_K_M` GGUF；完整的 `BAAI/bge-small-en-v1.5` 模型目录；与 GGUF 对应的 Qwen tokenizer 目录。tokenizer 目录需要包含本地加载所需的 config、tokenizer 和 chat template 文件。路径中有空格时加引号。

研究使用 llama.cpp b11146、Qwen3.5-4B Q4_K_M、8192 上下文、temperature 0、seed 20261030、关闭 thinking 和服务端 prompt/slot 缓存。BGE 使用 CPU、归一化 FP32 CLS、512 token 截断。首次缓存配置曾出现原生运行时崩溃；完整研究恢复统一关闭缓存，不能据此断言崩溃原因。

模型需要自行获取并保留各自许可。仓库不分发权重。服务加载模型时使用 `local_files_only=True`，不会自动下载文件。

## 2. 安装并运行 CPU 检查

在仓库根目录打开终端：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r legacy/query_planner_v2/requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

七项测试只使用合成历史、脚本化规划动作和内存内 API/HTTP 客户端，不调用 GPU，不加载真实模型。当前环境可能出现 Starlette 的 httpx 弃用提示，不影响测试结果。

## 3. 启动本地服务

将下面的四个示例路径替换为你的真实路径：

```powershell
.\.venv\Scripts\python.exe legacy/query_planner_v2/scripts/run_local.py `
  --llama-server "C:/models/llama-server.exe" `
  --gguf "C:/models/Qwen3.5-4B-Q4_K_M.gguf" `
  --bge "C:/models/bge-small-en-v1.5" `
  --tokenizer "C:/models/qwen-tokenizer" `
  --no-auth
```

启动器先检查文件和端口，再原子创建 GPU 锁目录并写 owner/nonce，之后启动自己拥有的模型和 API。默认锁路径由启动器确定；独立运行可显式设置锁目录。多人共用 GPU 时以 `--lock-dir "共享绝对路径"` 指定统一锁。锁被占用时等待，不删除他人的锁或关闭已有服务。

默认模型地址为 `http://127.0.0.1:18405`，API 地址为 `http://127.0.0.1:8000`，均只绑定 loopback。可通过 `--model-port`、`--api-port` 显式修改空闲端口。读取 `.runtime/model.log` 和 `.runtime/api.log` 排查启动问题；端口已占用时启动器会停止并报错。

使用认证时先设置 `$env:MEMORY_API_KEY`，去掉 `--no-auth`，客户端在 Add/Search 携带对应服务密钥。实际密钥只保存在本地环境，不写入仓库或命令参数。`.env.example` 是变量说明，程序不会自动加载 `.env` 文件。

## 4. 写入和查询

另开一个 PowerShell 终端：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
$add = @{request_id='demo-1';user_id='demo';session_id='session-1';messages=@(@{role='user';content='My laboratory sample is teal.'})} | ConvertTo-Json -Depth 6
Invoke-RestMethod http://127.0.0.1:8000/add -Method Post -ContentType 'application/json' -Body $add
$search = @{user_id='demo';query='What color is my laboratory sample?';top_k=5} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/search -Method Post -ContentType 'application/json' -Body $search
```

真实历史使用稳定的 `request_id`、独立的 `user_id`、真实 `session_id` 和原文消息。时间戳可选，单位为毫秒整数。同一 request_id 不同内容会产生 409。Search 只接收 user_id/query/options/top_k；多余字段返回 422。`top_k` 为 1–100。

返回的 `data` 是证据，不是最终答案。调用平台负责将这些证据放入自身的 Answer 输入，并保持自己的提示、预算和评分逻辑。简单示例会触发完整来源覆盖旁路，零规划调用属于正常行为。

## 5. 查看成本并停止

原始记忆保存在 `data/memory.sqlite3`；每次 Search 的摘要记录保存在 `data/search-metrics.jsonl`，包含 query SHA256、查询次数、规划调用数、停止原因、延迟、token 消耗和付费 API 成本。默认摘要不记录问题或历史正文。发生模型传输失败时返回 502，错误摘要中的未知 token 保留为 null，程序不自动重复模型请求。

按启动终端的 Ctrl+C。启动器只停止自己创建的模型/API 子进程，等待退出后核对 owner nonce 并释放自己的锁，清理凭证位于 `.runtime/release.json`。异常断电留下锁时，应先人工核验 owner/PID；不要直接删除其他运行任务的锁。

## 6. 研究复现范围

CPU 检查可以在本仓库独立复现，源文件哈希可与 `SOURCE_MANIFEST.json` 核对。完整 144 题实验依赖另行保存的数据集、冻结 cohort 和原生评分代码；这些材料没有随本仓库发布。完整实验需由材料持有者按对应冻结入口运行并汇总。既有成功请求会按冻结身份复用；新的独立实跑应先另建、冻结实验目录，不能删除历史失败证据冒充同一轮。

本仓库不包含官方提交或自动晋升入口。研究与封装的验证边界、逐数据集成绩及真实失败类型见 `experiments/RESULTS.md`。
