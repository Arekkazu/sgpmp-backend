# TC-M03-084

Solo este caso.

## Identificador y nombre

- **ID:** TC-M03-084 (G47)  
- **Función:** `test_tc_m03_084_thi_ejemplo_matriz_en_edge`  
- **Archivo:** `test_tc_m03_g47.py` líneas 20–28  
- **Nombre:** ejemplo de matriz THI en el Edge: T=25 °C, HR=60 % → THI≈71 `NORMAL`, con `regla_aplicada`, `nombre_regla`, `version_regla`

## RF y caso de uso

**RF-55.2 / CU-02.** El script declara: la fórmula **no está** en `src/telemetry`; no se afirma que Dev calcule THI.

## Objetivo y precondiciones

Clasificar confort térmico (THI) en el nodo. Sensores IoT identificados incluyen temperatura y humedad. Falta motor Edge y fórmula en firmware (no verificada).

## Datos de prueba (literales de `THI_084`, no ejecutados en hardware)

`temperatura_c=25.0`, `humedad_pct=60.0`, `thi_aprox=71`, esperado `NORMAL`. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g47.py::test_tc_m03_084_thi_ejemplo_matriz_en_edge
```

## Resultado esperado / obtenido

Esperado: `NORMAL` + trazabilidad de regla en el nodo.  
Obtenido: **SKIPPED** (`rf55_preparacion.py:62`).

- 2026-10-25T16:17:20.715387-05:00 → 16:17:21.987113-05:00  
- **1 skipped in 0.10s**; EXIT=0  

## Estado funcional

**BLOQUEADO** (no es fallo de producto demostrado). Dev no implementa THI; el skip no prueba un cálculo incorrecto.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Dependencias

- **IoT/AIOT:** fórmula THI y metadatos de regla en el nodo.  
- **Backend:** no hay cálculo THI en `src/telemetry` (anotado en el script).  
- **QA:** confirmar fórmula de la matriz vs firmware.
