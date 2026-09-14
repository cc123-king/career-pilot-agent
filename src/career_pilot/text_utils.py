"""Deterministic text utilities used by the demo-mode agents."""

from __future__ import annotations

import re
from collections.abc import Iterable


SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "FastAPI": ("fastapi",),
    "Flask": ("flask",),
    "Django": ("django",),
    "LangGraph": ("langgraph",),
    "LangChain": ("langchain",),
    "RAG": ("rag", "retrieval augmented generation", "检索增强生成"),
    "MCP": ("mcp", "model context protocol"),
    "LLM": ("llm", "大语言模型", "大模型"),
    "AI Agent": ("ai agent", "智能体", "agent"),
    "Tool Calling": ("tool calling", "function calling", "工具调用", "函数调用"),
    "Prompt Engineering": ("prompt engineering", "提示词工程", "prompt"),
    "OpenAI API": ("openai api", "openai"),
    "DeepSeek API": ("deepseek api", "deepseek"),
    "REST API": ("rest api", "restful", "http api"),
    "Pydantic": ("pydantic",),
    "JSON": ("json",),
    "Gradio": ("gradio",),
    "Streamlit": ("streamlit",),
    "SQL": ("sql",),
    "SQLite": ("sqlite",),
    "MySQL": ("mysql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "Redis": ("redis",),
    "Chroma": ("chroma", "chromadb"),
    "FAISS": ("faiss",),
    "Elasticsearch": ("elasticsearch", "es检索"),
    "PyTorch": ("pytorch", "torch"),
    "TensorFlow": ("tensorflow",),
    "Transformers": ("transformers", "hugging face", "huggingface"),
    "scikit-learn": ("scikit-learn", "sklearn"),
    "pandas": ("pandas",),
    "NumPy": ("numpy",),
    "pytest": ("pytest",),
    "Git": ("git",),
    "GitHub Actions": ("github actions",),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Linux": ("linux",),
    "AWS": ("aws",),
    "Azure": ("azure",),
    "Java": ("java",),
    "C++": ("c++", "cpp"),
    "JavaScript": ("javascript",),
    "TypeScript": ("typescript",),
    "React": ("react", "reactjs"),
    "Vue": ("vue", "vue.js", "vuejs"),
}


TRANSFERABLE_SKILLS: dict[str, tuple[str, ...]] = {
    "SQL": ("SQLite", "MySQL", "PostgreSQL"),
    "FastAPI": ("Flask", "Django", "REST API"),
    "LangGraph": ("LangChain", "AI Agent"),
    "RAG": ("Chroma", "FAISS", "Elasticsearch"),
    "PostgreSQL": ("MySQL", "SQLite", "SQL"),
    "MySQL": ("PostgreSQL", "SQLite", "SQL"),
    "Docker": ("Linux", "GitHub Actions"),
    "React": ("Vue", "JavaScript", "TypeScript"),
    "PyTorch": ("TensorFlow", "Transformers"),
}


def normalize_space(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def nonempty_lines(text: str) -> list[str]:
    return [line.strip(" \t•·-—|：:") for line in text.splitlines() if line.strip()]


def contains_alias(text: str, alias: str) -> bool:
    lowered = text.lower()
    alias_lower = alias.lower()
    if re.fullmatch(r"[a-z0-9+#. -]+", alias_lower):
        pattern = rf"(?<![a-z0-9]){re.escape(alias_lower)}(?![a-z0-9])"
        return re.search(pattern, lowered) is not None
    return alias_lower in lowered


def extract_skills(text: str) -> list[str]:
    found: list[str] = []
    for canonical, aliases in SKILL_ALIASES.items():
        if any(contains_alias(text, alias) for alias in aliases):
            found.append(canonical)
    return found


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        clean = item.strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
    return output


def find_skill_evidence(text: str, skill: str, limit: int = 3) -> list[str]:
    aliases = SKILL_ALIASES.get(skill, (skill,))
    lines = nonempty_lines(text)
    evidence = [line for line in lines if any(contains_alias(line, alias) for alias in aliases)]
    return unique(evidence)[:limit]


def tokenize(text: str) -> set[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z][a-z0-9+#.-]{1,}", lowered)
    chinese_blocks = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    chinese: list[str] = []
    for block in chinese_blocks:
        if len(block) <= 4:
            chinese.append(block)
        else:
            chinese.extend(block[index : index + 2] for index in range(len(block) - 1))
    return set(latin + chinese)


def clip(text: str, length: int = 240) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= length else compact[: length - 1] + "…"
