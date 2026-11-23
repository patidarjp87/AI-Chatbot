"""Registry of the animated graphics. To add a component: create its file, import it here,
and add it to the tuple below. The scene's 'visual_type' picks the component."""
from src.video.gfx.components.base import Component
from src.video.gfx.components.information_card import InformationCard
from src.video.gfx.components.title_reveal import TitleReveal

COMPONENTS = {component.visual_type: component for component in (TitleReveal, InformationCard)}


def get_component(visual_type: str) -> type[Component]:
    if visual_type not in COMPONENTS:
        raise ValueError(f"Unknown visual_type '{visual_type}'. Available: {', '.join(COMPONENTS)}")
    return COMPONENTS[visual_type]