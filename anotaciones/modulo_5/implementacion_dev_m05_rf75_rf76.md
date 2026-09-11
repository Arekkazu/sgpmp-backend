# Implementación M05 CU-01 — Gestión de Suministros (RF-75, RF-76)

> **Fecha:** 2026-07-30
> **Módulo:** 5 (Gestión de Suministros) · `src/supplies` · schema `modulo5`
> **Alcance:** CU-01 "Gestionar Registro de Suministros" — registro y anulación de
> consumo de alimentos (RF-75) y aplicación de medicamentos (RF-76), con cálculo por
> individuo POBLACIONAL, control de duplicados, inmutabilidad y transición a
> EN_TRATAMIENTO vía RF-44.

## Resumen

| # | Entregable | Tipo | Qué se hizo |
|---|-----------|------|-------------|
| 1 | Paso 0 BD/RBAC | DDL/DML | Índices únicos, enum vía, columna `nombre_veterinario`, CHECK anulación, recursos 47/48 + permisos, `pgcrypto` |
| 2 | Modelos ORM | Código | `registros_consumo_alimentos`, `registros_medicamentos`, `tipos_alimentos` (schema modulo5) — **generados con sqlacodegen** desde la BD y adaptados (Base compartida, clase `<Agregado>Model`, enums PG como `String`, sin relationships cross-module) |
| 3 | Dominio | Código | Entidades `ConsumoAlimento`/`Medicamento`, VOs (estado, vía, justificación), 6 puertos |
| 4 | Infraestructura | Código | DTOs, repos SQLAlchemy, 4 adapters cross-module (RF-33/36/37/41/44) |
| 5 | Aplicación + API | Código | 6 use cases, schemas, 2 routers RBAC, registro en `main.py` |
| 6 | Documentación | Docs | Gaps, CURLs, este resumen |

Endpoints (todos bajo `/suministros`):
- `POST /consumo-alimentos` · `POST /consumo-alimentos/{id}/anulacion` · `GET /consumo-alimentos`
- `POST /medicamentos` · `POST /medicamentos/{id}/anulacion` · `GET /medicamentos`

## Paso 0 — Análisis de BD y RBAC (vía MCP postgres)
Ver `cu01_gaps_bd_rf75_rf76.md`. Puntos clave:
- **La BD implementa por triggers** el cálculo de costos, la inmutabilidad, el rechazo de
  borrado y **la auditoría** (`fn_trg_auditoria_*` → `auditorias_suministros`). La
  aplicación **no** duplica eso: valida en el use case (errores HTTP limpios) y deja el
  trigger como refuerzo. **No hay capa de auditoría en `src/supplies`.**
- RBAC nuevo: recursos `consumo_alimentos` (47) y `medicamentos` (48) + 15 permisos.
  Registro de medicamento restringido a Administrador y Veterinario.
- `CREATE EXTENSION pgcrypto` fue **imprescindible**: el trigger de hash de auditoría usa
  `digest()`; sin la extensión, todo INSERT fallaba con 500.

## Arquitectura (hexagonal, espejo de `configuration`)

```
Router → UseCase → Port(ABC, domain/repositories) ← Repository/Adapter(infrastructure)
```
- **Puertos de dominio:** `consumo_alimento_repository`, `medicamento_repository`,
  `activo_consulta_port` (RF-33/36), `ciclo_abierto_port` (RF-37/38),
  `evento_sanitario_consulta_port` (RF-41), `estado_activo_port` (RF-44).
- **Adapters cross-module** (`infrastructure/adapters`, bajo acoplamiento): reutilizan
  `biological_assets` sin que el dominio de suministros conozca modulo2.
  - `activo_m02_adapter` / `ciclo_m02_adapter` → `SqlAlchemyActivoBiologicoRepository`.
  - `evento_sanitario_m02_adapter` → SQL directo (join `eventos_sanitarios`↔`eventos_activos`).
  - `estado_activo_m02_adapter` (**RF-44 real**) → reutiliza el repo de activos + la entidad
    `cambiar_estado(EN_TRATAMIENTO)` + `SqlAlchemyHistoricoEstadoRepository` con `flush()`
    (sin commit). Participa en la MISMA transacción del use case (un único commit).
    Idempotente: si el activo ya está EN_TRATAMIENTO no hace nada (E11).

