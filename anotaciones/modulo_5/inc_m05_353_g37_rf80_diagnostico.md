# INC-M05-353-G37 · RF-80 — Rechazos de RF-79/RF-81 y campos mínimos por tipo

Fecha: 2026-11-14. Responsable Git: destroyerban.
Issue: [#1077](https://github.com/Arekkazu/sgpmp-backend/issues/1077).
Rama: `fix/m05-inc353-g37-auditoria-rechazos-rf79-rf81`, creada desde `origin/dev` en `94787ed9`.
Requerimiento consultado: RF-80 v2.0 (RFC-025), copia de Drive del 2026-11-14.

## Diagnóstico confirmado

QA (TC-M05-G37, reintento 1, corrida `run-20261111-204540`) reporta tres checkpoints en falla:

| Checkpoint | Qué pasaba | Causa en el código |
|---|---|---|
| A02c | `POST /suministros/nic41/ciclo/{id}/consolidar` con ciclo activo → 409 sin evento | `ConsolidarCicloUseCase.execute` y `CorregirProvisionUseCase.execute` hacían `rollback; raise` sin auditar |
| A02d | `GET /suministros/historial` con fechas invertidas → 422 sin evento | `_auditar_consulta` solo se llamaba en la ruta exitosa; lo mismo en la exportación |
| A04 | 11 eventos sin los campos mínimos de la Restricción 8 y marcados como completos | El evento no tenía `id_registro_suministro` ni `id_tipo_suministro`, y `registro_incompleto` solo miraba activo y ciclo |

El trigger `fn_sellar_auditoria_m05` (migración `a107980ae001`, 2026-11-12) ya marca incompleta una fila sin activo o sin ciclo, así que en `dev` la `CONSULTA_HISTORIAL_EJECUTADA` sin ciclo ya no sale como completa. Los demás mínimos por tipo no los conoce el trigger.

## Corrección

1. **Campos mínimos por tipo (A04).** `EventoAuditoriaSuministro` valida al construirse los mínimos de la Restricción 8 para su tipo (además de activo y ciclo, que exige a todos). Si falta alguno: `registro_incompleto = true` y `detalle_causa` termina en `Campos faltantes: …` con cada campo. Si el emisor ya trae una causa, se conserva delante.
2. **Registro y tipo de suministro.** El evento acepta `id_registro_suministro` e `id_tipo_suministro`. Se guardan dentro de `datos_nuevos` (la tabla no tiene columna propia; el hash de la fila los cubre porque `to_jsonb(NEW)` incluye `datos_nuevos`). `GET /suministros/auditoria` y su detalle los devuelven en primer nivel. Se llenan en:
   - `RegistradorMovimientoLedger`: `SUMINISTRO_REGISTRADO`/`CORREGIDO`, `PRECIO_MANUAL_INGRESADO`, `ACUMULADO_ACTUALIZADO`.
   - Rechazo y fallo de RF-78, fallo de la corrección, fallo del registro de medicamento.
   - Entrega a M06 (`PROVISION_INCREMENTAL_*`, `PROVISION_PENDIENTE`), que además ahora lleva el ciclo.
3. **Rechazos de RF-79 (A02c).** `ConsolidarCicloUseCase.registrar_rechazo` sigue el patrón de RF-78 (INC-M05-275-G37): revierte el intento y confirma solo el evento en una transacción aparte. Tipo = el de la operación (`CICLO_CONSOLIDADO` al consolidar, `REPORTE_COSTOS_GENERADO` al corregir), resultado `RECHAZADO` (4xx) o `FALLIDO` (5xx). Solo se enlaza la fase si existe. El cierre de ciclo (RF-38), que usa `consolidar_sin_commit`, no cambia.
4. **Rechazos de RF-81 (A02d).** `auditoria_historial.registrar_rechazo_historial`, compartido por consulta y exportación: mismo patrón, tipo `CONSULTA_HISTORIAL_EJECUTADA` o `EXPORTACION_HISTORIAL_GENERADA` con resultado `RECHAZADO`. Cubre 403, 404, 422 y 429. Solo enlaza el activo si el usuario lo ve, y el ciclo si pertenece al activo; lo pedido queda en `datos_nuevos.filtros_aplicados`.
5. **Ciclo del evento exitoso del historial.** El ciclo filtrado o, si el resultado abarca un solo ciclo, ese. Con varios ciclos no hay uno solo que registrar y el evento queda incompleto, como pide la Restricción 8.

## Decisiones tomadas sin consultar a Análisis

| Punto que el ticket deja abierto | Decisión | Por qué |
|---|---|---|
| Tipo de evento para los rechazos de RF-79/RF-81 | El de la operación con `RECHAZADO` | Es la primera opción del ticket, no requiere ampliar el enum (sin migración ni RFC) y CA-1 habla de «operación exitosa o fallida». |
| `id_ciclo_productivo` en `CONSULTA_HISTORIAL_EJECUTADA` | Se exige (incompleto si la consulta abarca varios ciclos) | Es lo que dice la Restricción 8 hoy. Si Análisis la relaja por RFC, basta con quitarlo de la tabla de mínimos. |
| Rechazo de consolidar sin costo | Queda incompleto con «costo afectado» faltante | Restricción 8 literal; un rechazo no mueve monto y lo declara. |
| Nombres en `detalle_causa` | En palabras («tipo de suministro»), no `id_tipo_suministro` | El detalle se muestra en la bitácora, su Excel y su PDF, y la regla de textos visibles (CLAUDE.md, 2026-11-05) prohíbe nombres de columna. Se nombra cada campo, que es lo que pide la re-prueba. |

## Persistencia

Sin migración ni cambios de RBAC: `RECHAZADO` y los tipos usados ya existen en los enums de PostgreSQL, y `datos_nuevos` es la columna JSON existente.

## Pruebas

| Grupo | Aprobadas | Fallidas |
|---|---:|---:|
| `tests/supplies` (incluye 30 nuevas en `test_inc_m05_353_g37_auditoria_rf79_rf81.py`) | 198 | 1 (*) |
| Integración nueva `test_inc_m05_353_g37_auditoria_rf79_rf81_integration.py` (A02c, A02d, A04) | 3 | 0 |
| Integración de G37 (#960), G39 y el resto de M05 (4 omitidas) | 156 | 10 (*) |

(*) Fallan igual en `dev` sin este cambio. Son del entorno local Windows: falta `tzdata` (G38) y la conexión de prueba es superusuario y los grants de `sgpmp_app` no aplican (RLS de finca, `permission denied for schema modulo1/modulo5`).

Se ajustaron dos pruebas de G39 que asumían que `REGISTRO_FALLIDO` solo exigía activo y ciclo: ahora el caso «completo» trae también tipo de suministro y número de reintentos.
