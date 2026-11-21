# TC-M03-081

Solo este caso.

## Identificador y nombre

- **ID:** TC-M03-081 (G45)  
- **Función:** `test_tc_m03_081_parser_edge_dato_invalido`  
- **Archivo:** `test_tc_m03_g45.py` líneas 17–21  
- **Nombre:** parser **Edge**: valor nulo o malformado → log de descarte, **sin clasificación falsa**

## RF y caso de uso

RF-55.1 / CU-02. El script afirma que el rechazo Pydantic de valor no numérico en Dev es **G58 (DTO), no este parser**. No se reasignó.

## Objetivo y precondiciones

El nodo descarta dato inválido y no emite `NORMAL`/`DESVIACION_*` inventados. Falta parser/firmware Edge.

## Datos de prueba

Ninguno enviado al dispositivo. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g45.py::test_tc_m03_081_parser_edge_dato_invalido
```

No se ejecutó `test_tc_m03_114_dto_rechaza_valor_no_numerico` como si fuera este CA.

## Resultado esperado / obtenido

Esperado: descarte y log en el nodo. Obtenido: SKIPPED (`rf55_preparacion.py:62`).

- 2026-10-25T15:46:09.907556-05:00 → 15:46:11.009170-05:00  
- Proceso 1.102 s; pytest **1 skipped in 0.08s**; EXIT=0  

## Estado

**BLOQUEADO** (SKIPPED). Un 422/ValidationError de FastAPI no sustituye el parser del firmware.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Siguiente acción

AIOT: nulo y formato inválido en el bus del sensor (temp/humedad/SpO2/acelerómetro). Criterio: no hay evento clasificado falso y hay log de descarte en el nodo.
