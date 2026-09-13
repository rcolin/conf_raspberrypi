import argparse
import sys
import time

import spidev

BUS = 0
DEVICE = 1
MAX_SPEED_HZ = 8000000
NUM_LEDS = 3

START_FRAME = [0x00] * 4
END_FRAME = [0xFF] * 4


def setup_spi(bus, device):
    spi = spidev.SpiDev()
    spi.open(bus, device)
    spi.max_speed_hz = MAX_SPEED_HZ
    return spi


def led_frame(brightness, red, green, blue):
    return [(0b11100000 | (brightness & 0x1F)), blue, green, red]


def show(spi, colors, brightness=31):
    frames = []
    for i in range(NUM_LEDS):
        if i < len(colors):
            r, g, b = colors[i]
        else:
            r, g, b = 0, 0, 0
        frames.extend(led_frame(brightness, r, g, b))
    spi.xfer2(START_FRAME + frames + END_FRAME)


def raw_to_colors(raw):
    acc = 0
    for token in raw.split(","):
        token = token.strip().lower()
        if not token:
            continue
        if token in ("r", "red"):
            acc = acc | 0x04
        elif token in ("g", "green"):
            acc = acc | 0x02
        elif token in ("b", "blue"):
            acc = acc | 0x01
        elif token in ("rouge",):
            acc = acc | 0x04
        elif token in ("vert",):
            acc = acc | 0x02
        elif token in ("bleu",):
            acc = acc | 0x01
        else:
            raise ValueError(f"Couleur inconnue : {token!r}")
    return [
        (0xFF if acc & 0x04 else 0),
        (0xFF if acc & 0x02 else 0),
        (0xFF if acc & 0x01 else 0),
    ]


def scan_pattern(spi, steps=6):
    base = [
        (0xFF, 0, 0),
        (0, 0xFF, 0),
        (0, 0, 0xFF),
    ]
    for step in range(steps * 3):
        colors = [base[(step + i) % 3] for i in range(NUM_LEDS)]
        show(spi, colors)
        time.sleep(0.3)


def rainbow_cycle(spi, steps=36):
    for step in range(steps):
        colors = []
        for i in range(NUM_LEDS):
            phase = (i * 2 + step) % 36
            if phase < 6:
                r, g, b = 0xFF, 51 * phase, 0
            elif phase < 12:
                r, g, b = 0xFF - 51 * (phase - 6), 0xFF, 0
            elif phase < 18:
                r, g, b = 0, 0xFF, 51 * (phase - 12)
            elif phase < 24:
                r, g, b = 0, 0xFF - 51 * (phase - 18), 0xFF
            elif phase < 30:
                r, g, b = 51 * (phase - 24), 0, 0xFF
            else:
                r, g, b = 0xFF, 51 * (phase - 30), 0xFF - 51 * (phase - 30) if phase < 33 else 0
            colors.append((r, g, b))
        show(spi, colors)
        time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description="Test des LEDs APA102 du ReSpeaker HAT")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_static = sub.add_parser("static", help="LEDs allumées en continu")
    p_static.add_argument("colors", nargs="*", help="Couleurs des LED 1..3 (ex: red green blue)")

    sub.add_parser("scan", help="Balayage séquentiel LED par LED")
    sub.add_parser("rainbow", help="Cycle arc-en-ciel")
    sub.add_parser("off", help="Éteindre toutes les LEDs")

    args = parser.parse_args()

    try:
        spi = setup_spi(BUS, DEVICE)
    except OSError as exc:
        print(
            f"Erreur : impossible d'ouvrir /dev/spidev{BUS}.{DEVICE} ({exc}).\n"
            "  - Le SPI est-il activé (dtparam=spi=on) et le Pi redémarré ?\n"
            "  - /dev/spidev* existe-t-il ? (ls /dev/spidev*)"
        )
        sys.exit(1)

    if args.mode == "static":
        if not args.colors:
            colors = [(0xFF, 0x50, 0)] * NUM_LEDS
        else:
            try:
                colors = [raw_to_colors(c) for c in args.colors]
            except ValueError as exc:
                print(f"Erreur : {exc}")
                sys.exit(1)
        if len(colors) != NUM_LEDS:
            print(f"Erreur : attendu {NUM_LEDS} couleurs, reçu {len(colors)}")
            sys.exit(1)
        show(spi, colors)
        details = ", ".join(f"LED{i + 1}=#{r:02x}{g:02x}{b:02x}" for i, (r, g, b) in enumerate(colors))
        print(f"LEDs allumées : {details}")
        print("Appuie sur Ctrl+C pour éteindre…")
        while True:
            time.sleep(1)
    elif args.mode == "scan":
        print("Balayage LED par LED (rouge, vert, bleu)…")
        scan_pattern(spi)
        show(spi, [(0, 0, 0)] * NUM_LEDS)
        print("Terminé.")
    elif args.mode == "rainbow":
        print("Cycle arc-en-ciel…")
        rainbow_cycle(spi)
        show(spi, [(0, 0, 0)] * NUM_LEDS)
        print("Terminé.")
    elif args.mode == "off":
        show(spi, [(0, 0, 0)] * NUM_LEDS)
        print("LEDs éteintes.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()