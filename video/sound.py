"""Small synthesized clicks, reveal sparkles, mine thumps, and win chords."""
import wave

import numpy as np

SR = 48000


def tone(freq, duration, decay=7, harmonics=(1, 0.2)):
    t = np.arange(int(SR * duration)) / SR
    envelope = np.minimum(1, t / 0.004) * np.exp(-decay * t)
    return envelope * sum(a * np.sin(2 * np.pi * freq * (i + 1) * t) for i, a in enumerate(harmonics))


def click():
    rng = np.random.default_rng(20)
    n = int(SR * 0.035)
    raw = np.convolve(rng.standard_normal(n), np.ones(10) / 10, "same")
    return raw * np.exp(-np.arange(n) / (SR * 0.007))


def boom():
    t = np.arange(int(SR * 0.9)) / SR
    rng = np.random.default_rng(21)
    return (np.sin(2 * np.pi * (78 - 35 * t) * t) + 0.28 * rng.standard_normal(len(t))) * np.exp(-5 * t)


def chord():
    return sum(tone(f, 1.8, 2.1, (1, 0.15)) for f in (261.63, 329.63, 392.0, 523.25)) / 2.5


def mix(events, duration):
    out = np.zeros((int(SR * (duration + 2)), 2))
    base_click = click()
    for at, kind, pan, amount in events:
        if kind == "click": wave_, gain = base_click, 0.045
        elif kind == "reveal": wave_, gain = tone(520 + min(amount, 18) * 17, 0.22, 10), 0.055
        elif kind == "boom": wave_, gain = boom(), 0.23
        else: wave_, gain = chord(), 0.16
        i = int(at * SR)
        segment = wave_[:max(0, len(out) - i)] * gain
        left, right = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
        out[i:i + len(segment), 0] += segment * left
        out[i:i + len(segment), 1] += segment * right
    return np.tanh(out * 1.25) / np.tanh(1.25)


def write_wav(path, audio):
    data = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as target:
        target.setnchannels(2); target.setsampwidth(2); target.setframerate(SR)
        target.writeframes(data.tobytes())

