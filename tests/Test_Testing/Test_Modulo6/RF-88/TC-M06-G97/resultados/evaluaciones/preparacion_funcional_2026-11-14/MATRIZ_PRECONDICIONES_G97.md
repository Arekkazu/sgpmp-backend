# Matriz de precondiciones — TC-M06-G97

**Fecha:** 2026-11-14 · Commit `3995b923`

| ID | Precondición | Clasificación | Estado | Evidencia / acción |
|---|---|---|---|---|
| P0 | Código G97 en workspace `laura` | Existente verificado | OK | `3995b923`, use case + router |
| P1 | Endpoint depreciación en TEST | Existente verificado | OK | GET 200 autenticado |
| P2 | Auth Contador + `valoracion_por_costo` R | Existente verificado | OK | `QA_CORREO` / permisos |
| P3 | Activo 12.000.000 / 72 meses | No disponible | FALTA | Inventario sin match |
| P4 | Activo real alternativo para 09 | Existente verificado | OK | **1858** (u 1635/2126…) |
| P5 | Fecha consulta = adq + 12 meses dominio | Calculada | OK | p. ej. 1858 → 2027-11-12 |
| P6 | Baseline dep. registrada conocida | Existente verificado | OK | 1858 = 0; 1567 = 112500 |
| P7 | Fixture POST 08 solo `VIDA_UTIL_NO_CONFIGURADA` | Requiere preparación autorizada | FALTA | 1864 tiene también clasificación |
| P8 | Evidencia GET propuesta con vida útil | Existente verificado | OK | 1864 |
| P9 | Histórico sin vida útil (08B) | No disponible | FALTA | Ningún costo sin vida |
| P10 | Autorización POST reconocimiento | Requiere autorización | FALTA | No ejecutar aún |
| P11 | No alterar especies compartidas | Restricción | OK | Cumplida |

## Resumen por escenario

| Escenario | ¿Listo? | Bloqueo residual |
|---|---|---|
| TC-M06-09 | **Sí** (con 1858 u alternativa) | Solo falta corrida formal / evidencias oficiales |
| TC-M06-08 A (POST) | **No** | Fixture limpia + autorización escritura |
| TC-M06-08 B | **No** | Registro histórico inexistente |
| Grupo G97 APROBADO | **No** | 08 incompleto; 09 no ejecutado formalmente |
