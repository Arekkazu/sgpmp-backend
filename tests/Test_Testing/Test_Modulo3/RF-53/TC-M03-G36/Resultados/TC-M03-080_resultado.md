# TC-M03-080 — resultado de ejecución / bloqueo

Fecha de documentación: 2026-10-25. Rama `laura`, commit `7292096f`.

## 1. ID y nombre

- **ID:** TC-M03-080  
- **Grupo:** G36  
- **Nombre:** medición válida **sin conectividad** — clasificación local y persistencia en buffer del nodo

## 2. RF y caso de uso

Script: **RF-55.1** (+ buffer **RF-54** / AIOT). CU-02. No se reasignó.

## 3. Objetivo y alcance

Clasificación local sin red HTTP del backend; persistencia en buffer del **nodo**, no `almacenado_buffer` del backend.

## 4. Precondiciones y datos

Conectividad del nodo en off. No hay mock de nodo Edge. Sin credenciales.

## 5. Pasos

Inspección + log pytest previo. **No** se reejecutó G36 el 2026-10-25 (evita sobrescribir `Resultados/TC-M03-G36.*`).

## 6. Resultado esperado

Clasificación local y dato en buffer del dispositivo; independencia del HTTP Dev.

## 7. Resultado obtenido

`test_tc_m03_080_medicion_valida_sin_conectividad SKIPPED`. El script anota que `SqlAlchemyEventoEdgeRepository.guardar` pone `almacenado_buffer` cuando el backend **ya recibió** el evento; eso no demuestra buffer local sin red.

## 8. Estado final

**BLOQUEADO** (SKIPPED en runner). Dependencia de firmware RF-54/RF-55.

## 9. Herramienta, comando, fecha y entorno

pytest 9.0.3, Python 3.13.7, Windows 11. Log previo: `TC-M03-G36-pytest.txt`. Script líneas 327–335.

## 10. Evidencias

- `Resultados/TC-M03-G36-pytest.txt`  
- `Resultados/evidencias_2026-10-25/copia-TC-M03-G36-pytest.txt`  
- `test_tc_m03_g36.py` 327–335

## 11. Siguiente acción

Confirmar con equipo AIOT disponibilidad de buffer local y mock de conectividad. Criterio de desbloqueo: medición clasificada en el nodo con red cortada y evidencia de cola local.
