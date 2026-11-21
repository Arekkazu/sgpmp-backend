# Diagnóstico integral — TC-M06-G96 (A+B)

**Fecha:** 2026-11-13  
**Dictamen técnico:** **VALIDACIÓN A+B COMPLETADA** (entorno aislado)  
**Estado del grupo QA:** `PREPARADO_CON_RIESGOS` respecto a APROBADO end-to-end en API TEST compartido — **no** se declara APROBADO E2E.

---

## 1. Qué se investigó

- Worktree `sgpmp-backend-g96-ab` HEAD `91f79e75` (incluye `8829599f`).
- Rama `laura` intacta.
- Dominio: `valor_por_costo`, `valor_libros_calculado`.
- Casos de uso: `RegistrarDeterioroUseCase`, `evento_valor_libros_cero`, cierre `_depreciar`, consulta de auditoría.
- Prueba `tests/integration/test_inc_m06_281_g68_valor_libros_cero.py` (cubre TC-M06-07 + controles).
- Migración `c6e8a0b2d453` y cadena Alembic hasta head.
- Fixtures `db_session` (rollback) y requisitos de `TEST_DATABASE_URL`.
- Entorno Docker local y contenedores preexistentes.
- Ausencia inicial de `TEST_DATABASE_URL`.
- Conflicto Windows: paquete `tests` de site-packages y módulo `fcntl`.

## 2. Recursos encontrados

| Recurso | Uso |
|---|---|
| `g43-postgres` (:5439, `sgpmp_g43_test`) | **No usado** (otro laboratorio) |
| `infra-db-1` (:5433, `sgpmp`) | **No usado** (no demostrada exclusividad) |
| API TEST `api.inmero.co` | **Sin escrituras** |
| Docker Engine 29.4.3 | Disponible → base temporal propia |

## 3. Entorno utilizado (creado en esta ejecución)

| Recurso propio | Identificador |
|---|---|
| Imagen | `g96-ab-postgres:tmp` (desde `Dockerfile.postgres`) |
| Contenedor | `g96-ab-postgres-tmp` |
| Volumen | `g96_ab_pgdata_tmp` |
| Puerto host | `127.0.0.1:55496` |
| Base | `g96_ab_test` |
| Roles bootstrap | `sgpmp_app`, `sgpmp_owner` (NOLOGIN, solo para GRANT de migraciones) |
| Worktree harness | `_qa_harness_g96/fcntl.py`, `tests/__init__.py` |

Credenciales: solo en proceso / archivo TEMP del usuario; **no** en evidencias.

## 4. Aislamiento verificado

1. Host `127.0.0.1`, puerto **nuevo** 55496 (no 5432/5433/5439).  
2. Nombre de BD `g96_ab_test` (contiene `test`).  
3. Contenedor/volumen/imagen con prefijo `g96-ab-` creados aquí.  
4. Migraciones **solo** sobre esa BD.  
5. Datos sintéticos; fixture con rollback.  
6. Assert programático pre-pytest: host/port/db.  
7. Sin POST/PUT/PATCH/DELETE al API TEST compartido.  
8. Sin tocar 2126 / 66 / 886 / 411 / 219 / 220.

## 5. Pruebas ejecutadas

| Capa | Comando / suite | Resultado |
|---|---|---|
| A | `test_tc_m06_g96_dominio_A.py` | **3 passed** |
| B | `test_inc_m06_281_g68_valor_libros_cero.py` | **3 passed** |
| Evidencia | `_capturar_evidencia_alerta.py` (rollback) | alerta total=1, calc=−2000000.0000 |

## 6. Criterios demostrados vs pendientes

**Demostrados en aislamiento:** cálculo 05/06/07, piso a cero, generación y consulta de `VALOR_LIBROS_AJUSTADO_A_CERO`, control de no-alerta cuando no hay negativo, alerta también desde depreciación de cierre.

**Pendientes si el AC exige E2E:** HTTP Contador en TEST compartido, seed DBA, `GET /finanzas/auditoria` sobre datos del ambiente desplegado.

## 7. Bloqueos que permanecen

- Ninguno para validación técnica A+B aislada.  
- Para APROBADO del grupo en ambiente compartido: sigue haciendo falta autorización/ejecución HTTP o aceptación formal de evidencia aislada como suficiente.

## 8. Limpieza

Tras archivar evidencias se eliminan **solo** contenedor/volumen/imagen/`TEMP` creds creados aquí. No se tocan otros contenedores.
