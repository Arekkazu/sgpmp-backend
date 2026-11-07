# TC-M03-122

Solo este caso.

## Identificador y nombre

- **ID:** TC-M03-122  
- **Nodo:** `test_error_configuracion_en_edge[TC-M03-122-escenario2]`  
- **Archivo:** `test_tc_m03_g38.py` líneas 37–43 y 47–52  
- **Nombre:** umbrales OK, parámetros de severidad ausentes; medición fuera de rango → severidad inválida y crudo a RF-62

## RF y caso de uso

RF-55.1 (clasificación Edge) y política **RF-62**. CU-02.

## Objetivo y precondiciones

No inventar severidad en Dev. El Edge marca severidad inválida; el crudo sigue RF-62.

Precondiciones: umbrales presentes, severidad no configurada, medición fuera de rango. Motor Edge ausente.

## Datos de prueba

Ninguno. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g38.py::test_error_configuracion_en_edge[TC-M03-122-escenario2]
```

## Fecha, duración y código de salida

- 2026-10-25T15:39:07.387527-05:00 → 15:39:08.569316-05:00  
- Proceso 1.182 s; pytest **1 skipped in 0.09s**; EXIT=0

## Resultado esperado

Marca de severidad inválida en Edge y entrega cruda según RF-62.

## Resultado obtenido

SKIPPED (`rf55_preparacion.py:62`). No hay envío a RF-62 en esta prueba.

## Estado

**BLOQUEADO** (SKIPPED). Dependencia Edge y RF-62.

## Evidencias

- `evidencias/pytest.txt`  
- `evidencias/pytest.html`  
- `evidencias/pytest.xml`

## Siguiente acción

Firmware + dueño RF-62. Un DTO que acepte `severidad=None` no cubre este CA.

---

## Reintento 2026-10-29 (TEST + firmware real)

- **Tipo:** integración MQTT / E2E **no iniciada**. E6 exige umbral incompleto ya en `umbrales.json` del laboratorio; **no** se tocó disco de ninguna Pi.
- **Contrato:** E5 comando solo banda `normal` → `ACK_UMBRAL` ERROR. E6 umbral guardado incompleto → un `ERROR_CONFIGURACION`, `severidad_invalida: true`, sin `severidad`, sin inventar `CRITICO`; crudo en `telemetry` (RF-62).
- **Obtenido:** ningún payload MQTT ni recepción backend.
- **Estado:** **BLOQUEADO** / **NO EJECUTADO** (E5, E6).
- **Evidencia:** `../evidencias/run-2026-10-29/PRECONDICION_ENTORNO.md`; `../INFORME_TC-M03-G38_2026-10-29.md`.
