# Implementación DEV — M05 CU06: Auditar Operaciones del Módulo (RF-80)

**Fecha:** 2026-07-31 · **Rama:** `feature/supplies`

Resumen de lo implementado para CU-06 (llamado CU-05 en la descripción narrativa del RF-80,
CU06 en la tabla de flujos — mismo caso de uso): consulta filtrada/paginada y exportación
(CSV/Excel/PDF) de la bitácora de auditoría de M05 para Administrador, Contador y Revisor Fiscal;
más el cierre de un gap de RF-81 (auto-auditoría de consulta/exportación del historial de
suministros). Sigue la arquitectura hexagonal/DDD del proyecto (ver `CLAUDE.md`).

## Decisiones clave (acordadas antes de codificar)

- **El lado de escritura ya existía**: durante CU-05 (RF-78/79) se construyó
  `modulo5.auditorias_suministros` como tabla de auditoría local de M05, con trigger de hash
  (`trg_audit_hash`) y columnas de clasificación/retención NIC41. En la práctica, esa tabla +
  trigger cumple el rol que RF-80 le asigna a un M12 externo (repositorio transversal con cola,
  hash, retención). El entregable real de este CU era el lado de **lectura**, que no existía.
- **No se crea tabla ni modelo ORM nuevo**: se reutiliza `AuditoriaSuministroModel` (ya generado
  con sqlacodegen en CU-05) para el lado de lectura también, en vez de crear una tabla genérica
  de eventos tipo `eventos_auditoria_m04` — evita duplicar lo que CU-05 ya construyó.
- **Patrón de referencia reutilizado**: `src/prediction` (M04, RF-73, `auditoria_m04_router.py` +
  sus use cases + repository) ya implementa exactamente este tipo de CU dos veces en el proyecto
  (M04 e IoT). Se reutilizó esa *forma* (filtros, paginación, endpoint de detalle, exportación)
  apuntando a la tabla ya existente de M05.
- **Exportación en 3 formatos** (CSV + Excel + PDF, decisión explícita del usuario) — a diferencia
  del precedente de RF-81/CU-04, que solo tenía CSV por falta de librerías. Se agregaron
  `openpyxl` y `reportlab` como dependencias nuevas del proyecto.
- **Sin cola/broker M05→M12, sin deduplicación at-least-once**: M05 no tiene arquitectura de cola
  separada — cada evento se inserta síncrono, en la misma transacción de la operación de negocio
  que lo origina. Las partes de RF-80 que dependen de esa arquitectura (umbrales de capacidad
  90%/100%, M12 no disponible 48h, dedup por `id_evento_m05`) se documentan como no aplicables,
  no se construyen artificialmente. Detalle completo en
  [`cu06_gaps_bd_rf80.md`](cu06_gaps_bd_rf80.md).
- **Cierre del gap de RF-81**: `CONSULTA_HISTORIAL_EJECUTADA`/`EXPORTACION_HISTORIAL_GENERADA`
  están en el catálogo de eventos de RF-80 pero los use cases de CU-04 nunca los emitían. Se
  cablearon en el mismo trabajo, con el mismo criterio no-bloqueante de auditoría que M04
  (`try/except` alrededor del `commit()` de auditoría; si falla, no rompe la respuesta de lectura).

Detalle completo de gaps de BD/RBAC (con todo el DDL aplicado) en
[`cu06_gaps_bd_rf80.md`](cu06_gaps_bd_rf80.md).

## Paso 0 (BD/RBAC) — aplicado vía MCP postgres, resumen

- 2 valores nuevos en `enum_auditoria_suministro_tipo_operacion`
  (`CONSULTA_HISTORIAL_EJECUTADA`, `EXPORTACION_HISTORIAL_GENERADA`).
- 4 índices nuevos en `auditorias_suministros` (`tipo_operacion`, `fecha_evento DESC`,
  `id_usuario`, `entidad_afectada`) — solo tenía PK + índice sobre `id_gestion_fases`.
- Recurso **57** (`bitacora_auditoria_suministros`) + 6 permisos RBAC (R=2, E=5 ×
  Admin/Contador/Revisor Fiscal).

## Estructura de código (`src/supplies/`)

### Dominio
- `domain/entities/evento_auditoria_suministro.py` — `EventoAuditoriaSuministroConsulta`
  (entidad de lectura completa, distinta del DTO angosto de escritura ya existente).
- `domain/repositories/auditoria_suministro_read_port.py` — `AuditoriaSuministroReadPort` +
  `FiltrosAuditoriaSuministro` (value object). `tipo_operacion` se valida como texto libre, no
  contra un enum Python cerrado, porque la columna real mezcla 8 valores de negocio con 4
  genéricos de triggers DML de otros CUs.

### Infraestructura
- `infrastructure/repositories/auditoria_suministro_read_repository.py` —
  `SqlAlchemyAuditoriaSuministroReadRepository` (paginación `select()` + `func.count()` sobre
  subquery, `order_by(fecha_evento.desc())`, mismo patrón que `evento_auditoria_m04_repository.py`).