## Flujo del caso de uso — registrar medicamento (RF-76)
1. Consultar activo (404 si no existe); estado ∈ {ACTIVO, EN_TRATAMIENTO} (422 si no).
2. Ciclo abierto (422 si no); fecha ≤ hoy y ≥ inicio de ciclo (400 si no).
3. Vía válida (VO); evento sanitario del mismo activo si se envía (422 si no).
4. POBLACIONAL → `dosis_por_individuo = dosis / cantidad_actual`.
5. `fecha_fin_retiro = fecha_aplicacion + periodo_retiro_dias` (si > 0).
6. Pre-check duplicado (409). Persistir (el trigger calcula `costo_total_medicamento`).
7. Si retiro > 0 → `estado_port.marcar_en_tratamiento(...)` (RF-44) en la misma transacción.
8. `commit`. Devolver el registro + `fecha_fin_retiro_vigente = MAX(fecha_fin_retiro)`.

(El de consumo es análogo, sin RF-44; el costo lo calcula el trigger con el precio del
catálogo, por eso el DTO de consumo no recibe `costo_unitario`.)

## Decisiones de diseño
- **Auditoría por trigger, no por aplicación.** Evita duplicar filas en `auditorias_suministros`.
- **Costo autoritativo en BD.** No se calcula en la app; se relee tras `flush/refresh`.
- **Anulación = UPDATE VALIDADO→ANULADO** tocando solo estado + justificación +
  `fecha_hora_anulacion` (el trigger de inmutabilidad protege el resto).
- **RF-44 de bajo acoplamiento** vía puerto + adapter que reutiliza el flujo real de
  biological_assets, sin acoplar el dominio de suministros a modulo2.
- **Enums PG mapeados como `String`** en los modelos ORM (CLAUDE.md).

## Cómo se verificó (end-to-end contra la BD dev)
Servidor `uvicorn`, tokens JWT para Administrador/Productor/Veterinario. Todos los
escenarios pasaron:
- Consumo INDIVIDUAL `201` (costo_total 10.5 calculado por trigger); duplicado `409`;
  fecha futura `400`; activo INACTIVO `422`; registro por Productor `201`.
- Consumo POBLACIONAL (activo 8, cantidad_actual 7650): `consumo_por_individuo_kg = 0.0100`.
- Medicamento con retiro 7d → `201`, `fecha_fin_retiro 2026-08-05`, y **activo 5 →
  EN_TRATAMIENTO (id_estado=3)** con histórico `1→3 (modulo5)`. Segundo tratamiento
  concurrente (E11) → vigente `MAX = 2026-08-08`, sin duplicar el cambio de estado.
- Medicamento POBLACIONAL: `dosis_por_individuo = 0.0020` (15.3/7650).
- Evento sanitario de otro activo `422`; del mismo activo `201`; vía inválida `400`;
  registro por Productor `403`.
- Anulaciones: justificación < 20 `400`; válida `200 ANULADO`; re-anular `409`; Productor
  anulando consumo `403`; medicamento anular `200`/`409`.
- Auditoría: `modulo5.auditorias_suministros` acumula INSERT/UPDATE con actor, snapshot,
  `hash_integridad` y `resultado=EXITOSO` (auto-generada por trigger).

Notas de datos de prueba (dev): quedaron registros de prueba (consumos 27/28/29,
medicamentos 13–16) — son append-only. El activo 5 queda EN_TRATAMIENTO porque su
tratamiento id 15 (VALIDADO) tiene retiro hasta 2026-08-08. Se reconciliaron históricos de
estado desincronizados en modulo2 para poder ejercitar RF-44 (ver el doc de gaps).

## Qué NO se hizo (alcance)
- Scheduler diario de vencimiento de retiro y reversión a ACTIVO (RF-44/RF-76 pasos 11-13).
- ICA/RF-74, acumulación por ciclo/RF-78, provisión NIC-41/RF-79, reporte de gastos/RF-77,
  export a M06 (tablas de modulo5 ya existentes pero fuera de CU-01).
- Bus asíncrono RF-80 y deduplicación por `id_evento_m05` (no modelado).
- Notificaciones al Veterinario/Productor sobre inicio de período de retiro (RF-76 paso 9).
