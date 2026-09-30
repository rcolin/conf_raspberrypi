# Installer un LLM local (SLM) sur Raspberry Pi 5

> Guide d'installation autonome et reproductible. Objectif : faire tourner un Small Language Model **100 % en local, hors-ligne, sans GPU**, exposé via une **API compatible OpenAI** sur `http://127.0.0.1:8080`. Conçu pour être identique sur chaque Raspberry de l'équipe (DevDay iRobot), afin que tous les robots utilisent le même modèle et le même contrat d'API.

---

## 0. Principe et prérequis

Le moteur d'inférence est **llama.cpp** (C++, optimisé CPU). Il charge un modèle au format **GGUF** (quantifié) et expose un serveur HTTP `llama-server` parlant le protocole OpenAI (`/v1/chat/completions`). Aucun accès Internet n'est requis une fois le modèle téléchargé.

Prérequis :
- Raspberry Pi 5, **Raspberry Pi OS 64-bit (Bookworm)**.
- ~6 Go d'espace disque libre (compilation + modèle).
- Accès terminal (SSH ou local).
- Une connexion Internet **uniquement** pour l'installation (compilation + téléchargement du modèle).

Convention : dans ce guide, remplacer `<USER>` par votre nom d'utilisateur (obtenu avec `whoami`). Les chemins sont sous `/home/<USER>`.

---

## 1. Paquets système

```bash
sudo apt update
sudo apt install -y build-essential cmake git libcurl4-openssl-dev
```

`build-essential` + `cmake` compilent llama.cpp ; `libcurl` permet le téléchargement direct de modèles.

---

## 2. Compiler llama.cpp

```bash
cd ~
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build
cmake --build build --config Release -j$(nproc)
```

La compilation prend quelques minutes sur Pi 5 (`-j$(nproc)` utilise les 4 cœurs). À la fin, le binaire est ici :
```
~/llama.cpp/build/bin/llama-server
```
Vérifier :
```bash
~/llama.cpp/build/bin/llama-server --version
```

---

## 3. Choisir et télécharger le modèle (GGUF)

Le choix du modèle est un **compromis vitesse / qualité** sur CPU. Débits indicatifs sur Pi 5 (sans accélérateur) :

| Modèle | Taille | Vitesse Pi 5 (CPU) | Qualité | Licence | Usage conseillé |
|---|---|---|---|---|---|
| **Qwen 2.5 1.5B** | 1.5B | ~8-12 tok/s | Correcte | Apache 2.0 | Robot / temps réel, licence propre |
| **Gemma 2 2B** | 2B | ~6-8 tok/s | Bonne | Gemma (permissive) | Meilleur équilibre vitesse/qualité |
| **Qwen 2.5 3B** | 3B | ~3-5 tok/s | Très bonne | Qwen (permissive) | Assistant conversationnel, qualité |
| **Phi-4-mini** | 3.8B | ~2-4 tok/s | Excellente (raisonnement) | MIT | Raisonnement, licence propre, plus lent |

**Recommandation DevDay (robot, latence critique) : Qwen 2.5 1.5B** — réactif et licence Apache 2.0. Pour un assistant conversationnel, Qwen 2.5 3B ou Gemma 2 2B. **L'équipe doit choisir UN modèle commun** pour la cohérence des robots.

Téléchargement (exemple avec les deux modèles recommandés — n'en prendre qu'un) :

```bash
mkdir -p ~/models
cd ~/models

# Option A — Qwen 2.5 1.5B (rapide, Apache 2.0) :
curl -L --progress-bar -o qwen2.5-1.5b-instruct-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"

# Option B — Qwen 2.5 3B (qualité) :
curl -L --progress-bar -o qwen2.5-3b-instruct-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
```

Vérifier la taille (doit être ~1-2 Go, non nulle) :
```bash
ls -lh ~/models/*.gguf
```

Note sur la quantification : **Q4_K_M** est le bon défaut (4 bits, équilibre taille/vitesse/qualité). Q5_K_M est un peu plus précis mais plus lent ; Q8 est inutilement lourd sur Pi.

---

## 4. Créer le lanceur

Un script unique qui démarre le serveur avec les bons réglages. Adapter la ligne `-m` au modèle choisi.

```bash
sudo tee /usr/local/bin/llm-server > /dev/null <<'EOF'
#!/usr/bin/env bash
exec /home/<USER>/llama.cpp/build/bin/llama-server \
    -m /home/<USER>/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    --host 127.0.0.1 --port 8080 \
    --ctx-size 2048 --threads 4 --parallel 1 \
    --batch-size 512
EOF
sudo chmod +x /usr/local/bin/llm-server
```

Remplacer `<USER>` par votre utilisateur dans les deux chemins. Réglages :
- `--ctx-size 2048` : fenêtre de contexte réduite = plus rapide (suffisant pour du dialogue court ou des commandes robot).
- `--threads 4` : les 4 cœurs du Pi 5.
- `--parallel 1` : une requête à la fois (un robot = un client).
- `--batch-size 512` : traitement du prompt plus rapide.

---

## 5. Test manuel

