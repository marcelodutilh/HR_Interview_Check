"""
ai.py — Anthropic API integration for interview analysis.

Uses api_key passed in, or ANTHROPIC_API_KEY environment variable.
"""

import json
import os
import anthropic

# ---------------------------------------------------------------------------
# Tool definition — forces the model to return a guaranteed JSON schema
# ---------------------------------------------------------------------------

ANALYSIS_TOOL = {
    "name": "submit_analysis",
    "description": "Submit the structured interview analysis result.",
    "input_schema": {
        "type": "object",
        "required": [
            "recommendation",
            "summary",
            "competency_ratings",
            "strengths",
            "red_flags",
            "open_questions",
        ],
        "properties": {
            "recommendation": {
                "type": "string",
                "enum": ["Strong Yes", "Yes", "Maybe", "No"],
                "description": "Overall hiring recommendation.",
            },
            "summary": {
                "type": "string",
                "description": "2-3 sentence overall assessment of the candidate.",
            },
            "competency_ratings": {
                "type": "array",
                "description": "Rating for each rubric competency.",
                "items": {
                    "type": "object",
                    "required": ["name", "rating", "evidence"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Competency name.",
                        },
                        "rating": {
                            "type": "string",
                            "enum": ["Strong", "Acceptable", "Weak", "Not assessed"],
                            "description": "How the candidate performed on this competency.",
                        },
                        "evidence": {
                            "type": "string",
                            "description": (
                                "Specific evidence from the transcript supporting "
                                "this rating (1-2 sentences). Quote or paraphrase directly."
                            ),
                        },
                    },
                },
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4 notable strengths demonstrated in the interview.",
            },
            "red_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concerns or red flags identified. Empty list if none.",
            },
            "open_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Follow-up questions worth exploring in future rounds. "
                    "Empty list if none."
                ),
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_rubric_text(competencies):
    if not competencies:
        return "No rubric defined — use your professional judgment."
    lines = []
    for c in competencies:
        lines.append(f"**{c['name']}**")
        if c.get("strong"):
            lines.append(f"  - Strong:      {c['strong']}")
        if c.get("acceptable"):
            lines.append(f"  - Acceptable:  {c['acceptable']}")
        if c.get("weak"):
            lines.append(f"  - Weak:        {c['weak']}")
    return "\n".join(lines)


def _build_prompt(candidate_name, job_title, competencies, transcript):
    rubric_text = _build_rubric_text(competencies)
    return f"""You are an expert hiring assessor. Evaluate the following interview transcript \
for a **{job_title}** role and submit a structured analysis.

## Candidate
{candidate_name}

## Evaluation Rubric
{rubric_text}

## Interview Transcript
---
{transcript}
---

Instructions:
- Rate the candidate on **every** competency listed in the rubric.
- If a competency was not covered in the interview, rate it "Not assessed".
- Cite specific evidence from the transcript for each rating.
- Be honest and critical — your assessment informs a real hiring decision.
- Identify genuine strengths, concrete red flags, and useful follow-up questions.
- Base the final recommendation solely on what you observed in the transcript."""


# ---------------------------------------------------------------------------
# Chat system-prompt builder
# ---------------------------------------------------------------------------

def build_chat_system(candidate_name, job_title, transcript, ai_analysis_json):
    """
    Build the system prompt for follow-up chat, embedding transcript + analysis
    as read-only context so the model can answer specific questions.
    """
    # Serialise the structured analysis into readable text
    analysis_text = "(No analysis available.)"
    if ai_analysis_json:
        try:
            a = json.loads(ai_analysis_json) if isinstance(ai_analysis_json, str) else ai_analysis_json
            parts = []
            if a.get("recommendation"):
                parts.append(f"Overall recommendation: {a['recommendation']}")
            if a.get("summary"):
                parts.append(f"Summary: {a['summary']}")
            ratings = a.get("competency_ratings") or []
            if ratings:
                parts.append("Competency ratings:")
                for cr in ratings:
                    parts.append(
                        f"  • {cr.get('name','?')}: {cr.get('rating','?')} — {cr.get('evidence','')}"
                    )
            if a.get("strengths"):
                parts.append("Strengths:\n" + "\n".join(f"  • {s}" for s in a["strengths"]))
            if a.get("red_flags"):
                parts.append("Red flags:\n" + "\n".join(f"  • {f}" for f in a["red_flags"]))
            if a.get("open_questions"):
                parts.append("Open questions:\n" + "\n".join(f"  • {q}" for q in a["open_questions"]))
            analysis_text = "\n".join(parts)
        except Exception:
            analysis_text = str(ai_analysis_json)

    transcript_section = transcript.strip() if transcript else "(No transcript recorded.)"

    return f"""You are an expert hiring advisor. You have full context of a recent interview \
for a **{job_title}** role.

## Candidate
{candidate_name}

## Interview Transcript
{transcript_section}

## Structured AI Analysis
{analysis_text}

Answer the recruiter's questions about this candidate and interview. Be concise and specific. \
Always ground your answers in evidence from the transcript. \
If something is not covered in the transcript, say so plainly."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_interview(candidate_name, job_title, competencies, transcript, api_key=None):
    """
    Analyse an interview transcript against a rubric using Claude.

    api_key: optional; if not provided, uses ANTHROPIC_API_KEY env var.

    Returns a dict with keys:
        recommendation, summary, competency_ratings,
        strengths, red_flags, open_questions

    Raises:
        ValueError  — No API key available
        RuntimeError — unexpected API response shape
        anthropic.APIError — network / API failure (caller should handle)
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "No Anthropic API key. Set it in Settings or use the ANTHROPIC_API_KEY environment variable."
        )

    client = anthropic.Anthropic(api_key=key)
    prompt = _build_prompt(candidate_name, job_title, competencies, transcript)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "submit_analysis"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_analysis":
            return block.input

    raise RuntimeError(
        "Unexpected API response: no submit_analysis tool_use block found."
    )
