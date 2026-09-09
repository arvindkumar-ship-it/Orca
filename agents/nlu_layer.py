"""
ORCA — agents/nlu_layer.py (NEW)

R2: detect language automatically, respond in the same language, Indian
regional languages emphasized. Wraps every chat turn: detect -> normalize
user text to English for tool-calling -> (later) translate the final answer
back to the detected language.

Uses the Groq API (OpenAI-compatible chat completions) directly for both
detect+translate steps — a lightweight non-tool-use call, kept separate
from the Planner's tool-use loop (agents/planner_agent.py) since these are
plain text-in/text-out transforms, not agent tool calls.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import os

from groq import Groq

_MODEL = "openai/gpt-oss-120b"
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


@dataclass
class DetectedLanguage:
    code: str          # BCP-47, e.g. "hi", "ta", "en"
    name: str           # human-readable, e.g. "Hindi", "Tamil"
    confidence: float


def detect_and_normalize(user_text: str) -> tuple[DetectedLanguage, str]:
    """Single API call does both: detect the language AND translate to
    English for the Planner's tool-use loop, since a single well-prompted
    call is cheaper and more consistent than two round-trips that could
    disagree with each other about what language was detected."""
    resp = _get_client().chat.completions.create(
        model=_MODEL, max_tokens=500,
        messages=[
            {"role": "system", "content": (
                "You are a language-detection and translation utility for a marine "
                "intelligence platform used across coastal India. Given a user "
                "message in any language (with emphasis on Indian regional "
                "languages — Hindi, Tamil, Telugu, Malayalam, Bengali, Marathi, "
                "Gujarati, Kannada, Odia, Punjabi, and Indian English), respond with "
                "ONLY a JSON object of exactly this shape, no other text: "
                '{"language_code": "<BCP-47 code>", "language_name": "<English name>", '
                '"confidence": <0.0-1.0>, "english_text": "<the message translated to '
                'English, preserving all place names, numbers, and technical terms '
                'exactly>"}'
            )},
            {"role": "user", "content": user_text},
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content.strip()
    parsed = json.loads(raw)
    return (
        DetectedLanguage(code=parsed["language_code"], name=parsed["language_name"], confidence=parsed["confidence"]),
        parsed["english_text"],
    )


def translate_response(english_text: str, target_language: DetectedLanguage) -> str:
    if target_language.code == "en":
        return english_text  # no-op — avoids a wasted API call and any risk of the model rephrasing an already-correct English answer
    resp = _get_client().chat.completions.create(
        model=_MODEL, max_tokens=1500,
        messages=[
            {"role": "system", "content": (
                f"Translate the following marine-safety advisory response into "
                f"{target_language.name}. Preserve all numbers, place names, "
                f"coordinates, and units exactly. Keep the tone clear and direct — "
                f"this may be read by a fisherman making a safety decision. Output "
                f"ONLY the translated text, no preamble."
            )},
            {"role": "user", "content": english_text},
        ],
    )
    return resp.choices[0].message.content.strip()