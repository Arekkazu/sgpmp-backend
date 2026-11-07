# TC-M03-095

Solo este caso.

## Identificador y nombre

- **ID:** TC-M03-095  
- **Nodo:** `test_error_configuracion_en_edge[TC-M03-095-escenario1]`  
- **Archivo:** `test_tc_m03_g38.py` líneas 28–35 y 47–52  
- **Nombre:** `umbral_min=0` o `umbral_max=0` → `ERROR_CONFIGURACION`; no división por cero

## RF y caso de uso

RF-55.1 / CU-02.

## Objetivo y precondiciones

Firmware trata 0 como error de configuración. Precondición: umbral en 0 y medición válida. Motor Edge ausente.

## Datos de prueba

Ninguno. Sin credenciales.

## Herramienta y comando

Corrida individual:

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g38.py::test_error_configuracion_en_edge[TC-M03-095-escenario1]
```

## Fecha, duración y código de salida

- 2026-10-25T15:39:06.207094-05:00 → 15:39:07.384070-05:00  
- Proceso 1.177 s; pytest **1 skipped in 0.11s**; EXIT=0

## Resultado esperado

`ERROR_CONFIGURACION` en el nodo, sin crash por división.

## Resultado obtenido

SKIPPED (`rf55_preparacion.py:62`). No hay evidencia de umbral 0 en firmware.

## Estado

**BLOQUEADO** (SKIPPED). Clasificación/validación de umbral 0 en Edge no verificada.

## Evidencias

- `evidencias/pytest.txt`  
- `evidencias/pytest.html`  
- `evidencias/pytest.xml`

## Siguiente acción

Nodo o simulador con umbral 0. Equipo AIOT. No hay test Dev equivalente.

---

## Reintento 2026-10-29 (TEST + firmware real)

- **Tipo:** integración MQTT / E2E **no iniciada**.
- **Diferencia matriz vs firmware (no se cambió el RF):** la matriz dice umbral 0 → `ERROR_CONFIGURACION`. El contrato `develop` parte el caso: **E2** min=max=0 ACK ERROR; **E3** banda `precaucion` ancho 0 ACK ERROR; **E4** límite 0 con bandas de ancho > 0 es **válido** (T=9 → `DESVIACION_SIMPLE` CRITICO). E4 **no** se marcaría FALLIDO por usar cero.
- **Firmware / Pi:** igual que 083 (`main` local sin clasificador; `e618a75` no instalado).
- **Obtenido:** ningún ACK ni evento. Sin prueba de división por cero en runtime (proceso Edge no arrancó).
- **Estado:** **BLOQUEADO** / **NO EJECUTADO** (E2, E3, E4).
- **Evidencia:** `../evidencias/run-2026-10-29/PRECONDICION_ENTORNO.md`; `../INFORME_TC-M03-G38_2026-10-29.md`.
