# TC-M03-089

Solo este caso. Convención Markdown (Módulo 3 no usa `.docx`).

## Identificador y nombre

- **ID:** TC-M03-089 (grupo G46)  
- **Función:** `test_tc_m03_089_max_severidad_entre_niveles_edge`  
- **Archivo:** `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G46/test_tc_m03_g46.py` líneas 19–25  
- **Nombre:** si la severidad de RF-55.1 (simple) y RF-55.2 (compuesto) difieren, el evento en el **nodo** lleva el máximo (`LEVE` < `MODERADO` < `CRITICO`)

## RF y caso de uso

Script: **RF-55.1 / RF-55.2 / CU-02**. Copiar `severidad` ya asignada en RF-56 **no** cubre este cálculo. No se reasignó el RF. Matriz de diseño no versionada en `Test_Modulo3/`.

## Objetivo y precondiciones

Evaluar ambos niveles en el firmware y consolidar la mayor severidad.  
Precondiciones no disponibles: motor Edge que calcule simple y compuesto. `localizar_motor_edge()` retorna `None`.

## Datos de prueba

Ninguno aplicado. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g46.py::test_tc_m03_089_max_severidad_entre_niveles_edge
```

Skip local (`skip_sin_motor_edge`). Sin MQTT, PostgreSQL ni POST.

## Resultado esperado

Evento consolidado en el nodo con `max(severidad_simple, severidad_compuesta)`.

## Resultado obtenido (runner)

**SKIPPED.** `rf55_preparacion.py:62`.

- Inicio: 2026-10-25T16:17:19.586351-05:00  
- Fin: 2026-10-25T16:17:20.712301-05:00  
- pytest: **1 skipped in 0.08s**  
- **EXIT=0** (omitido, no PASSED)

## Estado funcional

**BLOQUEADO.** No es defecto funcional confirmado: falta hardware/firmware. No es PASSED por EXIT=0.

## Evidencias

- `evidencias/pytest.txt`  
- `evidencias/pytest.html`  
- `evidencias/pytest.xml`

## Dependencias y siguiente acción

- **IoT/AIOT:** max de severidad entre niveles en el nodo.  
- **Backend:** recepción RF-56 de `severidad` ya calculada no sustituye este CA.  
- **QA:** confirmar ejemplos de matriz simple vs compuesto.
