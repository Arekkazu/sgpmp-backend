# INC-M02-74-G80 — transferencias/disponibles devuelve destinos incompatibles y de otras fincas

**RF:** RF-48 — Registrar transferencia interna (CU10C)
**Endpoint:** `GET /activos-biologicos/{id_activo}/transferencias/disponibles`

## Causa raíz (confirmada por QA en el propio reporte)

`RegistrarTransferenciaUseCase.listar_infraestructuras_disponibles` llamaba a
`infra_port.listar_activas(excluir_id=...)` sin aplicar ninguna de las reglas
que el propio `POST /transferencias` sí exige al confirmar el movimiento:

- **C1 (especie):** el `POST` rechaza con `INCOMPATIBILIDAD_ESPECIE` si
  `infra_destino.id_especie` no coincide con la especie del activo — el listado
  no filtraba por esto.
- **C3 (capacidad):** el `POST` rechaza con `CAPACIDAD_EXCEDIDA` si la
  ocupación + cantidad a mover excede `capacidad_maxima` — el listado tampoco
  lo calculaba.
- **Alcance por finca:** el listado no restringía a la finca de la
  infraestructura origen del activo — en el caso de QA, 34 de 38 destinos
  devueltos pertenecían a otra finca.

Resultado: "disponible" no implicaba "transferible", induciendo al usuario a
elegir destinos que el `POST` rechazaba de todas formas.

## Fix

`listar_infraestructuras_disponibles` ahora aplica las tres reglas en memoria
sobre la lista de infraestructuras activas, reutilizando exactamente la misma
semántica que ya validaba `execute()` (mismo helper `_cantidad_a_transferir`
para el cálculo de C3, dedupicado entre ambos métodos):

1. Obtiene la infraestructura origen (`infra_port.obtener_activa`) para saber
   `id_finca_origen`; si por algún motivo la origen ya no está activa, no se
   filtra por finca en vez de ocultar todo el listado (caso borde, no bloquea
   la consulta).
2. Descarta destinos de otra finca.
3. Descarta destinos con `id_especie` distinto al del activo (`id_especie is
   None` sigue significando "sin restricción de especie").
4. Descarta destinos sin capacidad disponible.

**C2 (compatibilidad por tipo de infraestructura) queda explícitamente fuera**
de este filtro — no existe todavía su modelo de compatibilidad, según el
propio reporte de QA (issue separado: INC-M02-72-G80/DEF-G80-01).

Sin cambios de esquema de BD ni de contrato de respuesta (mismo shape JSON).

## Pruebas

`tests/biological_assets/test_listar_infraestructuras_disponibles_use_case.py`
(nuevo, 4 casos: filtra por finca, filtra por especie, filtra por capacidad,
degrada correctamente si no hay origen activo). Suite completa de
`tests/biological_assets/`: 84 passed, sin regresiones.

## Adenda — el `POST` tampoco validaba alcance por finca (E-08 ausente)

Revisión posterior encontró que el fix de arriba solo corregía el **listado**.
`RegistrarTransferenciaUseCase.execute()` (el `POST` real que ejecuta el
movimiento) nunca validó alcance por finca en ningún punto — la numeración de
sus validaciones salta de `E-07` (especie) a `E-09` (capacidad), sin `E-08`.
Un cliente que llamara el `POST` directamente con un `infraestructura_destino_id`
de otra finca (sin pasar por `disponibles`) lograba la transferencia igual: el
filtro del listado era una sugerencia de UI, no una regla de negocio exigida.

Se agregó el `E-08` faltante en `execute()`: obtiene la infraestructura origen
vía `infra_port.obtener_activa(dto.infraestructura_origen_id)` y rechaza con
`BusinessRuleError(code='DESTINO_OTRA_FINCA')` si `id_finca` de origen y
destino difieren (ambos no nulos). Mismo criterio que ya aplicaba el listado,
ahora también en el punto de escritura real.

Test agregado: `tests/biological_assets/test_registrar_transferencia_e08_finca.py`
(no existía ningún test previo de `execute()` en este repo — el use case
completo no tenía cobertura unitaria antes de este fix, lo que explica cómo
pasó desapercibido). Suite completa de `tests/biological_assets/`: 86 passed
(84 + 2 nuevos), sin regresiones.
