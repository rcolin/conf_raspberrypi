#!/usr/bin/env bash
#
# Installation du ReSpeaker 2-Mic Pi HAT V1.0 (KS0314, codec WM8960)
# sur Raspberry Pi 5 / Debian 13 (kernel rpi 6.x).
#
# Aucun driver n'est compilé : le kernel fournit déjà
#   - l'overlay wm8960-soundcard.dtbo
#   - le driver codec snd-soc-wm8960
#   - le machine driver simple-audio-card
# Ce script configure le device tree + les outils + l'état ALSA des micros.

set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Ce script doit être exécuté avec sudo :"
    echo "    sudo ./install_respeaker.sh"
    exit 1
fi

model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)
if [[ "${model}" != Raspberry* ]]; then
    echo "Erreur : ce script ne fonctionne que sur un Raspberry Pi."
    exit 1
fi
echo "Raspberry Pi détecté : ${model}"

CONFIG=/boot/firmware/config.txt
if [[ ! -f ${CONFIG} ]]; then
    echo "Fichier ${CONFIG} introuvable."
    exit 1
fi

add_line() {
    local entry="$1"
    if grep -qxF "$entry" "$CONFIG"; then
        echo "  déjà présent : ${entry}"
    else
        echo "$entry" >> "$CONFIG"
        echo "  ajouté      : ${entry}"
    fi
}

echo "── Configuration du device tree ──"
# L'overlay active lui-même le bus I2S (nœud i2s_clk_producer du Pi 5).
add_line "dtoverlay=wm8960-soundcard"
# SPI pour les 3 LEDs APA102 du HAT (optionnel).
add_line "dtparam=spi=on"

echo "── Installation des outils ──"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y i2c-tools alsa-utils libasound2-plugins wget

echo "── Téléchargement de l'état ALSA (réglages micros) ──"
mkdir -p /etc/wm8960-soundcard
STATE_URL="https://raw.githubusercontent.com/waveshareteam/WM8960-Audio-HAT/master/wm8960_asound.state"
if command -v wget >/dev/null 2>&1; then
    wget -qO /etc/wm8960-soundcard/wm8960_asound.state "$STATE_URL"
else
    curl -fsSL -o /etc/wm8960-soundcard/wm8960_asound.state "$STATE_URL"
fi
echo "  → /etc/wm8960-soundcard/wm8960_asound.state"

echo "── Service d'application de l'état ALSA au démarrage ──"
ALSACTL=$(command -v alsactl)
cat > /usr/local/bin/wm8960-restore.sh <<EOF
#!/usr/bin/env bash
# Attend que la carte WM8960 soit présente puis applique l'état ALSA.
for i in \$(seq 1 30); do
    if arecord -l 2>/dev/null | grep -qi 'wm8960'; then
        ${ALSACTL} --file=/etc/wm8960-soundcard/wm8960_asound.state restore 2>/dev/null || true
        exit 0
    fi
    sleep 1
done
exit 1
EOF
chmod +x /usr/local/bin/wm8960-restore.sh

cat > /etc/systemd/system/wm8960-soundcard.service <<'EOF'
[Unit]
Description=Appliquer l'etat ALSA du ReSpeaker 2-Mic HAT (WM8960)
After=sound.target
Before=pipewire.service pipewire-pulse.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/wm8960-restore.sh

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable wm8960-soundcard.service

echo
echo "────────────── Terminé ──────────────"
echo "Un redémarrage est nécessaire pour charger l'overlay."
echo
echo "Ensuite :"
echo "  1. sudo reboot"
echo "  2. aplay -l            # doit lister 'wm8960-soundcard'"
echo "  3. arecord -l          # doit lister un device de capture"
echo "  4. uv run micro-test   # test des micros avec niveaux en direct"