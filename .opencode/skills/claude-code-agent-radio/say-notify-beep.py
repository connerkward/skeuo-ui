#!/usr/bin/env python3
"""Generate say-notify-beep.wav — the soft comms tone played before the spoken line.

A pure double sine blip (660 Hz, smooth raised-cosine envelope, low amplitude) chosen
by ear as non-grating for repeated use. Regenerate / tweak pitch here rather than
hand-editing the wav. Run:  python3 say-notify-beep.py   (writes alongside this file)
"""
import wave, math, struct, os

SR = 24000
def env(i, n, fade):                      # raised-cosine fade -> no click transients
    f = int(fade * SR)
    if i < f:     return 0.5 * (1 - math.cos(math.pi * i / f))
    if i > n - f: return 0.5 * (1 - math.cos(math.pi * (n - i) / f))
    return 1.0

def tone(freqs, beep=0.08, gap=0.06, amp=0.28, fade=0.012):
    s = []
    for k, fr in enumerate(freqs):
        n = int(beep * SR)
        s += [amp * math.sin(2 * math.pi * fr * i / SR) * env(i, n, fade) for i in range(n)]
        if k < len(freqs) - 1:
            s += [0.0] * int(gap * SR)
    return s

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "say-notify-beep.wav")
w = wave.open(out, "w"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x)) * 32767)) for x in tone([660, 660])))
w.close()
print("wrote", out)
