# TC-M04-180 — Resultado de ejecución

Fecha: 2026-10-25. Rama `laura`. Responsable matriz: Laura Lopez.  
Grupo: **TC-M04-G043**. RF-70 / CU-06.

Script interno: `test_tc_m04_011_activar_version_exige_aprobado_rf69_no_es_ota`. Correspondencia temática (rechazo de modelo no apto), **ID de matriz: TC-M04-180**. Histórico `TC-M04-011/` no se sobrescribió.

---

## 1. Identificador original

**TC-M04-180** — Rechazar la distribución de un modelo no aprobado.

## 2. Objetivo y criterios

Estados EN_VALIDACION, RECHAZADO y DEPRECADO: rechazo **antes** de iniciar OTA, HTTP **412** según matriz, sin descargas, activaciones ni cambios del modelo vigente. Comprobar estado del dispositivo y registros.

## 3. Precondiciones

Sin ficha RF-70 que fije 412 para OTA. Sin POST de distribución. Sin Edge.

## 4. Comandos

Mismo pytest G043 e inventario OTA que TC-M04-179. Sin POST a BD compartida.

## 5–7. Esperado vs observado

| Criterio | Esperado (matriz) | Observado |
|---|---|---|
| Rechazo OTA EN_VALIDACION / RECHAZADO / DEPRECADO | Antes de OTA | **No hay use case de inicio**; no se puede rechazar un proceso que Dev no arranca |
| HTTP 412 | Respuesta de distribución | **No hay HTTP de inicio.** API local timeout |
| Sin descarga/activación | Vigente intacto | No verificado en Edge (no hay canal) |
| `VersionModelo.activar()` desde EN_VALIDACION | — | Unitario: `VERSION_NO_APROBADA` (RF-69, no OTA). Atributo de `BusinessRuleError`, no HTTP 412 de CU-06 |

Pytest `test_tc_m04_011_*` **PASSED** solo caracteriza RF-69. **No** cubre TC-M04-180.

## 8. Auditoría

No ejecutada a nivel API.

## 9. Pruebas

| Ítem | Resultado |
|---|---|
| Unitario activar() RF-69 | PASSED (no es OTA) |
| API/Postman rechazo 412 OTA | **No ejecutada** |
| Edge | **No ejecutada** |

## 10. Limitaciones

Gate APROBADO vs ACTIVO sin ficha. HTTP 412 de matriz no aparece en el contrato Dev de CU-06 (GET 200/400/401/403/404). Activar versión documenta 422.

## 11. Evidencias

- `.../TC-M04-G043/Resultados/TC-M04-180/TC-M04-180_resultado.md`
- `.../TC-M04-180/evidencias/ejecucion-2026-10-25-2109/` (`g043-pytest.txt`, `inventario-ota.txt`, `api-local.txt`)
- `.../Resultados/auditoria-2026-10-25/g043.{txt,html,xml}`

## Estado

**BLOQUEADO.** No se declara RECHAZADO de producto: el criterio 412 OTA no está en ficha versionada aquí y el puerto de inicio no existe en Dev.
