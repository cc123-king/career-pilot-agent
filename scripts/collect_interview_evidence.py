"""Save a reproducible offline test, retrieval and business-demo evidence bundle."""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    for stream in (sys.stdout, sys.stderr):
        if getattr(stream, "reconfigure", None):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/reports")
    options = parser.parse_args()
    directory = options.output_dir.resolve() / f"evidence-{uuid4().hex}"
    directory.mkdir(parents=True, exist_ok=False)
    steps = [
        (
            "tests",
            [
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--basetemp={directory / 'pytest-temp'}",
                "--tb=short",
            ],
        ),
        (
            "legacy-retrieval",
            [
                "scripts/evaluate_retrieval.py",
                "--output",
                str(directory / "legacy-retrieval.json"),
            ],
        ),
        (
            "retrieval-benchmark",
            ["scripts/benchmark_retrieval.py", "--output-dir", str(directory)],
        ),
        (
            "business-demo",
            ["scripts/run_acceptance_demo.py", "--output-dir", str(directory)],
        ),
    ]
    results = []
    environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    for name, arguments in steps:
        command = [sys.executable, "-B", *arguments]
        print(f"运行：{name}", flush=True)
        try:
            process = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            output = process.stdout + process.stderr
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            output = "该步骤超过 120 秒；未声称通过。\n"
            returncode = 124
        (directory / f"{name}.log").write_text(output, encoding="utf-8")
        passed = re.search(r"\b(\d+) passed\b", output) if name == "tests" else None
        results.append(
            {
                "step": name,
                "command": command,
                "exit_code": returncode,
                "passed_tests": int(passed.group(1)) if passed else None,
                "log": f"{name}.log",
            }
        )
        print(f"{'PASS' if returncode == 0 else 'FAIL'} {name}", flush=True)
    fingerprints = {}
    for folder in ("src/career_pilot", "scripts", "tests", "knowledge", "evaluation"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".md", ".json"}:
                fingerprints[path.relative_to(ROOT).as_posix()] = sha256(
                    path.read_bytes()
                ).hexdigest()
    fingerprints["pyproject.toml"] = sha256(
        (ROOT / "pyproject.toml").read_bytes()
    ).hexdigest()
    success = all(item["exit_code"] == 0 for item in results)
    manifest = {
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "project_root": str(ROOT),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "scope": "offline_tests_keyword_retrieval_and_rule_workflow",
        "live_model_calls": False,
        "real_user_data": False,
        "all_steps_succeeded": success,
        "steps": results,
        "source_sha256": fingerprints,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    test_result = next(item for item in results if item["step"] == "tests")
    summary = [
        "# CareerPilot 离线面试证据",
        "",
        f"检查时间：{manifest['recorded_at_utc']}",
        f"项目：{ROOT}",
        f"整体检查：{'通过' if success else '有步骤未通过，请查日志'}",
        "",
        f"测试通过数量：{test_result['passed_tests']}；测试进程退出码：{test_result['exit_code']}。",
        "",
        "- manifest.json：环境、实际执行命令、返回码和源码指纹。",
        "- tests.log：完整测试输出和警告。",
        "- benchmark-*/summary.md：30 题检索评测与失败题目。",
        "- benchmark-*/report.json：开发参数对照和测试组逐题证据。",
        "- demo-*/summary.json：正常分析、技能缺口、知识不足三个验收场景。",
        "- demo-*/各场景目录：样例输入、结构化结果、执行记录和 Markdown 报告。",
        "",
        "本次没有调用真实聊天或 Embedding 服务，没有验证在线混合检索效果。",
        "检索数据来自两份指南上的作者编写小题集，不代表生产质量；规则匹配分也不是录用概率。",
        "向量检索、RRF、重排序和 OCR 的接口行为由离线测试覆盖，不能据此声称真实模型效果已验证。",
        "",
    ]
    (directory / "README.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"证据目录：{directory}")
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
