from dataclasses import dataclass
import time
import math

@dataclass
class ElixirTracker:
    current_elixir: float = 0.0
    last_update_ts: float = 0.0
    battle_started: bool = False
    battle_start_ts: float = 0.0
    last_timer_seconds: int | None = None
    latency_buffer: float = 0.00
    DETECTION_LAG: float = 3.2  # seconds of extra lag from timer read + phase 2 lock-in


    def start_battle(self, timer_seconds: int):
        # timer_seconds is the visible match clock when battle is first detected
        self.battle_started = True
        now = time.time()
        self.last_timer_seconds = timer_seconds

        # Calculate how many seconds have elapsed since match start (3:00 = 180s)
        elapsed = 180 - timer_seconds

        # Accumulate elixir gained during the time we were still detecting
        # Always single elixir rate (1/2.8) since this is always within first 2 min
        elapsed_with_lag = elapsed + self.DETECTION_LAG
        gained = elapsed_with_lag / 2.8

        # Backdate the battle start so future elapsed time is correct
        self.battle_start_ts = now - elapsed_with_lag
        self.last_update_ts = now

        self.current_elixir = min(10.0, 5.0 + gained)

    def get_rate(self, elapsed_seconds: float) -> float:
        # returns elixir per second
        if elapsed_seconds < 120:
            return 1 / 2.8
        elif elapsed_seconds < 240:
            return 1 / 1.4
        else:
            return 1 / 0.9

    def update_from_time(self):
        if not self.battle_started:
            return

        now = time.time()
        dt = now - self.last_update_ts
        elapsed = now - self.battle_start_ts

        self.current_elixir += dt * self.get_rate(elapsed)
        self.current_elixir = min(10.0, self.current_elixir)
        self.last_update_ts = now

    def spend(self, cost: int):
        self.update_from_time()
        if(self.current_elixir == 10):
            self.current_elixir = (self.current_elixir - cost - 1/self.get_rate())
        else:
            self.current_elixir = (self.current_elixir - cost - self.latency_buffer)

    def get_int(self) -> int:
        self.update_from_time()
        return self.current_elixir
        # return math.floor(self.current_elixir)

