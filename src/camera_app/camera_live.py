import os

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import cv2
from picamera2 import Picamera2

CAMERA_INDEX = 0

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
            cv2.imshow("Camera 1 - Live", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        picam2.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()