class TimerDetector:
    def __init__(self):
        self.good_reads = 0
        self.last_value = None

    def update(self, timer_seconds):
        if timer_seconds is None:
            self.good_reads = 0
            self.last_value = None
            return False

        if self.last_value is None or abs(timer_seconds - self.last_value) <= 1:
            self.good_reads += 1
        else:
            self.good_reads = 1

        self.last_value = timer_seconds
        return self.good_reads >= 3