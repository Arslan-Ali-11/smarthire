"""
Pydantic schemas for validating unified AI application insights.
Enforces strict structure for interview questions and resume feedback.
"""
from typing import List, Literal, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
import json
import re


def strip_json_fences(text: Union[str, dict, list]) -> str:
    """Strips markdown code fences (e.g. ```json ... ```) from LLM output."""
    if isinstance(text, (dict, list)):
        return json.dumps(text)
    if not isinstance(text, str):
        return str(text)

    s = text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # If it starts with ```, strip manually
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


class InterviewQuestion(BaseModel):
    category: Literal["technical", "gap_probe", "project", "behavioral"]
    question: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    good_answer_points: List[str] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v):
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ("technical", "gap_probe", "project", "behavioral"):
                return v_lower
            if "gap" in v_lower:
                return "gap_probe"
            if "proj" in v_lower:
                return "project"
            if "behav" in v_lower or "situat" in v_lower or "star" in v_lower:
                return "behavioral"
        return "technical"

    @field_validator("difficulty", mode="before")
    @classmethod
    def validate_difficulty(cls, v):
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ("easy", "medium", "hard"):
                return v_lower
            if "easy" in v_lower:
                return "easy"
            if "hard" in v_lower:
                return "hard"
        return "medium"

    @field_validator("good_answer_points", mode="before")
    @classmethod
    def validate_answer_points(cls, v):
        if isinstance(v, str):
            # Split lines or bullets
            points = [p.strip("- *• \t") for p in v.split("\n") if p.strip()]
            return points if points else [v.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []


class ResumeFeedback(BaseModel):
    summary: str
    priority_actions: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    section_tips: Dict[str, str] = Field(default_factory=dict)
    rewritten_bullets: List[str] = Field(default_factory=list)

    @field_validator("priority_actions", "missing_keywords", "rewritten_bullets", mode="before")
    @classmethod
    def validate_string_list(cls, v):
        if isinstance(v, str):
            items = [item.strip("- *• \t") for item in v.split("\n") if item.strip()]
            return items if items else [v.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []

    @field_validator("section_tips", mode="before")
    @classmethod
    def validate_section_tips(cls, v):
        if isinstance(v, dict):
            return {str(k): str(val) for k, val in v.items()}
        if isinstance(v, list):
            # Convert list of tips or dicts to dictionary
            result = {}
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    result.update({str(k): str(val) for k, val in item.items()})
                else:
                    result[f"tip_{i+1}"] = str(item)
            return result
        if isinstance(v, str):
            return {"general": v.strip()}
        return {}


class ApplicationInsights(BaseModel):
    interview_questions: List[InterviewQuestion]
    resume_feedback: ResumeFeedback
