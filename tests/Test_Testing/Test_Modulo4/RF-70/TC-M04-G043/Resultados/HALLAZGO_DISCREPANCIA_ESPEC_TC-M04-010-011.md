# Discrepancia de especificación — TC-M04-010 / TC-M04-011 (G043)

**No es incidencia oficial ni defecto de producto.** Sin ID `INC-M04-*`.

## Título

Contradicción de gate de estado para OTA (APROBADO vs ACTIVO) y ausencia de POST de distribución en Dev.

## Fuentes (exactas en este repo)

| Fuente | Qué dice |
|---|---|
| Script `test_tc_m04_g043.py` | RF-70 pide APROBADO; RF-69 propaga solo ACTIVO; CU-M04-06/FA-01: «no está en estado ACTIVO o no ha sido aprobada». |
| `ota_router.py` | RF-70 CU-06: solo GET ota-status y GET despliegues. |
| `anotaciones/modulo_4/curls_m04_cu06_ota.md` | Split: Dev consulta; IoT/IA escribe `modulo4.despliegues_ota`. |
| `anotaciones/modulo_4/api_reference_m04_prediccion.md` | OTA: GET; activar versión: POST `.../activar` desde **APROBADO** (RF-69). |
| `anotaciones/modulo_4/curls_m04_cu05_versiones_modelo.md` | Activar exige APROBADO + notas. |
| `VersionModelo.activar` / `ActivarVersionModeloUseCase` | Transición APROBADO → ACTIVO; no inicia OTA. |
| `src/prediction/application/use_cases/ota/` | Solo consulta y listado. |

Las fichas RF-70/RF-69/CU-M04-06 **no** están versionadas como archivos de requerimiento en este workspace; el texto de FA-01 se cita desde el script de prueba.

## Estado anterior → ahora

Matriz 2026-10-19: PENDING_SPEC + BLOCKED. 2026-10-25: igual, con reejecución segura.

## Clasificación

**Discrepancia de especificación** + **bloqueo de entorno/alcance Dev** (sin orquestador OTA).

## Acción y cierre

Analista elige ficha aplicable (APROBADO vs ACTIVO vs “ACTIVO o aprobada”). Implementar o no POST de inicio queda fuera de esta reevaluación. Criterio de cierre: ficha firmada + prueba de distribución (IoT/IA) si aplica.
