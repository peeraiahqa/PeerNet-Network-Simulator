from pathlib import Path
import streamlit.components.v1 as components

_FRONTEND = Path(__file__).resolve().parent / "frontend"

_component = components.declare_component(
    "peernet_topology_canvas",
    path=str(_FRONTEND),
)

def topology_canvas(
    nodes,
    edges,
    selected_device=None,
    height=560,
    key="peernet_topology",
):
    return _component(
        nodes=nodes,
        edges=edges,
        selected_device=selected_device,
        height=height,
        key=key,
        default=None,
    )
