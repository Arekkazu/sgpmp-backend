# Hallazgo de alcance — TC-M04-004 (G042)

**No es incidencia oficial.** No existe `INC-M04-*` en el repositorio. No se inventa ID.

## Identificador y título

Propuesta de registro: hallazgo de trazabilidad **TC-M04-004 / G042** — pesos Wfs/Wfa/Wfd vs `w_factor_*` en el motor.

## Grupo, caso y RF

G042, TC-M04-004. RF-65 **no acreditado** como dueño de la regla de rangos individuales. Código actual vive en el flujo CU-02 / `ConfigurarMotorUseCase`.

## Estado anterior → ahora

Matriz 2026-10-19: subcaso **FAIL** (rango 0–1 no implementado).  
2026-10-25: pytest de caracterización **PASSED**; clasificación **hallazgo de alcance** (sin defecto RF-65 confirmado).

## Descripción y esperado (matriz)

La matriz nombra pesos Wfs, Wfa, Wfd y rango individual 0–1. La ficha RF-65 no está en este repo.

## Observado

Suma = 1.0 sí se valida (`PESOS_CONTAGIO_INVALIDOS`). Rango por factor no. Pesos negativos con suma 1 se guardan en memoria.

## Severidad / prioridad

No determinadas: depende de si el dueño del requisito es RF-65, RF-68 u otro.

## Reproducción

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/Test_Testing/Test_Modulo4/RF-65/TC-M04-G042/test_tc_m04_g042.py::test_tc_m04_004_rango_individual_0_1_no_esta_en_el_use_case
```

## Evidencias

`TC-M04-004/evidencias/reeval-2026-10-25/`  
Código: `src/prediction/application/use_cases/motor_ia/configurar_motor_use_case.py` líneas del bloque “Pesos de contagio”.

## Clasificación

**Hallazgo de alcance / trazabilidad.** No defecto funcional de RF-65.

## Acción y cierre

Localizar ficha versionada que defina Wfs/Wfa/Wfd o `w_factor_*`. Si es RF-68, no mezclar con RF-65. Cierre: decisión de analista + ficha citada.
