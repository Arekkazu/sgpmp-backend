# TC-M03-083

Solo este caso. Convención Markdown (sin `.docx` en Módulo 3).

## Identificador y nombre

- **ID:** TC-M03-083  
- **Nodo pytest:** `test_error_configuracion_en_edge[TC-M03-083-escenario0]`  
- **Archivo:** `test_tc_m03_g38.py` (escenario líneas 20–26; skip 47–52)  
- **Nombre:** umbrales `umbral_min` y `umbral_max` no configurados en el nodo → `ERROR_CONFIGURACION`

## RF y caso de uso

RF-55.1 / CU-02. La recepción Dev de un código ya clasificado no es este caso.

## Objetivo y precondiciones

El nodo emite `ERROR_CONFIGURACION` si faltan umbrales; no bloquea mediciones siguientes.

Precondición: umbrales ausentes en Edge; medición válida. No hay motor Edge en este repo (`localizar_motor_edge()` → `None`).

## Datos de prueba

Ningún umbral ni medición inventados. Sin credenciales.

## Herramienta y comando

Corrida **individual** 2026-10-25 (no es el lote de 7 unitarios):

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g38.py::test_error_configuracion_en_edge[TC-M03-083-escenario0]
```

## Fecha, duración y código de salida

- Inicio: 2026-10-25T15:39:05.083451-05:00  
- Fin: 2026-10-25T15:39:06.204986-05:00  
- Duración proceso: 1.122 s; pytest: **1 skipped in 0.08s**  
- EXIT=0

## Resultado esperado

`ERROR_CONFIGURACION` originado en el firmware.

## Resultado obtenido

SKIPPED. `rf55_preparacion.py:62`: no hay motor/simulador Edge; no se usa POST `/iot/eventos-edge` como clasificador.

## Estado

**BLOQUEADO.** Runner: **SKIPPED**. No se aprueba por pruebas DTO/RF-56.

## Evidencias

- `evidencias/pytest.txt`  
- `evidencias/pytest.html`  
- `evidencias/pytest.xml`

## Incidencias y siguiente acción

Validación de umbrales ausentes en Edge no verificada. Dependencia: AIOT/firmware. Criterio: nodo sin umbrales emite `ERROR_CONFIGURACION` y sigue capturando.

---

## Reintento 2026-10-29 (TEST + firmware real)

- **Tipo:** integración MQTT / E2E **no iniciada**. No unitario, no FakeLink, no skip como aprobación.
- **Firmware comprobado:** local `main` `a90bb78` (sin clasificador). Requerido: `develop` `e618a75` / `v0.4.0-rc.2`. Pi no verificada.
- **Contrato a ejecutar (no corrido):** E1 (`casos_rf55.json`: T sin umbral + FR con umbral, 3 capturas). S8 (`humedad_suelo=99`) solo si la variable existe en catálogo TEST — **no comprobado**.
- **Esperado (firmware, no matriz recortada):** `ERROR_CONFIGURACION`, motivo `sin umbral RF-17 para la variable en este Edge`, `severidad_invalida: true`, sin campo `severidad`; FR sigue `DESVIACION_SIMPLE` MODERADO; telemetría cruda sí.
- **Obtenido:** ningún ACK, evento, log de `edge-agent` ni `id_evento`. Broker HTTP TEST `healthz` 200; MQTT TCP y seriales ausentes.
- **Estado:** **BLOQUEADO** (también **NO EJECUTADO** a nivel de escenario E1/S8).
- **Evidencia:** `../evidencias/run-2026-10-29/PRECONDICION_ENTORNO.md`; `../INFORME_TC-M03-G38_2026-10-29.md`.