- `infrastructure/schema/auditoria_suministro_schema.py` — `EventoAuditoriaSuministroResponse`,
  `AuditoriaSuministrosListResponse`.
- `infrastructure/routers/auditoria_suministros_router.py` — recurso 57: `GET ""` (listar,
  R=2), `GET "/exportar"` (R=5), `GET "/{id}"` (detalle, R=2).
- `infrastructure/factories/auditoria_suministros_factory.py` —
  `build_consultar_auditoria_use_case`, `build_exportar_auditoria_use_case`.

### Aplicación
- `application/use_cases/auditoria/consultar_auditoria_suministros_use_case.py` —
  `ConsultarAuditoriaSuministrosUseCase` (listar + detalle, solo lectura, sin auto-auditoría —
  RF-80 no define un evento de negocio para "se consultó la bitácora").
- `application/use_cases/auditoria/exportar_auditoria_suministros_use_case.py` —
  `ExportarAuditoriaSuministrosUseCase`: arma CSV (`csv.DictWriter`), Excel (`openpyxl.Workbook`,
  encabezados en negrita, autoancho básico) y PDF (`reportlab.platypus.SimpleDocTemplate` +
  `Table`, título + fecha de generación + total + tabla) a partir del mismo `consultar()`. Límite
  de exportación de 10.000 registros (no hay modo asíncrono para este CU, a diferencia de RF-81,
  porque el volumen de `auditorias_suministros` es órdenes de magnitud menor).

### Cierre del gap RF-81
- `application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py` y
  `exportar_historial_sincrono_use_case.py` — reciben `db: Session` y
  `auditoria_port: AuditoriaSuministroPort` nuevos; tras construir el resultado exitosamente,
  registran el evento correspondiente y hacen `commit()` en un bloque no-bloqueante.
- `infrastructure/factories/historial_suministros_factory.py` — inyecta
  `SqlAlchemyAuditoriaSuministroRepository(db)` (ya existía, de CU-05) en ambos use cases.

### `main.py`
- 1 router nuevo registrado (`auditoria_suministros_router`).

### `requirements.txt`
- `openpyxl==3.1.5`, `reportlab==4.4.4` (+ transitivas `et-xmlfile==2.0.0`, `pillow==12.3.0`).
  Instaladas en el venv del proyecto.

## Verificación end-to-end

Ejecutada contra servidor local real (`uvicorn main:app`), con 4 usuarios de prueba
(Administrador, Contador, Revisor Fiscal, Productor para el caso RBAC negativo). CURLs completos
y respuestas reales en [`curls_m05_cu06_auditoria.md`](curls_m05_cu06_auditoria.md).

Confirmado: listar sin filtros y filtrado por `tipo_operacion` (`200`); detalle de un evento real
(`200`) y de uno inexistente (`404`); `403` para Productor sin permiso en el recurso 57;
exportación CSV/XLSX/PDF con `Content-Type`/`Content-Disposition` correctos y los 3 archivos
válidos (CSV 88 líneas, XLSX reconocido como `Microsoft Excel 2007+`, PDF válido de 4 páginas);
`400` para formato inválido; y el cierre del gap de RF-81 — llamar
`GET /suministros/historial` y `GET /suministros/historial/exportar` generó filas reales
`CONSULTA_HISTORIAL_EJECUTADA`/`EXPORTACION_HISTORIAL_GENERADA` en `auditorias_suministros`,
visibles de inmediato vía el nuevo endpoint de este CU.

No se usaron contraseñas en texto plano (no se contaba con ellas): se generaron sesiones/tokens
válidos directamente vía MCP postgres y se firmaron los JWT con `src.shared.jwt.create_token`,
equivalente en efecto a un login real.

`pytest --collect-only` → 0 tests en el repo (no hay suite que romper).

## Qué NO se hizo (pendientes explícitos, ver gap doc)

- Cola persistente M05→M12 con umbrales de capacidad (FA-08/09, RNF-07) — no aplica, sin
  arquitectura de cola/broker en M05.
- M12 no disponible 48h (FA-10/11) — no aplica, no existe un M12 externo separado.
- Deduplicación at-least-once por `id_evento_m05` (CA-14/15, RNF-09) — no aplica, sin reentrega
  posible al no haber cola.
- `PROVISION_INCREMENTAL_FALLIDA` / `PROVISION_PENDIENTE` — requieren push real hacia M06; ya
  documentado en CU-05 que M05 es autocontenido frente a M06.
- `PRECIO_MANUAL_INGRESADO` / `ACUMULADO_ACTUALIZADO` — duplicarían el `costo_afectado`/
  `origen_precio` que ya viaja en `SUMINISTRO_REGISTRADO`/`SUMINISTRO_CORREGIDO`.
