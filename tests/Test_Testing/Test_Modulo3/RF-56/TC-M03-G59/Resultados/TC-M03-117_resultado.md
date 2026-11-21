# TC-M03-117 (tramo ERROR_CONFIGURACION) — resultado

Fecha de esta corrida: 2026-10-25T15:23:33-05:00. Distinta de la previa de 1.03s.

## 1. ID y nombre

**TC-M03-117** — recepción RF-56.  
Función ejecutada: `test_tc_m03_117_error_configuracion_guarda_evento_sin_paquete`.  
Otras funciones G59 **no** se reejecutaron en este lote.

## 2. RF y CU

**RF-56 / CU-02.** No es emisión Edge (G38).

## 3. Objetivo

Dado un evento **ya** clasificado `ERROR_CONFIGURACION`, guardar el evento, **no** crear paquete, **no** llamar al motor.

## 4. Precondiciones

Dobles `recibir_use_case()` / `dto_evento_edge()` en `rf56_dobles.py`. `SesionNula`. Sin PostgreSQL.

## 5. Pasos

pytest `--noconftest` sobre esa función, lote de 7.

## 6–7. Esperado vs obtenido

Esperado: evento persistido en memoria, `paquete_inferencia_estado is None`, repos de paquete y motor vacíos. Obtenido: **PASSED**.

## 8. Estado

**PASSED** este tramo unitario. **No** aprueba TC-M03-083.

## 9. Entorno

7 passed in 0.98s, EXIT=0, Python 3.13.7.

## 10. Evidencias

`Resultados/evidencias/pytest-unitarios-rf56-7-2026-10-25.log` (y html/xml en G55 evidencias).

## 11. Limitaciones

Memoria ≠ PostgreSQL. GET HTTP de paquete sigue skip en el archivo (`test_tc_m03_117_consulta_http_por_id_paquete`).
