#workers
import numpy as np
from PySide6.QtCore import QRunnable, QObject, Signal
from collections import OrderedDict

class WorkerSignals(QObject):
    finished = Signal(list, list, str, int)

class FunctionWorker(QRunnable):
    _cache = OrderedDict()
    _cache_maxsize = 50

    def __init__(self, func, func_str, range_param, is_implicit, cell_id, precision_mode=False):
        super().__init__()
        self.func = func
        self.func_str = func_str
        self.range_param = range_param
        self.is_implicit = is_implicit
        self.cell_id = cell_id
        self.precision_mode = precision_mode
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    @classmethod
    def get_from_cache(cls, key):
        if key in cls._cache:
            cls._cache.move_to_end(key)
            return cls._cache[key]
        return None

    @classmethod
    def add_to_cache(cls, key, value):
        if len(cls._cache) >= cls._cache_maxsize:
            cls._cache.popitem(last=False)
        cls._cache[key] = value

    @classmethod
    def clear_cache(cls):
        cls._cache.clear()

    def _split_into_segments(self, x, y):
        segments_x = []
        segments_y = []
        current_x = []
        current_y = []
        for xi, yi in zip(x, y):
            if np.isnan(yi):
                if current_x:
                    segments_x.append(current_x)
                    segments_y.append(current_y)
                    current_x = []
                    current_y = []
            else:
                current_x.append(xi)
                current_y.append(yi)
        if current_x:
            segments_x.append(current_x)
            segments_y.append(current_y)
        return segments_x, segments_y

    def run(self):
        print(f"[DEBUG] Worker for cell {self.cell_id}, range {self.range_param}, func_str={self.func_str}")
        try:
            t_min, t_max = self.range_param
            if not np.isfinite(t_min) or not np.isfinite(t_max):
                return

            width = abs(t_max - t_min)
            key = (t_min, t_max, self.precision_mode)

            #cached = self.get_from_cache(key)
            #if cached is not None:
            #    print(f"[DEBUG] Cache hit for cell {self.cell_id}, key={key}")
            #    if self._is_cancelled:
             #       return
              #  self.signals.finished.emit(cached[0], cached[1], self.func_str, self.cell_id)
               # return

            if self.precision_mode:
                if width > 100000:
                    num_points = 80000
                elif width > 10000:
                    num_points = 50000
                elif width > 1000:
                    num_points = 30000
                elif width > 100:
                    num_points = 20000
                else:
                    num_points = 10000
                threshold = 300
            else:
                if width > 10000:
                    num_points = 10000
                elif width > 1000:
                    num_points = 6000
                elif width > 100:
                    num_points = 4000
                else:
                    num_points = 3000
                threshold = 1000

            t = np.linspace(t_min, t_max, num_points)

            if self._is_cancelled:
                return

            vals = self.func(t)
            if not isinstance(vals, np.ndarray):
                vals = np.full_like(t, vals, dtype=float)

            vals[np.isinf(vals)] = np.nan
            vals[np.abs(vals) > 1e6] = np.nan

            finite_idx = np.where(np.isfinite(vals))[0]
            if len(finite_idx) > 1:
                diffs = np.abs(np.diff(vals[finite_idx]))
                jump = np.where(diffs > threshold)[0]
                for j in jump:
                    idx1 = finite_idx[j]
                    idx2 = finite_idx[j+1]
                    vals[idx1] = np.nan
                    vals[idx2] = np.nan

            for i in range(1, len(vals)-1):
                if np.isfinite(vals[i]) and np.abs(vals[i]) > 1e4:
                    if np.isfinite(vals[i-1]) and np.isfinite(vals[i+1]):
                        if np.abs(vals[i] - vals[i-1]) > threshold or np.abs(vals[i+1] - vals[i]) > threshold:
                            vals[i] = np.nan
                    else:
                        vals[i] = np.nan

            if self.is_implicit:
                x = vals
                y = t
            else:
                x = t
                y = vals

            seg_x, seg_y = self._split_into_segments(x, y)

            self.add_to_cache(key, (seg_x, seg_y))

            if self._is_cancelled:
                return

            self.signals.finished.emit(seg_x, seg_y, self.func_str, self.cell_id)

        except Exception as e:
            print(f"Ошибка вычисления: {e}")
            self.signals.finished.emit([], [], self.func_str, self.cell_id)