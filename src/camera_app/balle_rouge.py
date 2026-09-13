import os

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import cv2
import numpy as np
from picamera2 import Picamera2

CAMERA_INDEX = 0

LABEL = "BALLE ROUGE DETECTEE"
LABEL_COLOR = (0, 255, 0)
BOX_COLOR = (0, 255, 0)


def detect_red_balls(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    mask1 = cv2.inRange(hsv, np.array((0, 80, 80)), np.array((10, 255, 255)))
    mask2 = cv2.inRange(hsv, np.array((170, 80, 80)), np.array((180, 255, 255)))
    mask = cv2.bitwise_or(mask1, mask2)

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    balls = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 200:
            continue
        x, y, w, h = cv2.boundingRect(c)
        balls.append((x, y, w, h))
    return balls


def annotate(frame, balls):
    if not balls:
        return frame
    x, y, w, h = max(balls, key=lambda b: b[2] * b[3])
    cv2.rectangle(frame, (x, y), (x + w, y + h), BOX_COLOR, 3)
    (tw, th), _ = cv2.getTextSize(LABEL, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
    cv2.rectangle(frame, (x, y - th - 12), (x + tw + 12, y), BOX_COLOR, -1)
    cv2.putText(
        frame,
        LABEL,
        (x + 6, y - 6),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return frame


def main():
    info = Picamera2.global_camera_info()
    print(f"{len(info)} camera(s) détectée(s)")
    if not info:
        print("Erreur: aucune caméra détectée. Vérifiez le câble CSI et l'alimentation.")
        return
    if CAMERA_INDEX >= len(info):
        print(f"Erreur: index de caméra {CAMERA_INDEX} invalide (0 à {len(info)-1})")
        return

    print(f"Utilisation de la caméra: {info[CAMERA_INDEX]['Model']}")
    picam2 = Picamera2(CAMERA_INDEX)
    config = picam2.create_preview_configuration()
    picam2.configure(config)
    picam2.start()

    print("Appuyez sur 'q' pour quitter")

    try:
        while True:
            frame = picam2.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            balls = detect_red_balls(frame)
            frame = annotate(frame, balls)
            cv2.imshow("Camera 1 - Live", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        picam2.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()