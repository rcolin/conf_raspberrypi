import math
import os
import re
import subprocess
import sys
import time
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import numpy as np

RATE = 16000
CHANNELS = 2
FORMAT = "S32_LE"
SAMPLE_WIDTH = 4
DURATION = 5.0
CARD_NAME = "wm8960"

BAR_WIDTH = 32
FULL_BLOCK = "█"
EMPTY_BLOCK = "░"


def find_wm8960_card():
    """Retourne l'index ALSA de la carte WM8960, ou None."""
    try:
        out = subprocess.run(
            ["arecord", "-l"], capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        m = re.search(r"card (\d+):\s*(\S+)", line)
        if m and CARD_NAME in m.group(2).lower():
            return int(m.group(1))
    return None


def rms_db(samples):
    samples = samples.astype(np.float64)
    rms = math.sqrt(float(np.mean(samples ** 2)))
    if rms <= 1:
        return -100.0
    return 20.0 * math.log10(rms / (2 ** 31))


def meter(value_db, min_db=-60.0, max_db=0.0):
    ratio = max(0.0, min(1.0, (value_db - min_db) / (max_db - min_db)))
    filled = int(round(ratio * BAR_WIDTH))
    return FULL_BLOCK * filled + EMPTY_BLOCK * (BAR_WIDTH - filled)


def main():
    card = find_wm8960_card()
    if card is None:
        print(
            "Erreur : aucune carte WM8960 détectée.\n"
            "  - Le HAT ReSpeaker est-il bien branche sur les broches ?\n"
            "  - 'dtoverlay=wm8960-soundcard' est-il dans /boot/firmware/config.txt ?\n"
            "  - Avez-vous redemarré apres l'installation ?"
        )
        return

    device = f"plughw:{card},0"
    print(f"Carte WM8960 détectee (index {card}) → {device}")

    out_path = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "micro_test.wav")
    )

    print(f"Enregistrement de {DURATION}s à {RATE} Hz, {CHANNELS} canaux ({FORMAT})")
    print("Parlez face aux micros du HAT…\n")

    args = [
        "arecord",
        "-D", device,
        "-f", FORMAT,
        "-r", str(RATE),
        "-c", str(CHANNELS),
        "-t", "raw",
    ]

    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    frames_per_chunk = 1024
    bytes_per_chunk = frames_per_chunk * CHANNELS * SAMPLE_WIDTH
    raw = bytearray()
    peak = -100.0

    start = time.time()
    try:
        while time.time() - start < DURATION:
            chunk = proc.stdout.read(bytes_per_chunk)
            if not chunk:
                break
            raw.extend(chunk)
            samples = np.frombuffer(chunk, dtype=np.int32).reshape(-1, CHANNELS)
            left = rms_db(samples[:, 0])
            right = rms_db(samples[:, 1])
            peak = max(peak, left, right)
            line = f" L {meter(left)} {left:6.1f} dB  R {meter(right)} {right:6.1f} dB"
            sys.stdout.write("\r" + line)
            sys.stdout.flush()
    finally:
        proc.terminate()
        proc.wait()

    print(f"\r Pic sonore : {peak:6.1f} dBFS" + " " * (BAR_WIDTH * 2 + 24))

    if not raw:
        print("Erreur : aucun échantillon capturé. La carte ne délivre pas de signal.")
        return

    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(RATE)
        wf.writeframes(bytes(raw))

    duration = len(raw) / (RATE * CHANNELS * SAMPLE_WIDTH)
    print(f"Fichier enregistré : {out_path} ({duration:.1f}s)")

    print("Lecture du fichier enregistré… (casque ou haut-parleur sur le HAT)")
    try:
        subprocess.run(["aplay", "-D", device, out_path], check=True)
    except subprocess.CalledProcessError:
        print("Problème lors de la lecture (périphérique de sortie WM8960 introuvable).")


if __name__ == "__main__":
    main()