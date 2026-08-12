"""Stand-in for adafruit-circuitpython-neopixel, so the tests run off-hardware.

Records what would have been written to the LED strip, which is how the tests
check what the clock actually draws.
"""


class NeoPixel:
    def __init__(self, pin, count, brightness=1.0, auto_write=True):
        self.pin = pin
        self.count = count
        self.brightness = brightness
        self.auto_write = auto_write
        self.buffer = [(0, 0, 0)] * count
        self.shows = 0

    def __setitem__(self, index, color):
        if not isinstance(index, int) or index < 0 or index >= self.count:
            raise IndexError(f"pixel {index} out of range")
        if len(color) != 3 or any(not 0 <= int(channel) <= 255 for channel in color):
            raise ValueError(f"bad color {color}")
        self.buffer[index] = tuple(int(channel) for channel in color)

    def __getitem__(self, index):
        return self.buffer[index]

    def fill(self, color):
        self.buffer = [tuple(color)] * self.count

    def show(self):
        self.shows += 1

    def lit(self):
        return [i for i, color in enumerate(self.buffer) if color != (0, 0, 0)]
