# 图发布核验与规划实验

当前图版本的实现、依赖和运行清单保存在 `releases/graph-v4-m05/`。复现图版本请使用 [运行指南](RUN_GUIDE.zh-CN.md)；`graph_tools/` 提供开发树与固定文件的校验工具：

```shell
python graph_tools/verify_layout.py
python graph_tools/verify_layout.py --frozen-only
```

`legacy/query_planner_v2/` 是早期查询规划实验。它的开发安装和测试独立于正式图运行入口，从仓库根目录执行：

```shell
python -m pip install -e legacy/query_planner_v2
python -m unittest discover -s legacy/query_planner_v2/tests -p "test_*.py"
```

规划测试使用合成输入及模拟编码器，不启动正式服务；通过这组测试不能证明图 Full 的复现结果。已有实验记录位于 `experiments/`，其中的结果与成本保留各自原有实验范围。

实际运行的私密配置、模型凭据和数据库不随仓库提供。发布身份与方法说明见 [PROVENANCE.md](../PROVENANCE.md)，许可证见 [LICENSE](../LICENSE)。
