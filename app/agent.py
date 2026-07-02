# ruff: noqa
import sys

# Fix Windows UnicodeEncodeError: Windows terminal uses cp1252 by default,
# which cannot encode emoji/Unicode characters used in output and print statements.
# Reconfigure stdout/stderr to UTF-8 before any other imports.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import re
import datetime
from typing import Any
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent
from google.adk.workflow import Workflow, START
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.tools import AgentTool
from google.genai import types
from google.adk.apps import App

# MCP Imports
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from app.config import config

# --- Rate Limit (429) Fallback: patch Gemini.generate_content_async ---
# The ADK framework catches 429 ClientError and wraps it as _ResourceExhaustedError
# BEFORE our async_request patch can intercept it. We must patch at the Gemini
# model level instead to correctly catch and handle quota exhaustion.
import asyncio
from google.adk.models.google_llm import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types

def get_mock_llm_response(llm_request) -> LlmResponse:
    """Build a rule-based LlmResponse from the request content when quota is exhausted."""
    # Extract all text from the request contents
    prompt_parts = []
    si = ""
    try:
        if llm_request.config and hasattr(llm_request.config, "system_instruction"):
            si_val = llm_request.config.system_instruction
            if si_val:
                if hasattr(si_val, "parts"):
                    si = " ".join(p.text for p in si_val.parts if hasattr(p, "text") and p.text)
                elif isinstance(si_val, str):
                    si = si_val
    except Exception:
        pass

    try:
        for content in (llm_request.contents or []):
            if hasattr(content, "parts"):
                for p in content.parts:
                    if hasattr(p, "text") and p.text:
                        prompt_parts.append(p.text)
    except Exception:
        pass

    prompt = " ".join(prompt_parts)
    prompt_lower = prompt.lower()

    # Classifier agent path
    if "Emergency Classifier Agent" in si:
        if "gas" in prompt_lower or "leak" in prompt_lower:
            text = json.dumps({"category": "GAS_LEAK", "severity": "CRITICAL"})
        elif "fire" in prompt_lower or "smoke" in prompt_lower:
            text = json.dumps({"category": "FIRE", "severity": "CRITICAL"})
        elif any(w in prompt_lower for w in ["grandmother", "unconscious", "heart", "fall", "fell", "medical", "injured", "faint"]):
            text = json.dumps({"category": "MEDICAL", "severity": "HIGH"})
        elif "spark" in prompt_lower or "electric" in prompt_lower:
            text = json.dumps({"category": "ELECTRICAL", "severity": "MEDIUM"})
        elif "alone" in prompt_lower or "child" in prompt_lower:
            text = json.dumps({"category": "CHILD_ALONE", "severity": "HIGH"})
        elif "earthquake" in prompt_lower or "shaking" in prompt_lower:
            text = json.dumps({"category": "EARTHQUAKE", "severity": "CRITICAL"})
        elif "flood" in prompt_lower or "rising water" in prompt_lower:
            text = json.dumps({"category": "FLOOD", "severity": "HIGH"})
        else:
            text = json.dumps({"category": "UNKNOWN", "severity": "LOW"})
    else:
        # Protocol / Orchestrator agent path
        if "gas" in prompt_lower or "leak" in prompt_lower or "GAS_LEAK" in prompt:
            category, severity = "GAS_LEAK", "CRITICAL"
            steps = ["Immediately evacuate the house.", "Do NOT touch any electrical switches or phones.", "Move 100m away and call 1122.", "Do NOT re-enter until declared safe."]
            warnings = ["DO NOT light matches or open flames.", "DO NOT use any electrical switches inside."]
        elif "fire" in prompt_lower or "smoke" in prompt_lower or "FIRE" in prompt:
            category, severity = "FIRE", "CRITICAL"
            steps = ["Evacuate immediately, shout 'Fire!'", "Stay low to avoid smoke.", "Check doors before opening.", "Call Fire Brigade (16) once outside."]
            warnings = ["DO NOT use elevators.", "DO NOT throw water on electrical fires."]
        elif any(w in prompt_lower for w in ["grandmother", "unconscious", "heart", "fall", "fell", "medical", "injured"]) or "MEDICAL" in prompt:
            category, severity = "MEDICAL", "HIGH"
            steps = ["Assess consciousness and breathing.", "Call Rescue 1122 immediately.", "Administer CPR if trained.", "Keep patient still and warm.", "Gather ID and medical records."]
            warnings = ["DO NOT give food/water to semi-conscious patient.", "DO NOT move patient if spinal injury suspected."]
        elif "spark" in prompt_lower or "electric" in prompt_lower or "ELECTRICAL" in prompt:
            category, severity = "ELECTRICAL", "MEDIUM"
            steps = ["Shut off the main circuit breaker.", "Do NOT touch any sparking wires.", "Use Class C extinguisher if fire starts.", "Call a certified electrician."]
            warnings = ["DO NOT use water on electrical fires.", "DO NOT touch a shocked person directly."]
        elif "earthquake" in prompt_lower or "shaking" in prompt_lower or "EARTHQUAKE" in prompt:
            category, severity = "EARTHQUAKE", "CRITICAL"
            steps = ["Drop, Cover and Hold On!", "Stay indoors away from windows.", "Move outdoors to open area if safe.", "Check for injuries after shaking stops."]
            warnings = ["DO NOT run outside during shaking.", "DO NOT use elevators."]
        elif "flood" in prompt_lower or "rising water" in prompt_lower or "FLOOD" in prompt:
            category, severity = "FLOOD", "HIGH"
            steps = ["Move to higher ground immediately.", "Avoid walking through floodwater.", "Disconnect electrical appliances.", "Monitor emergency broadcasts."]
            warnings = ["DO NOT drive through flooded roads.", "DO NOT touch wet electrical equipment."]
        else:
            category, severity = "UNKNOWN", "LOW"
            steps = ["Stay calm, assess the situation.", "Evacuate if in immediate danger.", "Call Rescue 1122 or Police 15."]
            warnings = ["DO NOT take unnecessary risks.", "DO NOT delay calling for help."]

        text = json.dumps({
            "category": category,
            "severity": severity,
            "protocol_steps": steps,
            "critical_warnings": warnings
        })

    mock_content = genai_types.Content(role="model", parts=[genai_types.Part.from_text(text=text)])
    mock_response = genai_types.GenerateContentResponse(candidates=[genai_types.Candidate(content=mock_content)])
    return LlmResponse.create(mock_response)


