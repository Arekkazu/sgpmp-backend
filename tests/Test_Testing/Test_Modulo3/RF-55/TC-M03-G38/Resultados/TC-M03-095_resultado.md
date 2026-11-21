# TC-M03-095 — resultado

Fecha: 2026-10-25. Rama `laura` @ `7292096f`.

## 1. ID y nombre

**TC-M03-095** (G38). Umbral mínimo o máximo = 0 → `ERROR_CONFIGURACION`; no división por cero.

## 2. RF y CU

**RF-55.1 / CU-02.** No hay test Dev de división por cero en umbrales del nodo.

## 3. Objetivo

Firmware trata 0 como error de configuración, no como rango válido.

## 4. Precondiciones

`umbral_min=0` o `umbral_max=0`; medición válida. Sin credenciales.

## 5. Pasos

Misma corrida pytest G38 que TC-M03-083 (`-rs`). Skip en `rf55_preparacion.py:62`.

## 6–7. Esperado vs obtenido

Esperado: `ERROR_CONFIGURACION` en el nodo, sin crash por división. Obtenido: SKIPPED. No hay evidencia de firmware.

## 8. Estado

**BLOQUEADO** (SKIPPED). Unitarios G58/G59 **no** cubren umbral 0.

## 9. Entorno

pytest 9.0.3, Python 3.13.7, `--noconftest`. 3 skipped in 0.07s (grupo).

## 10. Evidencias

- `Resultados/evidencias/pytest-g38-2026-10-25.log`  
- `test_tc_m03_g38.py` escenario TC-M03-095 (líneas 28–35, 47–52)

## 11. Desbloqueo

Nodo o simulador con umbral 0. Equipo AIOT. No hay prueba unitaria backend equivalente.

## 12. Reintento 2026-10-29

**BLOQUEADO / NO EJECUTADO** (E2, E3, E4). E4 no se trataría como fallo por límite 0. Ver `INFORME_TC-M03-G38_2026-10-29.md`.
