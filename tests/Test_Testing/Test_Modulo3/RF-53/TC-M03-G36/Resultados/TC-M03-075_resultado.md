# TC-M03-075 — resultado de ejecución / bloqueo

Fecha de documentación: 2026-10-25 (America/Bogota). Rama `laura`, commit `7292096f`. Evaluadora: Laura López.

## 1. ID y nombre

- **ID:** TC-M03-075  
- **Grupo:** G36 (`TC-M03-G36`)  
- **Nombre (script):** medición válida con conectividad — clasificación local RF-55.1 (`NORMAL`)  
- **Nombre (matriz QA referida en diagnóstico):** ingesta estructurada de visión (RF-53)

## 2. RF y caso de uso (matriz vigente vs script)

| Fuente | RF | CU | Alcance |
|---|---|---|---|
| Script `test_tc_m03_g36.py` (líneas 1, 29–30, 317–324) | **RF-55 / RF-55.1** | CU-02 | Procesar medición vs umbral en el **nodo Edge** |
| Pedido / matriz QA usada en diagnóstico | **RF-53** | CU-02 | Visión / `POST /iot/telemetria/vision` |

**No se reasignó el RF ni se editó el script.** Queda registrada la discrepancia.

## 3. Objetivo y alcance

Según el script: procesar una medición válida dentro de umbral local y clasificar `NORMAL`, con conectividad. El envío al backend es secundario.

Fuera de alcance de esta ejecución: clasificador firmware, POST de visión, POST `/iot/eventos-edge` como clasificador.

## 4. Precondiciones y datos

No hay dispositivo, umbral ni medición de QA autorizados en esta corrida. El script **prohíbe inventarlos**. No se usaron credenciales.

## 5. Pasos de ejecución

1. Inspección estática del código (script G36, DTO RF-56, stub M04).  
2. **No** se reejecutó pytest G36 el 2026-10-25 (el fixture de sesión reescribe `Resultados/TC-M03-G36.{json,txt,html}` ya existentes).  
3. Se recuperó el log previo `TC-M03-G36-pytest.txt`.

## 6. Resultado esperado (CA funcional)

Clasificación `NORMAL` en el nodo, tiempo de procesamiento medible, sin inventar clasificación en Dev.

## 7. Resultado obtenido (evidencia)

- Log previo: `test_tc_m03_075_medicion_valida_con_conectividad SKIPPED`.  
- Inspección: `RecibirEventoEdgeUseCase` exige `clasificacion_rf55` de entrada; no evalúa umbral.  
- `NodoEdgeStubAdapter` no clasifica.  
- Visión RF-53 existe en otro ID (`tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py`), no ligado a TC-M03-075.

## 8. Estado final

**BLOQUEADO** (también SKIPPED en el runner).  
Justificación: no hay motor/simulador Edge en este repositorio. Las pruebas unitarias RF-56 **no** cubren este CA. La discrepancia de RF no se resolvió.

## 9. Herramienta, comando, fecha y entorno

- Herramienta: pytest 9.0.3 + inspección (log previo).  
- Entorno: Windows 11, Python 3.13.7, rama `laura` @ `7292096f`.  
- Log recuperado: 3 passed, 2 skipped in 4.18s (fecha original del JSON G36: `2026-09-28T04:21:13Z`).

## 10. Evidencias (rutas relativas)

- `Resultados/TC-M03-G36-pytest.txt` (intacto en esta tarea)  
- `Resultados/evidencias_2026-10-25/copia-TC-M03-G36-pytest.txt`  
- `Resultados/evidencias_2026-10-25/NOTA_NO_REEJECUTAR_G36.md`  
- `test_tc_m03_g36.py` líneas 317–324 (`pytest.skip`)

## 11. Incidencias, limitaciones y siguiente acción

- Incidencia: matriz RF-53 visión vs script RF-55.1. Confirmar con liderazgo QA / dueño de matriz **sin cambiar archivos de diseño**.  
- Dependencia: firmware o simulador Edge (equipo AIOT). No hay compromiso fechado en este repositorio.  
- Desbloqueo: nodo o simulador que clasifique vs umbral local; entonces reejecutar G36 (aceptando que reescribirá json/txt/html) o capturar evidencia del nodo.  
- GET `/v1/healthz` del broker HTTP **no** aprueba este caso.
