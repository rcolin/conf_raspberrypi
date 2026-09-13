import argparse
import json
import re
import subprocess
import sys
import time

import os

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import requests
import vosk

RATE = 16000
CARD_NAME = "wm8960"
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-fr-0.22")
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "ministral-3-3b"
LLM_TIMEOUT = 120

SYSTEM_PROMPT = (
    "Tu es un assistant vocal embarqué sur un Raspberry Pi. "
    "Réponds de manière concise et en français."
)


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


def transcribe_loop(card):
    device = f"plughw:{card},0"
    args = [
        "arecord", "-D", device,
        "-f", "S16_LE", "-r", str(RATE), "-c", "1",
        "-t", "raw",
    ]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)

    model = vosk.Model(MODEL_PATH)
    rec = vosk.KaldiRecognizer(model, RATE)
    print("(parle dans le micro — Ctrl+C pour quitter)\n", flush=True)

    bytes_per_chunk = 8000
    while True:
        raw = proc.stdout.read(bytes_per_chunk)
        if not raw:
            break
        if rec.AcceptWaveform(raw):
            result = json.loads(rec.Result())
            text = result.get("text", "").strip()
            if text:
                yield text
                rec.Reset()


def ask_llm(text):
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 256,
        "stream": False,
    }
    try:
        resp = requests.post(LLM_URL, json=payload, timeout=LLM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"[erreur LLM] {exc}"


def main():
    parser = argparse.ArgumentParser(
        description="Assistant vocal : micro → Vosk (STT) → Ministral 3 3B → stdout"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Transcrire une seule phrase puis s'arrêter (mode test unitaire)",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Afficher la transcription sans interroger le LLM",
    )
    args = parser.parse_args()

    card = find_wm8960_card()
    if card is None:
        print(
            "Erreur : aucune carte WM8960 détectée.\n"
            "  - Le HAT ReSpeaker est-il bien branché ?\n"
            "  - l'overlay wm8960-soundcard est-il actif et le Pi redémarré ?"
        )
        sys.exit(1)

    for text in transcribe_loop(card):
        print(f"\n[VOIX] {text}", flush=True)
        if args.no_llm:
            if args.once:
                return
            continue
        print("[LLM…]", flush=True)
        start = time.time()
        answer = ask_llm(text)
        elapsed = time.time() - start
        print(f"[RÉPONSE ({elapsed:.1f}s)] {answer}", flush=True)
        if args.once:
            return


if __name__ == "__main__":
    main()