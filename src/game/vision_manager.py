# Class to capture screen and detect certain objects (ie: elixir, cards, towers)

import pyautogui
import numpy as np
import cv2
"""
NOTE: In order for tesseract to run on your device, you must install it.
It is not simply a python library, it requires an executable download.

For macbook users, you can use homebrew: brew install tesseract
For Windows: https://github.com/UB-Mannheim/tesseract/wiki
"""
import pytesseract
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class VisionManager:

    def capture_screen(self):
        screenshot = pyautogui.screenshot()
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame

    def capture_clash_window(self, top_left, size):
        x, y = top_left
        w, h = size
        screenshot = pyautogui.screenshot(region=(x, y, w, h))
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return frame

    # ---------------------------------------------------------------------------
    # Match-start detection
    # ---------------------------------------------------------------------------

    def detect_match_start(self, frame, size, debug: bool = False) -> bool:
        w, h = size
        MIN_BLUE_PIXELS = 200  # tune this — see debug tip above

        # Shield sits at horizontal center, ~45% down from top
        x1 = int(w * 0.30)
        x2 = int(w * 0.70)
        y1 = int(h * 0.38)
        y2 = int(h * 0.52)
        shield_region = frame[y1:y2, x1:x2]

        # Clash Royale UI blue: strong saturated blue, hue ~100-130 in HSV
        hsv = cv2.cvtColor(shield_region, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([95,  120, 120])
        upper_blue = np.array([135, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        blue_pixels = int(np.sum(mask > 0))
        shield_detected = blue_pixels >= MIN_BLUE_PIXELS

        if debug:
            cv2.imshow("Shield Region", shield_region)
            cv2.imshow("Blue Mask", mask)
            cv2.waitKey(1)
            print(f"[MatchStart] blue_pixels={blue_pixels}  detected={shield_detected}")

        return shield_detected

    # ---------------------------------------------------------------------------
    # Timer detection
    # ---------------------------------------------------------------------------

    def detect_timer(self, frame, size) -> int | None:
        w, h = size

        # Timer: 85-95% from left 
        # Timer: 2.5-6% from top on y-axis
        x1 = int(w * 0.85)
        x2 = int(w * 0.98)
        y1 = int(h * 0.025)
        y2 = int(h * 0.055)
        timer_crop = frame[y1:y2, x1:x2]

        # Upscale — small text needs this
        scale = 4
        enlarged = cv2.resize(timer_crop, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)

        # Try multiple threshold strategies — game fonts can be tricky.
        # We attempt each and return the first one that parses successfully.
        threshold_attempts = [
            # 1. Isolate bright pixels (white/yellow text on dark bg)
            cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1],
            # 2. Isolate dark pixels (dark text on light bg)
            cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)[1],
            # 3. OTSU auto (good when contrast is high)
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
            # 4. OTSU inverted
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1],
        ]

        # DEBUG — show raw crop and all threshold attempts
        # cv2.imshow("Timer Raw", enlarged)
        # for i, t in enumerate(threshold_attempts):
        #     cv2.imshow(f"Timer Thresh {i}", t)
        # cv2.waitKey(1)

        psm_config = "--psm 7 -c tessedit_char_whitelist=0123456789:"
        for i, thresh in enumerate(threshold_attempts):
            text = pytesseract.image_to_string(thresh, config=psm_config).strip()
            print(f"[TimerOCR] attempt={i} raw='{text}'")
            result = self._parse_timer(text)
            if result is not None:
                return result

        return None

    def _parse_timer(self, text: str) -> int | None:
        text = text.strip().replace(" ", "")
        try:
            if ":" in text:
                parts = text.split(":")
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    if 0 <= minutes <= 3 and 0 <= seconds <= 59:
                        return minutes * 60 + seconds
            # Fallback: no colon — treat as MSS (e.g. "246" = 2min 46sec)
            elif len(text) == 3:
                minutes = int(text[0])
                seconds = int(text[1:])
                if 0 <= minutes <= 3 and 0 <= seconds <= 59:
                    return minutes * 60 + seconds
            # Could also be SS only if leading digit was dropped (e.g. "46")
            elif len(text) == 2:
                seconds = int(text)
                if 0 <= seconds <= 59:
                    # Assume we're in the last minute if only 2 digits
                    return seconds
        except ValueError:
            pass
        return None

    # ---------------------------------------------------------------------------
    # Elixir detection
    # ---------------------------------------------------------------------------

    """
    Note: OCR on the elixir number is unreliable.
    Use ElixirTracker (time-based) as the primary source.
    This method is kept as a future correction/sync signal.
    """
    def detect_elixir(self, frame, size):
        """
        Estimates elixir from the on-screen number above the purple bar.
        Returns an int 0-10, or 0 if the bar is undetected.
        """
        w, h = size
        bar_top = int(h * 19 / 20)
        bar_bottom = h
        bar_area = frame[bar_top:bar_bottom, 0:w]

        hsv = cv2.cvtColor(bar_area, cv2.COLOR_RGB2HSV)
        lower_purple = np.array([110, 50, 50])
        upper_purple = np.array([160, 255, 255])
        mask = cv2.inRange(hsv, lower_purple, upper_purple)

        ys, xs = np.where(mask > 0)
        if len(xs) == 0 or len(ys) == 0:
            return 0

        x_min, x_max = xs.min(), xs.max()
        y_min, y_max = ys.min(), ys.max()
        number_crop = bar_area[max(y_min - int((y_max - y_min) * 2), 0):y_max, x_min:x_max]

        gray = cv2.cvtColor(number_crop, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 150, 255,
                               cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

        text = pytesseract.image_to_string(
            thresh, config="--psm 7 -c tessedit_char_whitelist=0123456789"
        )

        # DEBUG
        # cv2.imshow("Elixir Bar Area", bar_area)
        # cv2.waitKey(5)
        # print("OCR input shape:", number_crop.shape)
        # print("OCR detected:", text.strip())

        try:
            return int(text.strip())
        except ValueError:
            return 0


if __name__ == "__main__":
    """
    vision = VisionManager()
    frame = vision.capture_screen()
    cv2.imshow("Screen", frame)
    cv2.waitKey(0)
    """
