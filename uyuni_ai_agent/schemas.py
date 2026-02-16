from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """Structured output schema for the LLM's root cause analysis.

    The ReAct agent's final response is parsed into this schema,
    giving us reliable fields for alert enrichment and Slack formatting.
    """

    root_cause: str = Field(
        description="One-sentence summary of the root cause, e.g. "
        "'stress-ng process consuming 98% CPU and 33% memory'"
    )
    evidence: List[str] = Field(
        description="Key evidence from the investigation, e.g. "
        "['PID 289151: stress-ng-vm at 98.3% CPU', 'No OOM kills detected']"
    )
    remediation: List[str] = Field(
        description="Ordered remediation steps, e.g. "
        "['Kill the stress-ng process: kill -9 289151', 'Check crontab for scheduled tests']"
    )
    urgency: str = Field(
        description="Urgency rating: one of 'low', 'medium', 'high', 'critical'"
    )
    description: str = Field(
        description="Full human-readable analysis suitable for a Slack alert, "
        "written in markdown. Include all the context an on-call engineer needs."
    )
