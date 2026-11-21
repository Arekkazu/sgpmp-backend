# TC-M04-004

Reevaluación 2026-10-25. Hallazgo de **trazabilidad/alcance**, no defecto RF-65.

## Identificador

**TC-M04-004** (G042). Pesos `Wfs`/`Wfa`/`Wfd` vs campos `w_factor_sanitario`, `w_factor_ambiental`, `w_factor_densidad`.

## Runner

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m04_g042.py::test_tc_m04_004_pesos_validos_suma_uno
  tests/.../test_tc_m04_g042.py::test_tc_m04_004_suma_distinta_de_uno_rechaza
  tests/.../test_tc_m04_g042.py::test_tc_m04_004_rango_individual_0_1_no_esta_en_el_use_case
```

Tres nodos **PASSED**, EXIT=0.

## Qué se verificó

- Suma 0.400+0.300+0.300 = 1.000 se acepta y persiste en el doble.
- Suma 1.1 → `PESOS_CONTAGIO_INVALIDOS`; `config_version` vigente = 1.
- Peso negativo −0.100 con suma 1.0 **es aceptado** por el use case (no hay rango individual 0–1). El test caracteriza ese comportamiento; no es un FAILED de pytest.

## Dónde aparecen los campos (evidencia)

Código: `ConfigurarMotorDTO`, entidad/ORM `configuracion_motor_ia`, `ConfigurarMotorUseCase._validar_comunes` (suma = 1.0 ± 0.001, código `PESOS_CONTAGIO_INVALIDOS`).  
Docs internas: `anotaciones/modulo_4/curls_m04_cu02_configurar_motor_ia.md`, `api_reference_m04_prediccion.md`.  
**No** hay ficha RF-65 en el repositorio que nombre `Wfs`/`Wfa`/`Wfd`.  
RF-68 v1.1 en `anotaciones/implementacion_rfc006_rfc009_rfc011.md` habla de `definicion_fs` e `id_area_productiva` en riesgo de contagio y declara RF-68 **no implementado** (mock). **No** se reclasifica el campo a RF-68 sin ficha.

## Estado funcional

Hallazgo de alcance. **No** se declara defecto de RF-65 por una regla de rango 0–1 que no está en especificación versionada aquí. Informe: `../HALLAZGO_ALCANCE_TC-M04-004_pesos_Wfs.md`.

## Evidencias

`evidencias/reeval-2026-10-25/test_tc_m04_004_*.{txt,html,xml}`
