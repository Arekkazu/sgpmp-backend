# CU06 (M05) — Gaps entre el documento y la base de datos (RF-80)

## Fecha de análisis / aplicación
2026-07-31

## Contexto

CU-06 "Auditar Operaciones del Módulo" (llamado CU-05 en la descripción
narrativa del RF-80, CU06 en la tabla de flujos — mismo caso de uso) pide un
mecanismo de auditoría para los eventos de RF-78/79/81: hash SHA-256,
clasificación NIC41/TECNICO con retención diferenciada, cola persistente
M05→M12 con umbrales de capacidad, deduplicación at-least-once por
`id_evento_m05`, y consulta/exportación de la bitácora para Administrador/
Contador/Revisor Fiscal.

Al iniciar este CU se verificó vía MCP postgres y grep exhaustivo qué ya
existía. **Hallazgo clave: el lado de escritura ya estaba construido.**
Durante CU-05 (RF-78/79, [`cu05_gaps_bd_rf78_rf79.md`](cu05_gaps_bd_rf78_rf79.md))
se creó `modulo5.auditorias_suministros` como tabla de auditoría *local* de
M05 — el rol que RF-80 le asigna a un M12 externo (repositorio transversal
con cola, hash, retención) quedó colapsado en esta tabla + el trigger
`trg_audit_hash` (calcula `hash_integridad` en cada INSERT/UPDATE),
consistente con el patrón ya establecido del proyecto ("costos, inmutabilidad
y auditoría de `modulo5` los hacen triggers de BD; la app no los duplica").
Ya escribían ahí 7 valores de negocio (`SUMINISTRO_REGISTRADO`,
`SUMINISTRO_CORREGIDO`, `REGISTRO_FALLIDO`, `CONFLICTO_CONCURRENCIA`,
`CICLO_CONSOLIDADO`, `PROVISION_INCREMENTAL_ENTREGADA`,
`REPORTE_COSTOS_GENERADO`) más 4 genéricos `INSERT/UPDATE/DELETE/SELECT` de
triggers DML de CU-01/02/04. Columnas de RF-80 (`hash_integridad`,
`clasificacion_registro`/`retencion_aplicable`, `registro_incompleto`/
`detalle_causa`, `numero_reintentos`/`fecha_intentos`) también ya existían.
87 filas en dev al momento del análisis, 7 `tipo_operacion` distintos.

**Lo que no existía (el entregable real de este CU)**: ningún endpoint de
*consulta ni exportación* de esa bitácora — Administrador/Contador/Revisor
Fiscal no tenían forma de listar, filtrar, paginar ni exportar
`auditorias_suministros`.

**Decisiones del usuario para este CU**:
1. Exportar en **CSV + Excel + PDF** (no solo CSV, a diferencia del
   precedente de CU-04/RF-81 — ver decisión #2 de
   [`cu04_gaps_bd_rf77_rf81.md`](cu04_gaps_bd_rf77_rf81.md)). El proyecto no
   tenía librería de Excel/PDF; se agregaron `openpyxl` y `reportlab`.
2. Cerrar también el gap de RF-81: `CONSULTA_HISTORIAL_EJECUTADA` y
   `EXPORTACION_HISTORIAL_GENERADA` están en el catálogo de eventos de RF-80
   pero `consultar_historial_suministros_use_case.py` y
   `exportar_historial_sincrono_use_case.py` (CU-04, ya en producción) nunca
   llamaban a `AuditoriaSuministroPort`.

---

## Paso 0 — DDL/DML aplicado vía MCP postgres

### 1. Enum — 2 valores de RF-81 que faltaban

```sql
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'CONSULTA_HISTORIAL_EJECUTADA';
ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS 'EXPORTACION_HISTORIAL_GENERADA';
```

### 2. Índices — la tabla solo tenía PK + índice sobre `id_gestion_fases`; el CU nuevo filtra/pagina por estas columnas

```sql
CREATE INDEX idx_auditorias_suministros_tipo_operacion ON modulo5.auditorias_suministros (tipo_operacion);
CREATE INDEX idx_auditorias_suministros_fecha_evento ON modulo5.auditorias_suministros (fecha_evento DESC);
CREATE INDEX idx_auditorias_suministros_id_usuario ON modulo5.auditorias_suministros (id_usuario);
CREATE INDEX idx_auditorias_suministros_entidad_afectada ON modulo5.auditorias_suministros (entidad_afectada);
```

### 3. RBAC — recurso nuevo + matriz de permisos

`MAX(id_recurso)` confirmado en 56 → nuevo recurso 57. Actores de RF-80:
Administrador (1), Contador (5), Revisor Fiscal (8).

```sql
INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion, es_proceso_especial) VALUES
  (57, 'bitacora_auditoria_suministros', 'Consulta y exportación de la bitácora de auditoría de M05 — RF-80', true);

INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo) VALUES
  (1,57,2,'admin_leer_bitacora_auditoria_suministros',true),
  (5,57,2,'cont_leer_bitacora_auditoria_suministros',true),
  (8,57,2,'revfiscal_leer_bitacora_auditoria_suministros',true),
  (1,57,5,'admin_ejecutar_bitacora_auditoria_suministros',true),
  (5,57,5,'cont_ejecutar_bitacora_auditoria_suministros',true),
  (8,57,5,'revfiscal_ejecutar_bitacora_auditoria_suministros',true);
```

R=2 para listar/detalle, E=5 para exportar (mismo criterio que
`auditoria_m04_router.py`). No se aplicó alcance por unidad productiva
(`AlcanceActivoPort`) como en RF-81: los 3 roles de este CU ya tienen
visibilidad total en los recursos 55/56 de M05, es consistente no
restringir aquí tampoco.

Todo verificado post-aplicación: 2 valores de enum presentes, 4 índices
nuevos creados, recurso 57 y 6 filas de permisos confirmadas en DB.

---

## Partes del RF-80 que NO se construyeron (arquitectura del proyecto no aplica)

- **Cola persistente M05→M12 con umbrales 90%/100% (FA-08/09, RNF-07)** — M05
  no tiene broker/cola separada; cada evento se inserta de forma síncrona,
  dentro de la misma transacción de BD que la operación de negocio que lo
  origina. No hay backlog que pueda llenarse.
- **M12 no disponible 48h (FA-10/11)** — no existe un M12 externo separado;
  el "repositorio de auditoría" es la propia tabla `auditorias_suministros`
  de M05, siempre disponible mientras la BD lo esté.
- **Deduplicación por `id_evento_m05` bajo *at-least-once* (CA-14/15,
  RNF-09)** — no hay reentrega posible: al no existir cola/broker, cada
  evento se escribe exactamente una vez, en la misma transacción de la
  operación que lo genera.
- **`PROVISION_INCREMENTAL_FALLIDA` / `PROVISION_PENDIENTE`** — requieren
  reintentos de *push* real hacia M06; CU-05 ya documentó (Gap 11) que M05
  es autocontenido frente a M06 (solo expone lectura/pull, no hace push).
- **`PRECIO_MANUAL_INGRESADO` / `ACUMULADO_ACTUALIZADO`** — duplicarían 1:1
  el `costo_afectado`/`origen_precio` que ya viaja dentro del evento
  `SUMINISTRO_REGISTRADO`/`SUMINISTRO_CORREGIDO` de la misma operación.

Estas decisiones ya estaban implícitas en el diseño de CU-05; este CU solo
las deja documentadas explícitamente en el contexto de RF-80.

---

## Código nuevo (lado de lectura, el CU en sí)

Sigue el orden de capas de `CLAUDE.md`, imitando la forma de
`src/prediction/.../auditoria_m04_*` (RF-73, patrón ya construido dos veces
en el proyecto para este tipo de CU) pero leyendo `AuditoriaSuministroModel`
existente — no se creó tabla ni modelo ORM nuevo, para no duplicar lo que
CU-05 ya construyó:

- `domain/entities/evento_auditoria_suministro.py` —
  `EventoAuditoriaSuministroConsulta` (distinta del DTO de escritura
  `EventoAuditoriaSuministro` de `auditoria_suministro_port.py`).
- `domain/repositories/auditoria_suministro_read_port.py` —
  `AuditoriaSuministroReadPort` + `FiltrosAuditoriaSuministro`.
  `tipo_operacion` se valida como texto libre, no contra un enum Python
  cerrado, porque la columna real mezcla los 8 valores de negocio con los 4
  genéricos de triggers DML.
- `infrastructure/repositories/auditoria_suministro_read_repository.py` —
  `SqlAlchemyAuditoriaSuministroReadRepository` (paginación `select()` +
  `func.count()` sobre subquery, mismo patrón que
  `evento_auditoria_m04_repository.py`).
- `application/use_cases/auditoria/` — `ConsultarAuditoriaSuministrosUseCase`
  (listar + detalle) y `ExportarAuditoriaSuministrosUseCase` (CSV/XLSX/PDF).
  Ninguno se auto-audita: RF-80 no define un tipo de evento de negocio para
  "se consultó la bitácora" (a diferencia de RF-81, donde
  `CONSULTA_HISTORIAL_EJECUTADA` sí está en el catálogo).
- `infrastructure/schema/auditoria_suministro_schema.py`,
  `infrastructure/routers/auditoria_suministros_router.py` (recurso 57:
  `GET ""`, `GET "/exportar"`, `GET "/{id}"`),
  `infrastructure/factories/auditoria_suministros_factory.py`.
- `requirements.txt` — `openpyxl==3.1.5`, `reportlab==4.4.4` (+ transitivas
  `et-xmlfile`, `pillow`, ya instaladas en el venv del proyecto).

## Código modificado (cierre del gap de RF-81)

`consultar_historial_suministros_use_case.py` y
`exportar_historial_sincrono_use_case.py` (CU-04) reciben ahora `db: Session`
y `auditoria_port: AuditoriaSuministroPort` nuevos; tras construir el
resultado exitosamente, registran `CONSULTA_HISTORIAL_EJECUTADA` /
`EXPORTACION_HISTORIAL_GENERADA` y hacen `commit()` en un
`try/except: rollback()` que no bloquea la respuesta de lectura si la
auditoría falla (mismo criterio no-bloqueante de
`consultar_auditoria_m04_use_case.py`). `historial_suministros_factory.py`
inyecta `SqlAlchemyAuditoriaSuministroRepository(db)` (ya existía, de CU-05).

## Verificación end-to-end

Ejecutada contra servidor local real. Se generaron sesiones/tokens JWT
válidos directamente vía MCP postgres para 4 usuarios de prueba
(Administrador, Contador, Revisor Fiscal, Productor) porque no se contaba
con sus contraseñas en texto plano. Confirmado:

- `GET /suministros/auditoria` sin filtros y filtrado por `tipo_operacion`
  → `200`, paginación correcta.
- `GET /suministros/auditoria/{id}` con id real → `200`; con id inexistente
  → `404 AUDITORIA_SUMINISTRO_NO_ENCONTRADA`.
- `GET /suministros/auditoria` con usuario Productor (sin permiso en recurso
  57) → `403 ACCESO_DENEGADO`.
- `GET /suministros/auditoria/exportar?formato=csv|xlsx|pdf` → `200`,
  `Content-Type`/`Content-Disposition` correctos; los 3 archivos abren
  correctamente (CSV con 87 filas + encabezado, XLSX válido "Microsoft Excel
  2007+", PDF válido de 4 páginas).
- `?formato=doc` → `400` (rechazado por el patrón de `Query` en el router
  antes de llegar al use case).
- `GET /suministros/historial?id_activo_biologico=57` y
  `GET /suministros/historial/exportar?id_activo_biologico=57` → `200`, y
  ambos generaron una fila nueva en `auditorias_suministros`
  (`CONSULTA_HISTORIAL_EJECUTADA` id 95, `EXPORTACION_HISTORIAL_GENERADA`
  id 96) — confirma el cierre del gap de RF-81.
- `pytest --collect-only` → 0 tests en el repo (no hay suite que romper).
