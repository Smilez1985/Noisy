#!/bin/bash
# ==========================================================
# Noisy CLI - Zentrales Kommando-Interface
# Aufruf: noisy <befehl>
# Installation: install.sh verlinkt nach /usr/local/bin/noisy
# ==========================================================

APP_DIR="/home/noisy/noisy-app"
SERVICE="noisy.service"
DEBUG_FLAG="$APP_DIR/debug.flag"

# Version aus Manifest (Single Source of Truth)
if command -v jq >/dev/null 2>&1 && [ -f "$APP_DIR/manifest.json" ]; then
    VERSION=$(jq -r '.version // "unbekannt"' "$APP_DIR/manifest.json")
else
    VERSION="unbekannt"
fi

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

usage() {
    echo -e "${CYAN}${BOLD}Noisy v$VERSION - CLI${NC}"
    echo ""
    echo -e "Nutzung: ${GREEN}noisy <befehl>${NC}"
    echo ""
    echo "  restart        Noisy neu starten"
    echo "  stop           Noisy stoppen"
    echo "  start          Noisy starten"
    echo "  status         Service-Status anzeigen"
    echo "  log            Log live verfolgen"
    echo "  personality    AEI-Werte anzeigen"
    echo "  moods          Alle Moods anzeigen"
    echo "  calibrate      Raum neu kalibrieren"
    echo "  debug           Live KI-Analyse (Labels, Scores, Beat)"
    echo "  debug-on       Debug-Modus AN (Log auf SD)"
    echo "  debug-off      Debug-Modus AUS (Log in /tmp)"
    echo "  reset-pw       Web-UI Admin-Passwort zuruecksetzen (nur Passwort)"
    echo "  https on|off   Dashboard-HTTPS (Self-Signed) ein/aus"
    echo "  uninstall      Noisy deinstallieren"
    echo "  version        Version anzeigen"
    echo ""
}

case "${1}" in

    restart)
        sudo systemctl restart "$SERVICE"
        sleep 2
        if systemctl is-active --quiet "$SERVICE"; then
            echo -e "${GREEN}Noisy neu gestartet!${NC}"
        else
            echo -e "${RED}Fehler! Log pruefen: noisy log${NC}"
            journalctl -u "$SERVICE" --no-pager -n 20
        fi
        ;;

    stop)
        sudo systemctl stop "$SERVICE"
        sudo rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
        echo -e "${YELLOW}Noisy gestoppt.${NC}"
        ;;

    start)
        sudo rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
        sudo systemctl start "$SERVICE"
        sleep 2
        if systemctl is-active --quiet "$SERVICE"; then
            echo -e "${GREEN}Noisy gestartet!${NC}"
        else
            echo -e "${RED}Fehler! Log pruefen: noisy log${NC}"
            journalctl -u "$SERVICE" --no-pager -n 20
        fi
        ;;

    status)
        systemctl status "$SERVICE" --no-pager -l
        echo ""
        if [ -f "$DEBUG_FLAG" ]; then
            echo -e "Debug: ${RED}AN${NC} (Log: $APP_DIR/noisy.log)"
        else
            echo -e "Debug: ${GREEN}AUS${NC} (Log: /tmp/noisy.log)"
        fi
        ;;

    log)
        if [ -f "$DEBUG_FLAG" ]; then
            LOG_FILE="$APP_DIR/noisy.log"
        else
            LOG_FILE="/tmp/noisy.log"
        fi
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo -e "${YELLOW}Log nicht gefunden: $LOG_FILE${NC}"
            echo "Noisy laeuft vielleicht noch nicht. Versuche: noisy start"
            echo ""
            echo "Pruefe journalctl:"
            journalctl -u "$SERVICE" --no-pager -n 30
        fi
        ;;

    personality)
        python3 -c "
import json, time
try:
    d = json.load(open('$APP_DIR/personality.json'))
    age = (time.time() - d.get('birth_time', time.time())) / 86400
    total = d.get('total_interactions', 0)
    e = d.get('energy', 0.5)
    c = d.get('cheerful', 0.5)
    s = d.get('shy', 0.5)
    a = d.get('affection', 0.5)
    def bar(v):
        n = int(v * 20)
        return chr(9608) * n + chr(9617) * (20 - n)
    print()
    print('  NOISY IDENTITY')
    print('  ' + chr(9472) * 32)
    print(f'  Energy:    {e:.2f}  {bar(e)}')
    print(f'  Cheerful:  {c:.2f}  {bar(c)}')
    print(f'  Shy:       {s:.2f}  {bar(s)}')
    print(f'  Affection: {a:.2f}  {bar(a)}')
    print('  ' + chr(9472) * 32)
    print(f'  Alter: {age:.1f} Tage | Interaktionen: {total}')
    traits = {'Energy': e, 'Cheerful': c, 'Shy': s, 'Affection': a}
    print(f'  Dominant: {max(traits, key=traits.get)}')
    print()
except Exception as ex:
    print(f'Fehler: {ex}')
"
        ;;

    moods)
        python3 -c "
