"""
AIDE-X API Routes
Defines all HTTP endpoints for workflow processing and task management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging

from database import get_db, WorkflowTask, AuditLog
from ai_processor import process_request

logger = logging.getLogger("AIDE-X.routes")

# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    """Input payload for /process endpoint."""
    text: str = Field(..., min_length=5, max_length=5000, description="Natural language request text")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "I need to take 3 days leave from March 10th to March 12th due to a family emergency."
            }
        }


class ApprovalRequest(BaseModel):
    """Approve or reject a pending workflow task."""
    approved: bool
    reviewer_note: Optional[str] = None


class WorkflowResponse(BaseModel):
    """Full response returned after processing."""
    task_id: int
    intent: str
    entities: dict
    confidence: float
    risk_level: str
    risk_factors: List[str]
    compliance_status: str
    compliance_notes: List[str]
    compliance_recommendations: List[str]
    execution_mode: str
    status: str
    result_message: str
    agent_logs: List[dict]
    processing_time_ms: int
    created_at: str


# ─── Routers ──────────────────────────────────────────────────────────────────

health_router = APIRouter()
workflow_router = APIRouter()
tasks_router = APIRouter()


@health_router.get("/health", summary="Health check")
def health_check():
    """Returns system health status."""
    return {
        "status": "ok",
        "service": "AIDE-X",
        "timestamp": datetime.utcnow().isoformat()
    }


# ─── Workflow Routes ──────────────────────────────────────────────────────────

@workflow_router.post("/process", response_model=WorkflowResponse, summary="Process a natural language request")
def process_workflow(payload: ProcessRequest, db: Session = Depends(get_db)):
    """
    Main endpoint: accepts raw text, runs it through the multi-agent pipeline,
    stores the result, and returns structured output.
    """
    logger.info(f"[/process] Received: {payload.text[:60]}...")

    # Run multi-agent pipeline
    result = process_request(payload.text)

    # Persist to database
    task = WorkflowTask(
        raw_input=result["raw_input"],
        intent=result["intent"],
        entities=result["entities"],
        confidence=result["confidence"],
        execution_mode=result["execution_mode"],
        status=result["status"],
        result_message=result["result_message"],
        risk_level=result["risk_level"],
        compliance_status=result["compliance_status"],
        agent_logs=result["agent_logs"]
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Write audit log
    audit = AuditLog(
        task_id=task.id,
        action=f"workflow_processed:{result['execution_mode']}",
        details=f"Intent={result['intent']}, Confidence={result['confidence']:.2f}, Status={result['status']}"
    )
    db.add(audit)
    db.commit()

    logger.info(f"[/process] Task #{task.id} created. Mode: {result['execution_mode']}")

    return WorkflowResponse(
        task_id=task.id,
        **{k: v for k, v in result.items() if k != "raw_input"},
        created_at=task.created_at.isoformat()
    )


@workflow_router.post("/{task_id}/approve", summary="Approve or reject a pending task")
def approve_task(task_id: int, payload: ApprovalRequest, db: Session = Depends(get_db)):
    """
    Human-in-the-loop endpoint.
    Approves or rejects a task that was placed in 'request_approval' state.
    """
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in ["pending_approval"]:
        raise HTTPException(status_code=400, detail=f"Task is not pending approval (current: {task.status})")

    new_status = "approved" if payload.approved else "rejected"
    task.status = new_status
    task.updated_at = datetime.utcnow()
    if payload.approved:
        task.result_message += f" [Approved by reviewer: {payload.reviewer_note or 'No note'}]"

    audit = AuditLog(
        task_id=task_id,
        action=f"human_review:{new_status}",
        actor="human_reviewer",
        details=payload.reviewer_note or "No note provided"
    )
    db.add(audit)
    db.commit()

    return {"task_id": task_id, "new_status": new_status, "message": f"Task {new_status} successfully."}


# ─── Task Management Routes ───────────────────────────────────────────────────

@tasks_router.get("/", summary="List all workflow tasks")
def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    intent: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Returns paginated list of workflow tasks with optional filters."""
    query = db.query(WorkflowTask)
    if intent:
        query = query.filter(WorkflowTask.intent == intent)
    if status:
        query = query.filter(WorkflowTask.status == status)

    total = query.count()
    tasks = query.order_by(WorkflowTask.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "tasks": [
            {
                "id": t.id,
                "intent": t.intent,
                "confidence": t.confidence,
                "execution_mode": t.execution_mode,
                "status": t.status,
                "risk_level": t.risk_level,
                "created_at": t.created_at.isoformat()
            }
            for t in tasks
        ]
    }


@tasks_router.get("/{task_id}", summary="Get a specific task")
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Returns full details of a single workflow task including agent logs."""
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    audit_logs = db.query(AuditLog).filter(AuditLog.task_id == task_id).all()

    return {
        "id": task.id,
        "raw_input": task.raw_input,
        "intent": task.intent,
        "entities": task.entities,
        "confidence": task.confidence,
        "execution_mode": task.execution_mode,
        "status": task.status,
        "result_message": task.result_message,
        "risk_level": task.risk_level,
        "compliance_status": task.compliance_status,
        "agent_logs": task.agent_logs,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "audit_trail": [
            {"action": a.action, "actor": a.actor, "details": a.details, "timestamp": a.timestamp.isoformat()}
            for a in audit_logs
        ]
    }


@tasks_router.get("/stats/summary", summary="Dashboard statistics")
def get_stats(db: Session = Depends(get_db)):
    """Returns aggregated stats for the dashboard."""
    total = db.query(WorkflowTask).count()
    auto_exec = db.query(WorkflowTask).filter(WorkflowTask.execution_mode == "auto_execute").count()
    pending = db.query(WorkflowTask).filter(WorkflowTask.status == "pending_approval").count()
    completed = db.query(WorkflowTask).filter(WorkflowTask.status == "completed").count()

    return {
        "total_tasks": total,
        "auto_executed": auto_exec,
        "pending_approval": pending,
        "completed": completed,
        "automation_rate": round(auto_exec / total * 100, 1) if total > 0 else 0
    }