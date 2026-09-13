# Banc d'essai matériel Raspberry Pi

Dépôt de **tests unitaires du matériel** autour d'un Raspberry Pi (caméra,
audio, LEDs, GPS, assistant vocal). Le but final du projet n'est pas fixé :
chaque script vérifie qu'un composant fonctionne, de façon isolée.

| Commande | Rôle |
|---|---|
| `uv run camera-live` | affiche le flux de la caméra |
| `uv run balle-rouge` | test de traitement d'image (détection d'une balle rouge) |
| `uv run micro-test` | test des micros du HAT ReSpeaker |
| `uv run led-test` | test des LEDs du HAT ReSpeaker |
| `uv run voice-assistant` | assistant vocal local (STT vosk + LLM Ministral 3 3B) |

## Prérequis

Tout se fait sur un **Raspberry Pi 4 ou 5** (ou CM4/CM5) sous **Raspberry Pi OS
64 bits** (Debian Bookworm ou supérieur). Il faut une carte SD ≥ 16 Go, un
accès SSH, et un ordinateur pour flasher la carte.

### 1. Installer Raspberry Pi OS (64 bits)

1. Télécharger **Raspberry Pi Imager** : <https://www.raspberrypi.com/software/>
2. Lancer Imager → **Raspberry Pi OS (64-bit)**, choisir la carte SD, **Écrire**.
3. Avant d'écrire, cliquer sur ⚙ **Options** et activer **SSH** (onglet
   *Services*) ; définir un utilisateur/mot de passe dans **Général**.

> Si la carte est déjà écrite : créer un fichier vide `ssh` dans la partition `bootfs`
> de la carte.

### 2. Se connecter

```bash
ssh <user>@<adresse_ip_du_pi>      # ex. : ssh pi@192.168.1.42
```

Pour trouver l'adresse : `hostname -I` (sur le Pi avec un écran),
`ping raspberrypi.local` (mDNS), ou la liste des clients du routeur.

### 3. Mises à jour

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-picamera2 git      # picamera2 vient des dépôts Deb
```

## Matériel testé

| Composant | Référence | Notes |
|---|---|---|
| Carte | Raspberry Pi 5 8 GB | Rev 1.1 ; Pi 4 compatible |
| Caméra | InnoMaker CAM-OV5647 (OV5647) | Sans EEPROM : pas d'auto-détection fiable, forcer `dtoverlay=ov5647,cam1` si besoin |
| Audio / micros / LEDs | Keyestudio ReSpeaker 2-Mic Pi HAT V1.0 (KS0314, WM8960) | 2 micros, sortie 3,5 mm, 3 LEDs APA102, bouton GPIO17 |
| GPS/GNSS | u-blox MAX-M10S (HAT Waveshare) | GPS+GLONASS+Galileo+BeiDou, < 25 mW, UART `/dev/serial0` + PPS |
| Alimentation | Batterie Enerwow 27000 mAh | 418 g, alimente le Pi sans souci |

> La caméra OV5647 sans EEPROM n'est pas toujours auto-détectée : si `dmesg | grep ov5647`
> est vide après boot, ajouter `dtoverlay=ov5647,cam1` dans `/boot/firmware/config.txt`.

## Installation du projet

Cloner le dépôt, créer l'environnement et installer les dépendances :

```bash
git clone git@github.com:rcolin/conf_raspberrypi.git test
cd test
uv venv --system-site-packages   # requis pour accéder à picamera2 (installé via apt)
uv sync
```

> `uv` s'installe via `curl -LsSf https://astral.sh/uv/install.sh | sh`.

### ReSpeaker (micros + LEDs) — une seule fois

```bash
sudo ./install_respeaker.sh      # overlay wm8960-soundcard + SPI + état ALSA
sudo reboot
```

Vérifier : `aplay -l` / `arecord -l` doivent lister `wm8960-soundcard`.
L'état ALSA (réglages micros) est réappliqué à chaque boot par un service systemd.

### Assistant vocal (LLM local) — une seule fois

```bash
sudo ./install_llm.sh            # llama.cpp + modèle Ministral 3 3B + vosk
sudo systemctl start ministral.service
```

