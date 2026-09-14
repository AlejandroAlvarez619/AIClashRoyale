from src.game.game_state import GameState, BoardTroop, TowerState, Owner, Lane
from src.data_loader import load_data, YOLO_TO_CSV
from src.troop import Troop
import time


class GameStateBuilder:
    def __init__(self, troop_identifier, cycle_tracker, elixir_tracker, timer_detector, show_logs: bool = False):
        self.identifier = troop_identifier
        self.cycle = cycle_tracker
        self.elixir = elixir_tracker
        self.timer = timer_detector
        self.show_logs = show_logs
        self._frame = 0

        df = load_data()
        self._troop_db: dict[str, Troop] = {
            row["Card"]: Troop(row)
            for _, row in df.iterrows()
        }

        self._towers = self._init_towers()

    def build(self, frame, detected_hand=None) -> GameState:
        divider_height = int(frame.shape[0] * 0.8)

        board_troops = self._build_board_troops(frame, divider_height)
        hand = self._build_player_hand_from_detection(detected_hand)
        upcoming = self._get_upcoming_card()

        remaining = self._get_time_remaining()
        state = GameState(
            board_troops=board_troops,
            towers=self._towers,
            hand=hand,
            upcoming_card=upcoming,
            player_elixir=float(self.elixir.get_int()),
            time_remaining=remaining,
            is_double_elixir=remaining <= 60,
            frame_id=self._frame,
        )

        if self.show_logs:
            print("\n--- Built GameState Troops ---")
            for troop_data in state.board_troops:
                print(
                    f"{troop_data.troop.card} | owner={troop_data.owner.value} | "
                    f"x={troop_data.x:.2f} y={troop_data.y:.2f} lane={troop_data.lane.value}"
                )
            print("------------------------------")

        self._frame += 1
        return state

    def _build_player_hand_from_detection(self, detected_hand) -> list:
        if not detected_hand:
            return self.cycle.get_hand()

        hand = [None, None, None, None]

        for idx, yolo_name in enumerate(detected_hand[:4]):
            if yolo_name is None:
                continue

            csv_name = YOLO_TO_CSV.get(yolo_name)
            if csv_name is None:
                continue

            troop = self._troop_db.get(csv_name)
            if troop is not None:
                hand[idx] = troop

        return hand

    def update_tower_hp(self, owner: Owner, lane: Lane, hp_ratio: float):
        for tower in self._towers:
            if tower.owner == owner and tower.lane == lane:
                tower.hp_ratio = hp_ratio
                tower.is_destroyed = hp_ratio <= 0.0
                break

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_board_troops(self, frame, divider_height) -> list[BoardTroop]:
        sightings = self.identifier.get_troops_on_board(frame, divider_height)
        board_troops = []

        board_width = frame.shape[1]
        board_height = divider_height

        for sighting in sightings:
            troop = self._lookup_troop(sighting.name)
            if troop is None:
                print(f"[GameStateBuilder] Unknown label '{sighting.name}' - add to YOLO_TO_CSV")
                continue

            x_norm, y_norm = self._normalize(
                sighting.top_left,
                sighting.bottom_right,
                board_width,
                board_height,
            )

            owner = self._get_owner_from_sighting(sighting, y_norm)

            board_troops.append(BoardTroop(
                troop=troop,
                owner=owner,
                x=x_norm,
                y=y_norm,
            ))

        return board_troops

    def _lookup_troop(self, yolo_label: str):
        csv_name = YOLO_TO_CSV.get(yolo_label)
        return self._troop_db.get(csv_name) if csv_name else None

    def _normalize(
        self,
        top_left: tuple,
        bottom_right: tuple,
        board_width: int,
        board_height: int,
    ) -> tuple[float, float]:
        center_x = (float(top_left[0]) + float(bottom_right[0])) / 2.0
        center_y = (float(top_left[1]) + float(bottom_right[1])) / 2.0

        x_norm = center_x / float(board_width)
        y_norm = center_y / float(board_height)

        x_norm = max(0.0, min(1.0, x_norm))
        y_norm = max(0.0, min(1.0, y_norm))

        return round(x_norm, 3), round(y_norm, 3)

    def _get_owner_from_sighting(self, sighting, y_norm: float) -> Owner:
        geometric_owner = Owner.PLAYER if y_norm > 0.5 else Owner.OPPONENT

        raw_owner = str(getattr(sighting, "owner", "")).strip().lower()

        # Vision is strong positive signal for opponent
        if raw_owner == "opponent":
            return Owner.OPPONENT

        # If vision explicitly says player, trust it only near ambiguity zone
        if raw_owner == "player" and 0.35 <= y_norm <= 0.65:
            return Owner.PLAYER

        return geometric_owner

    def _get_upcoming_card(self):
        cycle_list = self.cycle.get_cycle()
        return cycle_list[0] if cycle_list else None

    def _init_towers(self) -> list[TowerState]:
        return [
            TowerState(Owner.PLAYER, Lane.LEFT, hp_ratio=1.0),
            TowerState(Owner.PLAYER, Lane.RIGHT, hp_ratio=1.0),
            TowerState(Owner.PLAYER, Lane.CENTER, hp_ratio=1.0),
            TowerState(Owner.OPPONENT, Lane.LEFT, hp_ratio=1.0),
            TowerState(Owner.OPPONENT, Lane.RIGHT, hp_ratio=1.0),
            TowerState(Owner.OPPONENT, Lane.CENTER, hp_ratio=1.0),
        ]

    def _get_time_remaining(self) -> float:
        if not self.elixir.battle_started:
            return 180.0
        elapsed = time.time() - self.elixir.battle_start_ts
        return max(0.0, 180.0 - elapsed)