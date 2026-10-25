# test_tc_m03_114_dto_acepta_clasificaciones_del_contrato[NORMAL]

Identificación **original pytest**. Pertenece al subcaso de script TC-M03-114 (RF-56). **No** es TC-M03-083 ni clasificación Edge.

## Identificador y nombre

- **Nodo:** `test_tc_m03_114_dto_acepta_clasificaciones_del_contrato[NORMAL]`  
- **Archivo:** `test_tc_m03_g58.py` líneas 83–89  
- **Nombre:** DTO `RecibirEventoEdgeDTO` acepta `clasificacion_rf55=NORMAL`

## RF y caso de uso

RF-56 / CU-02. Validación Pydantic in-process.

## Objetivo y precondiciones

`model_validate` de payload `_base(clasificacion_rf55="NORMAL", severidad=None)` no lanza error y conserva el literal.

## Datos de prueba

`device_id=1`, `sensor_id=1`, `access_key="k"`, una variable `TEMPERATURA_AMBIENTAL` Decimal 20. Sin credenciales reales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v --tb=short
  tests/.../test_tc_m03_g58.py::test_tc_m03_114_dto_acepta_clasificaciones_del_contrato[NORMAL]
```

Corrida **individual** 2026-10-25. Distinta del lote histórico 7 passed in 1.03s y del lote 7 passed in 0.98s.

## Fecha, duración y código de salida

- 2026-10-25T15:39:09.787194-05:00 → 15:39:11.623800-05:00  
- Proceso 1.837 s; pytest **1 passed in 0.65s**; EXIT=0

## Resultado esperado / obtenido

`dto.clasificacion_rf55 == "NORMAL"`. Obtenido: PASSED.

## Estado

**PASSED** (unitario DTO). No aprueba RF-55.1.

## Evidencias

- `evidencias/pytest.txt`  
- `evidencias/pytest.html`  
- `evidencias/pytest.xml`

## Siguiente acción

Ninguna para este nodo. G38 sigue independiente.