original_generate_content_async = Gemini.generate_content_async

async def patched_generate_content_async(self, llm_request, stream: bool = False):
    try:
        async for event in original_generate_content_async(self, llm_request, stream=stream):
            yield event
    except Exception as e:
        err_msg = str(e)
        is_quota = ("429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or
                    "_ResourceExhaustedError" in type(e).__name__ or
                    "quota" in err_msg.lower())
        if is_quota:
            print(f"⚠️ Gemini API Quota Exhausted. Switching to offline mock response...")
            yield get_mock_llm_response(llm_request)
        else:
            raise

Gemini.generate_content_async = patched_generate_content_async

# --- Security & Audit Logging ---
def log_audit(severity: str, event_type: str, details: dict):
    log_entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "severity": severity,
        "event_type": event_type,
        "details": details
    }
    try:
        log_path = "audit_log.json"
        logs = []
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                try:
                    logs = json.load(f)
                    if not isinstance(logs, list):
                        logs = []
                except Exception:
                    logs = []
        logs.append(log_entry)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Failed to write audit log: {e}")

# --- Pydantic Schemas ---
class ClassificationResult(BaseModel):
    category: str = Field(description="The category of the emergency. Must be one of: FIRE, GAS_LEAK, MEDICAL, ELECTRICAL, CHILD_ALONE, FLOOD, EARTHQUAKE, UNKNOWN")
    severity: str = Field(description="The severity of the emergency. Must be one of: CRITICAL, HIGH, MEDIUM, LOW")

class PlanResult(BaseModel):
    category: str = Field(description="Emergency category")
    severity: str = Field(description="Emergency severity level")
    protocol_steps: list[str] = Field(description="List of step-by-step emergency instructions for the family")
    critical_warnings: list[str] = Field(description="List of critical do-not-do warnings")

# --- Local Profiles Mocking (Fallback and Helper) ---
def get_mock_profile():
    profile_path = "family_profile.json"
    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "family_name": "Rahman Family",
        "city": "Karachi",
        "primary_contact_name": "Kamran Rahman (Father)",
        "primary_contact_phone": "0300-9876543",
        "nearest_hospital_name": "Aga Khan University Hospital",
        "nearest_hospital_phone": "021-111-911-911"
    }

def get_mock_emergency_numbers(city: str):
    return {
        "Rescue/Ambulance": "1122",
        "Edhi Foundation": "115",
        "Police": "15",
        "Fire Brigade": "16"
    }

