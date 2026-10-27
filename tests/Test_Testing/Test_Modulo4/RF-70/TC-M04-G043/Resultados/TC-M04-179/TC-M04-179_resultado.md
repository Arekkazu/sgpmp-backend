# TC-M04-179 — Resultado de ejecución

Fecha: 2026-10-25. Rama `laura`. Responsable matriz: Laura Lopez.  
Grupo: **TC-M04-G043**. RF-70 / CU-06. Prioridad Alta.  
Capa exigida: **API + Edge / API / Postman**.

El script interno usa `test_tc_m04_010_*`. **No es equivalente** al subcaso de matriz hasta esta correspondencia: mismo tema (inicio OTA de modelo apto), distinto ID. Este informe usa **TC-M04-179**.

Histórico `Resultados/TC-M04-010/` no se sobrescribió.

---

## 1. Identificador original

**TC-M04-179** — Distribuir modelo aprobado al nodo Edge.

## 2. Objetivo y criterios

Con modelo APROBADO y dispositivo Edge ACTIVO: iniciar y completar OTA (versión correcta, estados, artefacto SHA-256, descarga, integridad, activación, rollback de versión anterior, resultado, auditoría, continuidad de inferencia). Una HTTP 2xx que solo cree una orden no cierra el caso.

## 3. Datos y precondiciones

No se dispuso de: ficha RF-70 versionada, JWT, API local, dispositivo Edge, artefacto, ni autorización para escribir `modulo4.despliegues_ota`.

## 4. Comandos

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/Test_Testing/Test_Modulo4/RF-70/TC-M04-G043/test_tc_m04_g043.py
```

Inventario estático de `ota_router` y `DespliegueOtaModel`.  
`Invoke-WebRequest http://127.0.0.1:8000/docs` (timeout 2 s).

## 5–7. Esperado vs observado / HTTP / OTA

| Criterio | Esperado | Observado |
|---|---|---|
| POST inicio OTA | Endpoint de distribución | **No existe.** Solo GET `/prediccion/modelos/{id}/ota-status` y GET `/prediccion/despliegues` |
| Descarga Edge + hash + activación | Evidencia de OTA completa | **No ejecutada** (sin Edge, sin emisor IoT/IA) |
| HTTP | Códigos reales de distribución | **Ninguno.** API local ausente. Colección Postman G043 inexistente |
| Pytest | No sustituye API+Edge | EXIT=0: 2 passed (caracterización), 1 skipped `PENDING_SPEC` |

Repositorio OTA: solo `listar`, `obtener_por_id`, `obtener_por_version`. Sin lock, sin insert.

## 8. Auditoría / persistencia

Los GET de consulta registrarían `CONSULTA_OTA_STATUS` / `CONSULTA_DESPLIEGUES_OTA` si hubiera API+JWT. **No se llamó** (evitar escritura de auditoría en BD compartida).

## 9. Pruebas

| Nodo | Resultado | Relación con 179 |
|---|---|---|
| `test_tc_m04_010_011_ambiguedad_gate_aprobado_vs_activo` | SKIPPED | Gate no fijado |
| `test_tc_m04_010_router_ota_solo_lectura` | PASSED (unitario) | Confirma ausencia de POST; **no** es OTA exitosa |
| Distribución API+Edge | **No ejecutada** | Capa exigida |

## 10. Limitaciones

Fichas RF-69/RF-70 ausentes. Split Dev: consulta; IoT/IA escribe la tabla. Contradicción APROBADO vs ACTIVO no ratificada. Sin dispositivo.

## 11. Evidencias

- `.../TC-M04-G043/Resultados/TC-M04-179/TC-M04-179_resultado.md`
- `.../TC-M04-179/evidencias/ejecucion-2026-10-25-2109/g043-pytest.txt`
- `.../inventario-ota.txt`
- `.../api-local.txt`
- `.../Resultados/auditoria-2026-10-25/g043.{txt,html,xml}` (pytest del grupo)

## Estado

**BLOQUEADO.** Pytest EXIT=0 no aprueba el subcaso.
