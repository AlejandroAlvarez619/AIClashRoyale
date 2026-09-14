from src.game.vision_manager import VisionManager
from src.game.screen_manager import ScreenManager
from src.game.elixer_tracker import ElixirTracker
from src.game.timer_detection import TimerDetector
from src.models.troop_identify.troop_identifier import TroopIdentifier
from src.models.card_identify.card_identifier import CardIdentifier
from src.game.game_state_builder import GameStateBuilder
from src.game.game_state import Lane
from src.game.cycle_tracker import CycleTracker
from src.constants import PLAYER_GRID_SIZE, TOTAL_GRID_SIZE
import pyautogui
import time
import keyboard
import cv2
from src.data_loader import load_data, YOLO_TO_CSV
from src.troop import Troop
from src.game.decision_manager import DecisionManager


df = load_data()
troops = [Troop(row) for _, row in df.iterrows()]


def measure_emulator_window():
    """Lets you click-measure the Clash Royale window boundaries."""
    print("Move your mouse to the TOP-LEFT of the Clash Royale window, hold it there until captured")
    time.sleep(5)
    x1, y1 = pyautogui.position()
    print("Top-left captured:", (x1, y1))

    print("Move your mouse to the BOTTOM-RIGHT of the window, hold it there until captured")
    time.sleep(5)
    x2, y2 = pyautogui.position()
    print("Bottom-right captured:", (x2, y2))

    width = x2 - x1
    height = y2 - y1
    return (x1, y1), (width, height)


