"""
ORCA — agents/reporting_agent.py (NEW)

Final synthesis step: the Planner accumulates one AgentResult per tool call
it made during a turn; this agent compiles them into ONE response object —
{answer_text, explanation, sources, visuals} — matching R6's requirement
that every response be explainable and evidence-based, with the reasoning
trail intact (not just a final answer with no citation to what produced it).

This is the only agent that talks to the Groq API a second time within
one turn (after the Planner's tool-use loop finishes) — its job is purely
to phrase the accumulated structured data as natural language, not to
decide what data to fetch (that's the Planner's job, already done by the
time this runs).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import os
from groq import Groq

from agents.base import AgentResult

_MODEL = "openai/gpt-oss-120b"
_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


@dataclass
class CompiledResponse:
    answer_text: str
    explanation: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    visuals: dict = field(default_factory=dict)  # populated from any viz_agent AgentResult in the accumulated list


def compile_response(user_question_en: str, agent_results: list[AgentResult]) -> CompiledResponse:
    all_explanation = [line for r in agent_results for line in r.explanation]
    all_sources = sorted({s for r in agent_results for s in r.sources})
    visuals = {}
    for r in agent_results:
        for key in ("map_markers", "route_polyline", "chart_series"):
            if key in r.data:
                visuals[key] = r.data[key]

    # Ask Claude to phrase the accumulated evidence as one coherent answer —
    # it is NOT allowed to introduce new facts, only phrase what's already
    # in explanation/data; the prompt says so explicitly to keep this step
    # a synthesis, not a second (uncontrolled) source of claims.
    evidence_block = "\n".join(f"- {line}" for line in all_explanation) or "(no specific evidence points were gathered)"
    resp = _client.chat.completions.create(
        model=_MODEL, max_tokens=800,
        messages=[
            {"role": "system", "content": (
                "You are the final-answer compiler for a marine intelligence "
                "platform. You are given the user's question and a list of "
                "evidence lines already gathered by specialist agents. Write a "
                "clear, direct answer using ONLY the evidence given — do not add "
                "any fact not present in the evidence. If the evidence is empty "
                "or insufficient, say so plainly rather than guessing. Keep it "
                "concise — this may be read by a fisherman deciding whether to "
                "go to sea."
            )},
            {"role": "user", "content": f"Question: {user_question_en}\n\nEvidence gathered:\n{evidence_block}"},
        ],
    )
    answer_text = resp.choices[0].message.content.strip()

    return CompiledResponse(answer_text=answer_text, explanation=all_explanation, sources=all_sources, visuals=visuals)
