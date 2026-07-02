import os
import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Emergency Drill Server")

# 1. Database of standard protocols
PROTOCOLS = {
    "GAS_LEAK": {
        "protocol_steps": [
            "Immediately evacuate the house. Do not stop to collect belongings.",
            "Do NOT touch any electrical switches, light switches, appliances, or phones (sparks can trigger explosion).",
            "Open doors and windows only if it doesn't delay evacuation.",
            "Move at least 100 meters away from the house before calling emergency services.",
            "Do NOT re-enter the house until professional emergency responders declare it safe."
        ],
        "critical_warnings": [
            "DO NOT light matches, use lighters, or create any open flame.",
            "DO NOT operate any switch, unplug any device, or use cell phones inside the leak area."
        ]
    },
    "CHILD_ALONE": {
        "protocol_steps": [
            "Instruct the child to stay inside, lock all doors and windows, and NOT open the door for anyone.",
            "Speak to the child in a calm, reassuring tone to minimize fear.",
            "Contact your trusted neighbor to physically check on the house.",
            "If child hears/sees an intruder, call the Police (15) immediately.",
            "Head home immediately or send a designated trusted family member."
        ],
        "critical_warnings": [
            "DO NOT instruct the child to leave the house unless there is a fire or gas leak.",
            "DO NOT show panic on the call, as the child will mimic your anxiety."
        ]
    },
    "ELECTRICAL": {
        "protocol_steps": [
            "Immediately shut off the main power/circuit breaker if safe to reach.",
            "Do NOT touch any sparking socket, wire, or appliance.",
            "Unplug other devices in the room only after turning off the main breaker.",
            "If fire starts, use a Class C dry chemical fire extinguisher.",
            "Call a certified electrician immediately."
        ],
        "critical_warnings": [
            "DO NOT use water to extinguish an electrical spark or fire (risk of electrocution).",
            "DO NOT touch a person receiving a shock directly; use a dry wooden stick to push them away."
        ]
    },
    "FIRE": {
        "protocol_steps": [
            "Evacuate immediately. Shout 'Fire!' to alert all family members.",
            "Stay low to the ground to avoid smoke inhalation.",
            "Feel doors with the back of your hand; do not open if they are hot.",
            "Once outside, call the local Fire Brigade (16).",
            "Do not return inside for pets or valuables."
        ],
        "critical_warnings": [
            "DO NOT use elevators; always take the stairs.",
            "DO NOT throw water on electrical or grease fires."
        ]
    },
    "MEDICAL": {
        "protocol_steps": [
            "Assess the patient's level of consciousness and breathing.",
            "Call Rescue (1122) immediately for an ambulance.",
            "Administer basic first aid/CPR if trained and necessary.",
            "Keep the patient calm, warm, and still.",
            "Gather the patient's ID and medical records for the ambulance crew."
        ],
        "critical_warnings": [
            "DO NOT give the patient food or water if they are semi-conscious or unconscious.",
            "DO NOT move the patient if you suspect a head, neck, or spinal injury."
        ]
    },
    "EARTHQUAKE": {
        "protocol_steps": [
            "Drop, Cover, and Hold On! Take cover under a sturdy table or desk.",
            "If indoors, stay there. Move away from glass, windows, outside doors and walls.",
            "If outdoors, move to an open area away from buildings, streetlights, and utility wires.",
            "Be prepared for aftershocks and check yourself for injuries before helping others."
        ],
        "critical_warnings": [
            "DO NOT stand in doorways or run outside while shaking is happening.",
            "DO NOT use elevators under any circumstances."
        ]
    },
    "FLOOD": {
        "protocol_steps": [
            "Move to higher ground immediately.",
            "Avoid walking, swimming, or driving through flood waters.",
            "Disconnect electrical appliances if safe to do so.",
            "Keep emergency kits ready and monitor local weather advisories."
        ],
        "critical_warnings": [
            "DO NOT walk or drive through flowing water (even 6 inches of water can sweep you away).",
            "DO NOT touch electrical equipment if you are wet or standing in water."
        ]
    }
}

@mcp.tool()
def get_emergency_protocol(category: str, severity: str) -> str:
    """Returns the step-by-step response protocol for a given emergency category and severity.

    Args:
        category: The category of emergency (e.g., FIRE, GAS_LEAK, MEDICAL, ELECTRICAL, CHILD_ALONE).
        severity: The severity level (e.g., CRITICAL, HIGH, MEDIUM, LOW).
    """
    cat = category.upper().strip()
    if cat in PROTOCOLS:
        return json.dumps(PROTOCOLS[cat])
    
    # Default fallback
    return json.dumps({
        "protocol_steps": [
            "Stay calm and assess the situation.",
            "Evacuate if there is immediate danger.",
            "Call local emergency services (Rescue 1122 or Police 15).",
            "Alert family members and move to a safe assembly point."
        ],
        "critical_warnings": [
            "DO NOT take unnecessary risks.",
            "DO NOT delay calling for professional rescue assistance."
        ]
    })

@mcp.tool()
def get_family_profile(profile_id: str) -> str:
    """Retrieves the saved family contacts, home address, and nearest hospital.

    Args:
        profile_id: The identifier for the family profile (e.g., 'default').
    """
    profile_path = "family_profile.json"
    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return json.dumps({"error": f"Failed to read profile: {e}"})
            
    # Default profile
    default_profile = {
        "family_name": "Rahman Family",
        "city": "Karachi",
        "home_address": "House 45-B, Street 3, PECHS, Karachi",
        "primary_contact_name": "Kamran Rahman (Father)",
        "primary_contact_phone": "0300-9876543",
        "secondary_contact_name": "Ayesha Rahman (Mother)",
        "secondary_contact_phone": "0333-1234567",
        "nearest_hospital_name": "Aga Khan University Hospital",
        "nearest_hospital_phone": "021-111-911-911"
    }
    return json.dumps(default_profile)

@mcp.tool()
def get_local_emergency_numbers(city: str) -> str:
    """Returns local emergency contacts (police, fire, rescue, nearest hospital) for a given city in Pakistan.

    Args:
        city: The name of the city (e.g., Karachi, Lahore, Islamabad).
    """
    city_lower = city.lower().strip()
    numbers = {
        "Rescue 1122": "1122",
        "Edhi Ambulance": "115",
        "Police": "15",
        "Fire Brigade": "16"
    }
    if "lahore" in city_lower:
        numbers["Nearest Hospital (Mayo Hospital)"] = "042-99211129"
    elif "islamabad" in city_lower:
        numbers["Nearest Hospital (PIMS)"] = "051-9261170"
    else:  # Karachi / Default
        numbers["Nearest Hospital (Aga Khan University Hospital)"] = "021-111-911-911"
        
    return json.dumps(numbers)

@mcp.tool()
def log_emergency_event(profile_id: str, category: str, severity: str, timestamp: str) -> str:
    """Logs an emergency drill event to a local JSON log file, excluding PII.

    Args:
        profile_id: The ID of the family profile.
        category: Category of the emergency.
        severity: Severity of the emergency.
        timestamp: Time of the emergency event.
    """
    log_entry = {
        "profile_id": profile_id,
        "category": category,
        "severity": severity,
        "timestamp": timestamp,
        "status": "Logged"
    }
    try:
        history_path = "emergency_history.json"
        history = []
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                try:
                    history = json.load(f)
                except Exception:
                    history = []
        history.append(log_entry)
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        return json.dumps({"status": "success", "message": "Event logged successfully"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

if __name__ == "__main__":
    mcp.run()
