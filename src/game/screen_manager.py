import pyautogui
import time
from src.constants import PLAYER_GRID_SIZE, TOTAL_GRID_SIZE
from src.game.decision_manager import place_anchor
import cv2

# class responsible for interacting with our sreen(clash royale window)
# will have methods like "read_snapshot_into_game_state()", "place_card(card_index: int)""
class ScreenManager():
    def __init__(self, clash_window: tuple[int], clash_window_size: tuple[int]):
        self.screen_size: tuple[int] = pyautogui.size()
        self.clash_window: tuple[int] = clash_window # pixel location of clash royale window (top left corner)
        self.clash_window_size: tuple[int] = clash_window_size # pixel size of clash royale window

        # All fields defined in these methods may need tuning later
        self._init_card_locations()
        self._init_tile_locations()
        self._init_training_camp_locations()

    def _get_tuple(self, multiplier_1: float, multiplier_2: float):
        return (
            int(self.clash_window[0] + (self.clash_window_size[0] * multiplier_1)), 
            int(self.clash_window[1] + (self.clash_window_size[1] * multiplier_2))
        )
    
    def _init_card_locations(self):
        card_center_y_multiplier: float = 0.875
        # location of cards
        self.cards: list[tuple[int]] = [
            self._get_tuple(0.299, card_center_y_multiplier),
            self._get_tuple(0.489, card_center_y_multiplier),
            self._get_tuple(0.680, card_center_y_multiplier),
            self._get_tuple(0.871, card_center_y_multiplier)
        ]

    def _init_tile_locations(self):
        self.total_grid_start: tuple[int] = self._get_tuple(0.086, 0.081)
        self.player_grid_start: tuple[int] = self._get_tuple(0.086, 0.444)
        self.tile_size: tuple[int] = (
            self.clash_window_size[0] * 0.047,
            self.clash_window_size[1] * 0.022
        )

    def _init_training_camp_locations(self):
        # buttons to click to start training camp match
        self.hamburger_menu: tuple[int] = self._get_tuple(0.928, 0.103)
        self.training_camp: tuple[int] = self._get_tuple(0.626, 0.320)
        self.training_camp_ok_button: tuple[int] = self._get_tuple(0.701, 0.570)
        # locations of items on screen during battle unique to training camp

    def print_screen_stats(self):
        print(f"Screen Size: {self.screen_size}")
        print(f"Clash Window Location: {self.clash_window}")
        print(f"Clash Window Size: {self.clash_window_size}")

    def get_grid_location(self, x, y):
        return (
            int((x - self.total_grid_start[0]) // self.tile_size[0]) + 1,
            int((y - self.total_grid_start[1]) // self.tile_size[1]) + 1
        )

    # place card anywhere in game grid
    def place_card(self, card_idx: int, tile_coord: tuple[int]):
        pyautogui.click(self.cards[card_idx])
        time.sleep(0.1) # small buffer to make sure card is selected before attempting to place, can expirement with deleting or changing this value later
        loc: tuple[int] = (
            self.total_grid_start[0] + (tile_coord[0] * self.tile_size[0]) + (self.clash_window_size[0] * 0.021),
            self.total_grid_start[1] + (tile_coord[1] * self.tile_size[1]) + (self.clash_window_size[1] * 0.011)
        )
        pyautogui.click(loc)

    # place card our player's side of the bridge
    def place_card_in_player_grid(self, card_idx: int, tile_coord: tuple[int]):
        pyautogui.click(self.cards[card_idx])
        time.sleep(0.1) # small buffer to make sure card is selected before attempting to place, can expirement with deleting or changing this value later
        loc: tuple[int] = (
            self.player_grid_start[0] + (tile_coord[0] * self.tile_size[0]) + (self.clash_window_size[0] * 0.021),
            self.player_grid_start[1] + (tile_coord[1] * self.tile_size[1]) + (self.clash_window_size[1] * 0.011)
        )
        pyautogui.click(loc)

    def start_training_camp_match(self):
        click_buffer: float = 0.3
        pyautogui.click(self.hamburger_menu)
        time.sleep(click_buffer)
        pyautogui.click(self.training_camp)
        time.sleep(click_buffer)
        pyautogui.click(self.training_camp_ok_button)
        # time before loading menu ends
        time.sleep(4)

    def normalized_to_player_tile(self, target):
        x, y = target
        player_y = max(0.0, min(1.0, (y - 0.5) * 2.0))
        tile_x   = max(0, min(17, round(x * 17)))
        tile_y   = max(0, min(14, round(player_y * 14)))
        return (tile_x, tile_y)
    
    def normalized_to_full_tile(self, target):
        x, y = target
        tile_x = max(0, min(17, round(x * 17)))
        tile_y = max(0, min(31, round(y * 31)))
        return (tile_x, tile_y)
    
    def debug_draw_anchors(self, frame):
        win_w, win_h = self.clash_window_size
        points = {
            "KING_FRONT":        place_anchor.king_front_pos,
            "LEFT_TOWER_FRONT":  place_anchor.left_tower_pos,
            "RIGHT_TOWER_FRONT": place_anchor.right_tower_pos,
            "LEFT_BRIDGE":       place_anchor.left_bridge_pos,
            "RIGHT_BRIDGE":      place_anchor.right_bridge_pos,
            "MIDDLE_LOW_LEFT":  place_anchor.middle_low_left,
            "MIDDLE_LOW_RIGHT": place_anchor.middle_low_right,
            "BEHIND_KING_LEFT": place_anchor.behind_king_left,
            "BEHIND_KING_RIGHT": place_anchor.behind_king_right,
        }
        for name, target in points.items():
            tile_x, tile_y = self.normalized_to_player_tile(target)
            px = int(self.player_grid_start[0] + tile_x * self.tile_size[0] + win_w * 0.021)
            py = int(self.player_grid_start[1] + tile_y * self.tile_size[1] + win_h * 0.011)
            # frame coords are relative to the captured window, so subtract the window origin
            px -= self.clash_window[0]
            py -= self.clash_window[1]
            cv2.circle(frame, (px, py), 10, (0, 255, 255), 2)
            cv2.putText(frame, name, (px + 12, py + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
# ScreenManager End


# test game runner
def run_game_place_diagonal(screen_manager: ScreenManager):
    x: int = 0
    y: int = 0
    sleep_time: int = 3
    while True:
        for i in range(4):
            time.sleep(sleep_time)
            screen_manager.place_card(i, (x, y))
            x += 1
            if x >= TOTAL_GRID_SIZE[0]:#PLAYER_GRID_SIZE[0]:
                x = 0
            y += 1
            if y >= TOTAL_GRID_SIZE[1]:#PLAYER_GRID_SIZE[1]:
                y = 0

def run_game_user_placement(screen_manager: ScreenManager):
    while True:
        inputs: list = input("Enter card as <idx x y>: ").split()
        card_idx, x, y = int(inputs[0]), int(inputs[1]), int(inputs[2])
        screen_manager.place_card_in_player_grid(card_idx, (x, y))

def read_mouse_position():
    screen_x, screen_y = pyautogui.size()
    print(f"x:{screen_x}, y:{screen_y}")
    print("-----------------")

    while True:
        mouse_x, mouse_y = pyautogui.position()
        print(f"x:{mouse_x}, y:{mouse_y}")


if __name__ == "__main__":
    read_mouse_position()

    # initial parameters for my setup
    # clash_window_top_left: tuple[int] = (0, 36) # will need to change this to fit your setup (use read_mouse_position to find (x,y) coords)
    # clash_window_size: tuple[int] = (556, 992) # will need to change this to fit your setup (use read_mouse_position to find (x,y) coords of bottom right, input difference between that and top left)
    # screen manager instantiation
    """
    screen_manager: ScreenManager = ScreenManager(clash_window_top_left, clash_window_size)
    screen_manager.print_screen_stats()
    screen_manager.start_training_camp_match()
    run_game_place_diagonal(screen_manager)
    run_game_user_placement(screen_manager)

    print(f"---{screen_manager.get_grid_location(143, 534)}---") # should be 4, 20
    print(f"---{screen_manager.get_grid_location(351, 637)}---") # should be 12, 24
    """
