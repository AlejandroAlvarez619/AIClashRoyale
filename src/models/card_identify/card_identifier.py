from ultralytics import YOLO
from dataclasses import dataclass
import cv2

@dataclass
class CardSighting:
    id: int
    name: str
    confidence: float
    # pixel location, will have to calculate grid location after receiving this result
    top_left: tuple[int, int]
    bottom_right: tuple[int, int]

class CardIdentifier:
    def __init__(self):
        self.model = YOLO("./src/models/card_identify/card_identify.pt")

    def _get_card_sightings(self, frame, confidence=0.6):
        results = self.model(frame, conf=confidence, verbose=False)

        card_sightings = []
        for box in results[0].boxes:
            troop_id = int(box.cls)
            label = self.model.names[troop_id]
            confidence = float(box.conf)
            x1, y1, x2, y2 = box.xyxy[0]

            if(label == "bomber"):
                continue
            # print("---Troop Identify Result---")
            # print(f"{label}: {confidence:.2f} at {x1:.0f}, {y1:.0f}")

            card_sighting = CardSighting(
                id=troop_id,
                name=label,
                confidence=confidence,
                top_left=(x1, y1),
                bottom_right=(x2, y2)
            )


            card_sightings.append(card_sighting)

        return card_sightings

    def get_hand(self, frame, divider_height):
        card_sightings = self._get_card_sightings(frame[divider_height:, :])

        hand = [None, None, None, None]
        best_by_slot = [None, None, None, None]

        # location of each hand position's x-bound by percentage of window width
        x_bounds = [
            (0.236, 0.411),
            (0.425, 0.600),
            (0.618, 0.785),
            (0.804, 0.975)
        ]

        card_bottom_bound = int(frame.shape[0] * 0.95)

        for card_sighting in card_sightings:
            center_x = int((card_sighting.top_left[0] + card_sighting.bottom_right[0]) // 2)
            center_y = int((card_sighting.top_left[1] + card_sighting.bottom_right[1]) // 2 + divider_height)

            # if center of card not within hand y-bound, then this is a hallucination
            if center_y <= divider_height or center_y >= card_bottom_bound:
                continue

            slot_idx = None
            for idx, bound in enumerate(x_bounds):
                left_x = int(frame.shape[1] * bound[0])
                right_x = int(frame.shape[1] * bound[1])
                if left_x <= center_x <= right_x:
                    slot_idx = idx
                    break

            # if center of card not within any hand position, ignore it
            if slot_idx is None:
                continue

            current_best = best_by_slot[slot_idx]
            if current_best is None or card_sighting.confidence > current_best.confidence:
                best_by_slot[slot_idx] = card_sighting

        for idx, best in enumerate(best_by_slot):
            if best is None:
                continue

            hand[idx] = best.name

            # draw bounding box for the winning detection only
            pt1 = (int(best.top_left[0]), int(best.top_left[1]) + divider_height)
            pt2 = (int(best.bottom_right[0]), int(best.bottom_right[1]) + divider_height)
            cv2.rectangle(frame, pt1, pt2, (255, 255, 255), 2)

            text = f"{best.name}: {best.confidence:.2f}"
            cv2.putText(
                frame,
                text,
                (int(best.top_left[0]), int(best.top_left[1]) + divider_height - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (100, 100, 200),
                2
            )

        return hand