Le serveur LLM (`llama-server`) écoute sur `127.0.0.1:8080` (API compatible
OpenAI), modèle **Ministral 3 3B** (le plus petit LLM de chez Mistral, Apache
2.0), stocké dans `~/models/`. Test : `curl http://127.0.0.1:8080/v1/models`.

## Scripts de test

### `camera-live` — caméra
Affiche le flux en direct (fenêtre « Camera 1 - Live », touche `q` pour
quitter). Messages explicites si la caméra n'est pas détectée ou l'index invalide.

### `balle-rouge` — détection d'une balle rouge
Analyse le flux en direct : seuillage HSV (deux plages autour de la teinte du
rouge), nettoyage morphologique, extraction de contours. La plus grosse zone
rouge est encadrée en vert (« BALLE ROUGE DETECTEE »). Simple scénario de test
d'image, pas une finalité en soi.

### `micro-test` — micros ReSpeaker
Détecte la carte WM8960, affiche les **niveaux L/R en temps réel**, enregistre
5 s en WAV (16 kHz, stéréo) puis rejoue le fichier.

### `led-test` — LEDs APA102
Pilote les 3 LEDs sur `/dev/spidev0.1` (SPI0, CS1) : `static red green blue`,
`scan`, `rainbow`, `off`.

```bash
uv run led-test static red green blue
```

### `voice-assistant` — assistant vocal local
Micro → **vosk** (STT français) → `[texte]` sur stdout → **Ministral 3 3B**
(llama.cpp local) → `[réponse]` sur stdout. Tout reste sur la machine (hors
ligne). Options : `--once` (une phrase puis fin), `--no-llm` (transcription seule).

```bash
uv run voice-assistant          # écoute continue
uv run voice-assistant --once   # une phrase, idéal pour un test
```

## Dépannage

| Problème | Cause probable | Solution |
|---|---|---|
| `i2c read error ... = -121` au boot | Nappe FPC caméra inversée ou mal branchée | Refaire le câblage en vérifiant le sens de la nappe |
| `0 camera(s) détectée(s)` | Caméra clone non reconnue | Forcer `dtoverlay=ov5647,cam1` dans `config.txt` |
| `Could not find the Qt platform plugin` lors de l'affichage | OpenCV cherche Wayland | Le script force `QT_QPA_PLATFORM=xcb` automatiquement |
| `ModuleNotFoundError: No module named 'picamera2'` | venv uv sans paquets système | Recréer avec `uv venv --system-site-packages` |
| `aucune carte WM8960 détectée` | Overlay audio inactif ou pas redémarré | Vérifier `dtoverlay=wm8960-soundcard` puis `sudo reboot` |
| `impossible d'ouvrir /dev/spidev0.1` | SPI désactivé | Vérifier `dtparam=spi=on` puis `sudo reboot` |
| LEDs muettes alors que `led-test` passe | HAT mal enfoncé / alimentation | Re-enfoncer le HAT ; alimenter via Micro USB |
| `[erreur LLM] Connection refused` | Serveur LLM arrêté | `sudo systemctl start ministral.service` |
| Réponse LLM lente | Inférence CPU sur Pi | Normal : ~3-5 tok/s ; questions courtes ou `--once` |

## Structure

```
test/
├── pyproject.toml          # dépendances + commandes uv
├── install_respeaker.sh    # installation du HAT ReSpeaker
├── install_llm.sh          # installation llama.cpp + Ministral 3 3B + vosk
├── commandes.txt           # commandes sudo utiles
└── src/camera_app/
    ├── camera_live.py      # test caméra
    ├── balle_rouge.py      # détection balle rouge
    ├── micro_test.py       # test micros
    ├── led_test.py         # test LEDs
    └── voice_assistant.py  # assistant vocal local
```

Modèles et outils volumineux (hors dépôt) : `~/models/` (Ministral 3 3B GGUF
Q4_K_M, vosk-fr) et `~/tools/llama.cpp/`.

Les commandes de test sont déclarées dans `pyproject.toml`, section
`[project.scripts]`, et s'invoquent avec `uv run <commande>` depuis la racine du
projet.