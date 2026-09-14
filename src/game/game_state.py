from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time

from src.constants import InputField, INPUT_SIZE


class Owner(Enum):
    PLAYER   = "player"
    OPPONENT = "opponent"


class Lane(Enum):
    LEFT   = "left"
    RIGHT  = "right"
    CENTER = "center"

class Depth(Enum):
    DEFENSIVE_BACK = "back near own king tower"  
    DEFENSIVE = "forward on own side" 
    RIVER = "near river/bridges"
    OFFENSIVE = "forward on opponent side"
    OFFENSIVE_BACK = "back near opponent king tower"

def infer_depth(y_norm: float) -> Depth:
    if y_norm < 0.2:
        return Depth.OFFENSIVE_BACK
    elif y_norm < 0.4:
        return Depth.OFFENSIVE
    elif y_norm < 0.6:
        return Depth.RIVER
    elif y_norm < 0.8:
        return Depth.DEFENSIVE
    else:
        return Depth.DEFENSIVE_BACK

def infer_lane(x_norm: float) -> Lane:
    if x_norm < 0.35:
        return Lane.LEFT
    elif x_norm > 0.65:
        return Lane.RIGHT
    return Lane.CENTER


@dataclass
class TowerState:
    owner:        Owner
    lane:         Lane
    hp_ratio:     float = 1.0   # 0.0–1.0, stub at 1.0 until tower HP detection is ready
    is_destroyed: bool  = False


@dataclass
class BoardTroop:
    """
    Wraps a Troop (static wiki stats from data_loader) with live CV position data.
    The decision manager only ever touches BoardTroop — never raw TroopSighting.

    Stat passthrough: board_troop.health, .damage, .cost etc. all work directly
    because __getattr__ delegates to the inner Troop object.
    """
    troop:     object  # src.troop.Troop instance
    owner:     Owner
    x:         float   # normalized 0.0–1.0 (left → right)
    y:         float   # normalized 0.0–1.0 (player side=1.0, opponent side=0.0)
    lane:      Lane    = field(init=False)
    depth:     Depth   = field(init=False)
    timestamp: float   = field(default_factory=time.time)

    def __post_init__(self):
        self.lane = infer_lane(self.x)
        self.depth = infer_depth(self.y)

    def __getattr__(self, item):
        # Delegates unknown attributes to the inner Troop so callers can do
        # board_troop.health, board_troop.damage, board_troop.cost, etc.
        return getattr(self.troop, item)

    def __repr__(self):
        return (
            f"BoardTroop({self.troop.card}, {self.owner.value}, "
            f"lane={self.lane.value}, x={self.x:.2f}, y={self.y:.2f})"
        )


# Used for decision manager to specify where to place a card on the board.
@dataclass
class PlacementSpot:
    x: float
    y: float 
    lane: Lane
    depth: Depth
    label: str 


# predefined card placement spots for the decision manager to choose from for easier model strategy
PLACEMENT_SPOTS = [
    PlacementSpot(0.25, 0.90, Lane.LEFT,   Depth.DEFENSIVE_BACK,      "left_defensive_back"),
    PlacementSpot(0.50, 0.90, Lane.CENTER, Depth.DEFENSIVE_BACK,      "center_defensive_back"),
    PlacementSpot(0.75, 0.90, Lane.RIGHT,  Depth.DEFENSIVE_BACK,      "right_defensive_back"),

    PlacementSpot(0.25, 0.72, Lane.LEFT,   Depth.DEFENSIVE, "left_defensive"),
    PlacementSpot(0.50, 0.72, Lane.CENTER, Depth.DEFENSIVE, "center_defensive"),
    PlacementSpot(0.75, 0.72, Lane.RIGHT,  Depth.DEFENSIVE, "right_defensive"),

    PlacementSpot(0.25, 0.50, Lane.LEFT,   Depth.RIVER,     "left_bridge"),
    PlacementSpot(0.75, 0.50, Lane.RIGHT,  Depth.RIVER,     "right_bridge"),

    PlacementSpot(0.25, 0.30, Lane.LEFT,   Depth.OFFENSIVE, "left_offensive"),
    PlacementSpot(0.50, 0.30, Lane.CENTER,   Depth.OFFENSIVE, "center_offensive"),
    PlacementSpot(0.75, 0.30, Lane.RIGHT,   Depth.OFFENSIVE, "right_offensive"),

    PlacementSpot(0.25, 0.10, Lane.LEFT,   Depth.OFFENSIVE_BACK, "left_offensive_back"),
    PlacementSpot(0.50, 0.10, Lane.CENTER,   Depth.OFFENSIVE_BACK, "center_offensive_back"),
    PlacementSpot(0.75, 0.10, Lane.RIGHT,   Depth.OFFENSIVE_BACK, "right_offensive_back"),
]

