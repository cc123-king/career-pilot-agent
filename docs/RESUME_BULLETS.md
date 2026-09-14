# 简历项目描述

## 推荐项目名称

**CareerPilot Agent——基于 LangGraph 的多智能体求职助手** 　`2026.08—至今`

## 简历精简版

- 基于 Python 与 LangGraph 设计多智能体求职助手，将简历解析、JD 分析、RAG 检索、人岗匹配、简历优化和模拟面试拆分为独立节点，并通过共享状态和条件路由完成工作流编排。
- 使用 Pydantic 建模简历、岗位、评分和建议等结构化数据，支持 PDF/DOCX/TXT/Markdown 简历解析；设计由必备技能、加分技能、关键词覆盖和项目证据构成的可解释匹配算法。
- 使用 FastAPI 提供 REST API、Gradio 构建演示页面、SQLite 管理投递记录；实现大模型增强、失败降级和自动测试，使系统在无 API Key 时仍可完成端到端演示。

## 一页简历空间不足时

- 基于 LangGraph 构建简历解析、JD 分析、RAG、人岗匹配和模拟面试多 Agent 工作流，使用 FastAPI、Gradio、Pydantic 和 SQLite 实现可运行、可解释、可降级的求职助手。

## 技术栈

`Python / LangGraph / Pydantic / RAG / Tool Calling / FastAPI / Gradio / SQLite / OpenAI API / pytest`

## GitHub 仓库简介

```text
基于 LangGraph 的多智能体求职助手：支持简历解析、JD 分析、可解释匹配、简历建议、模拟面试、轻量 RAG 和投递管理。提供 Gradio 页面、FastAPI 接口、SQLite 持久化及无 API Key 演示模式。
```

## 不要写的内容

- 不要写没有测量过的准确率、响应时间或用户量；
- 不要声称从零发明 LangGraph、RAG 或 OpenAI SDK；
- 不要说实现了线上部署，除非已经真的部署并能打开；
- 不要把示例简历的经历当成自己的经历；
- 后续增加真实测试数据后，再把实际测试数量和结果补进简历。

