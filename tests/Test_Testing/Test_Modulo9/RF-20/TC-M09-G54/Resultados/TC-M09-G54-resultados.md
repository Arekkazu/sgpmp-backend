# TC-M09-G54 (TC-M09-106) — Modificaciones simultáneas sobre una misma área productiva

**RF-20 / CU-04 — Gestionar Infraestructura Productiva**

## Estado vigente — reevaluación 2026-09-28

**Resultado: PASA** — 10 requests, 16 assertions, 0 failed.

El bloqueo ya no existe (migración `2dbb6d44046f` aplicada en TEST), y la prueba original solo
documentaba ese bloqueo: con `modulo9.tipos_area` presente se saltaba sola (`pytest.skip`).
Se reescribió como colección Newman (`TC-M09-G54.postman_collection.json`) que ejercita la
concurrencia optimista (FA-14) real vía API, con finca y área propias en cada corrida. Se
eliminaron `test_rf20_concurrencia_editar_infraestructura.py` y su `conftest.py`.

Cubre las dos ramas del chequeo de `EditarInfraestructuraUseCase` (marca `null` y marca con fecha):

```
Paso 2 - A y B leen el área (fecha_actualizacion=null)       -> 200
TC-M09-106a - A guarda con null                              -> 200 (fecha_actualizacion avanza)
TC-M09-106b - B guarda con null (desactualizada)             -> 412 CONFLICTO_CONCURRENCIA
Paso 5 - Refrescan (quedan los datos de A)                   -> 200
TC-M09-106c - A guarda con la marca vigente                  -> 200
TC-M09-106d - B guarda con la marca ya superada              -> 412 CONFLICTO_CONCURRENCIA
Paso 8 - Lectura final: datos de A v2, B nunca sobrescribió  -> 200
```

Evidencia: `Resultados/reporte-TC-M09-G54.html` (Newman htmlextra, 2026-09-28).

---

## Resultado original (2026-09-06) — histórico

**Estado: BLOQUEADO** (verificado, no supuesto) — mismo gap de `TC-M09-G48/NOTA_BLOQUEO.md`.

### Por qué esto no es "simplemente" el mismo bloqueo de siempre

A diferencia de TC-M09-G48/G49/G50/G53 (donde un `POST`/`PATCH` cualquiera falla con 500),
aquí valía la pena investigar el **orden exacto** de las validaciones: el chequeo de
concurrencia optimista (FA-14) en `EditarInfraestructuraUseCase` ocurre **antes** de la
revalidación de `tipo_area` (línea 73). Eso abría la posibilidad de que el control de
concurrencia en sí *sí* fuera observable (p. ej., que la primera edición reventara en
`tipo_area` pero la segunda recibiera 412 igual, si el mecanismo de concurrencia fuera
independiente del resto). Se comprobó con código real, no se asumió.

**Resultado real:** como ninguna edición llega a persistir (ambas revientan en el chequeo de
`tipo_area`, que ocurre después), el `fecha_actualizacion` del área **nunca avanza**. La
segunda "solicitud" ve exactamente el mismo estado que la primera, así que **también** pasa
el chequeo de concurrencia y revienta en el mismo punto — no hay manera de observar hoy un
`200` para una y un `412` para la otra. El control de concurrencia de RF-20 sigue sin poder
verificarse mientras el catálogo de tipos de área no exista.

### Cómo se probó

Mismo patrón que TC-M09-G39 (RF-18): dos `Session` de SQLAlchemy independientes bindeadas a
la misma conexión de la prueba (simulan dos requests HTTP reales, cada una con su propio
mapa de identidad), usando los repositorios SQLAlchemy reales (no fakes) contra una finca y
un área productiva insertadas directamente por SQL (evita `RegistrarInfraestructuraUseCase`,
que está bloqueado por el mismo gap).

### Resultado de la ejecución (2026-09-06)

```
tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G54/test_rf20_concurrencia_editar_infraestructura.py::test_TC_M09_106_ambas_ediciones_concurrentes_fallan_por_el_gap_de_tipos_area PASSED

1 passed, 1 warning in 5.05s
```

Ambas ediciones lanzaron `ProgrammingError` (relación `tipos_area` inexistente); el área
quedó exactamente como estaba antes (`nombre`/`superficie` sin cambios). Verificado además
que no quedó ningún efecto residual en la base compartida (la transacción exterior de la
prueba se revierte al finalizar).

### Cómo cerrar el caso

Una vez aplicada la migración pendiente de `TC-M09-G48`, esta prueba debe **reescribirse**
(no solo reejecutarse) para verificar el escenario real: la primera edición debería
completarse con `200` y avanzar `fecha_actualizacion`, y la segunda (con el timestamp
desactualizado) debería recibir `412 CONFLICTO_CONCURRENCIA` — el mismo patrón que
`tests/Test_Testing/Test_Modulo9/RF-18/TC-M09-G39/`. El test ya incluye un `pytest.skip`
automático si detecta que `modulo9.tipos_area` ya existe, como recordatorio de que quedó
pendiente de esa reescritura.