def format_plan_markdown(plan: dict) -> str:
    category = plan.get("category", "UNKNOWN")
    severity = plan.get("severity", "LOW")
    steps = plan.get("protocol_steps", [])
    warnings = plan.get("critical_warnings", [])
    alert_status = plan.get("alert_sent_status", "")
    local_nums = plan.get("local_emergency_numbers", {})
    family = plan.get("family_profile", {})

    severity_color = "🔴" if severity == "CRITICAL" else "🟠" if severity == "HIGH" else "🟡" if severity == "MEDIUM" else "🟢"
    
    md = f"### {severity_color} EMERGENCY PLAN: {category} ({severity} severity)\n\n"
    
    if alert_status:
        md += f"> **Alert Status:** {alert_status}\n\n"
        
    md += "#### 📋 Step-by-Step Response Protocol:\n"
    for i, step in enumerate(steps, 1):
        md += f"{i}. {step}\n"
    md += "\n"
    
    if warnings:
        md += "#### ⚠️ CRITICAL WARNINGS (DO NOT DO):\n"
        for w in warnings:
            md += f"- **{w}**\n"
        md += "\n"
        
    md += "#### 📞 Local Emergency Numbers:\n"
    for k, v in local_nums.items():
        md += f"- **{k}**: {v}\n"
    md += "\n"
    
    if family:
        md += "#### 🏠 Family Profile & Contacts:\n"
        md += f"- **Family:** {family.get('family_name')}\n"
        md += f"- **Primary Contact:** {family.get('primary_contact_name')} ({family.get('primary_contact_phone')})\n"
        md += f"- **Nearest Hospital:** {family.get('nearest_hospital_name')} ({family.get('nearest_hospital_phone')})\n"
        
    return md

# --- MCP Toolset Initialization ---
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "app.mcp_server"],
        ),
    ),
)

# --- Specialized LLM Agents ---
emergency_classifier = LlmAgent(
    name="emergency_classifier",
    model=config.model,
    instruction="""You are the Emergency Classifier Agent.
Analyze the user's emergency situation.
Identify the category and severity of the emergency.
Output MUST strictly follow the ClassificationResult schema.""",
    output_schema=ClassificationResult,
    description="Classifies the emergency category and severity level."
)

protocol_agent = LlmAgent(
    name="protocol_agent",
    model=config.model,
    instruction="""You are the Protocol Agent.
Retrieve the correct emergency protocol for the given category and severity.
Use the MCP tools:
1. 'get_emergency_protocol' to retrieve the standard steps and warnings.
2. 'get_family_profile' to personalize instructions using primary/secondary contacts and home address.
3. 'get_local_emergency_numbers' for local contacts.
Produce the final plan matching the PlanResult schema.""",
    tools=[mcp_toolset],
    output_schema=PlanResult,
    description="Generates the personalized emergency response protocol steps and warnings."
)

orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model=config.model,
    instruction="""You are the Emergency Orchestrator for a family emergency drill system.
You MUST always follow these steps for any message describing a home emergency:
1. Call 'emergency_classifier' with the user's full situation description to get the category and severity.
2. Call 'protocol_agent' with the category and severity to retrieve response steps and warnings.
3. Call 'log_emergency_event' to log only non-PII data: profile_id='family_001', category, severity, and timestamp.
4. Return a JSON object matching this exact structure:
{"category": "<CATEGORY>", "severity": "<SEVERITY>", "protocol_steps": ["step1", "step2"], "critical_warnings": ["warning1"]}

IMPORTANT: Always respond with a valid JSON object. Never respond with plain text or questions.""",
    tools=[AgentTool(emergency_classifier), AgentTool(protocol_agent), mcp_toolset],
    output_key="emergency_plan"
)

# --- Workflow Function Nodes ---
def security_checkpoint(ctx: Context, node_input: types.Content):
    text = ""
    if hasattr(node_input, "parts") and node_input.parts:
        text = " ".join([p.text for p in node_input.parts if p.text])
    elif isinstance(node_input, str):
        text = node_input
    
    # Prompt injection check
    injection_keywords = ["ignore", "override", "forget", "jailbreak", "system prompt", "developer instructions"]
    is_injection = any(kw in text.lower() for kw in injection_keywords)
    
    if is_injection:
        log_audit("CRITICAL", "Prompt injection attempt detected", {"input": text})
        return Event(output="Security Check: Access denied due to prompt injection detection.", route="SECURITY_EVENT")
    
    # PII Scrubbing
    scrubbed_text = text
    # Pakistani format: 03xx-xxxxxxx or +92xxxxxxxxxx
    phone_pattern = r"(\+92|03)\d{2}[-\s]?\d{7}"
    scrubbed_text = re.sub(phone_pattern, "[REDACTED_PHONE]", scrubbed_text)
    
    email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
    scrubbed_text = re.sub(email_pattern, "[REDACTED_EMAIL]", scrubbed_text)
    
    emergency_keywords = [
        "fire", "gas", "smoke", "leak", "spark", "burn", "smell", "alone",
        "hurt", "bleed", "accident", "hospital", "doctor", "rescue", "ambulance",
        "drill", "emergency", "help", "scared", "earthquake", "flood", "shock", "electric",
        "medical", "unconscious", "fell", "fallen", "fall", "stroke", "heart", "choke", "breathing", "breath", "faint"
    ]
    words = [w.strip("?,.!") for w in text.lower().split() if len(w) > 3]
    if len(words) >= 3 and not any(kw in text.lower() for kw in emergency_keywords):
        log_audit("WARNING", "Off-topic query blocked", {"input": text})
        return Event(output="Security Check: This assistant is strictly for home emergency drills. Please describe an emergency situation (e.g. fire, gas leak, medical event).", route="SECURITY_EVENT")

    log_audit("INFO", "Input processed by security checkpoint", {"original": text, "scrubbed": scrubbed_text})
    
    ctx.state["scrubbed_input"] = scrubbed_text
    return Event(output=scrubbed_text, route="__DEFAULT__")

