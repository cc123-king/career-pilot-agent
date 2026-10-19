# CareerPilot Agent

面向简历与岗位分析的可追溯应用：提取简历和JD、逐项核对来源与岗位要求，生成技能覆盖报告、修改建议和面试问题，并恢复历史草稿。

- LangGraph组织7个状态节点；FastAPI与Gradio共用入口。
- 支持PDF、DOCX、图片OCR；规则模式可离线运行，结构化模型提取可选。
- 岗位要求采用“确认、排除误提取、待核实”；待核实项暂停评分，排除原因进入报告。
- SQLite保存来源、确认状态、检索配置与草稿；明确别名匹配保留证据原文。

```mermaid
flowchart LR
    D[简历与JD] --> P[解析与来源校验]
    P --> H[岗位三态核对]
    H --> R[关键词或混合检索]
    R --> M[技能覆盖与证据]
    M --> A[建议 面试与报告]
    A --> S[SQLite历史与事实草稿]
```

## 快速开始

Python 3.12，在项目根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts/run_web.py --port 8001
```

打开 [网页](http://127.0.0.1:8001/ui/) 或 [API文档](http://127.0.0.1:8001/docs)。规则提取与关键词检索无需模型配置。

## 固定样例与演示

```powershell
.\.venv\Scripts\python.exe scripts/run_showcase.py
```

输入为 [合成简历](examples/resume.txt) 与 [示例JD](examples/job.md)。先只确认一项要求会暂停评分；全部确认后固定样例为100分，并验证草稿恢复。
查看 [三分钟演示步骤](docs/SHOWCASE.md) 与 [实际样例结果](docs/examples/showcase-result.json)。

## 验证与边界

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

历史验证：2026-10-19的两套本地Windows依赖环境各443项回归通过。评分、建议和面试问题采用规则；分数表示确认范围内的技能覆盖，不是录用概率。

本轮40道冻结新题首轮19/24可回答完成、16/16无答案正常拒答；助手语义复核保守18/24，固定8题中7题三次契约通过。Windows本地453项回归通过，保留供应商失败和语义反例；这一阶段的历史结果保留；最新修复与CI见下文。详见 [新题评测与限制](docs/FROZEN_QUESTIONS_V7.md)。

来源匹配只保证文本有依据，分类与经历真实性仍需核对。RAG问答使用已核验原文生成逐项陈述，并审查陈述是否受到引用支持；首次有效判不足时尝试有引用候选回答恢复，标准流程最多3次聊天调用。
当前面向本机单用户演示。v3曾在不含 `.env` 的全新Python 3.12环境完成安装、312项回归与实际启动验证；本轮443项结果分别来自当前环境与独立依赖环境。远程CI仍待公开同步后运行，结果以Pull Request检查为准。

[完整运行参考](docs/REFERENCE.md) · [核对接口与v3说明](docs/JOB_READY_UPGRADE.md) · [历史检索基线](docs/retrieval-evaluation.md) · [v4历史评测](docs/RAG_EVIDENCE_V4.md) · [v5完整回答证据链](docs/RAG_ANSWER_V5.md)

v5已完成35题真实问答初评，v5.1完成11道失败题复测；仍有语义误拒。详见 [真实评测与修复报告](docs/RAG_LIVE_V5_1.md)。v4结果为历史回归。

v6.2 已完成有引用候选回答恢复、加权RRF与相邻分块窗口。已知35题：19/19完成、16/16正常拒答；技术36题：22/24完成、11/12正常拒答，另1负例拦截。助手复核发现3条技术回答有引用或语气条件问题，不能把程序通过率当事实准确率。语料为34文档/1218分块，题集为作者标注且已重复使用。见 [真实验收、失败案例与限制](docs/RAG_LIVE_V6_2.md)。历史v5.1与v6初测单独保留。

本轮可靠性修复：保留API和参数原文上下文、API精确召回及条件对象核对；缓存失败答案已能由程序拦截。 最新Windows本地完整回归464项通过，未追加付费模型复测。实现与限制见 [可靠性修复说明](docs/RELIABILITY_V9.md)，远程验证以本次PR的Windows/Ubuntu检查结果为准。
