import numpy as np

class Colors:
    def __init__(self, size_or_colors):
        if isinstance(size_or_colors, int):
            self.r = np.zeros(size_or_colors, dtype=np.uint8)
            self.g = np.zeros(size_or_colors, dtype=np.uint8)
            self.b = np.zeros(size_or_colors, dtype=np.uint8)
        else:
            colors = size_or_colors
            if hasattr(colors, '__len__') and len(colors) == 0:
                raise RuntimeError("Colors constructor received empty list - this indicates a bug in effect generation")
            self.r = np.array([c.r for c in colors], dtype=np.uint8)
            self.g = np.array([c.g for c in colors], dtype=np.uint8)
            self.b = np.array([c.b for c in colors], dtype=np.uint8)

    def __getitem__(self, idx):
        from .led_controller import Color
        return Color(self.r[idx], self.g[idx], self.b[idx])

    def __setitem__(self, idx, color):
        self.r[idx] = color.r
        self.g[idx] = color.g
        self.b[idx] = color.b

    def __len__(self):
        return len(self.r)

    def copy(self):
        result = Colors(len(self))
        result.r = self.r.copy()
        result.g = self.g.copy()
        result.b = self.b.copy()
        return result