def security_event_handler(ctx: Context, node_input: Any):
    # Coerce Content or any non-str to a plain string
    if hasattr(node_input, "parts") and node_input.parts:
        text = " ".join([p.text for p in node_input.parts if p.text])
    elif isinstance(node_input, str):
        text = node_input
    else:
        text = str(node_input)
    yield Event(
        content=types.Content(
            role='model',
            parts=[types.Part.from_text(text=f"⚠️ {text}")]
        )
    )
    yield Event(output=text)

async def safety_advisor(ctx: Context, node_input: Any):
    # Get the plan from state (output_key stored it there)
    plan_raw = ctx.state.get("emergency_plan") or node_input
    
    # Coerce to dict — orchestrator stores JSON string or dict
    if isinstance(plan_raw, str):
        try:
            plan_raw = json.loads(plan_raw)
        except Exception:
            plan_raw = {}
    if not isinstance(plan_raw, dict):
        plan_raw = {}
    
    node_input = plan_raw
    category = node_input.get("category", "UNKNOWN")
    severity = node_input.get("severity", "LOW")
    
    log_audit("INFO", "Plan generated by orchestrator", {"category": category, "severity": severity})
    
    ctx.state["category"] = category
    ctx.state["severity"] = severity

    # HITL Step for High/Critical severity
    if severity in ["CRITICAL", "HIGH"]:
        if "alert_confirm" not in (ctx.resume_inputs or {}):
            log_audit("WARNING", "HITL Alert Confirmation Prompted", {"severity": severity})
            yield RequestInput(
                interrupt_id="alert_confirm",
                message="⚠️ [CRITICAL ALERT] Would you like me to send a simulated emergency SMS/alert to your primary family contact? (yes/no)"
            )
            return
        
        confirm_reply = ctx.resume_inputs.get("alert_confirm", "no").strip().lower()
        log_audit("INFO", "HITL Alert Confirmation Response Received", {"response": confirm_reply})
        
        if "yes" in confirm_reply:
            node_input["alert_sent_status"] = "✅ Simulated SMS Alert sent to your primary family contact!"
        else:
            node_input["alert_sent_status"] = "❌ Simulated SMS Alert cancelled by user."
            
    # Add local emergency numbers
    profile_data = get_mock_profile()
    city = profile_data.get("city", "Karachi")
    local_numbers = get_mock_emergency_numbers(city)
    
    node_input["local_emergency_numbers"] = local_numbers
    node_input["family_profile"] = {
        "family_name": profile_data.get("family_name", ""),
        "primary_contact_name": profile_data.get("primary_contact_name", ""),
        "primary_contact_phone": profile_data.get("primary_contact_phone", ""),
        "nearest_hospital_name": profile_data.get("nearest_hospital_name", ""),
        "nearest_hospital_phone": profile_data.get("nearest_hospital_phone", "")
    }

    # Render final output to Web UI
    yield Event(
        content=types.Content(
            role='model',
            parts=[types.Part.from_text(text=format_plan_markdown(node_input))]
        )
    )
    yield Event(output=node_input)

def logger_node(ctx: Context, node_input: Any):
    log_audit("INFO", "Emergency workflow execution finished", {"status": "SUCCESS"})
    return node_input

# --- Graph Workflow ---
root_agent = Workflow(
    name="emergency_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {"SECURITY_EVENT": security_event_handler, "__DEFAULT__": orchestrator_agent}),
        (orchestrator_agent, safety_advisor),
        (safety_advisor, logger_node),
        (security_event_handler, logger_node)
    ]
)

app = App(
    name="app",
    root_agent=root_agent,
)
