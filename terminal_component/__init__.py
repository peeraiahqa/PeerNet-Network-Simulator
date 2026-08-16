from pathlib import Path
import streamlit.components.v1 as components

_FRONTEND = Path(__file__).resolve().parent / "frontend"

_terminal = components.declare_component(
    "peernet_inline_terminal",
    path=str(_FRONTEND),
)


def inline_terminal(
    history,
    prompt,
    device_name,
    prefill="",
    height=360,
    key="peernet_terminal",
):
    return _terminal(
        history=history,
        prompt=prompt,
        device_name=device_name,
        prefill=prefill,
        height=height,
        key=key,
        default=None,
    )
