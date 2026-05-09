from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.roles import list_roles
from backend.app.schemas import AnswerResponse, RoleOption, SessionSummary, StartSessionResponse, SubmitAnswerRequest
from backend.app.services.interview import InterviewService
from backend.app.services.knowledge import get_knowledge_service

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/roles", response_model=list[RoleOption])
def get_roles() -> list[RoleOption]:
    return [RoleOption(value=role.value, label=role.label, blurb=role.blurb) for role in list_roles()]


@router.get("/knowledge/status")
def knowledge_status() -> dict:
    return get_knowledge_service().source_status()


@router.post("/interviews/sessions", response_model=StartSessionResponse)
async def start_session(
    role: str = Form(...),
    candidate_name: str | None = Form(default=None),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> StartSessionResponse:
    try:
        service = InterviewService(db)
        content = await resume.read()
        return await service.start_session(
            role_value=role,
            candidate_name=candidate_name,
            resume_filename=resume.filename or "resume.pdf",
            resume_bytes=content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/interviews/sessions/{session_id}/answers", response_model=AnswerResponse)
def answer_question(
    session_id: str,
    payload: SubmitAnswerRequest,
    db: Session = Depends(get_db),
) -> AnswerResponse:
    try:
        service = InterviewService(db)
        return service.submit_answer(session_id, payload)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("/interviews/sessions/{session_id}/summary", response_model=SessionSummary)
def session_summary(session_id: str, db: Session = Depends(get_db)) -> SessionSummary:
    try:
        service = InterviewService(db)
        return service.get_summary(session_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
