# TC-M03-114 (tramo DTO) — resultado de las 4 parametrizaciones ejecutadas

Fecha de **esta** corrida: 2026-10-25T15:23:33 a 15:23:36-05:00. Distinta de la previa comunicada (7 passed in 1.03s).

## 1. ID y nombre

**TC-M03-114** — contrato DTO `RecibirEventoEdgeDTO`.  
Función ejecutada: `test_tc_m03_114_dto_acepta_clasificaciones_del_contrato` (4 valores).  
**No** se ejecutaron en esta corrida: `test_tc_m03_114_dto_rechaza_*` ni el skip E5/M04.

## 2. RF y CU

**RF-56 / CU-02.** No es RF-55.1 ni G38.

## 3. Objetivo y alcance

El DTO Dev acepta `NORMAL`, `DESVIACION_SIMPLE`, `DESVIACION_COMPUESTA`, `ERROR_CONFIGURACION`. Alcance: validación Pydantic in-process. No clasifica mediciones.

## 4. Precondiciones

Payload mínimo en memoria (`_base()`). Sin red. `severidad=None` en esta función.

## 5. Pasos

```
python -m pytest --noconftest -p no:cacheprovider -v --tb=short -ra
  tests/.../test_tc_m03_g58.py::test_tc_m03_114_dto_acepta_clasificaciones_del_contrato
```

junto con las otras tres funciones del lote de 7.

## 6. Resultado esperado

`dto.clasificacion_rf55` igual al literal del parámetro.

## 7. Resultado obtenido

Cuatro PASSED: `[NORMAL]`, `[DESVIACION_SIMPLE]`, `[DESVIACION_COMPUESTA]`, `[ERROR_CONFIGURACION]`.

## 8. Estado

**PASSED** para este tramo DTO.  
G38 / TC-M03-083/095/122 siguen **BLOQUEADOS**. El skip `test_tc_m03_114_rechazo_esquema_por_m04` **no** forma parte de esta corrida.

## 9. Entorno

pytest 9.0.3, Python 3.13.7, lote **7 passed in 0.98s**, EXIT=0.

## 10. Evidencias

- `Resultados/evidencias/pytest-unitarios-rf56-7-2026-10-25.log`  
- `../TC-M03-G55/Resultados/evidencias/pytest-unitarios-rf56-7-2026-10-25.html`  
- `../TC-M03-G55/Resultados/evidencias/pytest-unitarios-rf56-7-2026-10-25.xml`

## 11. Limitaciones

No prueba umbrales Edge. Tramo E5/M04 no ejecutado (sigue skip en el archivo).
