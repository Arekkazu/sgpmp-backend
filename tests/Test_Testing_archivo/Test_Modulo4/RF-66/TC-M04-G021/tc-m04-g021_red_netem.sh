#!/usr/bin/env bash
# TC-M04-G021 - Sincronizacion HIBRIDA: simulacion de red con netem/tc (Linux, requiere root).
# Subcaso 3 (TC-M04-15): perdida total de conectividad (ventana rutinaria 30-60 min; 24 h como job nocturno).
# Subcaso 4 (TC-M04-24): retardo forzado para superar el limite de sincronizacion (>5 s) o de desfase (>10 s).
# SCRIPT SIN EJECUTAR: ambiente de pruebas aun no listo.
#
# Uso:
#   sudo ./tc-m04-g021_red_netem.sh corte  <interfaz> <minutos>        # 100% de perdida durante N minutos y luego restaura
#   sudo ./tc-m04-g021_red_netem.sh retardo <interfaz> <ms> <minutos>  # retardo fijo (ej. 7000 -> sync > 5 s; 12000 -> desfase > 10 s)
#   sudo ./tc-m04-g021_red_netem.sh limpiar <interfaz>
# Sugerencia 24 h: sudo ./tc-m04-g021_red_netem.sh corte eth0 1440
set -euo pipefail
LOG="${LOG:-tc-m04-g021_netem.log}"
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"; }
limpiar() { tc qdisc del dev "$1" root 2>/dev/null || true; log "netem eliminado en $1 (red restaurada)"; }
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar como root (sudo)"; exit 2; }
modo="${1:-}"; IF="${2:-}"
[ -n "$modo" ] && [ -n "$IF" ] || { sed -n 2,13p "$0"; exit 2; }
case "$modo" in
  corte)
    min="${3:?minutos}"; trap 'limpiar "$IF"' EXIT INT TERM
    log "INICIO corte total en $IF por $min min (el Edge debe seguir generando resultados y encolar la sincronizacion)"
    tc qdisc add dev "$IF" root netem loss 100%
    sleep "$((min * 60))"
    log "FIN del corte: al reconectar, verificar con el caso Postman 3.2 que el historial no perdio resultados" ;;
  retardo)
    ms="${3:?ms}"; min="${4:?minutos}"; trap 'limpiar "$IF"' EXIT INT TERM
    log "INICIO retardo de ${ms} ms en $IF por $min min"
    tc qdisc add dev "$IF" root netem delay "${ms}ms"
    sleep "$((min * 60))"
    log "FIN del retardo" ;;
  limpiar) limpiar "$IF" ;;
  *) sed -n 2,13p "$0"; exit 2 ;;
esac
