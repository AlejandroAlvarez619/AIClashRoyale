from ultralytics import YOLO
from dataclasses import dataclass
import numpy as np
import cv2

@dataclass
class TroopSighting:
    id: int
    name: str
    confidence: float
    # pixel location, will have to calculate grid location after receiving this result
    top_left: tuple[int, int]
    bottom_right: tuple[int, int]
    # grid location of unit on board
    loc: tuple[int, int]
    # differentiates between our cards and enemy cards
    owner: str = "unknown"  # can be "player", "opponent", or "unknown"
                            # due to the health bar only spawning after a troop is damaged
class TroopIdentifier:
    def __init__(self):
        self.model = YOLO("./src/models/troop_identify/troop_identify-3.pt")

    def parse_box(self, box):
        coords = box.xyxy[0].cpu().numpy()
        x1, y1, x2, y2 = int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])
        return x1, y1, x2, y2

    # --------------------------------------------------------------------------------------
    # RED PIXEL REGION DETECTION
    # --------------------------------------------------------------------------------------
    def get_red_region(self, troop_sighting):
        x1, y1 = troop_sighting.top_left
        x2, y2 = troop_sighting.bottom_right

        width  = x2 - x1
        height = y2 - y1

        # SAME WIDTH (no horizontal expansion)
        rx1 = x1
        rx2 = x2

        # STACKED ABOVE (no overlap)
        ry2 = y1                      # bottom of red box = top of troop box
        ry1 = int(y1 - 0.45 * height)  # height of detection region

        return rx1, ry1, rx2, ry2

    
    # --------------------------------------------------------------------------------------
    # RED BOX DETECTION
    # --------------------------------------------------------------------------------------
    def detect_by_red(self, frame, red_region):
        x1, y1, x2, y2 = red_region

        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return False
        
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # red range
        lower_red1 = np.array([0, 140, 80])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 140, 80])
        upper_red2 = np.array([179, 255, 255])

        mask = cv2.inRange(hsv, lower_red1, upper_red1) | \
            cv2.inRange(hsv, lower_red2, upper_red2)

        # clean noise
        kernel = np.ones((3,3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        red_pixels = np.sum(mask > 0)
        total_pixels = mask.size

        if total_pixels == 0:
            return False

        red_ratio = red_pixels / total_pixels

        # KEY THRESHOLDS
        if red_pixels < 15:
            return False

        return True

    def get_troops_on_board(self, frame, divider_height, confidence=0.6):
        results = self.model(frame[:divider_height, :], conf=confidence)

        troops_on_board = []

        for box in results[0].boxes:
            troop_id = int(box.cls)
            label = self.model.names[troop_id]
            confidence = float(box.conf)

            x1, y1, x2, y2 = self.parse_box(box)

            troop_on_board = TroopSighting(
                id=troop_id,
                name=label,
                confidence=confidence,
                top_left=(x1, y1),
                bottom_right=(x2, y2),
                loc=None
            )

            red_region = self.get_red_region(troop_on_board)
            is_enemy = self.detect_by_red(frame, red_region)
            troop_on_board.owner = "opponent" if is_enemy else "player"

            print("---Troop Identify Result---")
            print(f"{label}: {confidence:.2f} at ({x1}, {y1})  →  owner={troop_on_board.owner}")

            # draw bounding box
            pt1 = (int(troop_on_board.top_left[0]), int(troop_on_board.top_left[1]))
            pt2 = (int(troop_on_board.bottom_right[0]), int(troop_on_board.bottom_right[1]))
            cv2.rectangle(frame, pt1, pt2, (255, 255, 255), 2)

            # draw label for bounding box
            text = f"{troop_on_board.name}: {troop_on_board.confidence:.2f}: {troop_on_board.owner}"
            cv2.putText(frame, text, (int(troop_on_board.top_left[0]), int(troop_on_board.top_left[1])+4),  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 200), 2)

            # draw red region
            cv2.rectangle(frame, (red_region[0], red_region[1]), (red_region[2], red_region[3]), (0, 200, 255), 1)

            troops_on_board.append(troop_on_board)
        
        return troops_on_board