if __name__ == "__main__":
    """
    WARNING: Before you click run, know that you either have to
    bring mouse to top left corner or hit space to stop AI clicking manually.
    No time limit has been set, so it will keep clicking.
    """

    # --- Window setup ---
    clash_window_top_left, clash_window_size = measure_emulator_window()

    # --- Initializations ---
    vision_manager  = VisionManager()
    screen_manager  = ScreenManager(clash_window_top_left, clash_window_size)
    elixir_tracker  = ElixirTracker()
    timer_detector  = TimerDetector()
    troop_identifier = TroopIdentifier()
    card_identifier = CardIdentifier()
    cycle_tracker   = CycleTracker()
    game_state_builder = GameStateBuilder(troop_identifier, cycle_tracker, elixir_tracker, timer_detector)
    decision_manager = DecisionManager()

    screen_manager.print_screen_stats()
    screen_manager.start_training_camp_match()

    # -----------------------------------------------------------------------
    # Phase 1: Wait for "VS" banner — signals the match has loaded
    # -----------------------------------------------------------------------
    print("[Phase 1] Waiting for match start (looking for VS banner)...")
    while True:
        frame = vision_manager.capture_clash_window(clash_window_top_left, clash_window_size)

        if vision_manager.detect_match_start(frame, clash_window_size, debug=False):
            print("[Phase 1] VS banner detected — match starting!")
            break

        if keyboard.is_pressed("space"):
            print("Space pressed, exiting.")
            exit()

        time.sleep(0.2)  # Poll at ~5fps — VS screen lasts a couple seconds

    # -----------------------------------------------------------------------
    # Phase 2: Lock onto the timer with 3 consistent reads before tracking
    # -----------------------------------------------------------------------
    print("[Phase 2] Locking onto timer...")
    while True:
        frame = vision_manager.capture_clash_window(clash_window_top_left, clash_window_size)
        timer_seconds = vision_manager.detect_timer(frame, clash_window_size)

        print(f"  Timer read: {timer_seconds}")

        if timer_detector.update(timer_seconds):
            # 3 consistent reads confirmed — start the elixir tracker
            elixir_tracker.start_battle(timer_seconds)
            print(f"[Phase 2] Timer locked at {timer_seconds}s — elixir tracking started!")
            break

        if keyboard.is_pressed("space"):
            print("Space pressed, exiting.")
            exit()

        time.sleep(0.3)

    # -----------------------------------------------------------------------
    # Phase 3: Main game loop
    # -----------------------------------------------------------------------
    print("[Phase 3] Game loop running. Press SPACE to stop.")
    while True:
        frame = vision_manager.capture_clash_window(clash_window_top_left, clash_window_size)

        frame_height = int(frame.shape[0])
        divider_height = int(frame_height * 0.8)

        detected_hand = card_identifier.get_hand(frame, divider_height)
        state = game_state_builder.build(frame, detected_hand)
        print("\n--- Board Troops In State ---")
        for troop_data in state.board_troops:
            print(
            f"{troop_data.troop.card} | owner={troop_data.owner.value} | "
            f"x={troop_data.x:.2f} y={troop_data.y:.2f} lane={troop_data.lane.value}"
            )
        print("-----------------------------")
        # -- Action logic --
        action = decision_manager.choose_next_play(state)
        elixir_tracker.update_from_time()

        if action is not None:
            current_detected_hand = card_identifier.get_hand(frame, divider_height)

            # DEBUG
            # print("LOGICAL HAND:", [card.card if card else None for card in state.hand])
            # print("DETECTED HAND:", detected_hand)
            # print("CHOSEN SLOT:", action.card_slot_id)

            if action.spell_card_flag:
                tile = screen_manager.normalized_to_full_tile(action.target_xy_pos)
                screen_manager.place_card(action.card_slot_id, tile)
            else:
                tile = screen_manager.normalized_to_player_tile(action.target_xy_pos)
                screen_manager.place_card_in_player_grid(action.card_slot_id, tile)

            elixir_tracker.spend(state.hand[action.card_slot_id].cost or 0)
            cycle_tracker.play_card(state.hand[action.card_slot_id])

        # -- Elixir (time-based, always reliable) --
        elixir = elixir_tracker.get_int()

        # -- Optional: sync elixir from vision every ~5s --
        # vision_elixir = vision_manager.detect_elixir(frame, clash_window_size)
        # if vision_elixir > 0:
        #     elixir_tracker.current_elixir = float(vision_elixir)

        """
        # -- Print state for debugging --
            print(f"Elixir: {state.player_elixir} | Time: {state.time_remaining:.1f}s | Double: {state.is_double_elixir}")
            print(f"Board troops ({len(state.board_troops)}):")
            for t in state.board_troops:
                print(f"  {t}")
            print(f"Left under attack: {state.is_lane_under_attack(Lane.LEFT)}")
            print(f"Right under attack: {state.is_lane_under_attack(Lane.RIGHT)}")
            print(f"Input vector: {state.to_input_vector()}")

            need to fix this bc cycle tracker isnt being called to discover enemy hand or player hand, 
            inaccurately detects cards as opponent cards even tho they arent
        """

        print(f"Elixir: {elixir:.2f}")

        # get troop_sightings on the board
        troops_on_board = troop_identifier.get_troops_on_board(frame, divider_height)
        for troop in troops_on_board:
            troop.loc = screen_manager.get_grid_location(
                (troop.top_left[0] + troop.bottom_right[0]) // 2,
                (troop.top_left[1] + troop.bottom_right[1]) // 2
            )

        for troop_sighting in troops_on_board:
            csv_name = YOLO_TO_CSV.get(troop_sighting.name, None)
            match = next((t for t in troops if t.card == csv_name), None)
            if match:
                print(f"Detected {match.card} | Owner: {troop_sighting.owner} | AT {troop_sighting.loc} | HP: {match.health} | DMG: {match.damage} | Cost: {match.cost}")
            else:
                print(f"No match for: {troop_sighting.name}")

        # DEBUG - show annotated frame to the right of our clash screen
        screen_manager.debug_draw_anchors(frame)
        cv2.imshow("Troop and Hand Detection", frame)
        cv2.moveWindow("Troop and Hand Detection", 
                        x=screen_manager.clash_window[0]+screen_manager.clash_window_size[0], 
                        y=0)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # -- Exit condition --
        if keyboard.is_pressed("space"):
            print("Space pressed, stopping AI.")
            break

        # stall time between each game loop 
        time.sleep(0.5) # remove later
