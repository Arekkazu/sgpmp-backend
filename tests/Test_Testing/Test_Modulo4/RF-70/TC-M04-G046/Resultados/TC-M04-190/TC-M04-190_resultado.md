# TC-M04-190 — Resultado de ejecución

Fecha: 2026-10-25. Rama `laura`. Responsable: Laura Lopez.  
Grupo: **TC-M04-G046**. RF-70 / CU-06. Capa: **API + Edge**.

Script interno: `test_tc_m04_027_modos_inmediato_programado_lotes` (SKIP) y `test_tc_m04_027_consulta_filtra_por_dispositivo` (PASSED, **consulta**, no orquestación). ID de matriz: **TC-M04-190**. Colisión histórica: el número 027 también aparece en G038/RF-65; aquí no se usa 027 como ID oficial.

---

## 1. Identificador original

**TC-M04-190** — Modos INMEDIATO, PROGRAMADO y POR_LOTES.

## 2. Criterios (matriz / RF-70 CA-12 y E1, según enunciado)

- **INMEDIATO:** arranque en el próximo ciclo de comunicación; estado inicial, instante de inicio, evidencia de proceso.
- **PROGRAMADO:** fuera de ventana permanece PENDIENTE; no inicia OTA antes; transición si el entorno lo permite.
- **POR_LOTES:** subconjuntos secuenciales; no saturar el canal; tamaño de lote y estados.

## 3. Precondiciones

`modo_distribucion` es columna String(20) persistida y **expuesta en GET**. Dev no programa ventanas ni lotes. Ficha RF-70 (CA-12, E1) **no** está en el repo.

## 4. Comandos

Pytest G046. Inventario OTA. Sin API, sin Edge, sin varios dispositivos reales.

## 5–7. Esperado vs observado

| Modo | Esperado | Observado |
|---|---|---|
| INMEDIATO | Inicio en próximo ciclo | **No orquestado.** El campo puede leerse en un DTO de consulta |
| PROGRAMADO | PENDIENTE fuera de ventana | Columnas `ventana_inicio`/`ventana_fin` existen; **ningún job** las evalúa en `src/prediction` |
| POR_LOTES | Subconjuntos secuenciales | **Sin** tamaño de lote ni scheduler en este backend |
| Unitario filtro dispositivo | Aislamiento de listado | PASSED: INMEDIATO vs PROGRAMADO filtrados por `id_dispositivo` en memoria. **No** demuestra modos |

HTTP de orquestación: no hay. API local: timeout.

## 8. Auditoría

GET de listado auditaría `CONSULTA_DESPLIEGUES_OTA` si se llamara el use case con sesión real. No se ejecutó contra BD.

## 9. Pruebas

| Ítem | Resultado | Cuenta para 190 |
|---|---|---|
| `test_tc_m04_027_modos_*` | SKIPPED | El escenario de modos: no cubierto |
| `test_tc_m04_027_consulta_filtra_por_dispositivo` | PASSED unitario | No |
| Ciclos/ventanas/lotes Edge | **No ejecutada** | Obligatorio |

## 10. Limitaciones

Sin infraestructura de ciclos de comunicación, ventanas ni flota. Sin ficha CA-12/E1. Pytest EXIT=0 no aprueba.

## 11. Evidencias

- `.../TC-M04-G046/Resultados/TC-M04-190/TC-M04-190_resultado.md`
- `.../evidencias/ejecucion-2026-10-25-2109/`
- `.../auditoria-2026-10-25/g046.{txt,html,xml}`

## Estado

**BLOQUEADO.**
