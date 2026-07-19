"""Skill handlers for Pi-puck swarm agents."""

from .go_charge import go_charge

SKILL_HANDLERS = {
    "goCharge": go_charge,
}


def get_skill_handler(skill_name: str):
    return SKILL_HANDLERS.get(skill_name)
