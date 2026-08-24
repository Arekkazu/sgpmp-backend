# Resumen — RF-16 / #1633: Patologías por especie + validación de métricas

Rama: `feature/rf16-patologias-por-especie-mod9` (base `origin/dev`). Fecha: 2026-08-23.

## Qué se hizo

### 1. Patologías **por especie** (cumple la letra del RF-16)
La entidad M09 de patología pasó a vivir en `modulo9.especies_patologias` (antes un
pivot puro especie↔patología). Ahora lleva `nombre`, `descripcion`, `es_activo`,
`fecha_actualizacion`, `fecha_creacion` **propios por especie**, con unicidad
case-insensitive **por especie** vía índice funcional
`uq_especie_patologia_nombre (id_especie, lower(nombre))`.

- `id_patologia` (vínculo al catálogo clínico M04) pasó a **opcional/NULL**.
- Se **eliminó** la reutilización global anterior: registrar la misma "Fiebre Aftosa"
  en dos especies ahora crea dos filas independientes (descripción/estado propios).
- Se corrigió un **bug de responsabilidades**: `RegistrarPatologiaUseCase` escribía
  campos M09 dentro de `modulo9.patologias` (tabla de M04). Ya **no** lo hace.

Código (todo bajo `src/configuration/`): entity `especie_patologia.py` (ahora con
conducta `crear/actualizar/desactivar/_snapshot`), puerto + impl
`especie_patologia_repository.py`, use cases `patologias/registrar|editar|desactivar`,
`router/patologia_router.py` (el path param de PATCH es `id_especies_patologias`),
`schema/patologia_schema.py`, modelos `especie_patologia_model.py` y
`auditoria_patologia_model.py` (auditoría apunta a `id_especies_patologias`).
**Eliminados** (M09 ya no gestiona el catálogo M04): `domain/entities/patologia.py`,
`domain/repositories/patologia_repository.py`,
`infrastructure/repositories/patologia_repository.py`. El modelo ORM
`patologia_model.py` se conserva solo como lectura del catálogo M04.

### 2. Validación de métricas (RF-16, criterio de aceptación)
- **Bug fix**: `'l'` faltaba como unidad válida de `VOLUMEN` en
  `_UNIDADES_POR_TIPO` (registrar + editar métrica). Corregido.
- **BD (defensa en profundidad)**: CHECKs `chk_metricas_tipo_medicion` y
  `chk_metricas_aplica_a_tipo_activo` en `modulo9.metricas_produccion` (`NOT VALID` +
  `VALIDATE` guardado). La coherencia unidad↔tipo ya se validaba en la capa de app.

### 3. RF-32 (aplicar plantilla) — fix transversal obligatorio
`aplicar_plantilla_use_case.py` snapshoteaba patologías como lista de `id_patologia`
y las reconstruía por id. Con el nuevo modelo (identidad por `(id_especie, nombre)`,
`id_patologia` NULL) eso rompería en silencio. Ahora el snapshot guarda
`{nombre, descripcion, es_activo}` y `vincular_desde_snapshot` inserta una fila
por-especie desde ese payload.

## Migración
`alembic/versions/192872fafd40_rf16_patologias_por_especie_y_metricas_.py`
(down_revision `aa24fc52896e`). Idempotente (IF [NOT] EXISTS + DO $$). Hace: ADD
columns + backfill desde `modulo9.patologias` + SET NOT NULL/defaults + `id_patologia`
nullable + DROP `uq_especie_patologia` + CREATE índice único funcional + auditoría
(`id_especies_patologias` + FK, `id_patologia` nullable) + CHECKs de métricas.

**Aplicada a `sgpmp` (dev).** No se aplicó a `pruebas`: esa base **no tiene el esquema
`modulo9`** (solo `modulo1`), así que la migración de M09 no corre ahí; las pruebas de
integración de M09 verifican solo la compuerta RBAC (ver abajo).

Nota: `chk_metricas_tipo_medicion` quedó `NOT VALID` porque hay filas legacy con
`tipo_medicion` fuera del dominio (`TALLA`, `manual`, `calculada`). El CHECK aplica a
inserciones/updates nuevos; las filas legacy se toleran (limpieza = tarea aparte).
`modulo9.patologias.uq_enfermedad_nombre` se dejó **intacto** (es de M04).

## Coordinación M04 (avisar al equipo de `src/prediction`)
- `modulo9.patologias` **sin cambios** y sigue siendo de M04. M09 dejó de escribirla.
- `especies_patologias.id_patologia` ahora es **NULL opcional**: M04 no debe asumir que
  toda patología por especie mapea a una fila de catálogo (las de M09 tienen NULL). El
  chequeo de dependencias (`vw_rf16_dependencias_patologias`, aún stub) solo aplica
  cuando `id_patologia` no es NULL.
- La vista `vw_rf16_dependencias_patologias` no se ve afectada (join sobre
  `modulo9.patologias`, intacta).

## Pruebas
- Unit (fakes, sin BD): `tests/configuration/test_rf16_registrar_patologia_use_case.py`,
  `test_rf16_editar_patologia_use_case.py`, `test_rf16_metricas_coherencia.py`.
- Integración (compuerta RBAC recurso 18, patrón `test_rbac_mod9_1634.py`):
  `tests/integration/test_rf16_patologias_rbac.py`.
- Regresión RF-32: `test_rf32_concurrencia_aplicar_plantilla.py` sigue verde.
- Resultado: 22 passed (`tests/configuration` + integración M09), `TEST_DATABASE_URL=pruebas`.

## Verificación end-to-end
Ejercido contra `sgpmp` real (con rollback): mismo nombre en 2 especies → OK;
`id_patologia` None; duplicado en misma especie → `PATOLOGIA_DUPLICADA_EN_ESPECIE`
(por el índice único real); consulta por especie → OK.
