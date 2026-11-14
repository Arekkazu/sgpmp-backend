# TC-M03-083 — resultado

Fecha: 2026-10-25T15:23:36-05:00. Rama `laura` @ `7292096f`.

## 1. ID y nombre

**TC-M03-083** (G38). Umbrales `umbral_min` / `umbral_max` no configurados en el nodo → `ERROR_CONFIGURACION`.

## 2. RF y CU

**RF-55.1 / CU-02.** La recepción Dev de un `ERROR_CONFIGURACION` ya emitido es **G59 / TC-M03-117**, no este caso.

## 3. Objetivo y alcance

El nodo emite `ERROR_CONFIGURACION` si faltan umbrales; bitácora local; no bloquea mediciones siguientes. Alcance: firmware Edge. Fuera: DTO FastAPI.

## 4. Precondiciones

Umbrales ausentes en el nodo; medición válida. Sin datos inventados ni credenciales.

## 5. Pasos ejecutados

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G38/test_tc_m03_g38.py
```

El test llama `skip_sin_motor_edge` (`rf55_preparacion.py:61–67`). `localizar_motor_edge()` retorna `None`.

## 6. Resultado esperado

Clasificación `ERROR_CONFIGURACION` originada **en el Edge**.

## 7. Resultado obtenido

SKIPPED. Texto del runner: `BLOQUEADO TC-M03-083: no hay motor/simulador Edge...`

Corrida **distinta** (unitarios RF-56, 7 passed in 0.98s): `test_tc_m03_117_error_configuracion_guarda_evento_sin_paquete` PASSED. Eso prueba el **recibo Dev**, no la validación de umbrales ausentes en Edge.

## 8. Estado

**BLOQUEADO.** El runner marcó **SKIPPED**. No se cambia a PASSED por G59.

## 9. Entorno

pytest 9.0.3, Python 3.13.7, Windows 11, `--noconftest`. Exit 0 (solo skips).

## 10. Evidencias

- `Resultados/evidencias/pytest-g38-2026-10-25.log`  
- `test_tc_m03_g38.py` 47–52 (parámetro TC-M03-083)  
- `rf55_preparacion.py:62`

## 11. Desbloqueo

Dependencia: motor/simulador Edge. Confirmar con equipo **AIOT / firmware** (sin fecha comprometida aquí). Criterio: nodo sin umbrales emite `ERROR_CONFIGURACION` y sigue capturando. Relacionado Dev: TC-M03-117 (no sustituye).

## 12. Reintento 2026-10-29

**BLOQUEADO / NO EJECUTADO.** Ver `INFORME_TC-M03-G38_2026-10-29.md` y `TC-M03-083/TC-M03-083_resultado.md`.
