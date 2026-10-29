# TC-M03-076

Solo este caso. Convención Markdown (Módulo 3 no usa `.docx`).

## Identificador y nombre

- **ID:** TC-M03-076 (grupo G43)  
- **Función:** `test_tc_m03_076_clasificacion_normal_edge`  
- **Archivo:** `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G43/test_tc_m03_g43.py` líneas 17–22  
- **Nombre:** valor entre `umbral_min` y `umbral_max` en el **nodo** → evento `NORMAL`

## RF y caso de uso

Script y carpeta: **RF-55.1 / CU-02**. No hay matriz de diseño versionada en `Test_Modulo3/`. El script declara que recibir un DTO ya clasificado **no** cubre este grupo. No se reasignó el RF.

## Objetivo y precondiciones

Clasificar en firmware: medición dentro de rango → `NORMAL`.  
Precondiciones no disponibles: motor/simulador Edge, umbral local en el nodo, medición válida (temp/humedad/SpO2/acelerómetro; no se asumen pH/CO2).

## Datos de prueba

Ninguno aplicado. Sin credenciales. No se inventaron umbrales ni valores.

## Herramienta y comando

Corrida individual 2026-10-25 (skip local; sin MQTT, PostgreSQL ni POST):

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g43.py::test_tc_m03_076_clasificacion_normal_edge
```

## Resultado esperado

Clasificación `NORMAL` calculada en el Edge (no reenviada desde Dev).

## Resultado obtenido

SKIPPED. `rf55_preparacion.py:62`: no hay motor Edge; `RecibirEventoEdgeDTO` exige `clasificacion_rf55` ya calculada.

- Inicio: 2026-10-25T15:46:04.102032-05:00  
- Fin: 2026-10-25T15:46:05.263253-05:00  
- Proceso 1.161 s; pytest **1 skipped in 0.09s**; EXIT=0  

## Estado

**BLOQUEADO.** Runner: **SKIPPED**.  
No es PASSED por existir el DTO ni por unitarios RF-56 (p. ej. aceptación de `NORMAL` en G58).

## Evidencias

- `evidencias/pytest.txt`  
- `evidencias/pytest.html`  
- `evidencias/pytest.xml`

## Incidencias y siguiente acción

Clasificador Edge no está en este repositorio (`localizar_motor_edge()` → `None`). Equipo AIOT/firmware. Criterio: medición in-range (sensor IoT real) produce `NORMAL` en el nodo. GET healthz del broker HTTP no desbloquea este caso.
