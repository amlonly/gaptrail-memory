# v2 有界多轮查询规划：结果与诊断

这是方向05的独立查询规划修订。旧 v1 的源码、结果及协议保持原样。
候选冻结后完成全部 144 题、288 份有效评分，没有按 development/holdout 的本轮结果改参数。
**样本限制：每家族每 split 12 题；两个 split 都已被 v1 评估，因此 holdout 已曝光，不是新的盲测。48 题 development 筛选未执行。**

## 修订机制

修复 v1 先到先留笔记被首轮占满的问题；允许新证据替换旧笔记。补查使用原生 检索对照 的完整 raw 索引和 query_document_evidence 排名，观察前 80 名中至多 6 个尚未覆盖的原文来源片段。
规划器将所需关系与字面原文引用对应；支持引用需通过子串核验。生成的缺口文本仅用于内部查询，不作为记忆返回。最多两次补查、三次规划调用；最多四条新增原文、4,000 字符插入受保护的前两条之后。
对单个原文占总长度至少 50%、长度至少 2,000 字符的文档直接返回原版结果，避免此类情况消耗规划调用。所有路由基于来源结构，不看数据集/题型/标准答案/人工 evidence。没有叠加其他六个方向。

## 最终答案配对

| 数据集 | development 检索对照 / v2 | holdout 检索对照 / v2 | 合计 检索对照 / v2 | 总胜/负/平 |
|---|---:|---:|---:|---:|
| locomo | 58.33% / 58.33% | 33.33% / 33.33% | 45.83% / 45.83% | 0/0/24 |
| longmem | 41.67% / 41.67% | 75.00% / 75.00% | 58.33% / 58.33% | 0/0/24 |
| beam | 50.00% / 50.00% | 58.33% / 66.67% | 54.17% / 58.33% | 1/0/23 |
| clbench | 0.00% / 0.00% | 0.00% / 0.00% | 0.00% / 0.00% | 0/0/24 |
| persona1 | 83.33% / 83.33% | 41.67% / 41.67% | 62.50% / 62.50% | 0/0/24 |
| persona2 | 25.00% / 25.00% | 50.00% / 50.00% | 37.50% / 37.50% | 0/0/24 |

development 六家族宏平均：**43.06% → 43.06%**；胜/负/平 **0/0/72**。

holdout 六家族宏平均：**43.06% → 44.44%**；胜/负/平 **1/0/71**。

永久门槛：{"passed": false, "first_failure": "development final-answer macro accuracy did not improve"}。
全部门槛分数/覆盖违反项：["development macro final-answer accuracy did not strictly improve"]
逐题答案回退 0；覆盖回退记录 0；packed-input 标注覆盖增益 1。全部 ID 保留在 comparison.json。
分数据集分组 bootstrap 95% 宏平均差区间（百分点）：[0.0, 2.2727272727272725]；McNemar p=1.0。这是小样本本地自评，不是官方效果或总体等效证明。

## 机制是否实际生效

有 32 题最终笔记包含首轮选择之外的新编号；字面引用验证累计通过 351 条；无有效引用的 finish 被改为补查 3 次。
实际 Answer 输入新增原文 source 的题数 23，新增 session 的题数 0。这两个计数是检索行为诊断，不等于准确率或人工标注召回。

| 数据集 | 补查题数 | 额外查询 | 输入变化 | 新 source / session 题数 |
|---|---:|---:|---:|---:|
| locomo | 18 | 23 | 3 | 3 / 0 |
| longmem | 11 | 11 | 2 | 2 / 0 |
| beam | 21 | 31 | 10 | 6 / 0 |
| clbench | 0 | 0 | 0 | 0 / 0 |
| persona1 | 18 | 24 | 9 | 7 / 0 |
| persona2 | 23 | 30 | 8 | 5 / 0 |

查询次数分布：{"3": 28, "2": 63, "1": 53}
停止原因：{"query_budget": 11, "empty_or_repeated_query": 53, "supported_finish": 55, "dominant_original_document_passthrough": 25}
总查询 263，Planner 调用 238；Search 变化 32 题，实际输入变化 32 题。

## 成本

| 角色 | 实际本地调用 | 输入 token | 输出 token | 请求秒 |
|---|---:|---:|---:|---:|
| Planner | 238 | 392588 | 32659 | 484.105 |
| Answer | 176 | 717298 | 23556 | 470.760 |
| Judge | 155 | 172653 | 14139 | 207.034 |

平均 Search 延迟 检索对照 0.179s → v2 3.677s，v2 P95 7.703s。包含初始检索、规划、补查，排除锁等待、加载与 Answer/Judge。
所有研究模型调用均为本地，付费 API 成本 $0；本地运行时间和 token 不为零。六次合成 Judge 校准成本另列在 analysis.json。相同请求仅在 v2 内复用；逐题逻辑 Answer/Judge 成本和实际调用分别统计。

## 实际失败与回退