Lancer le serveur au premier plan pour vérifier :
```bash
/usr/local/bin/llm-server
```
Attendre le message `model loaded` puis `listening on http://127.0.0.1:8080`. Laisser tourner, ouvrir un **second terminal** et tester :
```bash
curl http://127.0.0.1:8080/v1/models
```
Réponse JSON avec le chemin du `.gguf` = serveur OK. Puis un vrai échange :
```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Dis bonjour en une phrase."}]}'
```
Une réponse générée = le LLM fonctionne. Revenir au premier terminal et faire **Ctrl+C** pour arrêter (on va l'automatiser).

---

## 6. Démarrage automatique (service systemd)

Pour que le LLM démarre seul au boot, sans intervention.

```bash
sudo tee /etc/systemd/system/llm.service > /dev/null <<'EOF'
[Unit]
Description=LLM local (llama-server, API OpenAI :8080)
After=network.target

[Service]
Type=simple
User=<USER>
ExecStart=/usr/local/bin/llm-server
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

**Important** : remplacer `<USER>` par votre utilisateur (ligne `User=`). Un mauvais utilisateur donne l'erreur `status=217/USER` (voir Dépannage). Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable llm.service
sudo systemctl start llm.service
sudo systemctl status llm.service --no-pager
```

Attendu : `active (running)`. Le modèle met ~20-30 s à charger en RAM au démarrage.

---

## 7. Utiliser l'API

L'API est compatible OpenAI, donc utilisable depuis n'importe quel langage. Exemple Python (avec `requests`) :

```python
import requests

def ask(prompt, system="Reponds en une phrase."):
    r = requests.post(
        "http://127.0.0.1:8080/v1/chat/completions",
        json={
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 150,
        },
        timeout=120,
    )
    return r.json()["choices"][0]["message"]["content"].strip()

print(ask("Quelle est la capitale de la France ?"))
```

Le même endpoint sert pour l'assistant vocal **et** pour le mode robot (commandes d'action) : seuls le prompt système et `max_tokens` changent.

---

## 8. Réglages de performance (CPU Pi 5)

Le débit est plafonné par le CPU : ~5-12 tok/s selon le modèle. Leviers, du plus efficace au moins :

1. **Raccourcir les réponses** : `max_tokens` bas (40 pour des commandes robot, 150 pour du dialogue) + prompt « réponds en une phrase ». C'est le plus gros gain, car la génération est mot à mot.
2. **Modèle plus petit** : passer d'un 3B à un 1.5B double quasiment la vitesse.
3. **Contexte réduit** : `--ctx-size 2048` (voire 1024 pour des commandes courtes).
4. **Garder le service actif** : le modèle reste chargé en RAM, seul le premier appel après boot est lent.

Accélération matérielle (au-delà du CPU) : le **Raspberry Pi AI HAT+ 2** (Hailo) permet des débits nettement supérieurs, à envisager si le temps réel devient critique. Non couvert par ce guide.

---

## 9. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `status=217/USER` au démarrage du service | `User=` pointe un utilisateur inexistant | Mettre le bon utilisateur (`whoami`), `daemon-reload`, `restart` |
| `curl` renvoie `{"...":"Loading model",...503}` | Modèle en cours de chargement en RAM | Attendre 20-30 s et refaire ; suivre avec `journalctl -u llm.service -f` (chercher `model loaded`) |
| `llama-server: command not found` | Chemin du binaire incorrect | Vérifier `~/llama.cpp/build/bin/llama-server` et le chemin dans le lanceur |
| Réponses très lentes | Modèle trop gros / réponses longues | Modèle plus petit + `max_tokens` bas + `ctx-size` réduit (section 8) |
| Le modèle se dit « Claude » ou « ChatGPT » | Confusion d'identité du modèle (normal) | Fixer l'identité dans le prompt système (« Tu es X, tu n'es pas Claude ») |
| Compilation échoue (mémoire) | Trop de threads en parallèle | Recompiler avec moins de threads : `cmake --build build -j2` |

Commandes de gestion du service :
```bash
sudo systemctl status llm.service --no-pager    # état
sudo systemctl restart llm.service              # redémarrer (après changement de modèle)
sudo systemctl stop llm.service                 # arrêter
journalctl -u llm.service -f                     # logs en direct (Ctrl+C pour quitter)
```

---

## 10. Changer de modèle

1. Télécharger le nouveau `.gguf` dans `~/models` (section 3).
2. Modifier la ligne `-m` de `/usr/local/bin/llm-server` (`sudo nano /usr/local/bin/llm-server`).
3. `sudo systemctl restart llm.service`.
4. Vérifier avec `curl http://127.0.0.1:8080/v1/models`.

---

## Récapitulatif — contrat commun pour l'équipe DevDay

Pour que tous les robots soient interopérables, figer ensemble :
- **Même modèle** (ex. Qwen 2.5 1.5B Q4_K_M) sur tous les Pi.
- **Même endpoint** : `http://127.0.0.1:8080/v1/chat/completions` (API OpenAI locale).
- **Mêmes réglages** : `ctx-size 2048`, `threads 4`, `parallel 1`.
- **Service `llm.service`** actif au boot sur chaque robot.

Le LLM est l'**interprète d'intention** (langage → commande), pas le pilote spatial. La localisation (vision/ArUco) et la logique de mouvement sont gérées ailleurs.

---

*Guide reproductible — installation d'un SLM local sur Raspberry Pi 5, sans GPU.*
