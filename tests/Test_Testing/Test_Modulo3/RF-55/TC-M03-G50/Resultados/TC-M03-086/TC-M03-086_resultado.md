# TC-M03-086

Solo este caso (G50). Convención Markdown.

## Identificador y nombre

- **ID:** TC-M03-086  
- **Función:** `test_tc_m03_086_cuatro_variables_en_edge`  
- **Archivo:** `test_tc_m03_g50.py` líneas 16–20  
- **Nombre:** regla compuesta con **4 variables** → rechazo de configuración en el nodo

## RF y caso de uso

**RF-55.2 / CU-02.** Helper: `CARDINALIDAD_MAX = 3` (anotación de matriz; no se evalúa en `src/`).

## Objetivo y precondiciones

El Edge rechaza una regla con más de 3 variables correlacionadas. Motor ausente.

## Datos de prueba

Ningún payload de 4 variables se envió. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g50.py::test_tc_m03_086_cuatro_variables_en_edge
```

## Resultado esperado / obtenido

Esperado: rechazo de configuración en firmware. Obtenido: **SKIPPED**.

- 2026-10-25T16:59:49.115246-05:00 → 16:59:50.310748-05:00  
- **1 skipped in 0.08s**; EXIT=0  

## Estado funcional

**BLOQUEADO.** No es PASSED. No se demostró que el nodo acepte o rechace 4 variables.

## Evidencias

`evidencias/pytest.txt`, `pytest.html`, `pytest.xml`

## Dependencias

IoT/AIOT: tope de cardinalidad. Backend: constante solo en tests. QA: confirmar max=3.
