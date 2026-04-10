from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Optional, TypedDict


Category = Literal["Waste", "Road", "Electrical", "Water"]


@dataclass
class ComplaintInput:
    issue_text: str
    location: str
    wait_text: str
    requester_name: str = "Citizen"


@dataclass
class PolicyChunk:
    text: str
    source: str
    category: str
    score: float = 0.0


@dataclass
class ContactRecord:
    ward: str
    neighborhood: str
    councillor: str
    zonal_executive: str
    email: str
    phone: str
    latitude: float
    longitude: float


@dataclass
class ComplaintResult:
    category: str
    validation_error: str
    recipient_name: str
    recipient_email: str
    recipient_phone: str
    deadline_hours: Optional[int]
    user_wait_hours: Optional[int]
    retrieved_policy: str
    policy_vs_reality: str
    complaint_email: str


class AgentState(TypedDict, total=False):
    issue_text: str
    location: str
    wait_text: str
    requester_name: str
    category: str
    validation_error: str
    retrieved_policy: str
    deadline_hours: int
    user_wait_hours: int
    recipient_name: str
    recipient_email: str
    recipient_phone: str
    policy_vs_reality: str
    complaint_email: str


def to_dict(result: ComplaintResult) -> dict:
    return asdict(result)
