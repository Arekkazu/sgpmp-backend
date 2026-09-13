# TC-M02-G23 (TC-M02-047) — BLOQUEO en la precondición: RF-37 `cambiar_fase` está roto para cualquier activo

**RF-37 / CU-02.** No es un bug de RF-35 — es un defecto de RF-37 (`POST /activos-biologicos/{id_activo}/fases`)
que impide construir la precondición literal de TC-M02-047 ("Existe un registro histórico de fase ya cerrado"). A
diferencia del bloqueo de RF-41 documentado en `TC-M02-G22/NOTA_BLOQUEO.md`, esta vez **la causa raíz se confirmó
100% por lectura de código, sin necesidad de acceso a la base de datos.**

## Qué se observó

`POST /activos-biologicos/{id_activo}/fases` devuelve **500** (`ERROR_INTERNO`, "Ocurrió un error interno") en
**cualquier intento de cambio de fase**, sobre **cualquier activo**, con **cualquier `id_ciclo_productiva` válido**:

- Activo 199 (especie 3, Camarón), `id_ciclo_productiva` = 1, 2, 3, 4, 5, 6, 7 → 500 en los 7 casos.
- Activo 51 (especie 2, Trucha, dato semilla histórico del propio dev, sin fases aún), `id_ciclo_productiva=2`
  (el mismo ID documentado como ejemplo funcional en `anotaciones/modulo_2/curls_m02_cu02_activo_individual.md`,
  con coincidencia exacta de especie) → también 500.
- Único caso que **no** da 500: `id_ciclo_productiva=9999` (claramente inexistente) → correctamente **400
  CICLO_INVALIDO**, confirmando que la ruta de validación de "ciclo inexistente" sí funciona; el 500 ocurre en un
  paso posterior, solo cuando el ciclo SÍ existe.

## Causa raíz confirmada (por lectura de código, no es una hipótesis)

`cambiar_fase_use_case.py`, línea 72:

```python
self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '')
```

Tres argumentos posicionales. Pero la firma real del método en el repositorio
(`activo_biologico_repository.py`, línea 386) exige **cuatro**:

```python
def cerrar_gestion_activa(self, id_activo: int, fecha_fin: datetime, motivo: str, usuario_id: int) -> None:
```

Falta `usuario_id` en la llamada. Esto produce un `TypeError: cerrar_gestion_activa() missing 1 required positional
argument: 'usuario_id'` de Python puro — ni siquiera llega a tocar la base de datos. Coincide exactamente con el
mensaje observado: `"Ocurrió un error interno. Intenta de nuevo..."` es el manejador genérico de excepciones no
controladas de FastAPI (`src/shared/error_handlers.py`), **distinto** del mensaje `"Error inesperado en base de
datos"` que sí usa `raise_from_db_error` para errores de SQLAlchemy — la diferencia de texto es la pista que llevó a
revisar el código en vez de asumir otro trigger de BD como en el bloqueo de RF-41.

## Por qué esto bloquea TC-M02-047

El caso exige como precondición "existe un registro histórico de fase ya cerrado (`fecha_fin` informada)". Como
`cambiar_fase` es la única vía de la API para crear el primer registro de `gestiones_fases` de un activo, y esa vía
está rota al 100%, **no existe ninguna forma de llegar siquiera a la primera fase**, mucho menos a una segunda que
cierre la primera. El bloqueo es total, no parcial.

## Cómo desbloquear

Cambio de una sola línea, sin tocar ninguna otra lógica:

```python
# cambiar_fase_use_case.py, línea 72 — antes:
self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '')

# después:
self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '', usuario.id_usuario)
```

Esta sesión **no aplicó el cambio** (se limitó a identificar y documentar la causa, sin tocar código de la
aplicación) — queda para que Desarrollo lo confirme y lo aplique.

## Cómo re-verificar tras el fix

```bash
newman run "tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23/TC-M02-G23.postman_collection.json" \
  -r cli,htmlextra --folder "3a. TC-M02-047 - [Precondicion, BLOQUEADA] Intentar la primera fase del ciclo del activo propio"
```

Debería pasar de `500` a `201`. En ese momento, TC-M02-047 puede completarse de verdad: avanzar el activo 199 a una
segunda fase, confirmar que `fecha_finalizacion` de la primera fase quedó fija, y luego intentar (y confirmar el
rechazo de) un `PATCH` directo sobre `/activos-biologicos/{id}/fases/{id_gestion_fases}` — ruta que hoy **no existe
en absoluto** (confirmado: 404, ver paso "3b" de la colección), lo cual ya es, en sí mismo, una forma válida —
aunque parcial— de verificar el carácter append-only exigido por el RF: no hay ningún endpoint público para editar
una fase existente, sin importar si está abierta o cerrada.

## Alcance del bloqueo

**Cualquier caso de RF-37 que dependa de crear o avanzar una fase productiva está bloqueado al 100% mientras esta
línea no se corrija** — no solo TC-M02-047. Esto incluye, indirectamente, cualquier flujo de RF-40 (eventos de
crecimiento) que dependa de "avance automático de fase por duración configurada" documentado en la auditoría del
módulo, y cualquier caso futuro de RF-38 (cierre de ciclo) que dependa de que exista una fase activa previa creada
por esta vía.
