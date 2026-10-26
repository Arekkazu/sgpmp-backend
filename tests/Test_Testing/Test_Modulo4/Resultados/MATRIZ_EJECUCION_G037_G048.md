# Matriz de ejecución TC-M04-G037–G048

Fecha: 2026-10-19. Rama `laura`. Pytest: 41 passed, 20 skipped, 0 failed.
Comando: `SECRET_KEY=test-m04-local-no-prod DATABASE_URL=sqlite:///:memory: python -m pytest tests/Test_Testing/Test_Modulo4 --noconftest -v`

Estados de **subcaso de matriz** (no se cuenta un SKIP de pytest como PASS del requisito).

| Grupo | TC matriz | RF | Archivo | Función/endpoint | Tipo | Resultado subcaso | Evidencia | Bloqueo |
|---|---|---|---|---|---|---|---|---|
| G037 | TC-M04-001 | RF-65 | `RF-65/TC-M04-G037/test_tc_m04_g037.py` | `ConfigurarMotorUseCase.execute` | Unitario | **BLOCKED** (hot-reload/SQL) | Apply+auditoría en memoria PASSED; skip hot-reload | Edge; persistencia PostgreSQL |
| G037 | TC-M04-002 | RF-65 | idem | rangos 0.50–0.95 y 5–15 | Unitario | **PASS** | límites in/out PASSED | — |
| G037 | TC-M04-003 | RF-65 | idem | alerta ≥ riesgo | Unitario | **PASS** | 422 `UMBRAL_CRITICA_MENOR_QUE_RIESGO`, vigente intacta | — |
| G038 | TC-M04-005 | RF-65 | `RF-65/TC-M04-G038/...` | versión no ACTIVO | Unitario | **PASS** | 412 `MODELO_NO_ACTIVO` APROBADO/DEPRECADO/RECHAZADO | HTTP real contra BD no ejecutado |
| G038 | TC-M04-021 | RF-65 | idem | compatibilidad llave | Unitario | **PASS** (conflicto HTTP) | Dev 422 `VERSION_MODELO_INCOMPATIBLE`; matriz pedía 409 | Contrato 409 vs 422 |
| G039 | TC-M04-006 | RF-65 | `RF-65/TC-M04-G039/...` | auditoría append | Unitario + skip SQL | **BLOCKED** (SQL) | registro usuario/diff PASSED; UPDATE/DELETE SQL no ejecutado | BD aislada; triggers |
| G039 | TC-M04-019 | RF-65 | idem | config_version en inferencia | Skip | **BLOCKED** | `resultados_inferencia` sin `config_version` | Campo inexistente |
| G039 | TC-M04-020 | RF-65 | idem | rollback al aplicar | Unitario | **PASS** | fallo simulado, vigente v1, rollback | No es HTTP 500 de API |
| G040 | TC-M04-007 | RF-65 | `RF-65/TC-M04-G040/...` | sync Edge ≤5 s | Skip | **BLOCKED** | — | Cliente Edge |
| G040 | TC-M04-008 | RF-65 | idem | fallback ≤2 s | Skip | **BLOCKED** | — | Cliente Edge |
| G040 | TC-M04-022 | RF-65 | idem | EDGE/HIBRIDO sin nodos | Unitario | **PASS** | `MODO_EDGE_SIN_NODOS`; stub prod siempre True | Stub productivo no prueba ausencia real |
| G040 | TC-M04-023 | RF-65 | idem | reconciliación >5 s / FALLIDA >30 s | Skip | **BLOCKED** | — | Estado nodo / alerta |
| G041 | TC-M04-009 | RF-65 | `RF-65/TC-M04-G041/...` | POST `/prediccion/motor-ia` RBAC | API in-process | **PASS** | HTTP 403 `ACCESO_DENEGADO` | Sin tabla permisos real |
| G041 | TC-M04-024 | RF-65 | idem | token ausente/expirado/firma | API + jwt | **PASS** | 401 `TOKEN_REQUERIDO`; `TOKEN_EXPIRADO`; `TOKEN_INVALIDO` | JWT de prueba local, no producción |
| G042 | TC-M04-004 | RF-65 | `RF-65/TC-M04-G042/...` | pesos w_* | Unitario | **FAIL** (rango 0–1) | suma=1.0 se valida; peso negativo+suma 1 se acepta | Rango individual no implementado |
| G043 | TC-M04-010 / 179 | RF-70 | `RF-70/TC-M04-G043/...` | inicio OTA | Skip | **PENDING_SPEC** + **BLOCKED** | router solo GET | Sin POST OTA; gate APROBADO vs ACTIVO |
| G043 | TC-M04-011 / 180 | RF-70 | idem | rechazo no aprobado | Skip | **PENDING_SPEC** + **BLOCKED** | `activar()` RF-69 ≠ OTA | Idem |
| G044 | TC-M04-012 / 181 | RF-70 | `RF-70/TC-M04-G044/...` | reanudación | Skip | **BLOCKED** | puerto solo lectura | IoT/IA |
| G044 | TC-M04-013 / 182 | RF-70 | idem | SHA-256 / rollback hash | Skip | **BLOCKED** | — | IoT/IA |
| G044 | TC-M04-014 / 183 | RF-70 | idem | rollback activación | Skip | **BLOCKED** | — | IoT/IA |
| G044 | TC-M04-015 / 184 | RF-70 | idem | batería/almacén/ventana | Skip | **BLOCKED** | — | IoT/IA |
| G045 | TC-M04-016 / 185 | RF-70 | `RF-70/TC-M04-G045/...` | ≤10 min / ≤2 s | Skip | **BLOCKED** | — | Artefacto + Edge |
| G045 | TC-M04-017 / 186 | RF-70 | idem | TLS canal OTA | Skip | **BLOCKED** | — | Canal distribución |
| G046 | TC-M04-018 / 187 | RF-70 | `RF-70/TC-M04-G046/...` | un OTA por dispositivo | Skip | **BLOCKED** | — | Lock / POST |
| G046 | TC-M04-027 / 190 | RF-70 | idem | INMEDIATO/PROGRAMADO/LOTES | Skip | **BLOCKED** | filtro consulta ≠ orquestación | Orquestador |
| G047 | TC-M04-025 / 188 | RF-70 | `RF-70/TC-M04-G047/...` | consulta M09 | Skip M09; unit consulta M04 | **BLOCKED** (M09) | GET status en memoria PASSED | Integración M09 |
| G047 | TC-M04-026 / 189 | RF-70 | idem | SIN_CAMBIOS sin transferencia | Skip transferencia | **BLOCKED** | filtro SIN_CAMBIOS PASSED | Inicio OTA |
| G047 | TC-M04-029 / 192 | RF-70 | idem | reporte / persistencia | Skip | **BLOCKED** | — | Reporte nodo |
| G048 | TC-M04-028 / 191 | RF-70 | `RF-70/TC-M04-G048/...` | destino inactivo | Skip | **BLOCKED** | — | Validación destino OTA |
| G048 | TC-M04-030 / 193 | RF-70 | idem | BOLA A→B | Skip | **BLOCKED** | sin ruta download | Dos dispositivos + artefacto |

Logs: `Resultados/pytest-g037-g048.txt`, `Resultados/junit-g037-g048.xml`.
