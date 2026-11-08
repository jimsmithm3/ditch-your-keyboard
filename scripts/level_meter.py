"""Print the mic level in half-second steps, the same way the app reads it.

Usage (from the project folder):
    .\\.venv\\Scripts\\python.exe scripts\\level_meter.py 10

The first number is seconds to listen. The optional second is a device index. By
default it uses the mic saved by name, the same one the app uses. Each line shows the average and peak for that half second,
in calibrated dB using the saved offset, and dBFS for the raw signal.
"""

import array
import math
import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.listener import SAMPLE_RATE, _open_stream  # noqa: E402
from app.prefs_page import saved_offset  # noqa: E402

STEP = 0.5


def block_dbfs(data: bytes) -> float:
    samples = array.array("h")
    samples.frombytes(data)
    if not samples:
        return -120.0
    rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
    return -120.0 if rms <= 0 else 20 * math.log10(rms / 32768)


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    if len(sys.argv) > 2:
        device = int(sys.argv[2])
    else:
        from app.listener import _saved_mic_index, input_devices

        device = _saved_mic_index(input_devices())
        if device is None:
            raise SystemExit("No saved mic. Pass a device index as the second argument.")
    offset = saved_offset()
    q: queue.Queue[bytes] = queue.Queue()
    rate, stream = _open_stream(device, lambda indata, frames, t, status: q.put(bytes(indata)))
    print(f"device {device} at {rate} Hz, calibrated offset {offset:+.1f} dB. Speak now.")
    start = time.time()
    bucket: list[float] = []
    bucket_end = start + STEP
    try:
        while time.time() - start < seconds:
            try:
                data = q.get(timeout=0.1)
            except queue.Empty:
                continue
            bucket.append(block_dbfs(data))
            if time.time() >= bucket_end:
                if bucket:
                    avg_db = sum(bucket) / len(bucket) + offset
                    peak_db = max(bucket) + offset
                    raw_peak = max(bucket)
                    print(f"{bucket_end - start:5.1f}s  avg {avg_db:5.1f} dB  peak {peak_db:5.1f} dB   (raw peak {raw_peak:6.1f} dBFS)")
                bucket = []
                bucket_end += STEP
    finally:
        stream.stop()
        stream.close()
    print("done")


if __name__ == "__main__":
    main()
