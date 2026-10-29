# TC-M09-G54 (TC-M09-106) — Modificaciones simultáneas sobre una misma área productiva

**RF-20 v1.1 / CU-04 — Gestionar Infraestructura Productiva**

## Estado vigente — reevaluación 2026-10-07 (RF-20 v1.1)

**Resultado: PASA**: el defecto de actualización perdida del 2026-10-06 (INC-M09-64-G54) quedó
corregido. Las ediciones realmente simultáneas ya no pasan las dos.

**Totales Newman:** 61 requests, 57 assertions, **0 failed**. Es la misma colección del
2026-10-06, sin cambios; solo cambió el backend.

**Corrección verificada:** `9f479187 fix(rf20-mod9): #498 bloquear la fila al editar para que dos
ediciones simultaneas no pasen el 412`, que llegó a TEST con el release `v1.0.0-rc.75`
(`origin/test` 15121f3f, traído a `juanma` por fast-forward). La lectura para editar ahora usa
`SELECT … FOR UPDATE`: la segunda transacción espera a la primera, ve la marca nueva y responde
412.

### 1. Concurrencia en secuencia (TC-M09-106a a 106d): PASA

Sin cambios respecto al 2026-10-06: marca `null` → 200 / 412; marca con fecha → 200 / 412;
lectura final con los datos de A v2.

### 2. Concurrencia real (TC-M09-106e): PASA

```
Intento  1 (área 235): A=200 B=412   OK
Intento  2 (área 236): A=200 B=412   OK
Intento  3 (área 237): A=412 B=200   OK
Intento  4 (área 238): A=412 B=200   OK
Intento  5 (área 239): A=412 B=200   OK
Intento  6 (área 240): A=412 B=200   OK
Intento  7 (área 241): A=200 B=412   OK
Intento  8 (área 242): A=200 B=412   OK
Intento  9 (área 243): A=412 B=200   OK
Intento 10 (área 244): A=412 B=200   OK
-> 0/10 actualizaciones perdidas
```

En cada intento, exactamente una edición recibe 200 y la otra 412 `CONFLICTO_CONCURRENCIA`, y el
área refleja la edición aceptada. El ganador alterna entre A y B, lo que confirma que las dos
solicitudes llegan realmente a la vez y que la serialización ocurre en la base.

Reproducción independiente con hilos (`concurrencia_simultanea_g54.py --intentos 20`, áreas
245 a 264): `{'200/412': 20}`, **0/20 actualizaciones perdidas** (antes 3/10 y 5/10).

Evidencia: `Resultados/reporte-TC-M09-G54.html` (Newman htmlextra, 2026-10-07).

---

## Reevaluación 2026-10-06 (RF-20 v1.1): histórico

**Resultado: FALLA (1 defecto real)**: el control optimista funciona en secuencia, pero no
frente a ediciones realmente simultáneas.

**Totales Newman:** 61 requests, 57 assertions, **18 failed**. Las 18 fallas son todas de la
parte simultánea (TC-M09-106e, 2 assertions por cada uno de los 9 intentos con actualización
perdida). La parte en secuencia pasa completa.

### 1. Concurrencia en secuencia (TC-M09-106a a 106d): PASA

La lógica es la misma que en la reevaluación del 2026-09-28; solo se adaptó a v1.1: la
colección crea su propia especie y envía `especie_id` (ahora obligatorio) al registrar y al
editar. Sin ese ajuste, todo POST/PATCH daba 400 antes de llegar al chequeo de concurrencia.

```
Área recién creada (fecha_actualizacion null)
TC-M09-106a  Admin A guarda con la marca null         -> 200
TC-M09-106b  Admin B guarda con la marca null         -> 412 CONFLICTO_CONCURRENCIA
TC-M09-106c  Admin A guarda con la marca vigente      -> 200
TC-M09-106d  Admin B guarda con la marca ya superada  -> 412 CONFLICTO_CONCURRENCIA
Lectura final: datos de A v2; B nunca sobrescribió
```

### 2. Concurrencia real (TC-M09-106e): FALLA

En la colección, 10 intentos sobre un área nueva cada uno. Tras una lectura común, los dos PATCH
con la misma `fecha_actualizacion` se lanzan en paralelo (`pm.sendRequest` sin esperar uno al
otro). Lo esperado en cada intento es exactamente un 200 y un 412 `CONFLICTO_CONCURRENCIA`, y
que el área refleje la única edición aceptada.

```
Intento  1 (área 212): A=200 B=412   OK
Intento  2 (área 213): A=200 B=200   ACTUALIZACIÓN PERDIDA
Intento  3 (área 214): A=200 B=200   ACTUALIZACIÓN PERDIDA
Intento  4 (área 215): A=200 B=200   ACTUALIZACIÓN PERDIDA
Intento  5 (área 216): A=200 B=200   ACTUALIZACIÓN PERDIDA
Intento  6 (área 217): A=200 B=200   ACTUALIZACIÓN PERDIDA
Intento  7 (área 218): A=200 B=200   ACTUALIZACIÓN PERDIDA
Intento  8 (área 219): A=200 B=200   ACTUALIZACIÓN PERDIDA
Intento  9 (área 220): A=200 B=200   ACTUALIZACIÓN PERDIDA
Intento 10 (área 221): A=200 B=200   ACTUALIZACIÓN PERDIDA
-> 9/10 actualizaciones perdidas
```

El defecto se reprodujo en todas las corridas, con frecuencia variable según qué tan juntos
lleguen los dos PATCH: 9/10 con `pm.sendRequest`; 3/10 y 5/10 con hilos de Python
(`concurrencia_simultanea_g54.py`, que se mantiene como reproducción independiente fuera de
Newman).

**Defecto:** con ediciones simultáneas, las dos solicitudes pueden recibir `200` y la última
sobrescribe a la primera sin aviso (actualización perdida). El usuario cuyo cambio se perdió
recibió un 200 de confirmación.

**Causa en el código:** el chequeo es *check-then-act* sin bloqueo.
- `SqlAlchemyInfraestructuraRepository.obtener_por_id` lee el área sin `SELECT … FOR UPDATE`.
- `EditarInfraestructuraUseCase` compara la `fecha_actualizacion` en Python.
- `actualizar` hace el UPDATE sin condicionarlo a la marca leída (no hay
  `WHERE fecha_actualizacion = :marca`).

Con READ COMMITTED, dos transacciones que leen la misma marca pasan las dos el chequeo, y la
segunda pisa a la primera.

**Corrección sugerida:** una de dos.
- Bloquear la fila al leerla para editar (`with_for_update()`).
- Hacer el UPDATE condicional a la marca leída y responder 412 si afecta 0 filas.

Evidencia de esa corrida: el HTML de Newman del 2026-10-06 (18 assertions fallidas en la parte
simultánea), reemplazado por el del 2026-10-07; queda en el historial de git (commit 5bdaa987).

---

## Reevaluación 2026-09-28 (RF-20 v1.0): histórico

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
