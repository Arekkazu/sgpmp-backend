# TC-M03-111

Solo este caso (único nodo de G54). Convención Markdown.

## Identificador y nombre

- **ID:** TC-M03-111  
- **Grupo:** TC-M03-G54  
- **Función:** `test_tc_m03_111_campos_de_regla_en_evento_edge`  
- **Archivo:** `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G54/test_tc_m03_g54.py` líneas 18–22  
- **Nombre:** evento `DESVIACION_COMPUESTA` generado en Edge incluye `regla_aplicada`, `nombre_regla` y `version_regla`

## RF y caso de uso

**RF-55.2 / CU-02.** El script: copiar `metadata_edge` en RF-56 (G59) **no** genera esos campos. No se reasignó el RF.

## Objetivo y precondiciones

El nodo emite trazabilidad de regla junto con la desviación compuesta.  
`localizar_motor_edge()` → `None`. El test llama `skip_sin_motor_edge`.  
`RecibirEventoEdgeDTO` tiene `metadata_edge: Optional[dict]` genérico; no hay campos dedicados `regla_aplicada` / `nombre_regla` en el DTO de evento. `version_regla` aparece en entidades de alerta M03 (`alerta.py` / `regla_alerta_model.py`), no como emisión Edge de este CA.

## Datos de prueba

Ningún evento de nodo. Sin credenciales.

## Herramienta y comando

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G54/test_tc_m03_g54.py::test_tc_m03_111_campos_de_regla_en_evento_edge
```

Sin MQTT, PostgreSQL ni POST.

## Resultado esperado

`DESVIACION_COMPUESTA` con los tres campos emitidos **por el nodo**.

## Resultado obtenido (runner)

**SKIPPED.** `rf55_preparacion.py:62`.

- Inicio: 2026-10-25T17:32:03.467985-05:00  
- Fin: 2026-10-25T17:32:04.585985-05:00  
- Proceso: 1.118 s  
- pytest: **1 skipped in 0.08s**  
- **EXIT=0** (omitido, no PASSED)

## Estado funcional

**BLOQUEADO.** Falta motor/firmware que emita los campos. No hay evidencia de un resultado incorrecto del nodo; no se declara defecto funcional confirmado.

## Evidencias

- `evidencias/pytest.txt`  
- `evidencias/pytest.html`  
- `evidencias/pytest.xml`

## Dependencias y siguiente acción

- **IoT/AIOT:** incluir `regla_aplicada`, `nombre_regla`, `version_regla` en el evento compuesto.  
- **Backend:** no tratar `metadata_edge` opaco ni `version_regla` de alertas como este CA.  
- **QA:** contrato exacto de nombres de campo vs DTO.
