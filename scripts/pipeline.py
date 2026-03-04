from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


TIMEZONE_ALIASES = {
    "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",
    "mst": "America/Denver",
    "mdt": "America/Denver",
    "cst": "America/Chicago",
    "cdt": "America/Chicago",
    "est": "America/New_York",
    "edt": "America/New_York",
    "ist": "Asia/Kolkata",
    "utc": "UTC",
    "gmt": "UTC",
}

DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_TO_FULL = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}

SERVICE_KEYWORDS = {
    "sprinkler": "sprinkler service",
    "fire alarm": "fire alarm service",
    "alarm": "alarm systems",
    "extinguisher": "fire extinguisher service",
    "electrical": "electrical service",
    "hvac": "hvac service",
    "inspection": "inspections",
    "maintenance": "facility maintenance",
    "monitoring": "monitoring",
}

ROLE_KEYWORDS = [
    "dispatch",
    "on-call technician",
    "on-call manager",
    "phone tree",
    "service manager",
    "after-hours line",
    "operator",
    "office",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "account"


def sanitize_account_stem(stem: str) -> str:
    cleaned = re.sub(r"(?:^|[-_])(demo|onboarding|call|transcript|recording)(?:[-_]|$)", "-", stem, flags=re.I)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or stem


def stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def unique_keep_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        norm = item.strip()
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def split_sentences(text: str) -> List[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [normalize_spaces(c) for c in chunks if normalize_spaces(c)]


def first_match(patterns: Iterable[str], text: str, flags: int = re.I) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return normalize_spaces(match.group(1))
    return ""


def get_nested_value(data: Dict[str, Any], keys: Iterable[str]) -> Any:
    if not isinstance(data, dict):
        return None
    lowered = {str(k).lower(): k for k in data.keys()}
    for key in keys:
        lk = key.lower()
        if lk in lowered:
            return data[lowered[lk]]
    for value in data.values():
        if isinstance(value, dict):
            nested = get_nested_value(value, keys)
            if nested is not None:
                return nested
    return None


def load_source(path: Path) -> Dict[str, Any]:
    ext = path.suffix.lower()
    structured: Dict[str, Any] = {}
    transcript_text = ""
    raw_text = read_text_file(path)

    if ext == ".json":
        try:
            structured = json.loads(raw_text)
        except json.JSONDecodeError:
            structured = {}
            transcript_text = raw_text
        transcript_val = get_nested_value(structured, ["transcript", "text", "conversation"])
        if isinstance(transcript_val, str):
            transcript_text = transcript_val
    else:
        transcript_text = raw_text

    account_id_value = get_nested_value(structured, ["account_id", "accountId", "account"])
    if isinstance(account_id_value, str) and account_id_value.strip():
        account_id = slugify(account_id_value)
    else:
        base = sanitize_account_stem(path.stem)
        account_id = slugify(base)
        if account_id == "account":
            account_id = f"account-{stable_hash(path.name)}"

    return {
        "path": str(path),
        "file_name": path.name,
        "account_id": account_id,
        "structured": structured,
        "text": transcript_text,
    }


def detect_company_name(text: str, structured: Dict[str, Any]) -> str:
    structured_name = get_nested_value(structured, ["company_name", "company", "business_name", "client_name"])
    if isinstance(structured_name, str) and structured_name.strip():
        return normalize_spaces(structured_name)

    patterns = [
        r"(?:company|business|client)\s*name\s*[:\-]\s*([A-Za-z0-9&.,' \-]{3,})",
        r"this is\s+[A-Za-z0-9&.,' \-]{2,}\s+from\s+([A-Za-z0-9&.,' \-]{3,})",
        r"we are\s+([A-Za-z0-9&.,' \-]{3,})",
        r"we're\s+([A-Za-z0-9&.,' \-]{3,})",
        r"this is\s+([A-Za-z0-9&.,' \-]{3,})\s+from\s+[A-Za-z0-9&.,' \-]{2,}",
        r"([A-Za-z0-9&.,' \-]{3,})\s+is\s+calling",
        r"welcome to\s+([A-Za-z0-9&.,' \-]{3,})",
    ]
    candidate = first_match(patterns, text)
    return candidate.rstrip(" .,-")


def detect_timezone(text: str, structured: Dict[str, Any]) -> str:
    structured_tz = get_nested_value(structured, ["timezone", "time_zone", "tz"])
    if isinstance(structured_tz, str) and structured_tz.strip():
        return normalize_spaces(structured_tz)

    lowered = text.lower()
    for abbr, zone in TIMEZONE_ALIASES.items():
        if re.search(rf"\b{re.escape(abbr)}\b", lowered):
            return zone
    return ""


def to_day_short(day_token: str) -> str:
    token = day_token.strip().lower()
    if token.startswith("mon"):
        return "mon"
    if token.startswith("tu"):
        return "tue"
    if token.startswith("wed"):
        return "wed"
    if token.startswith("th"):
        return "thu"
    if token.startswith("fri"):
        return "fri"
    if token.startswith("sat"):
        return "sat"
    if token.startswith("sun"):
        return "sun"
    return ""


def sort_days(days: List[str]) -> List[str]:
    short_days = [to_day_short(d) for d in days]
    normalized = [d for d in short_days if d in DAY_ORDER]
    unique = []
    seen = set()
    for day in normalized:
        if day in seen:
            continue
        seen.add(day)
        unique.append(day)
    return [DAY_TO_FULL[d] for d in DAY_ORDER if d in unique]


def normalize_day_tokens(day_text: str) -> List[str]:
    lowered = day_text.lower()
    if "24/7" in lowered or "24x7" in lowered:
        return [DAY_TO_FULL[d] for d in DAY_ORDER]
    if "weekdays" in lowered:
        return [DAY_TO_FULL[d] for d in ["mon", "tue", "wed", "thu", "fri"]]
    if "weekends" in lowered:
        return [DAY_TO_FULL[d] for d in ["sat", "sun"]]

    found: List[str] = []
    for short, full in DAY_TO_FULL.items():
        if re.search(rf"\b{short}(?:day)?\b", lowered):
            found.append(short)

    day_pattern = r"(?:mon(?:day)?|tue(?:sday)?|tues|wed(?:nesday)?|thu(?:rsday)?|thur|thurs|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
    range_match = re.search(rf"({day_pattern})\s*(?:-|to|through)\s*({day_pattern})", lowered)
    if range_match:
        start, end = to_day_short(range_match.group(1)), to_day_short(range_match.group(2))
        if start and end:
            si = DAY_ORDER.index(start)
            ei = DAY_ORDER.index(end)
            if si <= ei:
                ordered = DAY_ORDER[si : ei + 1]
            else:
                ordered = DAY_ORDER[si:] + DAY_ORDER[: ei + 1]
            found.extend(ordered)

    return sort_days([DAY_TO_FULL[s] for s in found if s in DAY_TO_FULL])


def normalize_time_token(token: str) -> str:
    raw = normalize_spaces(token).lower()
    raw = raw.replace(".", "")
    if re.fullmatch(r"\d{1,2}:\d{2}", raw):
        parts = raw.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    if re.fullmatch(r"\d{1,2}", raw):
        hour = int(raw)
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", raw)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or "0")
        meridiem = match.group(3)
        hour = hour % 12
        if meridiem == "pm":
            hour += 12
        return f"{hour:02d}:{minute:02d}"
    return ""


def detect_business_hours(text: str, structured: Dict[str, Any]) -> Dict[str, Any]:
    structured_hours = get_nested_value(structured, ["business_hours", "office_hours"])
    if isinstance(structured_hours, dict):
        days = structured_hours.get("days") or []
        if isinstance(days, str):
            days = normalize_day_tokens(days)
        elif isinstance(days, list):
            days = sort_days([str(d) for d in days])
        start = structured_hours.get("start", "")
        end = structured_hours.get("end", "")
        timezone_value = structured_hours.get("timezone", "") or detect_timezone(text, structured)
        return {
            "days": days if isinstance(days, list) else [],
            "start": normalize_time_token(str(start)) if start else "",
            "end": normalize_time_token(str(end)) if end else "",
            "timezone": normalize_spaces(str(timezone_value)) if timezone_value else "",
        }

    lowered = text.lower()
    if "24/7" in lowered or "24x7" in lowered:
        return {
            "days": [DAY_TO_FULL[d] for d in DAY_ORDER],
            "start": "00:00",
            "end": "23:59",
            "timezone": detect_timezone(text, structured),
        }

    time_pattern = r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b\d{1,2}:\d{2}\b"
    for sentence in split_sentences(text):
        lowered = sentence.lower()
        if not any(
            token in lowered
            for token in [
                "business hours",
                "office hours",
                "weekday",
                "weekdays",
                "weekends",
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
                "mon-fri",
            ]
        ):
            continue

        times = re.findall(time_pattern, sentence, re.I)
        if len(times) < 2:
            continue
        days = normalize_day_tokens(sentence)
        if not days:
            continue
        start = normalize_time_token(times[0])
        end = normalize_time_token(times[1])
        if start and end:
            return {"days": days, "start": start, "end": end, "timezone": detect_timezone(text, structured)}

    return {"days": [], "start": "", "end": "", "timezone": detect_timezone(text, structured)}

def detect_address(text: str, structured: Dict[str, Any]) -> str:
    structured_address = get_nested_value(structured, ["office_address", "address"])
    if isinstance(structured_address, str) and structured_address.strip():
        return normalize_spaces(structured_address)

    address_patterns = [
        r"(\d{2,6}\s+[A-Za-z0-9.\- ]+\s(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Boulevard|Blvd|Lane|Ln|Way|Court|Ct)\b[^,\n]*,\s*[A-Za-z .]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
        r"address\s+is\s+([^\n]{8,120})",
        r"(?:address|office)\s*[:\-]\s*([^\n]{8,120})",
    ]
    return first_match(address_patterns, text)


def detect_services(text: str, structured: Dict[str, Any]) -> List[str]:
    services: List[str] = []
    structured_services = get_nested_value(structured, ["services_supported", "services"])
    if isinstance(structured_services, list):
        services.extend([normalize_spaces(str(s)) for s in structured_services if str(s).strip()])
    elif isinstance(structured_services, str):
        services.extend([normalize_spaces(s) for s in re.split(r",|/|;", structured_services) if normalize_spaces(s)])

    lowered = text.lower()
    for keyword, label in SERVICE_KEYWORDS.items():
        if keyword in lowered:
            services.append(label)
    return unique_keep_order(services)


def detect_emergency_definition(text: str, structured: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    structured_emergency = get_nested_value(structured, ["emergency_definition", "emergency_triggers"])
    if isinstance(structured_emergency, list):
        items.extend([normalize_spaces(str(s)) for s in structured_emergency if str(s).strip()])
    elif isinstance(structured_emergency, str):
        items.extend([normalize_spaces(s) for s in re.split(r",|;|\n", structured_emergency) if normalize_spaces(s)])

    for sentence in split_sentences(text):
        lowered = sentence.lower()
        if ("non-emergency" in lowered or "non emergency" in lowered) and "emergency means" not in lowered:
            continue
        if "emergency" in lowered:
            items.append(sentence)
            continue
        if any(trigger in lowered for trigger in ["sprinkler leak", "alarm triggered", "fire panel", "water flow", "smoke", "active fire"]):
            items.append(sentence)
    return unique_keep_order(items)


def extract_phone_numbers(text: str) -> List[str]:
    pattern = r"(?:\+?1[\s\-.]?)?(?:\(\d{3}\)|\d{3})[\s\-.]\d{3}[\s\-.]\d{4}"
    numbers = re.findall(pattern, text)
    cleaned = [normalize_spaces(n) for n in numbers]
    return unique_keep_order(cleaned)


def detect_fallback_sentence(text: str) -> str:
    for sentence in split_sentences(text):
        lowered = sentence.lower()
        if "transfer fails" in lowered or "if no answer" in lowered or "fallback" in lowered:
            return sentence
    return ""


def detect_routing_rules(text: str, structured: Dict[str, Any], emergency: bool) -> Dict[str, Any]:
    key_prefix = "emergency" if emergency else "non_emergency"
    structured_rules = get_nested_value(structured, [f"{key_prefix}_routing_rules", f"{key_prefix}_routing"])
    if isinstance(structured_rules, dict):
        who = structured_rules.get("who_to_call") or structured_rules.get("contacts") or []
        if isinstance(who, str):
            who = [who]
        order = structured_rules.get("order") or who
        if isinstance(order, str):
            order = [order]
        fallback = structured_rules.get("fallback", "")
        return {
            "who_to_call": [normalize_spaces(str(v)) for v in who if str(v).strip()],
            "order": [normalize_spaces(str(v)) for v in order if str(v).strip()],
            "fallback": normalize_spaces(str(fallback)) if fallback else "",
        }

    relevant: List[str] = []
    for sentence in split_sentences(text):
        lowered = sentence.lower()
        has_route_verb = any(word in lowered for word in ["route", "transfer", "call", "dispatch", "send"])
        if not has_route_verb:
            continue
        if "non-emergency" in lowered or "non emergency" in lowered:
            if emergency:
                continue
        if emergency and ("emergency" in lowered or "urgent" in lowered):
            relevant.append(sentence)
        if not emergency and ("non-emergency" in lowered or "non emergency" in lowered or "after hours" in lowered or "during business hours" in lowered):
            relevant.append(sentence)

    contacts: List[str] = []
    for sentence in relevant:
        contacts.extend(extract_phone_numbers(sentence))
        lowered = sentence.lower()
        for role in ROLE_KEYWORDS:
            if role in lowered:
                contacts.append(role)

    fallback = detect_fallback_sentence(" ".join(relevant)) or detect_fallback_sentence(text)
    contacts = unique_keep_order(contacts)
    return {"who_to_call": contacts, "order": contacts, "fallback": fallback}


def detect_call_transfer_rules(text: str, structured: Dict[str, Any]) -> Dict[str, Any]:
    structured_rules = get_nested_value(structured, ["call_transfer_rules", "transfer_rules"])
    if isinstance(structured_rules, dict):
        timeout = structured_rules.get("timeout_seconds")
        retries = structured_rules.get("retries")
        fail_phrase = structured_rules.get("what_to_say_if_fails") or structured_rules.get("failure_message") or ""
        return {
            "timeout_seconds": int(timeout) if isinstance(timeout, int) or (isinstance(timeout, str) and timeout.isdigit()) else None,
            "retries": int(retries) if isinstance(retries, int) or (isinstance(retries, str) and retries.isdigit()) else None,
            "what_to_say_if_fails": normalize_spaces(str(fail_phrase)) if fail_phrase else "",
        }

    timeout_match = re.search(r"(\d{1,3})\s*(?:seconds|second|sec)\b", text, re.I)
    retries_match = re.search(r"(\d+)\s*(?:retry|retries|attempts)\b", text, re.I)
    timeout = int(timeout_match.group(1)) if timeout_match else None
    retries = int(retries_match.group(1)) if retries_match else None
    fail_phrase = detect_fallback_sentence(text)
    return {"timeout_seconds": timeout, "retries": retries, "what_to_say_if_fails": fail_phrase}


def detect_integration_constraints(text: str, structured: Dict[str, Any]) -> List[str]:
    constraints: List[str] = []
    structured_constraints = get_nested_value(structured, ["integration_constraints", "constraints"])
    if isinstance(structured_constraints, list):
        constraints.extend([normalize_spaces(str(v)) for v in structured_constraints if str(v).strip()])
    elif isinstance(structured_constraints, str):
        constraints.extend([normalize_spaces(v) for v in re.split(r";|\n", structured_constraints) if normalize_spaces(v)])

    for sentence in split_sentences(text):
        lowered = sentence.lower()
        if "servicetrade" in lowered:
            constraints.append(sentence)
            continue
        if ("integration" in lowered or "api" in lowered) and any(
            token in lowered for token in ["never", "do not", "must not", "cannot", "can't"]
        ):
            constraints.append(sentence)
    return unique_keep_order(constraints)


def summarize_office_hours_flow(memo: Dict[str, Any]) -> str:
    route = ", ".join(memo["non_emergency_routing_rules"]["who_to_call"]) or "configured non-emergency route"
    timeout = memo["call_transfer_rules"]["timeout_seconds"]
    timeout_phrase = f"{timeout} seconds" if isinstance(timeout, int) else "configured timeout"
    return (
        "Greet the caller, ask the purpose, collect name and callback number, route or transfer based on the request, "
        f"follow fallback messaging if transfer fails after {timeout_phrase}, ask if anything else is needed, and close the call. "
        f"Primary office-hours route: {route}."
    )


def summarize_after_hours_flow(memo: Dict[str, Any]) -> str:
    emergency_route = ", ".join(memo["emergency_routing_rules"]["who_to_call"]) or "configured emergency route"
    return (
        "Greet the caller, ask purpose, confirm if emergency, collect name, number, and address immediately for emergencies, "
        "attempt transfer, use fallback apology and follow-up assurance if transfer fails, collect non-emergency details for next business day follow-up, "
        "ask if anything else is needed, and close the call. "
        f"Emergency route: {emergency_route}."
    )


def build_unknowns(memo: Dict[str, Any]) -> List[str]:
    unknowns: List[str] = []

    if is_empty(memo.get("company_name")):
        unknowns.append("Confirm company_name.")

    business_hours = memo.get("business_hours", {})
    if is_empty(business_hours.get("days")) or is_empty(business_hours.get("start")) or is_empty(business_hours.get("end")):
        unknowns.append("Confirm complete business_hours (days/start/end).")
    if is_empty(business_hours.get("timezone")):
        unknowns.append("Confirm business_hours.timezone.")

    if is_empty(memo.get("services_supported")):
        unknowns.append("Confirm services_supported list.")

    if is_empty(memo.get("office_address")):
        unknowns.append("Confirm office_address.")

    if is_empty(memo.get("emergency_definition")):
        unknowns.append("Confirm emergency_definition triggers.")

    emergency_rules = memo.get("emergency_routing_rules", {})
    if is_empty(emergency_rules.get("who_to_call")):
        unknowns.append("Confirm emergency_routing_rules.who_to_call and order.")

    transfer = memo.get("call_transfer_rules", {})
    if transfer.get("timeout_seconds") is None:
        unknowns.append("Confirm call_transfer_rules.timeout_seconds.")
    if transfer.get("retries") is None:
        unknowns.append("Confirm call_transfer_rules.retries.")

    return unique_keep_order(unknowns)


def extract_account_memo(source: Dict[str, Any], stage: str) -> Dict[str, Any]:
    text = source["text"]
    structured = source["structured"]

    company_name = detect_company_name(text, structured)
    business_hours = detect_business_hours(text, structured)
    office_address = detect_address(text, structured)
    services_supported = detect_services(text, structured)
    emergency_definition = detect_emergency_definition(text, structured)
    emergency_routing = detect_routing_rules(text, structured, emergency=True)
    non_emergency_routing = detect_routing_rules(text, structured, emergency=False)
    transfer_rules = detect_call_transfer_rules(text, structured)
    integration_constraints = detect_integration_constraints(text, structured)

    memo: Dict[str, Any] = {
        "account_id": source["account_id"],
        "company_name": company_name,
        "business_hours": business_hours,
        "office_address": office_address,
        "services_supported": services_supported,
        "emergency_definition": emergency_definition,
        "emergency_routing_rules": emergency_routing,
        "non_emergency_routing_rules": non_emergency_routing,
        "call_transfer_rules": transfer_rules,
        "integration_constraints": integration_constraints,
        "after_hours_flow_summary": "",
        "office_hours_flow_summary": "",
        "questions_or_unknowns": [],
        "notes": (
            f"Generated from {stage} input ({source['file_name']}). "
            "Only explicitly detected values were captured."
        ),
    }

    memo["office_hours_flow_summary"] = summarize_office_hours_flow(memo)
    memo["after_hours_flow_summary"] = summarize_after_hours_flow(memo)
    memo["questions_or_unknowns"] = build_unknowns(memo)
    return memo


def default_memo(account_id: str) -> Dict[str, Any]:
    memo = {
        "account_id": account_id,
        "company_name": "",
        "business_hours": {"days": [], "start": "", "end": "", "timezone": ""},
        "office_address": "",
        "services_supported": [],
        "emergency_definition": [],
        "emergency_routing_rules": {"who_to_call": [], "order": [], "fallback": ""},
        "non_emergency_routing_rules": {"who_to_call": [], "order": [], "fallback": ""},
        "call_transfer_rules": {"timeout_seconds": None, "retries": None, "what_to_say_if_fails": ""},
        "integration_constraints": [],
        "after_hours_flow_summary": "",
        "office_hours_flow_summary": "",
        "questions_or_unknowns": [],
        "notes": "Empty baseline memo.",
    }
    memo["office_hours_flow_summary"] = summarize_office_hours_flow(memo)
    memo["after_hours_flow_summary"] = summarize_after_hours_flow(memo)
    memo["questions_or_unknowns"] = build_unknowns(memo)
    return memo


def deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged: Dict[str, Any] = {}
        for key in set(base.keys()) | set(patch.keys()):
            if key in base and key in patch:
                merged[key] = deep_merge(base[key], patch[key])
            elif key in patch:
                merged[key] = patch[key]
            else:
                merged[key] = base[key]
        return merged

    if isinstance(base, list) and isinstance(patch, list):
        if is_empty(patch):
            return base
        return patch

    if is_empty(patch):
        return base
    return patch


def merge_demo_and_onboarding(v1_memo: Dict[str, Any], onboarding_memo: Dict[str, Any], source_file: str) -> Dict[str, Any]:
    merged = deep_merge(v1_memo, onboarding_memo)
    merged["account_id"] = v1_memo["account_id"]
    merged["office_hours_flow_summary"] = summarize_office_hours_flow(merged)
    merged["after_hours_flow_summary"] = summarize_after_hours_flow(merged)
    merged["questions_or_unknowns"] = build_unknowns(merged)
    merged["notes"] = (
        f"v2 merged from onboarding input ({source_file}) over existing v1 values. "
        "Onboarding values override v1 where explicitly present."
    )
    return merged

def build_agent_prompt(memo: Dict[str, Any], version: str) -> str:
    business_days = ", ".join(memo["business_hours"]["days"]) or "not provided"
    start = memo["business_hours"]["start"] or "not provided"
    end = memo["business_hours"]["end"] or "not provided"
    timezone_value = memo["business_hours"]["timezone"] or "not provided"
    address = memo["office_address"] or "not provided"
    emergency_route = ", ".join(memo["emergency_routing_rules"]["order"]) or "not provided"
    non_emergency_route = ", ".join(memo["non_emergency_routing_rules"]["order"]) or "not provided"
    timeout = memo["call_transfer_rules"]["timeout_seconds"]
    retries = memo["call_transfer_rules"]["retries"]
    fallback_line = memo["call_transfer_rules"]["what_to_say_if_fails"] or (
        "Apologize, confirm callback details, and assure prompt follow-up."
    )

    prompt = f"""
You are Clara Answers for account {memo["account_id"]}. This is configuration version {version}.
Company name: {memo["company_name"] or "Unknown"}.
Office address: {address}.
Business hours: {business_days}, {start} to {end}, timezone {timezone_value}.
Services supported: {", ".join(memo["services_supported"]) or "not provided"}.
Emergency definition: {", ".join(memo["emergency_definition"]) or "not provided"}.

Core rules:
- Keep calls concise and calm.
- Do not mention internal tools, automations, or function calls.
- Only collect information needed for routing and dispatch.
- If data is missing, ask one focused clarification question.

Business-hours flow:
1. Greet caller.
2. Ask purpose of the call.
3. Collect caller name and callback number.
4. Route or transfer using non-emergency routing: {non_emergency_route}.
5. If transfer fails, apply fallback protocol.
6. Confirm next steps.
7. Ask if the caller needs anything else.
8. Close the call professionally.

After-hours flow:
1. Greet caller.
2. Ask purpose.
3. Confirm whether this is an emergency.
4. If emergency, immediately collect caller name, callback number, and incident address.
5. Attempt transfer using emergency routing: {emergency_route}.
6. If transfer fails, apologize and assure fast follow-up.
7. If non-emergency, collect concise details and promise follow-up during business hours.
8. Ask if the caller needs anything else.
9. Close the call professionally.

Transfer protocol:
- Timeout: {timeout if timeout is not None else "not provided"} seconds.
- Retries: {retries if retries is not None else "not provided"}.
- Failure script: {fallback_line}
""".strip()
    return prompt


def build_agent_spec(memo: Dict[str, Any], version: str) -> Dict[str, Any]:
    timeout = memo["call_transfer_rules"]["timeout_seconds"]
    retries = memo["call_transfer_rules"]["retries"]
    fallback_message = memo["call_transfer_rules"]["what_to_say_if_fails"] or (
        "Apologize for transfer failure, confirm callback details, and assure quick follow-up."
    )
    return {
        "agent_name": f"clara-{memo['account_id']}-{version}",
        "voice_style": "professional, calm, concise",
        "system_prompt": build_agent_prompt(memo, version=version),
        "key_variables": {
            "timezone": memo["business_hours"]["timezone"],
            "business_hours": memo["business_hours"],
            "office_address": memo["office_address"],
            "emergency_routing": memo["emergency_routing_rules"],
            "non_emergency_routing": memo["non_emergency_routing_rules"],
        },
        "tool_invocation_placeholders": [
            {"name": "check_business_hours", "purpose": "Determine if caller is within office hours."},
            {"name": "transfer_call", "purpose": "Transfer call to configured route."},
            {"name": "create_callback_ticket", "purpose": "Create follow-up callback task when transfer fails."},
        ],
        "call_transfer_protocol": {
            "timeout_seconds": timeout,
            "retries": retries,
            "route_priority": memo["emergency_routing_rules"]["order"],
        },
        "fallback_protocol_if_transfer_fails": {
            "message": fallback_message,
            "collect": ["caller_name", "callback_number", "incident_address_if_emergency", "short_issue_summary"],
            "next_step": "notify_dispatch_and_create_callback_ticket",
        },
        "version": version,
    }


def flatten_for_diff(value: Any, prefix: str = "") -> Dict[str, Any]:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, val in value.items():
            path = f"{prefix}.{key}" if prefix else key
            out.update(flatten_for_diff(val, path))
        return out
    if isinstance(value, list):
        return {prefix: value}
    return {prefix: value}


def diff_objects(old: Dict[str, Any], new: Dict[str, Any], section: str) -> List[Dict[str, Any]]:
    old_map = flatten_for_diff(old)
    new_map = flatten_for_diff(new)
    paths = sorted(set(old_map.keys()) | set(new_map.keys()))
    changes: List[Dict[str, Any]] = []
    for path in paths:
        old_val = old_map.get(path, None)
        new_val = new_map.get(path, None)
        if old_val == new_val:
            continue
        if old_val is None and new_val is not None:
            reason = "Added from onboarding input."
        elif old_val is not None and new_val is None:
            reason = "Cleared by onboarding input."
        else:
            reason = "Updated from onboarding input."
        changes.append(
            {
                "section": section,
                "field_path": path,
                "old_value": old_val,
                "new_value": new_val,
                "reason": reason,
            }
        )
    return changes


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def upsert_task(tracker_file: Path, task: Dict[str, Any]) -> None:
    tracker_file.parent.mkdir(parents=True, exist_ok=True)
    existing: Dict[str, Any] = {"tasks": []}
    if tracker_file.exists():
        try:
            existing = read_json(tracker_file)
        except json.JSONDecodeError:
            existing = {"tasks": []}
    if "tasks" not in existing or not isinstance(existing["tasks"], list):
        existing["tasks"] = []

    replaced = False
    for idx, current in enumerate(existing["tasks"]):
        if current.get("task_id") == task.get("task_id"):
            existing["tasks"][idx] = task
            replaced = True
            break
    if not replaced:
        existing["tasks"].append(task)
    write_json(tracker_file, existing)

def process_demo_file(source_path: Path, output_root: Path, tracker_file: Path) -> Dict[str, Any]:
    source = load_source(source_path)
    memo = extract_account_memo(source, stage="demo")
    spec = build_agent_spec(memo, version="v1")

    account_dir = output_root / source["account_id"]
    v1_dir = account_dir / "v1"
    write_json(v1_dir / "account_memo.json", memo)
    write_json(v1_dir / "retell_agent_spec.json", spec)

    existing_manifest_path = account_dir / "manifest.json"
    if existing_manifest_path.exists():
        manifest = read_json(existing_manifest_path)
    else:
        manifest = {"account_id": source["account_id"], "latest_version": "v1", "versions": {}}
    manifest["latest_version"] = "v1"
    manifest.setdefault("versions", {})
    manifest["versions"]["v1"] = {
        "source_file": source["file_name"],
        "memo_path": str(v1_dir / "account_memo.json"),
        "agent_spec_path": str(v1_dir / "retell_agent_spec.json"),
        "generated_at": utc_now_iso(),
    }
    write_json(existing_manifest_path, manifest)

    task = {
        "task_id": f"{source['account_id']}-v1-review",
        "account_id": source["account_id"],
        "stage": "demo",
        "status": "generated",
        "artifact_paths": [str(v1_dir / "account_memo.json"), str(v1_dir / "retell_agent_spec.json")],
        "updated_at": utc_now_iso(),
    }
    upsert_task(tracker_file, task)

    return {
        "account_id": source["account_id"],
        "version": "v1",
        "source_file": source["file_name"],
        "memo_path": str(v1_dir / "account_memo.json"),
        "agent_spec_path": str(v1_dir / "retell_agent_spec.json"),
    }


def process_onboarding_file(source_path: Path, output_root: Path, tracker_file: Path) -> Dict[str, Any]:
    source = load_source(source_path)
    account_dir = output_root / source["account_id"]
    v1_dir = account_dir / "v1"
    v2_dir = account_dir / "v2"

    if (v1_dir / "account_memo.json").exists():
        v1_memo = read_json(v1_dir / "account_memo.json")
    else:
        v1_memo = default_memo(source["account_id"])
        write_json(v1_dir / "account_memo.json", v1_memo)
        write_json(v1_dir / "retell_agent_spec.json", build_agent_spec(v1_memo, version="v1"))

    v1_spec = read_json(v1_dir / "retell_agent_spec.json")
    onboarding_memo = extract_account_memo(source, stage="onboarding")
    v2_memo = merge_demo_and_onboarding(v1_memo, onboarding_memo, source["file_name"])
    v2_spec = build_agent_spec(v2_memo, version="v2")

    write_json(v2_dir / "account_memo.json", v2_memo)
    write_json(v2_dir / "retell_agent_spec.json", v2_spec)

    memo_changes = diff_objects(v1_memo, v2_memo, section="account_memo")
    spec_changes = diff_objects(v1_spec, v2_spec, section="retell_agent_spec")
    changes_payload = {
        "account_id": source["account_id"],
        "from_version": "v1",
        "to_version": "v2",
        "source_file": source["file_name"],
        "generated_at": utc_now_iso(),
        "changes": memo_changes + spec_changes,
    }
    write_json(account_dir / "changes.json", changes_payload)

    manifest_path = account_dir / "manifest.json"
    existing_manifest = read_json(manifest_path) if manifest_path.exists() else {"account_id": source["account_id"], "versions": {}}
    existing_manifest["latest_version"] = "v2"
    existing_manifest.setdefault("versions", {})
    existing_manifest["versions"]["v2"] = {
        "source_file": source["file_name"],
        "memo_path": str(v2_dir / "account_memo.json"),
        "agent_spec_path": str(v2_dir / "retell_agent_spec.json"),
        "changes_path": str(account_dir / "changes.json"),
        "generated_at": utc_now_iso(),
    }
    write_json(manifest_path, existing_manifest)

    task = {
        "task_id": f"{source['account_id']}-v2-review",
        "account_id": source["account_id"],
        "stage": "onboarding",
        "status": "generated",
        "artifact_paths": [str(v2_dir / "account_memo.json"), str(v2_dir / "retell_agent_spec.json"), str(account_dir / "changes.json")],
        "updated_at": utc_now_iso(),
    }
    upsert_task(tracker_file, task)

    return {
        "account_id": source["account_id"],
        "version": "v2",
        "source_file": source["file_name"],
        "memo_path": str(v2_dir / "account_memo.json"),
        "agent_spec_path": str(v2_dir / "retell_agent_spec.json"),
        "changes_path": str(account_dir / "changes.json"),
    }


def list_input_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    allowed = {".txt", ".md", ".json"}
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in allowed], key=lambda p: p.name.lower())


def run_batch(
    demo_dir: Path,
    onboarding_dir: Path,
    output_root: Path,
    tracker_file: Path,
    mode: str,
    run_log_path: Path,
) -> Dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    tracker_file.parent.mkdir(parents=True, exist_ok=True)

    demo_files = list_input_files(demo_dir)
    onboarding_files = list_input_files(onboarding_dir)
    results = {"demo": [], "onboarding": []}

    if mode in {"all", "demo"}:
        for file_path in demo_files:
            results["demo"].append(process_demo_file(file_path, output_root, tracker_file))

    if mode in {"all", "onboarding"}:
        for file_path in onboarding_files:
            results["onboarding"].append(process_onboarding_file(file_path, output_root, tracker_file))

    summary = {
        "run_at": utc_now_iso(),
        "mode": mode,
        "demo_inputs": [p.name for p in demo_files],
        "onboarding_inputs": [p.name for p in onboarding_files],
        "demo_processed": len(results["demo"]),
        "onboarding_processed": len(results["onboarding"]),
        "accounts_touched": sorted(
            unique_keep_order(
                [entry["account_id"] for entry in results["demo"]] + [entry["account_id"] for entry in results["onboarding"]]
            )
        ),
    }
    append_jsonl(run_log_path, summary)
    return {"summary": summary, "results": results}
