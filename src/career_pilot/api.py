"""FastAPI interface for integration with other applications."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .config import Settings
from .database import ApplicationRepository
from .models import AnalysisResult, ApplicationCreate, ApplicationRecord
from .service import CareerPilotService


settings = Settings.from_env()
service = CareerPilotService(settings)
repository = ApplicationRepository(settings.database_path)

app = FastAPI(
    title="CareerPilot Agent API",
    version="0.1.0",
    description="简历解析、人岗匹配、简历建议、模拟面试和投递管理 API。",
)


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(min_length=20)
    jd_text: str = Field(min_length=20)
    company: str = ""
    role: str = ""


class StatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "CareerPilot Agent API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "mode": settings.llm_provider if settings.ai_enabled else "demo",
        "ai_enabled": settings.ai_enabled,
    }


@app.post("/api/v1/analyze", response_model=AnalysisResult)
def analyze(request: AnalyzeRequest) -> AnalysisResult:
    try:
        return service.analyze(
            resume_text=request.resume_text,
            jd_text=request.jd_text,
            company=request.company,
            role=request.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/analyze-file", response_model=AnalysisResult)
async def analyze_file(
    resume: UploadFile = File(...),
    jd_text: str = Form(...),
    company: str = Form(""),
    role: str = Form(""),
) -> AnalysisResult:
    suffix = Path(resume.filename or "resume.pdf").suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=415, detail="仅支持 PDF、DOCX、TXT 和 Markdown 简历。")

    temp_path: Path | None = None
    try:
        content = await resume.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="文件不能超过 10 MB。")
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        return service.analyze(
            resume_path=temp_path,
            jd_text=jd_text,
            company=company,
            role=role,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.get("/api/v1/applications", response_model=list[ApplicationRecord])
def list_applications() -> list[ApplicationRecord]:
    return repository.list()


@app.post("/api/v1/applications", response_model=ApplicationRecord, status_code=201)
def create_application(data: ApplicationCreate) -> ApplicationRecord:
    return repository.create(data)


@app.patch("/api/v1/applications/{record_id}", response_model=ApplicationRecord)
def update_application(record_id: int, update: StatusUpdate) -> ApplicationRecord:
    try:
        return repository.update_status(record_id, update.status, update.notes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/v1/applications/{record_id}", status_code=204)
def delete_application(record_id: int) -> None:
    if not repository.delete(record_id):
        raise HTTPException(status_code=404, detail=f"不存在投递记录：{record_id}")


def main() -> None:
    import uvicorn

    uvicorn.run("career_pilot.api:app", host=settings.app_host, port=settings.api_port)


if __name__ == "__main__":
    main()

