# TC-M02-G42 — Inmutabilidad de eventos biológicos ante intentos de edición o eliminación (ASVS V4.2)

**CU-05 · RF-39 — Registro de Eventos Biológicos (base).**

| Campo | Valor |
|---|---|
| Sub-caso | (TC-M02-080) (Seguridad) Bloquear eliminación/edición de eventos registrados |
| Tipo | Seguridad — OWASP ASVS V4.2 |
| Herramienta | Pytest |
| Responsable | Juan Manuel · Prioridad Alta |

## ✅ Resultado: PASS — 10/10 tests, dos capas de defensa verificadas

Detalle completo en `RESULTADOS/TC-M02-G42_resultado.md`.

### Por qué se probaron dos capas, no solo la API

ASVS V4.2 (Access Control) exige que un control crítico como "los registros son append-only" no dependa
únicamente de que la aplicación no tenga un botón de editar — debe sostenerse aunque alguien tenga acceso de
escritura más profundo (una migración mal escrita, un script de mantenimiento, una cuenta de servicio comprometida).
Por eso esta prueba verifica **dos capas independientes**, ambas contra el entorno TEST real:

1. **Capa de API**: no existe ninguna ruta HTTP para editar o eliminar un evento específico. Se probaron 3 patrones
   de URL plausibles con `DELETE` y 2 con `PATCH` — todos dan **404** (la ruta no existe, no es un 403/405
   aplicado a propósito, simplemente nunca se definió un endpoint de escritura para un evento puntual).
2. **Capa de base de datos** (con autorización explícita del usuario, todas las operaciones dentro de una
   transacción que termina siempre en `ROLLBACK`): un `UPDATE`/`DELETE` directo contra
   `modulo2.eventos_activos` y `modulo2.eventos_sanitarios`, usando una conexión con permiso de escritura real a
   nivel de `GRANT` (no una cuenta de solo lectura de Postgres), es rechazado por el trigger
   `trg_fn_eventos_activos_inmutable` en las 4 combinaciones probadas (UPDATE/DELETE × tabla padre/hija).

### GIVEN / WHEN / THEN

| Capa | GIVEN | WHEN | THEN | Resultado |
|---|---|---|---|---|
| API | Evento sanitario real, recién creado | `DELETE`/`PATCH` sobre 5 patrones de URL distintos | 404 en todos | **PASS** |
| API | — | `GET /historial` tras los intentos | El evento sigue existiendo | **PASS** |
| BD | Mismo evento | `UPDATE`/`DELETE` directo (con permiso de escritura) | Rechazado por `trg_fn_eventos_activos_inmutable`, `ERRCODE` propio | **PASS** (4/4 combinaciones) |

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta API: `admin.test@sgpmp.com.co`. Activo de prueba: `218` (individual).
- Base de datos: `158.69.200.27:5448/sgpmp_test`, credencial `member_qa` (con permiso de escritura a nivel de
  `GRANT`, aunque documentada como "de solo consulta" para el uso normal del equipo de QA) — acceso y las
  operaciones de escritura de esta prueba autorizados explícitamente por el usuario, todas terminan en `ROLLBACK`.
- Pytest 9.0.3 + `requests` + `psycopg2`. Fecha de ejecución: 2026-09-10.

### Cómo re-ejecutar

```bash
python -m pytest tests/Test_Testing/Test_Modulo2/RF-39/TC-M02-G42/test_tc_m02_g42_inmutabilidad_eventos.py -v
```

No modifica datos: cada ejecución crea un evento nuevo (vía la API) y todas las operaciones de la capa de base de
datos terminan en `ROLLBACK` explícito, incluso si la aserción de rechazo fallara.