import sys
sys.path.insert(0, '$APP_DIR')
from moods import get_all_groups, get_group_moods, get_mood_name, is_fast_track, get_all_moods
from moods import _LABEL_MAP, _IGNORE_LABELS
from moods.musik import *; from moods.emotionen import *
from moods.koerper import *; from moods.umgebung import *; from moods.idle import *
print()
print('  NOISY MOOD REGISTRY')
print('  ' + chr(9472) * 40)
for g in get_all_groups():
    ids = get_group_moods(g)
    names = [get_mood_name(i) for i in ids]
    ft = [get_mood_name(i) for i in ids if is_fast_track(i)]
    print(f'  {g:12s}: {len(ids):2d} -> {names}')
    if ft:
        print(f'               Fast-Track: {ft}')
m = len(_LABEL_MAP); ig = len(_IGNORE_LABELS)
print('  ' + chr(9472) * 40)
print(f'  Total: {len(get_all_moods())} Moods | Labels: {m}+{ig}={m+ig}/527')
print()
"
        ;;

    calibrate)
        sudo systemctl stop "$SERVICE" 2>/dev/null
        sudo rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
        cd "$APP_DIR" && python3 noisy_calibrate.py
        sudo systemctl start "$SERVICE"
        echo -e "${GREEN}Noisy neu kalibriert und gestartet!${NC}"
        ;;

    debug)
        echo -e "${CYAN}Stoppe Noisy Service fuer Debug...${NC}"
        sudo systemctl stop "$SERVICE" 2>/dev/null
        sudo rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
        sleep 1
        cd "$APP_DIR" && python3 noisy_debug.py
        echo ""
        echo -e "${CYAN}Debug beendet. Starte Noisy wieder...${NC}"
        sudo rm -f /dev/shm/noisy_mood /dev/shm/noisy_audio
        sudo systemctl start "$SERVICE"
        sleep 2
        if systemctl is-active --quiet "$SERVICE"; then
            echo -e "${GREEN}Noisy laeuft wieder!${NC}"
        else
            echo -e "${RED}Fehler beim Neustart! Log pruefen: noisy log${NC}"
        fi
        ;;

    debug-on)
        touch "$DEBUG_FLAG"
        sudo systemctl restart "$SERVICE"
        echo -e "${RED}${BOLD}Debug-Modus AN${NC} - Log auf SD-Karte"
        echo -e "${YELLOW}Vergiss nicht: noisy debug-off${NC}"
        ;;

    debug-off)
        rm -f "$DEBUG_FLAG"
        sudo systemctl restart "$SERVICE"
        echo -e "${GREEN}Debug-Modus AUS${NC} - Log nur in /tmp"
        ;;

    reset-pw)
        echo -e "${YELLOW}Setze Web-UI Admin-Passwort zurueck (nur das Passwort,"
        echo -e "Personality/Config/Modelle bleiben unangetastet)...${NC}"
        python3 -c "
import sys
sys.path.insert(0, '$APP_DIR')
from noisy_auth import AuthManager
AuthManager().reset_password()
print('Passwort-Material geloescht.')
"
        sudo systemctl restart "$SERVICE"
        echo -e "${GREEN}Noisy neu gestartet.${NC} Beim naechsten Web-Login ein neues Passwort setzen."
        ;;

    https)
        case "${2}" in
            on|ON|an|AN)   PYVAL="True";  STATE="AN";;
            off|OFF|aus|AUS) PYVAL="False"; STATE="AUS";;
            *)
                echo -e "${YELLOW}Nutzung: noisy https on|off${NC}"
                exit 1
                ;;
        esac
        python3 -c "
import sys
sys.path.insert(0, '$APP_DIR')
from noisy_runtime import RuntimeConfig
RuntimeConfig().set_https($PYVAL)
print('HTTPS = $STATE')
"
        sudo systemctl restart "$SERVICE"
        if [ "$PYVAL" = "True" ]; then
            echo -e "${GREEN}HTTPS aktiviert.${NC} Verbinde unter https://<adresse>:8080 (Self-Signed-Warnung einmal bestaetigen)."
        else
            echo -e "${GREEN}HTTPS deaktiviert.${NC} Verbinde unter http://<adresse>:8080"
        fi
        ;;

    uninstall)
        if [ -f "$APP_DIR/uninstall.sh" ]; then
            sudo bash "$APP_DIR/uninstall.sh"
        else
            echo -e "${RED}uninstall.sh nicht gefunden!${NC}"
        fi
        ;;

    version)
        echo -e "${CYAN}Noisy v$VERSION (Orchestrator)${NC}"
        echo "  Architektur: Orchestrator -> Audio(Subprocess) + Renderer(Thread) + Input(GPIO)"
        echo "  Moods: 35 in 5 Gruppen"
        if [ -f "$APP_DIR/personality.json" ]; then
            AGE=$(python3 -c "import json,time;d=json.load(open('$APP_DIR/personality.json'));print(f'{(time.time()-d[\"birth_time\"])/86400:.1f}')" 2>/dev/null)
            echo "  Alter: ${AGE} Tage"
        fi
        ;;

    *)
        usage
        ;;
esac
