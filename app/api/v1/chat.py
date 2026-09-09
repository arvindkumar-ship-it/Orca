"""
ORCA — app/api/v1/chat.py (NEW)

The conversational entry point (Section 2 architecture diagram's top-level
flow): NLU layer (detect + normalize) -> Planner agent (tool-use loop across
every specialist agent) -> Reporting agent (final synthesis) -> NLU layer
(translate back) -> response.

Same APIRouter/limiter/request:Request pattern every other ORCA router uses
(see geofence.py/zones.py/route.py) — chat gets a tighter rate limit since
each call may chain multiple Anthropic API calls (NLU detect, N tool-loop
iterations, Reporting compile, NLU translate).
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import limiter
from agents.nlu_layer import detect_and_normalize, translate_response, DetectedLanguage
from agents.planner_agent import run_planner_turn
from agents.reporting_agent import compile_response

router = APIRouter(prefix="/v1", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # None starts a new session


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    detected_language: str
    explanation: list[str]
    sources: list[str]
    visuals: dict


def _load_session(db: Session, session_id: str | None) -> tuple[str, list[dict], dict]:
    if session_id is None:
        return str(uuid.uuid4()), [], {}
    row = db.execute(text("SELECT id, turns, resolved_entities FROM chat_sessions WHERE id = :id"),
                      {"id": session_id}).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    return str(row["id"]), row["turns"], row["resolved_entities"] or {}


def _save_session(db: Session, session_id: str, turns: list[dict], detected_language: DetectedLanguage,
                   resolved_entities: dict) -> None:
    db.execute(text("""
        INSERT INTO chat_sessions (id, detected_language_code, detected_language_name, turns, resolved_entities, last_active_at)
        VALUES (:id, :lang_code, :lang_name, CAST(:turns AS jsonb), CAST(:entities AS jsonb), now())
        ON CONFLICT (id) DO UPDATE SET
            turns = EXCLUDED.turns, detected_language_code = EXCLUDED.detected_language_code,
            detected_language_name = EXCLUDED.detected_language_name,
            resolved_entities = EXCLUDED.resolved_entities, last_active_at = now()
    """), {"id": session_id, "lang_code": detected_language.code, "lang_name": detected_language.name,
           "turns": __import__("json").dumps(turns), "entities": __import__("json").dumps(resolved_entities)})
    db.commit()


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")  # tighter than read endpoints — each call chains several LLM calls, not a cheap DB read
def chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    session_id, history, resolved_entities = _load_session(db, payload.session_id)

    detected_language, english_text = detect_and_normalize(payload.message)
    turn = run_planner_turn(db, english_text, history, resolved_entities)
    compiled = compile_response(english_text, turn.agent_results)
    translated_answer = translate_response(compiled.answer_text, detected_language)

    updated_history = history + [
        {"role": "user", "content": payload.message},
        {"role": "assistant", "content": compiled.answer_text},
    ]
    _save_session(db, session_id, updated_history, detected_language, turn.resolved_entities)

    return ChatResponse(
        session_id=session_id, answer=translated_answer, detected_language=detected_language.name,
        explanation=compiled.explanation, sources=compiled.sources, visuals=compiled.visuals,
    )
