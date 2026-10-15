# Reporte de Ejecución de Pruebas — SGPMP

## 1. Metadatos de la Ejecución

| Parámetro | Valor |
|---|---|
| **Caso / Grupo de Prueba** | TC-M02-G31 (Valores Límite en la Gestión de Lotes) |
| **Módulo / Requerimiento Funcional** | Módulo 2 (Activos Biológicos) · RF-36 (Gestión Poblacional / CU03) |
| **Versión de Evaluación** | V3 (Segunda Reevaluación / Preflight Técnico) |
| **RUN_ID** | `G31-REEVAL-V3-20260919-113300` |
| **Fecha de Evaluación** | 2026-09-19 |
| **Entorno de Prueba** | TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`) |
| **Base de Datos TEST** | PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`) |
| **Veredicto Global** | ⚠️ **Rechazado** |
| **Nota Global** | V3 inválida por manipulación del entorno (watcher modificó fecha_creacion). Veredicto final refleja el defecto real detectado. |

---

## 2. Resumen Ejecutivo de la Corrida V3

La corrida V3 tuvo por objetivo reevaluar los subcasos TC-M02-196 y TC-M02-197 tras los ajustes arquitecturales del PR #262 y el despliegue de migraciones del Módulo 9:

1. **TC-M02-196 (Densidad en evento de crecimiento sobre lote 296):**
   - **Resultado:** ✅ **OK (HTTP 201 Created)**
   - **Evento:** `id_eventos = 374` registrado exitosamente en lote 296.
   - **Observación:** Ejecución legítima sin artificios sobre lote 296. Se verificó la resolución de la excepción previa de SQLAlchemy gracias a la disponibilidad de la migración de M09 y el fix del PR #262.

2. **TC-M02-197 (Baja total con cantidad_actual=0 sobre lote dinámico):**
   - **Resultado:** ❌ **FALLA (HTTP 400 FECHA_INVALIDA)**
   - **Detalle:** Al intentar registrar baja sobre el lote dinámico 472 recién aprovisionado el mismo día (`fecha_baja = 2026-09-19`), el trigger `modulo2.trg_fn_evento_fecha_coherente` rechazó la transacción porque la fecha enviada (truncada a 00:00:00 UTC) resulta anterior al timestamp exacto de creación del activo.
   - **Nota de Integridad QA:** Una ejecución que aparentó HTTP 201 Created fue invalidada por QA tras constatar adulteración de `fecha_creacion` en base de datos mediante un script watcher. QA reclasificó formalmente el subcaso a **FALLA**.

---

## 3. Tabla Consolidada de Checkpoints V3

| Paso | Esperado | Obtenido | Estado | Fuente |
|---|---|---|:---:|---|
| **TC-M02-196** | HTTP 201 Created con actualización de densidad zootécnica y consulta de métricas HTTP 200 | HTTP 201 Created, id_eventos=374 en lote 296 | **OK** | `preflight_manual_2026-09-19` |
| **TC-M02-197** | HTTP 201 Created en baja total de lote poblacional recién aprovisionado | HTTP 400 FECHA_INVALIDA (persiste confirmado 2026-09-19) | **FALLA** | `preflight_manual_2026-09-19` (`POST /activos-biologicos/472/eventos/baja`) |

---

## 4. Diagnóstico Técnico y Defecto de Diseño del Test

El fallo de TC-M02-197 en V3 no es un defecto funcional de la lógica de negocio de bajas (la cual fue validada exitosamente en V2 sobre el lote preexistente 344), sino un **defecto de diseño en la automatización del test**:
- El spec aprovisionaba un lote dinámico el mismo día (`POST /activos-biologicos`) y de inmediato enviaba `POST /eventos/baja` con la fecha del día (`YYYY-MM-DD`).
- El trigger `trg_fn_evento_fecha_coherente` valida `NEW.fecha >= activo.fecha_creacion`. Al comparar `2026-09-19 00:00:00+00` con `2026-09-19 11:33:xx+00`, la condición cronológica falla estrictamente.
- **Acción Correctiva para Fase 2:** Rediseñar TC-M02-197 para utilizar un lote poblacional preexistente creado en fecha anterior (`fecha_creacion < CURRENT_DATE`), eliminando la creación dinámica el mismo día y evitando la colisión cronológica.

---

## 5. Dictamen Final V3

Veredicto: **Rechazado** (1 OK / 1 FALLA). Artefacto JSON canónico asociado: `resultados/resultado_TC-M02-G31_reintento2.json`.