# Rules for whether a card can be placed in a specific depth based on type of card 

@dataclass
class CardPlacementRule:
    allowed_depths: set[Depth]
 


CARD_PLACEMENT_RULES = { 
    # allowed on any area of the board 
    "spell": CardPlacementRule(
        allowed_depths={Depth.DEFENSIVE_BACK, Depth.DEFENSIVE, Depth.RIVER, Depth.OFFENSIVE, Depth.OFFENSIVE_BACK}),

    "special": CardPlacementRule(
        allowed_depths={Depth.DEFENSIVE_BACK, Depth.DEFENSIVE, Depth.RIVER, Depth.OFFENSIVE, Depth.OFFENSIVE_BACK}),

    # allowed in only defensive areas 
    "building": CardPlacementRule(
        allowed_depths={Depth.DEFENSIVE_BACK, Depth.DEFENSIVE}),
    
    # allowed up to bridge 
    "troop": CardPlacementRule(
        allowed_depths={Depth.DEFENSIVE_BACK, Depth.DEFENSIVE, Depth.RIVER})
}


@dataclass
class GameState:
    # --- Board ---
    board_troops: list[BoardTroop] = field(default_factory=list)
    towers:       list[TowerState] = field(default_factory=list)

    # --- Hand (list of Troop objects from CycleTracker.get_hand()) ---
    hand:          list  = field(default_factory=list)  # up to 4 Troop objects
    upcoming_card: object = None                        # next Troop in cycle (optional)

    # --- Resources ---
    player_elixir:    float = 0.0
    time_remaining:   float = 180.0
    is_double_elixir: bool  = False

    # --- Meta ---
    frame_id:  int   = 0
    timestamp: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # Query helpers — for the decision manager
    # ------------------------------------------------------------------

    def by_owner(self, owner: Owner) -> list[BoardTroop]:
        return [t for t in self.board_troops if t.owner == owner]

    def by_lane(self, lane: Lane) -> list[BoardTroop]:
        return [t for t in self.board_troops if t.lane == lane]

    def is_lane_under_attack(self, lane: Lane) -> bool:
        return any(
            t.owner == Owner.OPPONENT and 
            t.lane == lane and 
            t.depth in {Depth.DEFENSIVE, Depth.DEFENSIVE_BACK}
            for t in self.board_troops
        )
    
    def is_under_attack(self) -> list[BoardTroop]:
        """True if any lane is under attack."""
        return any(
            t.owner == Owner.OPPONENT and 
            t.depth in {Depth.DEFENSIVE, Depth.DEFENSIVE_BACK}
            for t in self.board_troops
        )
    

    def opponent_troops_in_lane(self, lane: Lane) -> list[BoardTroop]:
        return [t for t in self.by_lane(lane) if t.owner == Owner.OPPONENT]

    def total_elixir_on_board(self, owner: Owner) -> float:
        """Sum of elixir costs of all troops currently on board for a given owner."""
        return sum(t.troop.cost or 0 for t in self.by_owner(owner))

    def get_tower(self, owner: Owner, lane: Lane) -> Optional[TowerState]:
        return next(
            (t for t in self.towers if t.owner == owner and t.lane == lane),
            None
        )
    

    def card_allowed_in_depth(self, card, depth: Depth) -> bool:
        card_type = getattr(card, "card_type", None)
        rule = CARD_PLACEMENT_RULES.get(card_type)
        if rule is None:
            return True  # if we don't have specific rules for this card type, allow all placements
        return depth in rule.allowed_depths        


    def can_play(self, card_index: int) -> bool:
        if card_index >= len(self.hand):
            return False

        card = self.hand[card_index]
        if card is None:
            return False

        cost = card.cost or 0
        return self.player_elixir >= cost

    # ------------------------------------------------------------------
    # Model input vector — maps state → InputField enum (constants.py)
    # ------------------------------------------------------------------

    def to_input_vector(self) -> list[float]:
        """
        Converts this GameState into the flat float vector expected by the model.
        Indexed by InputField from constants.py.
        Call: input_tensor = torch.tensor(state.to_input_vector()).float().unsqueeze(0)
        """
        vec = [0.0] * INPUT_SIZE

        # Elixir
        vec[InputField.ELIXIR.value] = self.player_elixir / 10.0

        # Tower HPs (stubbed at 1.0 until tower HP detection is implemented)
        vec[InputField.FRIENDLY_PRINCESS_HP_LEFT.value]  = self._tower_hp(Owner.PLAYER,   Lane.LEFT)
        vec[InputField.FRIENDLY_PRINCESS_HP_RIGHT.value] = self._tower_hp(Owner.PLAYER,   Lane.RIGHT)
        vec[InputField.FRIENDLY_KING_HP.value]           = self._tower_hp(Owner.PLAYER,   Lane.CENTER)
        vec[InputField.ENEMY_PRINCESS_HP_LEFT.value]     = self._tower_hp(Owner.OPPONENT, Lane.LEFT)
        vec[InputField.ENEMY_PRINCESS_HP_RIGHT.value]    = self._tower_hp(Owner.OPPONENT, Lane.RIGHT)
        vec[InputField.ENEMY_KING_HP.value]              = self._tower_hp(Owner.OPPONENT, Lane.CENTER)

        # Cards in hand
        card_fields = [
            (InputField.CARD_IN_HAND_1_ID, InputField.CARD_IN_HAND_1_COST, InputField.CARD_IN_HAND_1_PLAYABLE),
            (InputField.CARD_IN_HAND_2_ID, InputField.CARD_IN_HAND_2_COST, InputField.CARD_IN_HAND_2_PLAYABLE),
            (InputField.CARD_IN_HAND_3_ID, InputField.CARD_IN_HAND_3_COST, InputField.CARD_IN_HAND_3_PLAYABLE),
            (InputField.CARD_IN_HAND_4_ID, InputField.CARD_IN_HAND_4_COST, InputField.CARD_IN_HAND_4_PLAYABLE),
        ]
        all_cards = list(self._troop_db().values()) if hasattr(self, '_troop_db') else []
        total_cards = max(len(all_cards), 1)

        for i, (id_f, cost_f, play_f) in enumerate(card_fields):
            if i < len(self.hand):
                card = self.hand[i]
                vec[id_f.value]   = self._card_id_normalized(card, total_cards)
                vec[cost_f.value] = (card.cost or 0) / 10.0
                vec[play_f.value] = 1.0 if self.player_elixir >= (card.cost or 0) else 0.0

        # Upcoming card
        if self.upcoming_card:
            vec[InputField.CARD_UPCOMING_ID.value]   = self._card_id_normalized(self.upcoming_card, total_cards)
            vec[InputField.CARD_UPCOMING_COST.value] = (self.upcoming_card.cost or 0) / 10.0

        # TODO: add grid fields for friendly/enemy unit positions once InputField is extended

        return vec

    def _tower_hp(self, owner: Owner, lane: Lane) -> float:
        tower = self.get_tower(owner, lane)
        return tower.hp_ratio if tower else 1.0

    def _card_id_normalized(self, card, total_cards: int) -> float:
        """
        Stable normalized card ID based on card name hash.
        Keeps the same card always mapping to the same float.
        Replace with a proper card registry ID if you build one later.
        """
        return (hash(card.card or "") % total_cards) / max(total_cards, 1)