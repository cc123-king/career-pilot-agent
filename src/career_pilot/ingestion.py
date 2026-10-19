from pathlib import Path

from career_pilot.documents import read_text_document
from career_pilot.models import JobProfile, ResumeProfile
from career_pilot.parsers import parse_job_text, parse_resume_text


def load_resume_profile(path: str | Path) -> ResumeProfile:
    """Read and parse a resume document."""
    resume_text = read_text_document(path)
    return parse_resume_text(resume_text)


def load_job_profile(
    path: str | Path,
    *,
    company: str,
    role: str,
) -> JobProfile:
    """Read and parse a job-description document."""
    job_text = read_text_document(path)
    return parse_job_text(
        job_text,
        company=company,
        role=role,
    )
