"""
Decision Manager: reads game state data and returns a play action
(card slot + normalized target) or none for wait.

Priority Order:
1. If an enemy swarm is in the reaction zone, wait for and use a spell.
2. If an enemy tank or mini tank is in the reaction zone, counter it.
   Preferred order:
   swarm -> ranged_dps -> mini_tank -> building
3. If idling too long, spawn a non-spell troop at a tower front or bridge.
4. In general, spawn with friendly troops to build a snowball push.

logging: set show_logs=False on DecisionManager to silence all prints.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import math

from src.game.game_state import (
    GameState as game_state_data,
    BoardTroop as board_troop_data,
    Owner as troop_owner,
    Lane as troop_lane,
)


player_side = troop_owner.PLAYER
enemy_side = troop_owner.OPPONENT
left_lane = troop_lane.LEFT
right_lane = troop_lane.RIGHT


# ---------------------------------------------------------------------------
# Public Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class play_action:
    card_slot_id: int
    target_xy_pos: tuple[float, float]
    spell_card_flag: bool = False


class card_role(Enum):
    tank_role = "tank"
    mini_tank = "mini_tank"
    ranged_dps = "ranged_dps"
    swarm_role = "swarm"
    spell_role = "spell"
    building_role = "building"
    win_condition = "win_condition"
    unknown_role = "unknown"


# ---------------------------------------------------------------------------
# Named Placement Anchors
# ---------------------------------------------------------------------------

class place_anchor:
    king_front_pos = (0.50, 0.80)
    left_tower_pos = (0.15, 0.68)
    right_tower_pos = (0.80, 0.68)
    left_bridge_pos = (0.15, 0.47)
    right_bridge_pos = (0.80, 0.47)
    middle_low_left = (.45, .65)
    middle_low_right = (.55, .65)
    behind_king_left = (.45,.95)
    behind_king_right = (.55,.95)


def get_tower_front(lane_side: troop_lane) -> tuple[float, float]:
    if lane_side == left_lane:
        return place_anchor.left_tower_pos
    if lane_side == right_lane:
        return place_anchor.right_tower_pos
    return place_anchor.king_front_pos

def get_behind_king(lane_side: troop_lane) -> tuple[float, float]:
    if lane_side == left_lane:
        return place_anchor.behind_king_left
    if lane_side == right_lane:
        return place_anchor.behind_king_left
    return place_anchor.king_front_pos


def get_bridge_pos(lane_side: troop_lane) -> tuple[float, float]:
    if lane_side == left_lane:
        return place_anchor.left_bridge_pos
    if lane_side == right_lane:
        return place_anchor.right_bridge_pos
    return (0.50, 0.55)


def get_anchor_name(target_xy_pos: tuple[float, float]) -> Optional[str]:
    for anchor_name in (
        "king_front_pos",
        "left_tower_pos",
        "right_tower_pos",
        "left_bridge_pos",
        "right_bridge_pos",
        "middle_low_left",
        "middle_low_right",
        "behind_king_left",
        "behind_king_right"
    ):
        if getattr(place_anchor, anchor_name) == target_xy_pos:
            return anchor_name
    return None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@dataclass
class game_event:
    pass


@dataclass
class new_enemy_troop(game_event):
    troop_data: board_troop_data


@dataclass
class enemy_crossed_bridge(game_event):
    troop_data: board_troop_data


@dataclass
class elixir_full_now(game_event):
    pass


@dataclass
class hand_card_changed(game_event):
    card_data: object


@dataclass
class tower_now_down(game_event):
    owner_side: troop_owner
    lane_side: troop_lane


@dataclass
class phase_now_start(game_event):
    phase_name: str


@dataclass
class idle_heartbeat(game_event):
    pass


def get_event_text(event_data: game_event) -> str:
    if isinstance(event_data, new_enemy_troop):
        troop_data = event_data.troop_data
        return (
            f"new_enemy_troop({get_card_name(troop_data)} at "
            f"x={troop_data.x:.2f}, y={troop_data.y:.2f}, lane={troop_data.lane.value})"
        )

    if isinstance(event_data, enemy_crossed_bridge):
        troop_data = event_data.troop_data
        return f"enemy_crossed_bridge({get_card_name(troop_data)} in {troop_data.lane.value})"

    if isinstance(event_data, elixir_full_now):
        return "elixir_full_now(10/10)"

    if isinstance(event_data, hand_card_changed):
        return f"hand_card_changed(new={get_card_name(event_data.card_data)})"

    if isinstance(event_data, tower_now_down):
        return f"tower_now_down({event_data.owner_side.value} {event_data.lane_side.value})"

    if isinstance(event_data, phase_now_start):
        return f"phase_now_start({event_data.phase_name})"

    if isinstance(event_data, idle_heartbeat):
        return "idle_heartbeat()"

    return event_data.__class__.__name__


# ---------------------------------------------------------------------------
# Safe Value Helpers
# ---------------------------------------------------------------------------

def get_float_num(raw_value, default_num: float = 0.0) -> float:
    if raw_value is None:
        return default_num

    if isinstance(raw_value, str):
        cleaned_value = raw_value.strip().replace(",", "")
        if cleaned_value == "" or cleaned_value.lower() == "nan":
            return default_num
        try:
            return float(cleaned_value)
        except (TypeError, ValueError):
            return default_num

    try:
        number_value = float(raw_value)
        if math.isnan(number_value):
            return default_num
        return number_value
    except (TypeError, ValueError):
        return default_num


def get_text_str(raw_value) -> str:
    return str(raw_value).strip().lower() if raw_value is not None else ""


# ---------------------------------------------------------------------------
# Card Role Helper
# ---------------------------------------------------------------------------

def get_card_role(card_data) -> card_role:
    if card_data is None:
        return card_role.unknown_role

    type_text = get_text_str(getattr(card_data, "type", None))
    if "spell" in type_text:
        return card_role.spell_role
    if "spawner" in type_text or "building" in type_text:
        return card_role.building_role

    card_cost = get_float_num(getattr(card_data, "cost", None))
    card_health = get_float_num(getattr(card_data, "health", None))
    card_damage = get_float_num(getattr(card_data, "damage", None))
    card_range = get_float_num(getattr(card_data, "range", None))
    troop_count = get_float_num(getattr(card_data, "count", None), default_num=1.0)
    tower_damage = get_float_num(getattr(card_data, "crown_tower_damage", None))

    if tower_damage > 0 and card_cost >= 3 and card_health >= 800:
        return card_role.win_condition
    if card_range >= 5:
        return card_role.ranged_dps
    if troop_count >= 3:
        return card_role.swarm_role
    if card_health >= 2000:
        return card_role.tank_role
    if 900 <= card_health < 2000 and card_cost <= 4:
        return card_role.mini_tank
    if card_damage > 0:
        return card_role.mini_tank

    return card_role.unknown_role


# ---------------------------------------------------------------------------
# Log Helpers
# ---------------------------------------------------------------------------

def show_log_line(show_logs: bool, log_tag: str, log_text: str) -> None:
    if show_logs:
        print("\n--- Decision Manager ---")
        print(f"Type: {log_tag}")
        print(f"Info: {log_text}")
        print("------------------------")
        None


def format_troop_debug(troop_data: Optional[board_troop_data]) -> str:
    if troop_data is None:
        return "none"
    return (
        f"{get_card_name(troop_data)} "
        f"(x={troop_data.x:.2f}, y={troop_data.y:.2f}, lane={troop_data.lane.value})"
    )


def show_state_snapshot(
    show_logs: bool,
    state_data: game_state_data,
    event_list: list[game_event],
) -> None:
    enemy_list = state_data.by_owner(enemy_side)
    player_list = state_data.by_owner(player_side)
    bridge_swarm = get_enemy_bridge_swarm(state_data)
    bridge_tank = get_enemy_bridge_tank(state_data)
    main_threat = get_main_threat(state_data)
    push_lane = get_friendly_push_lane(state_data)

    event_names = [event_data.__class__.__name__ for event_data in event_list]

    show_log_line(
        show_logs,
        "snapshot",
        (
            f"events={event_names} | "
            f"elixir={state_data.player_elixir:.1f} | "
            f"player_troops={len(player_list)} | "
            f"enemy_troops={len(enemy_list)} | "
            f"main_threat={format_troop_debug(main_threat)} | "
            f"bridge_swarm={format_troop_debug(bridge_swarm)} | "
            f"bridge_tank={format_troop_debug(bridge_tank)} | "
            f"push_lane={push_lane.value if push_lane else 'none'}"
        ),
    )


# ---------------------------------------------------------------------------
# Event Detector
# ---------------------------------------------------------------------------

class event_detector:
    def __init__(
        self,
        match_gap_max: float = 0.08,
        idle_time_sec: float = 6.0,
        idle_elixir_min: float = 6.0,
        show_logs: bool = False,
    ):
        self.match_gap_max = match_gap_max
        self.idle_time_sec = idle_time_sec
        self.idle_elixir_min = idle_elixir_min
        self.show_logs = show_logs
        self.last_event_time: float = 0.0

    def get_new_events(
        self,
        old_state: Optional[game_state_data],
        new_state: game_state_data,
    ) -> list[game_event]:
        event_list: list[game_event] = []

        if old_state is None:
            for troop_data in new_state.by_owner(enemy_side):
                event_list.append(new_enemy_troop(troop_data=troop_data))

            if new_state.hand:
                for card_data in new_state.hand:
                    event_list.append(hand_card_changed(card_data=card_data))

            if event_list:
                self.last_event_time = new_state.timestamp
                show_log_line(
                    self.show_logs,
                    "event",
                    f"first frame; {len(event_list)} bootstrap event(s):",
                )
                for event_data in event_list:
                    show_log_line(self.show_logs, "event", f"  - {get_event_text(event_data)}")

            return event_list

        old_enemy = old_state.by_owner(enemy_side)
        new_enemy = new_state.by_owner(enemy_side)
        used_old_ids: set[int] = set()
        troop_pair_list: list[tuple[board_troop_data, board_troop_data]] = []

        for new_troop in new_enemy:
            best_old_id = -1
            best_gap_num = math.inf

            for old_id, old_troop in enumerate(old_enemy):
                if old_id in used_old_ids:
                    continue
                if get_card_name(old_troop) != get_card_name(new_troop):
                    continue

                move_gap_num = math.hypot(old_troop.x - new_troop.x, old_troop.y - new_troop.y)
                if move_gap_num < best_gap_num and move_gap_num <= self.match_gap_max:
                    best_old_id = old_id
                    best_gap_num = move_gap_num

            if best_old_id >= 0:
                used_old_ids.add(best_old_id)
                troop_pair_list.append((old_enemy[best_old_id], new_troop))
            else:
                event_list.append(new_enemy_troop(troop_data=new_troop))

        for old_troop, new_troop in troop_pair_list:
            if old_troop.y < 0.5 <= new_troop.y:
                event_list.append(enemy_crossed_bridge(troop_data=new_troop))

        if old_state.player_elixir < 10.0 <= new_state.player_elixir:
            event_list.append(elixir_full_now())

        old_hand_names = [get_card_name(card_data) for card_data in old_state.hand]
        new_hand_names = [get_card_name(card_data) for card_data in new_state.hand]
        for slot_id, card_name in enumerate(new_hand_names):
            if slot_id >= len(old_hand_names) or old_hand_names[slot_id] != card_name:
                if card_name and slot_id < len(new_state.hand):
                    event_list.append(hand_card_changed(card_data=new_state.hand[slot_id]))

        for new_tower in new_state.towers:
            old_tower = old_state.get_tower(new_tower.owner, new_tower.lane)
            if old_tower and old_tower.hp_ratio > 0 and new_tower.hp_ratio <= 0:
                event_list.append(
                    tower_now_down(
                        owner_side=new_tower.owner,
                        lane_side=new_tower.lane,
                    )
                )

        if new_state.is_double_elixir and not old_state.is_double_elixir:
            event_list.append(phase_now_start(phase_name="double"))

        if event_list:
            self.last_event_time = new_state.timestamp
        elif (
            new_state.player_elixir >= self.idle_elixir_min
            and (new_state.timestamp - self.last_event_time) >= self.idle_time_sec
        ):
            event_list.append(idle_heartbeat())
            self.last_event_time = new_state.timestamp

        if event_list:
            show_log_line(
                self.show_logs,
                "event",
                f"{len(event_list)} event(s) this tick:",
            )
            for event_data in event_list:
                show_log_line(self.show_logs, "event", f"  - {get_event_text(event_data)}")

        return event_list


def get_card_name(card_data) -> str:
    direct_name = getattr(card_data, "card", None)
    if direct_name is not None:
        return get_text_str(direct_name)

    nested_troop = getattr(card_data, "troop", None)
    if nested_troop is not None:
        return get_text_str(getattr(nested_troop, "card", None))

    return ""


def has_idle_heartbeat(event_list: list[game_event]) -> bool:
    return any(isinstance(event_data, idle_heartbeat) for event_data in event_list)


# ---------------------------------------------------------------------------
# Shared State Helpers
# ---------------------------------------------------------------------------

def is_reaction_zone(troop_data: board_troop_data) -> bool:
    return troop_data.y >= 0.38


def is_emergency_zone(troop_data: Optional[board_troop_data]) -> bool:
    if troop_data is None:
        return False
    return troop_data.y >= 0.50


def get_enemy_reaction_troops(state_data: game_state_data) -> list[board_troop_data]:
    return [
        troop_data
        for troop_data in state_data.by_owner(enemy_side)
        if is_reaction_zone(troop_data)
    ]


def get_enemy_bridge_swarm(state_data: game_state_data) -> Optional[board_troop_data]:
    enemy_list = [
        troop_data
        for troop_data in get_enemy_reaction_troops(state_data)
        if get_card_role(troop_data.troop) == card_role.swarm_role
    ]
    if not enemy_list:
        return None
    return max(enemy_list, key=lambda troop_data: troop_data.y)


def get_enemy_bridge_tank(state_data: game_state_data) -> Optional[board_troop_data]:
    enemy_list = [
        troop_data
        for troop_data in get_enemy_reaction_troops(state_data)
        if get_card_role(troop_data.troop) in (
            card_role.tank_role,
            card_role.mini_tank,
            card_role.win_condition,
        )
    ]
    if not enemy_list:
        return None
    return max(enemy_list, key=lambda troop_data: troop_data.y)


def get_bridge_swarm_cluster(
    state_data: game_state_data,
    radius_num: float = 0.10,
) -> tuple[int, Optional[tuple[float, float]]]:
    swarm_anchor = get_enemy_bridge_swarm(state_data)
    if swarm_anchor is None:
        return 0, None

    enemy_list = get_enemy_reaction_troops(state_data)
    near_list = [
        troop_data
        for troop_data in enemy_list
        if math.hypot(troop_data.x - swarm_anchor.x, troop_data.y - swarm_anchor.y) <= radius_num
    ]

    if not near_list:
        return 0, None

    center_x = sum(troop_data.x for troop_data in near_list) / len(near_list)
    center_y = sum(troop_data.y for troop_data in near_list) / len(near_list)
    return len(near_list), (center_x, center_y)


def get_main_threat(state_data: game_state_data) -> Optional[board_troop_data]:
    enemy_list = state_data.by_owner(enemy_side)
    if not enemy_list:
        return None
    return max(enemy_list, key=lambda troop_data: troop_data.y)


def get_lane_leader(
    state_data: game_state_data,
    lane_side: Optional[troop_lane] = None,
) -> Optional[board_troop_data]:
    friend_list = state_data.by_owner(player_side)
    if lane_side is not None:
        friend_list = [troop_data for troop_data in friend_list if troop_data.lane == lane_side]
    if not friend_list:
        return None
    return min(friend_list, key=lambda troop_data: troop_data.y)


def get_friendly_push_lane(state_data: game_state_data) -> Optional[troop_lane]:
    best_lane = None
    best_score = -math.inf

    for lane_side in (left_lane, right_lane):
        friend_list = [
            troop_data
            for troop_data in state_data.by_owner(player_side)
            if troop_data.lane == lane_side
        ]
        if not friend_list:
            continue

        lane_count = len(friend_list)
        front_y = min(troop_data.y for troop_data in friend_list)
        lane_score = lane_count * 10.0 - front_y

        if lane_score > best_score:
            best_score = lane_score
            best_lane = lane_side

    return best_lane


def get_idle_spawn_pos(state_data: game_state_data) -> tuple[tuple[float, float], str]:
    push_lane = get_friendly_push_lane(state_data)
    if push_lane is not None:
        leader = get_lane_leader(state_data, push_lane)
        # if leader is not None and leader.y < 0.5:
        return  get_behind_king(push_lane), f"idle bridge support in {push_lane.value}"
        # return get_tower_front(push_lane), f"idle tower support in {push_lane.value}"

    bridge_pos, lane_side = get_clear_bridge(state_data)
    return get_behind_king(lane_side), f"idle behind king in {lane_side.value}"
    # return bridge_pos, f"idle clear bridge in {lane_side.value}"


def get_clear_bridge(state_data: game_state_data) -> tuple[tuple[float, float], troop_lane]:
    left_count = len(state_data.opponent_troops_in_lane(left_lane))
    right_count = len(state_data.opponent_troops_in_lane(right_lane))

    if left_count < right_count:
        return place_anchor.left_bridge_pos, left_lane
    if right_count < left_count:
        return place_anchor.right_bridge_pos, right_lane

    left_tower = state_data.get_tower(enemy_side, left_lane)
    right_tower = state_data.get_tower(enemy_side, right_lane)
    left_hp = left_tower.hp_ratio if left_tower else 1.0
    right_hp = right_tower.hp_ratio if right_tower else 1.0

    if left_hp <= right_hp:
        return place_anchor.left_bridge_pos, left_lane
    return place_anchor.right_bridge_pos, right_lane


def should_idle_cycle(state_data: game_state_data, event_list: list[game_event]) -> bool:
    if not has_idle_heartbeat(event_list):
        return False

    enemy_count = len(state_data.by_owner(enemy_side))
    player_count = len(state_data.by_owner(player_side))
    push_lane = get_friendly_push_lane(state_data)

    if enemy_count > 0:
        return False

    if state_data.player_elixir < 6.0:
        return False

    # Do not idle-spawn if we already have a meaningful push
    if player_count >= 2:
        return False

    if push_lane is not None:
        return False

    return True

# ---------------------------------------------------------------------------
# Card Chooser
# ---------------------------------------------------------------------------

class card_chooser:
    def __init__(self, play_score_min: float = 1.0, show_logs: bool = True):
        self.play_score_min = play_score_min
        self.show_logs = show_logs

    def choose_card_slot(
        self,
        state_data: game_state_data,
        event_list: list[game_event],
    ) -> Optional[int]:
        threat_data = get_main_threat(state_data)
        enemy_board_cost = state_data.total_elixir_on_board(enemy_side)
        player_board_cost = state_data.total_elixir_on_board(player_side)
        elixir_edge_num = state_data.player_elixir - (enemy_board_cost - player_board_cost)

        show_state_snapshot(self.show_logs, state_data, event_list)

        show_log_line(
            self.show_logs,
            "choose",
            f"start choose | elixir={state_data.player_elixir:.1f} "
            f"edge={elixir_edge_num:.1f} "
            f"threat={format_troop_debug(threat_data)}",
        )

        # Priority 1: enemy swarm in reaction zone -> wait for spell
        bridge_swarm = get_enemy_bridge_swarm(state_data)
        if bridge_swarm is not None:
            show_log_line(
                self.show_logs,
                "priority_1",
                f"enemy reaction swarm detected -> {format_troop_debug(bridge_swarm)}",
            )

            best_spell_slot = None
            best_spell_cost = math.inf

            for slot_id, card_data in enumerate(state_data.hand):
                if card_data is None:
                    continue
                role_now = get_card_role(card_data)
                card_cost = get_float_num(card_data.cost)
                can_play_now = state_data.can_play(slot_id)

                show_log_line(
                    self.show_logs,
                    "priority_1",
                    f"check slot {slot_id}: {get_card_name(card_data)} "
                    f"role={role_now.value} cost={card_cost:.0f} can_play={can_play_now}",
                )

                if not can_play_now:
                    continue
                if role_now != card_role.spell_role:
                    continue

                if card_cost < best_spell_cost:
                    best_spell_cost = card_cost
                    best_spell_slot = slot_id

            if best_spell_slot is not None:
                show_log_line(
                    self.show_logs,
                    "priority_1",
                    f"selected spell slot {best_spell_slot}: "
                    f"{get_card_name(state_data.hand[best_spell_slot])}",
                )
                return best_spell_slot

            show_log_line(
                self.show_logs,
                "priority_1",
                "no playable spell found -> wait",
            )
            return None

        # Priority 2: enemy tank in reaction zone -> counter it
        bridge_tank = get_enemy_bridge_tank(state_data)
        if bridge_tank is not None:
            show_log_line(
                self.show_logs,
                "priority_2",
                f"enemy reaction tank detected -> {format_troop_debug(bridge_tank)}",
            )

            role_order = [
                (card_role.swarm_role, "swarm"),
                (card_role.mini_tank, "mini_tank"),
                (card_role.ranged_dps, "ranged_dps"),
                (card_role.building_role, "building"),
            ]

            for target_role, target_name in role_order:
                best_counter_slot = None
                best_counter_cost = math.inf

                show_log_line(
                    self.show_logs,
                    "priority_2",
                    f"searching for counter type {target_name}",
                )

                for slot_id, card_data in enumerate(state_data.hand):
                    if card_data is None:
                        continue
                    role_now = get_card_role(card_data)
                    card_cost = get_float_num(card_data.cost)
                    can_play_now = state_data.can_play(slot_id)

                    show_log_line(
                        self.show_logs,
                        "priority_2",
                        f"check slot {slot_id}: {get_card_name(card_data)} "
                        f"role={role_now.value} cost={card_cost:.0f} can_play={can_play_now}",
                    )

                    if not can_play_now:
                        continue
                    if role_now != target_role:
                        continue

                    if card_cost < best_counter_cost:
                        best_counter_cost = card_cost
                        best_counter_slot = slot_id

                if best_counter_slot is not None:
                    show_log_line(
                        self.show_logs,
                        "priority_2",
                        f"selected {target_name} slot {best_counter_slot}: "
                        f"{get_card_name(state_data.hand[best_counter_slot])}",
                    )
                    return best_counter_slot

            show_log_line(
                self.show_logs,
                "priority_2",
                "no playable tank counter found -> wait",
            )
            return None

        # Priority 3: idle too long -> cheap non-spell troop
        if should_idle_cycle(state_data, event_list):
            show_log_line(
                self.show_logs,
                "priority_3",
                "idle cycle active -> searching for cheapest non-spell troop",
            )

            best_idle_slot = None
            best_idle_cost = math.inf

            for slot_id, card_data in enumerate(state_data.hand):
                if card_data is None:
                    continue
                role_now = get_card_role(card_data)
                card_cost = get_float_num(card_data.cost)
                can_play_now = state_data.can_play(slot_id)

                show_log_line(
                    self.show_logs,
                    "priority_3",
                    f"check slot {slot_id}: {get_card_name(card_data)} "
                    f"role={role_now.value} cost={card_cost:.0f} can_play={can_play_now}",
                )

                if not can_play_now:
                    continue
                if role_now in (card_role.spell_role, card_role.building_role):
                    continue

                if card_cost < best_idle_cost:
                    best_idle_cost = card_cost
                    best_idle_slot = slot_id

            if best_idle_slot is not None:
                show_log_line(
                    self.show_logs,
                    "priority_3",
                    f"selected idle slot {best_idle_slot}: "
                    f"{get_card_name(state_data.hand[best_idle_slot])}",
                )
                return best_idle_slot

            show_log_line(
                self.show_logs,
                "priority_3",
                "idle cycle active but no playable troop found -> wait",
            )
            return None

        # Priority 4: general snowball logic
        best_slot_id = None
        best_score_num = -math.inf
        push_lane = get_friendly_push_lane(state_data)

        show_log_line(
            self.show_logs,
            "priority_4",
            f"general snowball mode | push_lane={push_lane.value if push_lane else 'none'}",
        )

        for slot_id, card_data in enumerate(state_data.hand):
            if card_data is None:
                continue
            if not state_data.can_play(slot_id):
                show_log_line(
                    self.show_logs,
                    "priority_4",
                    f"slot {slot_id}: {get_card_name(card_data)} "
                    f"(cost {get_float_num(card_data.cost):.0f}) - cant afford",
                )
                continue

            role_now = get_card_role(card_data)

            if role_now == card_role.spell_role:
                show_log_line(
                    self.show_logs,
                    "priority_4",
                    f"slot {slot_id}: {get_card_name(card_data)} - skip blind spell",
                )
                continue

            score_num = 0.0
            reason_list: list[str] = []

            if push_lane is not None:
                score_num += 3.0
                reason_list.append("friendly_push_lane")

            if role_now == card_role.ranged_dps:
                score_num += 1.25
                reason_list.append("ranged_support")
            elif role_now == card_role.mini_tank:
                score_num += 1.75
                reason_list.append("mini_tank_support")
            elif role_now == card_role.swarm_role:
                score_num += 1.75
                reason_list.append("swarm_support")
            elif role_now == card_role.win_condition:
                score_num += 1
                reason_list.append("win_condition_push")
            elif role_now == card_role.tank_role:
                score_num += 2.0
                reason_list.append("tank_push")
            elif role_now == card_role.unknown_role:
                score_num += 1.0
                reason_list.append("unknown_follow_friendlies")
            elif role_now == card_role.building_role:
                score_num -= 1.0
                reason_list.append("building_penalty")

            if threat_data is not None and threat_data.y >= 0.35:
                if threat_data.lane in (left_lane, right_lane):
                    if role_now in (card_role.ranged_dps, card_role.mini_tank, card_role.swarm_role):
                        score_num += 3.0
                        reason_list.append(f"defend_{threat_data.lane.value}_lane")
                    if role_now in (card_role.win_condition, card_role.tank_role):
                        score_num -= 2.0
                        reason_list.append("too_slow_for_defense")

            card_cost = get_float_num(card_data.cost)
            score_num -= 0.10 * card_cost
            reason_list.append(f"cost_penalty={0.10 * card_cost:.2f}")

            show_log_line(
                self.show_logs,
                "priority_4",
                f"slot {slot_id}: {get_card_name(card_data)} role={role_now.value} "
                f"score={score_num:+.2f} reasons={reason_list}",
            )

            if score_num > best_score_num:
                best_score_num = score_num
                best_slot_id = slot_id

        if best_slot_id is None:
            show_log_line(self.show_logs, "priority_4", "no playable cards -> wait")
            return None
        
        # makes AI wait instead of playing low-value cards, can be adjusted or removed as needed, 
        # basically waits until it has a somewhat decent play instead of throwing away elixir for small score boosts
        if best_score_num < self.play_score_min:
            show_log_line(
            self.show_logs,
            "priority_4",
            f"best score {best_score_num:+.2f} below minimum {self.play_score_min:.2f} -> wait",
        )
            return None

        show_log_line(
            self.show_logs,
            "priority_4",
            f"selected slot {best_slot_id}: {get_card_name(state_data.hand[best_slot_id])} "
            f"score={best_score_num:+.2f}",
        )
        return best_slot_id


# ---------------------------------------------------------------------------
# Placer
# ---------------------------------------------------------------------------

class card_placer:
    def __init__(self, show_logs: bool = True):
        self.show_logs = show_logs

    def get_drop_point(
        self,
        card_data,
        state_data: game_state_data,
    ) -> Optional[tuple[float, float]]:
        role_now = get_card_role(card_data)

        if role_now == card_role.spell_role:
            result = self.get_spell_drop(state_data, card_data)
            if result is None:
                return None
            drop_pos, drop_note = result
        elif role_now == card_role.building_role:
            drop_pos, drop_note = self.get_building_drop(state_data)
        elif role_now == card_role.swarm_role:
            drop_pos, drop_note = self.get_swarm_drop(state_data)
        elif role_now == card_role.ranged_dps:
            drop_pos, drop_note = self.get_ranged_drop(state_data)
        elif role_now == card_role.tank_role:
            drop_pos, drop_note = self.get_tank_drop(state_data)
        elif role_now == card_role.win_condition:
            drop_pos, drop_note = self.get_win_drop(state_data)
        elif role_now == card_role.mini_tank:
            drop_pos, drop_note = self.get_mini_drop(state_data)
        else:
            drop_pos, drop_note = self.get_unknown_drop(state_data)

        anchor_name = get_anchor_name(drop_pos)
        anchor_text = f" anchor={anchor_name}" if anchor_name else ""

        show_log_line(
            self.show_logs,
            "place",
            f"{get_card_name(card_data)} role={role_now.value} -> "
            f"target=({drop_pos[0]:.2f}, {drop_pos[1]:.2f}){anchor_text} "
            f"[{drop_note}]",
        )
        return drop_pos

    def get_tank_drop(self, state_data: game_state_data) -> tuple[tuple[float, float], str]:
        threat_data = get_main_threat(state_data)

        if is_emergency_zone(threat_data) and threat_data is not None and threat_data.lane in (left_lane, right_lane):
            return get_tower_front(threat_data.lane), f"tank emergency defend {threat_data.lane.value}"

        friend_lane = get_friendly_push_lane(state_data)
        if friend_lane is not None:
            leader = get_lane_leader(state_data, friend_lane)
            if leader is not None and leader.y < 0.5:
                return get_bridge_pos(friend_lane), f"tank snowballing {friend_lane.value} bridge"
            return get_tower_front(friend_lane), f"tank supporting {friend_lane.value} tower"

        if threat_data is not None and threat_data.lane in (left_lane, right_lane) and threat_data.y >= 0.35:
            return get_tower_front(threat_data.lane), f"tank defend {threat_data.lane.value}"

        bridge_pos, lane_side = get_clear_bridge(state_data)
        return get_behind_king(lane_side), f"tank behind king in {lane_side.value}"
        return bridge_pos, f"tank default clear bridge in {lane_side.value}"

    def get_win_drop(self, state_data: game_state_data) -> tuple[tuple[float, float], str]:
        friend_lane = get_friendly_push_lane(state_data)
        if friend_lane is not None:
            return get_bridge_pos(friend_lane), f"win condition snowballing {friend_lane.value} bridge"

        threat_data = get_main_threat(state_data)
        if is_emergency_zone(threat_data) and threat_data is not None and threat_data.lane in (left_lane, right_lane):
            return get_tower_front(threat_data.lane), f"win condition emergency defend {threat_data.lane.value}"

        bridge_pos, lane_side = get_clear_bridge(state_data)
        return get_behind_king(lane_side), f"win condition behind king in {lane_side.value}"
        return bridge_pos, f"win condition at open {lane_side.value} bridge"

    def get_ranged_drop(self, state_data: game_state_data) -> tuple[tuple[float, float], str]:
        threat_data = get_main_threat(state_data)
        friend_lane = get_friendly_push_lane(state_data)

        if is_emergency_zone(threat_data) and threat_data is not None and threat_data.lane in (left_lane, right_lane):
            mid_pos = place_anchor.middle_low_left if threat_data.lane == left_lane else place_anchor.middle_low_right
            return mid_pos, f"ranged dps emergency defending from middle vs {threat_data.lane.value}"

        if friend_lane is not None:
            leader = get_lane_leader(state_data, friend_lane)
            if leader is not None and leader.y < 0.5:
                return get_bridge_pos(friend_lane), f"ranged dps snowballing {friend_lane.value} bridge"
            mid_pos = place_anchor.middle_low_left if friend_lane == left_lane else place_anchor.middle_low_right
            return mid_pos, f"ranged dps holding middle supporting {friend_lane.value} push"

        if threat_data is not None and threat_data.lane in (left_lane, right_lane) and threat_data.y >= 0.35:
            mid_pos = place_anchor.middle_low_left if threat_data.lane == left_lane else place_anchor.middle_low_right
            return mid_pos, f"ranged dps defending from middle vs {threat_data.lane.value}"

        bridge_pos, lane_side = get_clear_bridge(state_data)
        return get_behind_king(lane_side), f"ranged dps holding behind king in {lane_side.value}"
        # return bridge_pos, f"ranged dps default clear bridge in {lane_side.value}"

    def get_swarm_drop(self, state_data: game_state_data) -> tuple[tuple[float, float], str]:
        bridge_tank = get_enemy_bridge_tank(state_data)
        if bridge_tank is not None and bridge_tank.lane in (left_lane, right_lane):
            return (
                get_tower_front(bridge_tank.lane),
                f"swarm defending {bridge_tank.lane.value} vs {get_card_name(bridge_tank)}",
            )

        threat_data = get_main_threat(state_data)
        if is_emergency_zone(threat_data) and threat_data is not None and threat_data.lane in (left_lane, right_lane):
            return get_tower_front(threat_data.lane), f"swarm emergency defending {threat_data.lane.value}"

        friend_lane = get_friendly_push_lane(state_data)
        if friend_lane is not None:
            leader = get_lane_leader(state_data, friend_lane)
            if leader is not None and leader.y < 0.5:
                return get_bridge_pos(friend_lane), f"swarm snowballing {friend_lane.value} bridge"
            return get_tower_front(friend_lane), f"swarm supporting {friend_lane.value} tower"

        if threat_data is not None and threat_data.lane in (left_lane, right_lane) and threat_data.y >= 0.35:
            return get_tower_front(threat_data.lane), f"swarm defending active {threat_data.lane.value} lane"

        bridge_pos, lane_side = get_clear_bridge(state_data)
        return bridge_pos, f"swarm attack at open {lane_side.value} bridge"

    def get_mini_drop(self, state_data: game_state_data) -> tuple[tuple[float, float], str]:
        threat_data = get_main_threat(state_data)
        friend_lane = get_friendly_push_lane(state_data)

        if is_emergency_zone(threat_data) and threat_data is not None and threat_data.lane in (left_lane, right_lane):
            return get_tower_front(threat_data.lane), f"mini tank emergency defending {threat_data.lane.value}"

        if friend_lane is not None:
            leader = get_lane_leader(state_data, friend_lane)
            if leader is not None and leader.y < 0.5:
                return get_bridge_pos(friend_lane), f"mini tank snowballing {friend_lane.value} bridge"
            return get_tower_front(friend_lane), f"mini tank supporting {friend_lane.value} tower"

        if threat_data is not None and threat_data.lane in (left_lane, right_lane) and threat_data.y >= 0.35:
            return get_tower_front(threat_data.lane), f"mini tank defending {threat_data.lane.value}"

        bridge_tank = get_enemy_bridge_tank(state_data)
        if bridge_tank is not None and bridge_tank.lane in (left_lane, right_lane):
            return get_tower_front(bridge_tank.lane), f"mini tank defending {bridge_tank.lane.value}"

        bridge_pos, lane_side = get_clear_bridge(state_data)
        return get_behind_king(lane_side), f"mini tank behind king in {lane_side.value}"
        return bridge_pos, f"mini tank default clear bridge in {lane_side.value}"

    def get_building_drop(self, state_data: game_state_data) -> tuple[tuple[float, float], str]:
        threat_data = get_main_threat(state_data)
        if threat_data is not None and threat_data.lane in (left_lane, right_lane):
            return get_tower_front(threat_data.lane), f"building pull toward {threat_data.lane.value}"
        return place_anchor.king_front_pos, "building in front of king tower"

    def get_unknown_drop(self, state_data: game_state_data) -> tuple[tuple[float, float], str]:
        threat_data = get_main_threat(state_data)
        friend_lane = get_friendly_push_lane(state_data)

        if is_emergency_zone(threat_data) and threat_data is not None and threat_data.lane in (left_lane, right_lane):
            return get_tower_front(threat_data.lane), f"unknown emergency defending {threat_data.lane.value}"

        if friend_lane is not None:
            leader = get_lane_leader(state_data, friend_lane)
            if leader is not None and leader.y < 0.5:
                return get_bridge_pos(friend_lane), f"unknown joining {friend_lane.value} bridge push"
            return get_tower_front(friend_lane), f"unknown joining {friend_lane.value} tower support"

        if threat_data is not None and threat_data.lane in (left_lane, right_lane) and threat_data.y >= 0.35:
            return get_tower_front(threat_data.lane), f"unknown defending {threat_data.lane.value}"

        bridge_pos, lane_side = get_clear_bridge(state_data)
        return bridge_pos, f"unknown default clear bridge in {lane_side.value}"

    def get_spell_drop(self, state_data: game_state_data, card_data) -> Optional[tuple[tuple[float, float], str]]:
        # Added adaptive spell for cluster size

        # Determines spell type 
        role_now = get_card_role(card_data)
        if role_now != card_role.spell_role:
            return None
        spell_cost = get_float_num(card_data.cost)

        cluster_size, cluster_pos = get_bridge_swarm_cluster(state_data)

        # If no cluster skip
        if cluster_pos is None:
            return None
        
        # Adaptive spell logic based on cluster size and spell cost
        if spell_cost <= 2.0:
            min_cluster = 2
        elif spell_cost <= 3.0:
            min_cluster = 3
        else:
            min_cluster = 4
        
        '''if cluster_size >= 2 and cluster_pos is not None:
            return cluster_pos, f"spell on enemy swarm cluster of {cluster_size}"
        '''

        # Avoid wasting spells if friendly troops already counter the swarm
        friendly_nearby = any(
            troop.owner == player_side and abs(troop.y - cluster_pos[1]) < 0.10
            for troop in state_data.by_owner(player_side)
        )

        if friendly_nearby and cluster_size < (min_cluster + 1):
            return None

        # Double elixir: slightly more aggressive
        if state_data.is_double_elixir:
            min_cluster -= 1

        # Final decision
        if cluster_size >= min_cluster:
            return cluster_pos, f"adaptive spell on cluster size {cluster_size} (min={min_cluster})"

        '''
        bridge_swarm = get_enemy_bridge_swarm(state_data)
        if bridge_swarm is not None:
            return (bridge_swarm.x, bridge_swarm.y), f"spell on single enemy {get_card_name(bridge_swarm)}"

        return (0.50, 0.50), "ERROR: spell requested with no valid enemy target"
        '''
        return None


# ---------------------------------------------------------------------------
# Main Manager
# ---------------------------------------------------------------------------

class DecisionManager:
    def __init__(
        self,
        card_picker: Optional[card_chooser] = None,
        card_dropper: Optional[card_placer] = None,
        event_reader: Optional[event_detector] = None,
        cooldown_time_sec: float = 0.5,
        show_logs: bool = True,
    ):
        self.show_logs = show_logs
        self.card_picker = card_picker or card_chooser(show_logs=show_logs)
        self.card_dropper = card_dropper or card_placer(show_logs=show_logs)
        self.event_reader = event_reader or event_detector(show_logs=show_logs)
        self.cooldown_time_sec = cooldown_time_sec
        self.last_state_data: Optional[game_state_data] = None
        self.last_play_time: float = 0.0

    def choose_next_play(self, state_data: game_state_data) -> Optional[play_action]:
        if state_data.timestamp - self.last_play_time < self.cooldown_time_sec:
            show_log_line(
                self.show_logs,
                "wait",
                f"cooldown active ({state_data.timestamp - self.last_play_time:.2f}s / "
                f"{self.cooldown_time_sec:.2f}s)",
            )
            return None

        event_list = self.event_reader.get_new_events(self.last_state_data, state_data)
        self.last_state_data = state_data

        if not event_list:
            show_log_line(self.show_logs, "wait", "no events this tick")
            return None

        slot_id = self.card_picker.choose_card_slot(state_data, event_list)
        if slot_id is None:
            return None

        chosen_card = state_data.hand[slot_id]
        role_now = get_card_role(chosen_card)

        show_log_line(
            self.show_logs,
            "decision",
            f"chosen card={get_card_name(chosen_card)} role={role_now.value}",
        )

        if role_now == card_role.spell_role and get_enemy_bridge_swarm(state_data) is None:
            show_log_line(
                self.show_logs,
                "decision",
                "spell was selected but there is no valid enemy target -> cancel action",
            )
            return None

        if should_idle_cycle(state_data, event_list) and role_now not in (card_role.spell_role, card_role.building_role):
            drop_pos, idle_note = get_idle_spawn_pos(state_data)
            show_log_line(self.show_logs, "place", f"idle placement -> {idle_note}")
        else:
            result = self.card_dropper.get_drop_point(chosen_card, state_data)

            if result is None:
                return None  # skip playing entirely

            drop_pos = result

        self.last_play_time = state_data.timestamp

        action_data = play_action(
            card_slot_id=slot_id,
            target_xy_pos=drop_pos,
            spell_card_flag=(role_now == card_role.spell_role),
        )

        show_log_line(
            self.show_logs,
            "action",
            f"play slot {action_data.card_slot_id} "
            f"({get_card_name(chosen_card)}, "
            f"cost {get_float_num(getattr(chosen_card, 'cost', None)):.0f}) at "
            f"({action_data.target_xy_pos[0]:.2f}, {action_data.target_xy_pos[1]:.2f})",
        )

        return action_data
