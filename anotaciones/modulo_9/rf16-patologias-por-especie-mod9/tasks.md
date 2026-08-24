# RF-16 / #1633 — Patologías por especie + validación de métricas

Rama: `feature/rf16-patologias-por-especie-mod9` (base `origin/dev`).

## Contexto
RF-16 exige patología **única por especie** (case-insensitive) con descripción/estado
independientes por especie. Hoy `modulo9.patologias` tiene `UNIQUE` global
(`uq_enfermedad_nombre`) y el código reutiliza una fila de catálogo para todas las
especies. Decisión: cumplir la letra del RF → **por especie**, sin mezclar
responsabilidades M09 (config) / M04 (catálogo clínico).

`modulo9.patologias` es de **M04** (`src/prediction/`: `patologia_m04_model.py`, FK
`modulo4.patologias_variables_sensoricas → modulo9.patologias`, use case
`prediction/.../catalogo_patologias/`). NO se toca esa tabla ni `uq_enfermedad_nombre`.
El entity M09 por-especie vive en el pivot enriquecido `modulo9.especies_patologias`.

## Tareas

- [ ] **Rama + carpeta + tasks.md** (base origin/dev, no main — main está atrás).
- [ ] **Migración Alembic** `rf16_patologias_por_especie_y_metricas_checks`
      (down_revision `aa24fc52896e`):
  - [ ] `especies_patologias`: +nombre/descripcion/es_activo/fecha_actualizacion/fecha_creacion
  - [ ] backfill desde `modulo9.patologias` por `id_patologia`
  - [ ] SET NOT NULL/defaults; `id_patologia` → nullable
  - [ ] DROP `uq_especie_patologia`; CREATE UNIQUE INDEX `uq_especie_patologia_nombre (id_especie, lower(nombre))`
  - [ ] `auditorias_patologias`: +`id_especies_patologias` + FK; `id_patologia` nullable
  - [ ] CHECKs métricas `tipo_medicion` / `aplica_a_tipo_activo` (NOT VALID + VALIDATE guardado)
  - [ ] `uq_enfermedad_nombre` intacto (M04)
  - [ ] aplicar a `pruebas` y `sgpmp`
- [ ] **Código patologías** (src/configuration): entity `especie_patologia` con conducta;
      port + repo (obtener_por_id, obtener_por_especie_y_nombre, guardar, actualizar);
      use cases registrar/editar/desactivar/consultar; router (PATCH sobre
      id_especies_patologias); schema; models (pivot + auditoría). Eliminar escritura
      M09 al catálogo M04 (quitar puerto/impl `patologia_repository`).
- [ ] **Fix RF-32** aplicar plantilla: snapshot patologías como {nombre,descripcion,es_activo};
      `vincular_desde_snapshot` inserta fila por-especie.
- [ ] **Fix métricas** bug: `'l'` en `_UNIDADES_POR_TIPO['VOLUMEN']` (registrar+editar).
- [ ] **Pruebas** unit (`tests/configuration/`) + integración (`tests/integration/`)
      RF-16; verificar RF-32 sigue verde.
- [ ] **Docs**: `cu02_gaps_bd_rf16.md` (Gap 2 resuelto), `estado_M09.md`, curls;
      `resumen.md`; nota coordinación M04.
- [ ] **Commit** sin coautoría.

## Coordinación M04 (avisar)
- `modulo9.patologias` sin cambios; M09 deja de escribirla.
- `especies_patologias.id_patologia` ahora NULL opcional: M04 no debe asumir mapeo 1:1.
- `vw_rf16_dependencias_patologias` sin afectación (join sobre patologias intacta).
