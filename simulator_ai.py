from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, is_dataclass
from typing import Any

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_FALLBACK_MODELS = ("gemini-2.5-flash-lite",)


def _secret(name: str) -> str:
    import streamlit as st

    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, KeyError):
        value = ""
    return str(value or os.getenv(name, "")).strip()


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def topology_context(devices: dict, links: list, selected_device: str) -> str:
    selected = devices.get(selected_device)
    payload = {
        "selected_device": selected_device,
        "selected_device_state": _json_safe(selected) if selected else None,
        "device_names_and_types": {
            name: getattr(device, "device_type", "Unknown")
            for name, device in devices.items()
        },
        "links": _json_safe(links),
    }
    return json.dumps(payload, indent=2)[:24000]


def generate_command_guidance(
    request: str,
    devices: dict,
    links: list,
    selected_device: str,
    previous_answer: str = "",
) -> str:
    from google import genai

    api_key = _secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add it to Streamlit Secrets "
            "or your local .env file."
        )

    model = _secret("GEMINI_MODEL") or DEFAULT_MODEL
    configured_fallbacks = _secret("GEMINI_FALLBACK_MODELS")
    fallback_models = tuple(
        item.strip()
        for item in configured_fallbacks.split(",")
        if item.strip()
    ) or DEFAULT_FALLBACK_MODELS
    models = tuple(dict.fromkeys((model, *fallback_models)))
    context = topology_context(devices, links, selected_device)
    prompt = f"""
You are PeerNet AI Command Assistant inside PeerNet Network Simulator.
Generate only commands supported by this simulator's Cisco-style console.
Use the supplied device names, interfaces, IP addresses and topology state.
Never invent an interface that is not present. Never execute commands.
If required information is missing, state exactly what the user must provide.
Avoid destructive commands unless the user explicitly requests them.

Format the answer with these headings:
Summary
Commands
Explanation
Verification

Put executable commands in one fenced text code block. Do not include CLI
prompts such as R1# in the code block. Keep commands ordered for the selected
device. If other devices require configuration, use a separate clearly
labelled code block for each device.

Selected device: {selected_device}
Current simulator context:
{context}

User request:
{request.strip()}

Previous assistant answer, if this is a follow-up:
{previous_answer[-12000:] if previous_answer else "No previous answer."}
""".strip()

    client = genai.Client(api_key=api_key)
    last_error: Exception | None = None

    for model_name in models:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if not response.text:
                    raise RuntimeError("Gemini returned an empty response.")
                return response.text
            except Exception as error:
                last_error = error
                message = str(error).upper()
                temporary = any(
                    marker in message
                    for marker in (
                        "503",
                        "UNAVAILABLE",
                        "HIGH DEMAND",
                        "INTERNAL",
                        "DEADLINE_EXCEEDED",
                    )
                )
                if not temporary:
                    raise
                if attempt == 0:
                    time.sleep(1.2)

    raise RuntimeError(
        "Gemini is temporarily busy after retrying the configured models. "
        "Please try again shortly."
    ) from last_error


def extract_commands(answer: str) -> list[str]:
    blocks = re.findall(r"```(?:text|shell|bash|ios|cisco)?\s*\n(.*?)```", answer, re.S | re.I)
    commands: list[str] = []
    for block in blocks:
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", "!", "//")):
                continue
            line = re.sub(r"^[A-Za-z0-9_.-]+(?:\([^)]*\))?[>#]\s*", "", line)
            if line and line not in commands:
                commands.append(line)
    return commands
