"""
Created for initial simplicity of decision making 
For initial testing
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, List

from src.game.game_state import (
    GameState, BoardTroop, Owner, Lane, Depth, PlacementSpot, PLACEMENT_SPOTS, CARD_PLACEMENT_RULES
)


# Two output types:
# 1. Decision: which card to place and where to place it
# 2. Skip this play/wait

@dataclass
class Decision:
    card_index: int     # index into cards in hand (0-3)
    placement: PlacementSpot    # where to place the card

    # string representation for debugging
    def __repr__(self):
        return(
            f"Decision(card_index={self.card_index},"
            f"lane={self.placement.lane}, depth={self.placement.depth}, label={self.placement.label})"
        )


# Helpers


def valid_placement_spots(card) -> List[PlacementSpot]:
    card_type = getattr(card, "card_type", None)
    rule = CARD_PLACEMENT_RULES.get(card_type)

    if rule is None:
        # fallback: allow all spots if we don't have specific rules for this card type
        return PLACEMENT_SPOTS

    return [s for s in PLACEMENT_SPOTS if s.depth in rule.allowed_depths]

# Returns cheapest affordable card, if none available returns None
def cheapest_card_index(game_state: GameState) -> Optional[int]:
    playable = [
        i for i in range(len(game_state.hand))
        if game_state.can_play(i)
    ]
    if not playable:
        return None
    return min(playable, key=lambda i: game_state.hand[i].cost or 0)


def choose_action(state: GameState) -> Optional[Decision]:
    # check which cards are playable (can afford)
    playable = [
        i for i in range(len(state.hand))
        if state.can_play(i)
    ]

    if not playable:
        return None
    
    # sort from cheapest to most expensive card, so agent always plays cheapest card available
    playable.sort(key=lambda i: state.hand[i].cost or 0)

    # Our defensive side is under attack
    # Logic: try to play in the lane that is under attack in a defensive depth (if possible), 
    if state.is_under_attack():
        if state.is_lane_under_attack(Lane.LEFT):
            decision = legal(state, 
                                  playable, 
                                  preferred_lanes={Lane.LEFT},
                                  preferred_depths={Depth.DEFENSIVE, Depth.DEFENSIVE_BACK})
            if decision:
                return decision
        if state.is_lane_under_attack(Lane.CENTER):
            decision = legal(state, 
                                  playable, 
                                  preferred_lanes={Lane.CENTER},
                                  preferred_depths={Depth.DEFENSIVE, Depth.DEFENSIVE_BACK})
            if decision:
                return decision
        if state.is_lane_under_attack(Lane.RIGHT):
            decision = legal(state, 
                                  playable, 
                                  preferred_lanes={Lane.RIGHT},
                                  preferred_depths={Depth.DEFENSIVE, Depth.DEFENSIVE_BACK})
            if decision:
                return decision

        # fallback logic if we are under attack but can't play in that lane for some reason
        decision = legal(state, playable, preferred_depths={Depth.DEFENSIVE, Depth.DEFENSIVE_BACK})
        if decision:
            return decision
        
    # not under attack or no defensive play available
    # Logic: try to play in the most offensive spot available
    decision = legal(
        state, 
        playable, 
        preferred_lanes={Lane.LEFT, Lane.CENTER, Lane.RIGHT},
        preferred_depths={Depth.OFFENSIVE, Depth.OFFENSIVE_BACK, Depth.RIVER, Depth.DEFENSIVE, Depth.DEFENSIVE_BACK}
    )
    return decision

    
# Checks if enough elixir to play the card and if the placement is legal
def legal(state: GameState, playable: List[int], preferred_lanes: list[Lane], preferred_depths: list[Depth]) -> Optional[Decision]:
    for i in playable:
        card = state.hand[i]
        spot = placement_legal(card, preferred_lanes, preferred_depths)
        if spot:
            return Decision(card_index=i, placement=spot)
    return None

def placement_legal(card, preferred_lanes: list[Lane], preferred_depths: list[Depth]) -> Optional[PlacementSpot]:
    for spot in valid_placement_spots(card):
        if spot.lane in preferred_lanes and spot.depth in preferred_depths:
            return spot

    return None