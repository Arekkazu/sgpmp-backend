# Hallazgo — Gate APROBADO vs ACTIVO (TC-M04-179 / TC-M04-180)

**No es incidencia de producto ni defecto confirmado.** Distinto de `HALLAZGO_DISCREPANCIA_ESPEC_TC-M04-010-011.md` (histórico; no se modificó).

## Contradicción citada (matriz)

- RF-70 / precondiciones / CA-1: solo modelos **APROBADOS**.
- RF-69 fase 7: la versión **ACTIVA** queda disponible para RF-70.
- CU-M04-06/FA-01: gate «ACTIVO **o** aprobada».

## Fuentes en este repositorio (2026-10-25)

| Fuente | Contenido |
|---|---|
| Fichas RF-69, RF-70, CU-M04-06 | **Ausentes** como archivos versionados |
| `ota_router.py` / curls CU-06 | Solo GET. Split: IoT/IA escribe `modulo4.despliegues_ota` |
| `use_cases/ota/` | Consulta y listado. **No seleccionan** versión por estado |
| `VersionModelo.activar` / `POST .../activar` | RF-69: solo desde **APROBADO** → **ACTIVO**. No inicia OTA |
| `api_reference_m04_prediccion.md` | Activa exige APROBADO; OTA es lectura |

## Conclusión de implementación

El backend **no distribuye** una versión APROBADA ni ACTIVA: **no hay selector OTA**. Quien cree filas de despliegue (IoT/IA, fuera de este código) decide qué `id_version_modelo` persiste. RF-69 puede dejar una versión ACTIVA *antes* de un despliegue, pero eso no demuestra el gate de RF-70.

No se eligió APROBADO, ACTIVO ni “ACTIVO o aprobada” como expectativa de prueba.

## Cierre

Analista/dueño de ficha: una redacción. Luego prueba API+Edge del emisor OTA. Hasta entonces, TC-M04-179 y TC-M04-180 permanecen **BLOQUEADOS** por especificación + alcance Dev.