失败类别：{"unchanged_input_baseline_failure": 63, "remaining_incomplete_annotated_coverage": 5, "complete_annotated_coverage_but_answer_wrong": 3, "changed_input_unannotated_native_answer_failure": 10}

| 数据集 | Case ID | Split | 查询 | 回退/错误 | packed recall 检索对照 → v2 |
|---|---|---|---:|---|---|
| locomo | conv-30#q0017 | development | 2 | tie: unchanged_input_baseline_failure | 1.0 → 1.0 |
| locomo | conv-44#q0018 | development | 2 | tie: remaining_incomplete_annotated_coverage | 0.0 → 0.0 |
| longmem | b0479f84 | development | 2 | tie: complete_annotated_coverage_but_answer_wrong | 1.0 → 1.0 |
| persona1 | f861c1ff-df77-47fe-98b7-aa5b4f5c50c1 | development | 3 | tie: changed_input_unannotated_native_answer_failure | None → None |

类别描述观察到的输入/评分现象，不把粗粒度覆盖当成充分证据，也不把所有错误归因于检索。完整失败 ID、每题动作和答案均保留本地。

## 复现与完整性

从项目根目录用 models/.venv/Scripts/python.exe 执行本报告上级目录的 `recover_wait_fast.py`；完成后 `finalize_recovery.py` 只做 CPU 汇总。协议、所有模型/数据/源码哈希在 protocol.json。
核验 检索对照 的完整 Search 与 packed 输入对 v1 全部一致；原文偏移、元数据和前两条保护通过；最终审计在 final-audit.json。
逐题查询次数、停止原因、延迟、token 与成本在 per-case-costs.json；所有回退和门槛输入在 comparison.json、gate-input.json。
自己的 18405 本地模型已停止，匹配所有权的公共锁已释放，没有停止别人的服务。未提交 Smoke/Full、未修改 incumbent、官方提示/评分、数据、账号、路由、队列或自动化。
faithful-v2 的 76% 和旧 82% 均不参与本次与 检索对照 的成绩比较。

## 运行时恢复及总消耗

首次 v2 原生进程以 `0xC0000409` 异常退出，14/16 份已记录评分有效，未计算该轮准确率。故障记录全部保留；本报告采用预先声明的完整统一恢复结果。恢复仅关闭本地提示/slot 缓存，保持权重、数据、候选、提示、采样和评分不变，重新生成全部规划和两臂 Answer/Judge，没有复用首次模型输出。根因仍未知。

`embedding-costs.json` 补充每题逻辑 embedding 数、新增 CPU BGE 前向调用和缓存向量；`total-attempt-costs.json` 合并首次与恢复的已计量成功调用消耗。首次三个失败/丢失响应的 token 用量为未知，没有按零计算。准确率分母不跨轮合并。

恢复轮共 575 个成功运行时请求收据，未完成或不确定请求 0 个；服务端提示缓存 token 合计 0。本地完整收据复用单独计数，见 runtime-cost-audit.json。

复现使用上级目录 `recover_wait_fast.py`，完成后运行 `finalize_recovery.py` 只做 CPU 汇总。两次等待轮询调整均单独留档，不影响冻结候选或评分设置。

`screening-assessment.json` 将本固定小样本上的研究筛选指标与未修改的永久门槛分开报告；没有完成更大的 48 题 development 筛选，也没有官方准入或晋升。

## 资源交接与续跑

按用户授权的研究资源协调，在 2026-10-30T18:31:22.308426+00:00 完成 31 题、62 条有效双臂评分后暂停。暂停时模型空闲、pending intents 为零；仅停止自己的 worker/18405 并按匹配 nonce 释放锁。04 完成短收尾窗口后，于 2026-10-30T18:43:37.986240+00:00 启动同一冻结恢复方案，原子取得锁后继续未完成题目。完整成功请求收据和已完成配对保留，没有重发不确定请求或改变候选、提示、数据、模型、预算、评分；前一段所有权/清理证据保存在 resource-yield-04/。

## 发布封装与下一步研究边界

发布版沿用逐字节一致的规划器和 检索对照 检索依赖，另加独立本地 API；API 封装只通过合成 CPU 测试，上述准确率来自冻结研究管线。

91 题进行了补查，32 题实际输入变化，其中只有 1 题最终答案得分提高；其余 59 个补查题没有改变实际输入。23 题加入新原文 source，但没有题目新增 session，尚未显示扩大跨会话覆盖的作用。53 次以空或重复查询停止，说明额外调用仍有明显浪费。

CL 的 24 题两臂均为 0，且没有输入变化；这是固定本地模型、提示与原生严格评分下的观察，不能通过改评分来消除。3 个失败题在粗粒度标注覆盖完整时仍答错，说明覆盖不等于充分关系证据或推理成功。Persona 失败没有人工覆盖标注，不能直接归因为检索。

在当前暴露样本上继续调参会削弱验证可信度。该候选保留为机制生效但收益不足的研究版本；后续修订需要另行冻结开发方案和新的验证安排。没有自动提交或晋升。
