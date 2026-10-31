# GapTrail Memory v0.35

当前参赛候选为直接原文块图 V4（`query_document_block_graph`）。它按原文块、标题和列表依赖联合选择证据，保留来源偏移；Add/Search 不调用生成式语言模型，embedding 使用官方 `text-embedding-v4`。Answer 和 Judge 均由评测平台统一执行。

实际部署代码在 [releases/graph-v4-m05](releases/graph-v4-m05)，文件身份见该目录的 `M05_MANIFEST.json`。40 个算法与依赖文件保持冻结版本原样；`m05_graph_entry.py` 只适配 GapTrail 健康信息和独立 m05 数据目录。请以该入口启动当前候选。

这是复用已有图 V4 方法的独立部署，不声称新增算法原创性。图 V4 参考发布为 [AmlSsu/travor-dip-memory](https://github.com/AmlSsu/travor-dip-memory/tree/18bbf3d499d5fd3afd8794f16fd2d3bdbceb42aa)，作者披露为余付 / DataSpot；其检索依赖来源为 SourceTrail / Context Weave，原 MIT 许可与版权保留。原文出处和所有改动见 [PROVENANCE.md](PROVENANCE.md)。

## 运行

服务运行于 Python 3.12、Linux。使用独立虚拟环境安装 `releases/graph-v4-m05/requirements.txt`，将该目录放在独立发布目录；创建 `/var/lib/memory-lab/m05/graph-v4-8b314bc69c6e`，将其归属设为运行服务的用户。认证与 embedding 凭据通过私有环境文件注入，不能提交到仓库。

```sh
cd releases/graph-v4-m05
python -m pip install -r requirements.txt
python -m uvicorn m05_graph_entry:app --host 127.0.0.1 --port 18105 --workers 1
```

私有环境必须提供 `MEMORY_API_KEY`、`DASHSCOPE_API_KEY` 和经过审核的 HTTPS `AE_EMBEDDING_URL`；其他 embedding 配置按照冻结源码 `env.example` 设置。启动入口固定 `AE_MODE=query_document_block_graph`、24000 字符证据预算和上述独立数据库路径。认证 Add/Search 使用 `X-Api-Key`；health 无需认证。公开反向代理应路由到 18105，不能直接开放数据库或环境文件。

平台输入 `request_id/user_id/session_id/messages` 同步写入；Search 输入 `user_id/query/options/top_k`。Search 返回 `{"data":[...]}`，空结果为 `{"data":[]}`，只包含来源证据；`user_id` 隔离，同用户允许跨会话检索。

## 验证边界

图 V4 在原账号的两次完整 Smoke 为 65.8854167、59.0798611（均 46/46）；不是本账号分数，也不能证明稳定优于对照。当前方法尚无完整本地最终答案评分，永久性能门槛未通过。本账号的新部署、Smoke 与 Full 状态另行记录，不将旧通过记录冒充当前部署验证。

仓库原有 `gaptrail/`、`scripts/` 与 `research/RESULTS.md` 对应早期 v2 本地研究封装，不是本次图 V4 运行入口，其成绩不能用于本次版本。

## 许可

MIT。保留所有原有版权和依赖归属，不分发数据集、评测题目、模型权重、运行数据库或认证材料。
