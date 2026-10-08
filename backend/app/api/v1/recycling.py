"""
backend/app/api/v1/recycling.py — Recycling Event Ingestion & Query Endpoints.
Enforces Section R5: Anti-Replay on event_id.
"""

from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, status
from shared.schemas.recycling_event import RecyclingEvent
from backend.app.core.errors import ReplayDetectedError, ResourceNotFoundError

router = APIRouter(prefix="/recycling", tags=["Recycling"])

# In-memory store for events
_EVENT_STORE: Dict[str, RecyclingEvent] = {}


@router.post("/events", response_model=RecyclingEvent, status_code=status.HTTP_201_CREATED)
def submit_recycling_event(event: RecyclingEvent):
    """
    Submits a new recycling intake event.
    Enforces anti-replay on unique event_id (Adversarial Case E).
    """
    if event.event_id in _EVENT_STORE:
        raise ReplayDetectedError(
            f"Replay detected: Recycling event '{event.event_id}' has already been ingested."
        )

    _EVENT_STORE[event.event_id] = event
    return event


@router.get("/events/{event_id}", response_model=RecyclingEvent)
def get_recycling_event(event_id: str):
    """Retrieves recycling intake event by identifier."""
    if event_id not in _EVENT_STORE:
        raise ResourceNotFoundError(f"Recycling event '{event_id}' not found.")
    return _EVENT_STORE[event_id]


@router.get("/events", response_model=List[RecyclingEvent])
def list_recycling_events():
    """Lists all ingested recycling events."""
    return list(_EVENT_STORE.values())


def get_event_by_id(event_id: str) -> Optional[RecyclingEvent]:
    return _EVENT_STORE.get(event_id)
