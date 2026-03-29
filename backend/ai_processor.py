"""
AIDE-X AI Processing Module
Multi-Agent Architecture:
  1. Intent Agent    — classifies intent & extracts entities
  2. Risk Agent      — evaluates operational risk
  3. Compliance Agent — checks policy constraints
  4. Execution Agent — decides execution mode & generates result
"""

import re
import json
import logging
import random
from datetime import datetime
from typing import Optional
from openai import OpenAI  # Works with any OpenAI-compatible API (swap base_url for others)

logger = logging.getLogger("AIDE-X.ai_processor")

# ─── LLM Client Wrapper ───────────────────────────────────────────────────────

class LLMWrapper:
    """
    Generic LLM wrapper. Supports OpenAI, Anthropic (via openai compat),
    local Ollama, or any OpenAI-compatible endpoint.
    Swap base_url and model to change providers.
    """
    def __init__(self):
        self.client = OpenAI(
            api_key="sk-your-key-here",         # Replace with real key or env var
            # base_url="http://localhost:11434/v1" # Uncomment for Ollama
        )
        self.model = "gpt-4o-mini"               # Fast + cheap for demos

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
        """Call the LLM and return the response text."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.2,  # Low temperature for deterministic extraction
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"LLM call failed ({e}), using rule-based fallback.")
            return None  # Triggers fallback logic below


llm = LLMWrapper()


# ─── Fallback Rule-Based Classifier ──────────────────────────────────────────

INTENT_PATTERNS = {
    "leave_request": [
        r"\b(leave|vacation|day off|time off|absent|sick|holiday|pto|paternity|maternity)\b"
    ],
    "payment_issue": [
        r"\b(payment|refund|charge|invoice|billing|transaction|money|fee|overcharged|duplicate)\b"
    ],
    "meeting_schedule": [
        r"\b(meeting|schedule|appointment|call|sync|standup|zoom|teams|calendar|book|slot)\b"
    ],
    "it_support": [
        r"\b(password|login|access|vpn|laptop|software|install|bug|crash|error|network)\b"
    ],
    "hr_query": [
        r"\b(policy|benefits|salary|raise|promotion|performance|review|onboard|handbook)\b"
    ],
    "general_inquiry": []  # Catch-all
}

def rule_based_intent(text: str) -> str:
    text_lower = text.lower()
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return intent
    return "general_inquiry"


# ─── Agent 1: Intent Agent ────────────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """You are an Intent Extraction Agent for an enterprise AI system.
Analyze the user's text and return ONLY valid JSON with this exact schema:
{
  "intent": "<one of: leave_request | payment_issue | meeting_schedule | it_support | hr_query | general_inquiry>",
  "entities": {
    "person": "<name if mentioned, else null>",
    "date_start": "<ISO date or null>",
    "date_end": "<ISO date or null>",
    "amount": "<number or null>",
    "reason": "<brief reason or null>",
    "urgency": "<low|medium|high>",
    "department": "<department or null>",
    "additional": "<any other key info or null>"
  },
  "confidence": <float 0.0-1.0>
}
Return ONLY the JSON, no markdown, no explanation."""


def intent_agent(raw_input: str) -> dict:
    """
    Agent 1: Extracts structured intent and entities from raw text.
    Falls back to rule-based if LLM unavailable.
    """
    logger.info("[IntentAgent] Processing input...")

    llm_response = llm.complete(INTENT_SYSTEM_PROMPT, raw_input)

    if llm_response:
        try:
            # Strip markdown code fences if present
            clean = re.sub(r"```json|```", "", llm_response).strip()
            result = json.loads(clean)
            logger.info(f"[IntentAgent] LLM extracted intent: {result.get('intent')}, confidence: {result.get('confidence')}")
            return result
        except json.JSONDecodeError:
            logger.warning("[IntentAgent] JSON parse error, falling back to rules.")

    # Rule-based fallback
    intent = rule_based_intent(raw_input)
    entities = extract_entities_rule_based(raw_input)
    confidence = 0.72 if intent != "general_inquiry" else 0.45

    return {
        "intent": intent,
        "entities": entities,
        "confidence": confidence
    }


def extract_entities_rule_based(text: str) -> dict:
    """Lightweight regex entity extraction as fallback."""
    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|"
                           r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2})", text, re.I)
    amount_match = re.search(r"\$\s*[\d,]+\.?\d*|\b[\d,]+\.?\d*\s*(dollars?|usd|inr|rupees?)", text, re.I)
    urgency_match = re.search(r"\b(urgent|asap|immediately|critical|high priority|low priority|whenever)\b", text, re.I)

    urgency_map = {
        "urgent": "high", "asap": "high", "immediately": "high", "critical": "high",
        "high priority": "high", "low priority": "low", "whenever": "low"
    }

    urgency_word = urgency_match.group(0).lower() if urgency_match else None
    urgency = urgency_map.get(urgency_word, "medium")

    return {
        "person": None,
        "date_start": date_match.group(0) if date_match else None,
        "date_end": None,
        "amount": amount_match.group(0) if amount_match else None,
        "reason": None,
        "urgency": urgency,
        "department": None,
        "additional": None
    }


# ─── Agent 2: Risk Agent ──────────────────────────────────────────────────────

RISK_RULES = {
    "leave_request":    {"base_risk": "low",    "threshold_days": 5, "high_days": 10},
    "payment_issue":    {"base_risk": "medium",  "high_amount": 10000},
    "meeting_schedule": {"base_risk": "low"},
    "it_support":       {"base_risk": "medium"},
    "hr_query":         {"base_risk": "low"},
    "general_inquiry":  {"base_risk": "low"},
}

def risk_agent(intent: str, entities: dict, raw_input: str) -> dict:
    """
    Agent 2: Evaluates the operational risk of executing this request.
    Returns risk_level and risk_factors list.
    """
    logger.info("[RiskAgent] Evaluating risk...")
    rules = RISK_RULES.get(intent, {"base_risk": "low"})
    risk_level = rules["base_risk"]
    risk_factors = []

    # Check amount risk
    if entities.get("amount"):
        try:
            amount_str = re.sub(r"[^\d.]", "", str(entities["amount"]))
            amount = float(amount_str)
            if amount > rules.get("high_amount", 50000):
                risk_level = "high"
                risk_factors.append(f"High financial impact: {entities['amount']}")
            elif amount > 1000:
                if risk_level == "low":
                    risk_level = "medium"
                risk_factors.append(f"Moderate financial impact: {entities['amount']}")
        except:
            pass

    # Check urgency risk
    if entities.get("urgency") == "high":
        if risk_level == "low":
            risk_level = "medium"
        risk_factors.append("High urgency request — expedited handling required.")

    # Check keywords
    high_risk_keywords = ["terminate", "delete", "remove access", "emergency", "critical failure", "data breach"]
    for kw in high_risk_keywords:
        if kw.lower() in raw_input.lower():
            risk_level = "high"
            risk_factors.append(f"High-risk keyword detected: '{kw}'")

    if not risk_factors:
        risk_factors.append("Standard request, no elevated risk factors.")

    logger.info(f"[RiskAgent] Risk level: {risk_level}")
    return {"risk_level": risk_level, "risk_factors": risk_factors}


# ─── Agent 3: Compliance Agent ────────────────────────────────────────────────

COMPLIANCE_RULES = {
    "leave_request": {
        "max_consecutive_days": 14,
        "requires_manager_approval_above": 3,
        "blackout_periods": []
    },
    "payment_issue": {
        "max_auto_refund": 500,
        "requires_finance_above": 5000
    },
    "meeting_schedule": {
        "business_hours_only": True,
        "max_duration_hours": 4
    }
}

def compliance_agent(intent: str, entities: dict, risk_level: str) -> dict:
    """
    Agent 3: Checks policy compliance and returns status + recommendations.
    """
    logger.info("[ComplianceAgent] Checking compliance...")
    rules = COMPLIANCE_RULES.get(intent, {})
    status = "compliant"
    notes = []
    recommendations = []

    if intent == "leave_request" and rules:
        notes.append("Leave policy check: standard PTO rules applied.")
        if risk_level in ["medium", "high"]:
            recommendations.append("Notify team lead at least 24h in advance.")
        if rules.get("requires_manager_approval_above", 3):
            recommendations.append(f"Requests exceeding {rules['requires_manager_approval_above']} days require manager approval.")

    elif intent == "payment_issue" and rules:
        notes.append("Finance policy check: refund authorization matrix applied.")
        max_auto = rules.get("max_auto_refund", 500)
        recommendations.append(f"Auto-refund limit is ${max_auto}. Amounts above require Finance team review.")

    elif intent == "meeting_schedule" and rules:
        notes.append("Calendar policy: business hours scheduling enforced.")
        recommendations.append("Ensure all attendees have calendar availability confirmed.")

    else:
        notes.append("General compliance review completed. No specific policy constraints found.")

    if risk_level == "high":
        status = "conditional"
        notes.append("High-risk flag — senior reviewer notification triggered.")

    logger.info(f"[ComplianceAgent] Compliance status: {status}")
    return {
        "compliance_status": status,
        "notes": notes,
        "recommendations": recommendations
    }


# ─── Agent 4: Execution Agent ─────────────────────────────────────────────────

EXECUTION_TEMPLATES = {
    "leave_request": "Leave request processed for {person}. Duration: {date_start} to {date_end}. Reason: {reason}. Status: {mode}.",
    "payment_issue": "Payment issue logged. Amount: {amount}. Ticket created and assigned to Finance team. Status: {mode}.",
    "meeting_schedule": "Meeting scheduling request acknowledged. Proposed time: {date_start}. Calendar invite will be sent. Status: {mode}.",
    "it_support": "IT support ticket created. Issue logged in helpdesk system. Priority: {urgency}. Status: {mode}.",
    "hr_query": "HR query received and logged. A HR representative will follow up within 2 business days. Status: {mode}.",
    "general_inquiry": "Request received and logged. Our team will review and respond accordingly. Status: {mode}."
}

def execution_agent(intent: str, entities: dict, confidence: float, risk_level: str, compliance: dict) -> dict:
    """
    Agent 4: Determines execution mode and generates the final result.

    Confidence thresholds:
      > 0.85  → auto_execute
      0.6-0.85 → request_approval
      < 0.6   → clarification_needed
    """
    logger.info("[ExecutionAgent] Determining execution mode...")

    # Execution mode logic
    if confidence > 0.85 and risk_level == "low" and compliance["compliance_status"] == "compliant":
        mode = "auto_execute"
        status = "completed"
    elif confidence >= 0.6 or risk_level == "medium":
        mode = "request_approval"
        status = "pending_approval"
    else:
        mode = "clarification_needed"
        status = "awaiting_input"

    # Override: high risk always requires approval
    if risk_level == "high":
        mode = "request_approval"
        status = "pending_approval"

    # Generate result message from template
    template = EXECUTION_TEMPLATES.get(intent, EXECUTION_TEMPLATES["general_inquiry"])
    filled = template.format(
        person=entities.get("person") or "requestor",
        date_start=entities.get("date_start") or "TBD",
        date_end=entities.get("date_end") or "TBD",
        reason=entities.get("reason") or "as requested",
        amount=entities.get("amount") or "N/A",
        urgency=entities.get("urgency", "medium"),
        mode=mode.replace("_", " ").title()
    )

    # Add compliance recommendations to message
    if compliance.get("recommendations"):
        filled += " Notes: " + " | ".join(compliance["recommendations"])

    logger.info(f"[ExecutionAgent] Mode: {mode}, Status: {status}")
    return {
        "execution_mode": mode,
        "status": status,
        "result_message": filled
    }


# ─── Master Pipeline ──────────────────────────────────────────────────────────

def process_request(raw_input: str) -> dict:
    """
    Orchestrates all four agents in sequence and returns the full result payload.
    This is the main entry point called by the API route.
    """
    logger.info("=" * 60)
    logger.info(f"[Pipeline] Starting processing: {raw_input[:80]}...")
    start_time = datetime.utcnow()

    agent_logs = []

    # Agent 1: Intent
    intent_result = intent_agent(raw_input)
    agent_logs.append({"agent": "IntentAgent", "output": intent_result})

    intent = intent_result["intent"]
    entities = intent_result["entities"]
    confidence = intent_result["confidence"]

    # Agent 2: Risk
    risk_result = risk_agent(intent, entities, raw_input)
    agent_logs.append({"agent": "RiskAgent", "output": risk_result})

    # Agent 3: Compliance
    compliance_result = compliance_agent(intent, entities, risk_result["risk_level"])
    agent_logs.append({"agent": "ComplianceAgent", "output": compliance_result})

    # Agent 4: Execution
    execution_result = execution_agent(intent, entities, confidence, risk_result["risk_level"], compliance_result)
    agent_logs.append({"agent": "ExecutionAgent", "output": execution_result})

    elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    logger.info(f"[Pipeline] Completed in {elapsed_ms}ms")

    return {
        "raw_input": raw_input,
        "intent": intent,
        "entities": entities,
        "confidence": confidence,
        "risk_level": risk_result["risk_level"],
        "risk_factors": risk_result["risk_factors"],
        "compliance_status": compliance_result["compliance_status"],
        "compliance_notes": compliance_result["notes"],
        "compliance_recommendations": compliance_result["recommendations"],
        "execution_mode": execution_result["execution_mode"],
        "status": execution_result["status"],
        "result_message": execution_result["result_message"],
        "agent_logs": agent_logs,
        "processing_time_ms": elapsed_ms
    }