# TC-M03-107

Solo este caso (G50).

## Identificador y nombre

- **ID:** TC-M03-107  
- **Función:** `test_tc_m03_107_una_variable_en_edge`  
- **Archivo:** `test_tc_m03_g50.py` líneas 23–27  
- **Nombre:** `variables_correlacionadas` con **1 variable** → no evalúa compuesta (E1)

## RF y caso de uso

RF-55.2 / CU-02. Helper: `CARDINALIDAD_MIN = 2`.

## Objetivo y precondiciones

No disparar desviación compuesta con una sola variable. Motor Edge ausente.

## Datos de prueba

Ninguno aplicado. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g50.py::test_tc_m03_107_una_variable_en_edge
```

## Resultado esperado / obtenido

Esperado: no evalúa regla compuesta (E1). Obtenido: **SKIPPED** (`rf55_preparacion.py:62`).

- 2026-10-25T16:59:50.312892-05:00 → 16:59:51.403737-05:00  
- **1 skipped in 0.08s**; EXIT=0  

## Estado funcional

**BLOQUEADO.**

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Dependencias

IoT/AIOT: E1 en el nodo. QA: confirmar min=2.
