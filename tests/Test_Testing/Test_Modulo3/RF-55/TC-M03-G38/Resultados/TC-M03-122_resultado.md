# TC-M03-122 — resultado

Fecha: 2026-10-25. Rama `laura` @ `7292096f`.

## 1. ID y nombre

**TC-M03-122** (G38). Umbrales OK, parámetros de **severidad** ausentes; medición fuera de rango → `severidad_invalida` y envío **crudo a RF-62**.

## 2. RF y CU

**RF-55.1** (clasificación) + política **RF-62** (`apto_para_IA` / crudo). CU-02.

## 3. Objetivo

No inventar severidad en Dev; el Edge marca severidad inválida y el crudo sigue la política RF-62.

## 4. Precondiciones

Umbrales presentes; severidad no configurada; medición fuera de rango. Sin credenciales.

## 5. Pasos

Corrida G38 2026-10-25. Skip `rf55_preparacion.py:62`.

## 6–7. Esperado vs obtenido

Esperado: clasificación de error de severidad en Edge y traza RF-62. Obtenido: SKIPPED. G58 acepta `severidad=None` en el DTO Dev; **no** envía a RF-62. G57 omitió `apto_para_IA` (otro grupo).

## 8. Estado

**BLOQUEADO** (SKIPPED). Dependencia Edge **y** política RF-62.

## 9. Entorno

Misma sesión pytest G38. Exit 0.

## 10. Evidencias

- `Resultados/evidencias/pytest-g38-2026-10-25.log`  
- `test_tc_m03_g38.py` 37–43 y 47–52

## 11. Desbloqueo

Firmware + dueño RF-62. Criterio: medición fuera de rango sin parámetros de severidad no inventa categoría; hay evidencia de entrega cruda según política. G58 PASSED **no** desbloquea este caso.

## 12. Reintento 2026-10-29

**BLOQUEADO / NO EJECUTADO** (E5, E6). Ver `INFORME_TC-M03-G38_2026-10-29.md`.
