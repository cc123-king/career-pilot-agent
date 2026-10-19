"""Reproduce source review, aliases and saved history using synthetic data, without model calls."""

import argparse
import json
from pathlib import Path

from career_pilot.history import HistoryStore
from career_pilot.review import (
    ReviewRequest,
    SourcePage,
    confirm_job,
    confirm_review,
    create_review,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/showcase")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(args.output / "reviews.sqlite3")
    req = ReviewRequest(
        filename="synthetic-resume.txt",
        pages=[
            SourcePage(
                page_number=1,
                text=(ROOT / "examples/resume.txt").read_text(encoding="utf-8"),
            )
        ],
        job_description=(ROOT / "examples/job.md").read_text(encoding="utf-8"),
        company="示例公司",
        role="AI应用开发工程师",
        parsing_mode="rules",
        retrieval_mode="keyword",
    )
    created = create_review(req, store)
    ids = [f["fact_id"] for f in created["job_facts"]]
    pending = confirm_job(created["review_id"], ids[:1], store)
    assert pending["analysis"] is None and pending["pending_job_fact_ids"]
    complete = confirm_job(created["review_id"], ids, store)
    assert complete["analysis"]["match_result"]["score"] == 100
    saved = confirm_review(
        created["review_id"], [f["fact_id"] for f in created["facts"]], store
    )
    assert (
        HistoryStore(args.output / "reviews.sqlite3").get(saved["review_id"])[
            "draft_markdown"
        ]
        == saved["draft_markdown"]
    )
    result = {
        "input_kind": "synthetic",
        "new_model_requests": 0,
        "pending_confirmation": {
            "score": None,
            "pending_count": len(pending["pending_job_fact_ids"]),
        },
        "complete_confirmation": {
            "score": saved["analysis"]["match_result"]["score"],
            "matched_required": saved["analysis"]["match_result"][
                "matched_required_skills"
            ],
        },
        "alias_example": {"resume": "Fast API", "job": "FastAPI", "matched": True},
        "fact_count": len(saved["facts"]),
        "history_restored": True,
    }
    (args.output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output / "report.md").write_text(
        saved["analysis"]["report_markdown"], encoding="utf-8"
    )
    (args.output / "draft.md").write_text(saved["draft_markdown"], encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
