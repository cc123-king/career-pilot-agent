# CareerPilot Agent

面向求职场景的学习项目：解析简历和岗位要求、检索知识资料、计算技能匹配、生成修改建议与面试问题，并汇总报告。

## 启动网页与 API

在 PowerShell 中运行：

```powershell
cd D:\AgentProjects\career-pilot-agent
.\.venv\Scripts\python.exe scripts/run_web.py --port 8001
```

- 网页：http://127.0.0.1:8001/ui/
- 接口文档：http://127.0.0.1:8001/docs
- 健康检查：http://127.0.0.1:8001/health

同一个端口已有服务时，不要重复启动。可以改用其他空闲端口，例如 `--port 8002`。

## 最小演示

1. 在“简历分析”中点击“载入示例”，保留“本地关键词”。
2. 点击“分析简历”，查看分数、技能缺口、建议、面试问题、引用资料和执行记录。
3. 点击“导出报告”，再点击生成的报告文件下载 Markdown 文件。
4. 修改岗位要求，确认旧报告和下载链接被清除，然后重新分析。

示例的规则匹配分数为 85；它不是求职成功概率。“本地关键词”分析不需要 API Key。

## 实现入口

- `src/career_pilot/ui.py`：界面、输入验证、事件绑定、会话报告与导出。
- `src/career_pilot/api.py`：网页和 REST API 共用的分析入口。
- `src/career_pilot/web.py`：将 Gradio 挂载到 FastAPI，在同一进程共享上传知识。
- `scripts/run_web.py`：启动本地网页服务。

分析工作流：ResumeAgent → JobAgent → RAGAgent → MatchAgent → ResumeCoachAgent → InterviewAgent → ReportAgent。

## 当前边界

- 简历分析的解析、评分、建议和面试问题采用规则，不是大模型自主决策。
- “混合检索”和知识问答需要有效的大模型、Embedding 配置；配置放在 `.env`，不要上传密钥。
- 页面报告保存在当前浏览器会话中；修改输入、清空输入、载入示例或成功上传知识后会清除旧报告。
- 上传知识已持久化到本地 SQLite，重启后保留；使用“文档核对与历史”页查看原文依据和保存确认记录。
- 这是绑定 `127.0.0.1` 的本地学习演示，未实现生产环境的身份认证与用户知识库隔离。
- 只有点击导出时才保存 Markdown 报告，目录为 `data/reports`；导出的文件不会因清空页面而删除。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 离线检索评测

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_retrieval.py
.\.venv\Scripts\python.exe scripts/evaluate_retrieval.py --min-score 0.20 --output data/reports/retrieval-evaluation-score-020.json
```

固定问题集在 `evaluation/retrieval_cases.json`：8 个有答案问题、2 个无答案问题。
默认只看排名第一的分块（`top_k=1`），按来源统计 Recall@1、MRR@1 和无答案问题空检索率。
报告保存在 `data/reports`，包含每题的来源、分数、参数和数据指纹。

这是两份文档上的小型学习基线，不代表实际业务准确率；没有调用模型，也没有评估生成答案或模型拒答。
阈值实验不改变网页配置。完整说明见 `docs/retrieval-evaluation.md`。


## 求职项目升级

文档与岗位来源核对、岗位确认后评分、关键词/混合检索选择，以及草稿和配置恢复说明见 [本轮升级说明](docs/JOB_READY_UPGRADE.md)。

当前 v3 修正了缺失加分项时的评分权重、明确技能别名和岗位三态核对；报告显示确认范围、排除原因及实际权重。
