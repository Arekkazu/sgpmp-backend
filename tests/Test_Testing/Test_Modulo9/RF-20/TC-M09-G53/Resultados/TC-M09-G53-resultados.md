# TC-M09-G53 (TC-M09-105) — Auditoría de operaciones sobre infraestructura productiva

**RF-20 v1.1 / CU-04 — Gestionar Infraestructura Productiva**

## Estado vigente — reevaluación 2026-10-06 (RF-20 v1.1, RFC-009)

**Resultado: PENDIENTE (verificación de auditoría en BD).** Las operaciones pasan
(8 requests, 12 assertions, 0 failed), pero las filas de auditoría todavía no se leyeron.

Operaciones ejecutadas sobre el área propia **`id_infraestructura=169`** (finca 144), en este orden:

| # | Operación | HTTP | Auditoría esperada |
|---|---|---|---|
| 1 | Registro (`POST`) | 201 | `CREATE` (sin `valores_anteriores`) |
| 2 | Consulta del listado (`GET ?finca_id=144`) | 200 | `GET` (RF-20 audita el listado, no el detalle) |
| 3 | Modificación (`PATCH`): nombre → `Area Auditada Editada`, superficie 300 → 350 | 200 | `UPDATE` |
| 4 | Desactivación | 200 | `DEACTIVATE` (`es_activo` true → false) |
| 5 | Reactivación | 200, mismo `id_infraestructura` | **`UPDATE`** (`es_activo` false → true), no un segundo `CREATE` |

### Por qué falta la verificación

- `modulo9.auditorias_infraestructuras` sigue sin endpoint REST (la auditoría consolidada
  `/auditoria/` de M01 solo cubre eventos de M01).
- Desde la evaluación anterior, la tabla tiene RLS. La política de `SELECT` solo muestra filas si
  `modulo1.fn_rol_actual() = 'Administrador'`, así que la credencial QA de solo lectura
  (`member_qa`) ahora ve **0 filas**. La verificación de 2026-09 con `SELECT` directo ya no se
  puede repetir con esa credencial.

**Para cerrar el caso:** con una credencial de BD autorizada a leer la tabla, ejecutar

```bash
DB_USER=<usuario> DB_PASSWORD=<clave> python verificar_auditoria_g53.py --id 169
```

El script comprueba la secuencia `CREATE, GET, UPDATE, DEACTIVATE, UPDATE`, que haya un solo
`CREATE`, los `es_activo` antes/después de desactivar y de reactivar, el cambio de nombre en la
edición y el `id_usuario` del Administrador.

**Evidencia estática:** en `ReactivarInfraestructuraUseCase` la reactivación registra la auditoría
con `tipo_operacion="UPDATE"`, con el snapshot anterior y el nuevo. Esto confirma lo que está
implementado, pero no reemplaza la verificación en vivo.

### Observación de seguridad (para revisar con el equipo)

`modulo1.fn_rol_actual()`, en la que se apoya la política RLS, toma el rol de la variable de
sesión `app.current_role`. Esa variable la fija la propia conexión, no un mecanismo de la BD, así
que la política solo protege si ninguna credencial de BD distinta de la del backend puede fijarla.
Vale la pena revisarlo con quien mantiene las políticas RLS (rama `feature/RLSModulo9`).

Evidencia: `Resultados/reporte-TC-M09-G53.html` (Newman htmlextra, 2026-10-06; operaciones).

---

## Evaluación anterior (RF-20 v1.0, 2026-09): histórico

**Estado: PASA** (con alcance parcial documentado — ver abajo).

Mismo patrón de gap que TC-M09-G37 (RF-18) y TC-M09-G47 (RF-19): `modulo9.auditorias_infraestructuras`
se escribe correctamente, pero no tiene endpoint REST propio. Verificación puntual con `SELECT`
directo tras la corrida.

## Particularidad de RF-20: también audita lecturas

A diferencia de `auditorias_configuraciones_globales` y `auditorias_fincas` (solo
CREATE/UPDATE/DEACTIVATE), `auditorias_infraestructuras` **también** audita `GET` — pero
**solo al listar** (`ConsultarInfraestructurasUseCase.listar_por_finca`), no al consultar el
detalle individual (`obtener`, que no llama al repositorio de auditoría). Esto está
documentado explícitamente en el propio código: *"El DFD (paso 06) exige registrar
auditoría tipo GET al listar."* — confirmado al descubrir que mi primera prueba (contra el
endpoint de detalle) no generaba ninguna fila nueva; al cambiar al endpoint de listado sí
apareció. No es un bug, es un endpoint distinto al que se esperaba.

También vale la pena notar: el audit-on-GET es *best-effort* (`try/except: pass` por cada
ítem del listado, con `commit()` envuelto en su propio try/except) — un fallo al auditar una
lectura nunca bloquea la respuesta al usuario, a diferencia de CREATE/UPDATE/DEACTIVATE donde
un fallo de auditoría sí revierte toda la operación (mismo mecanismo que TC-M09-G38/RF-18).
Diferenciación de diseño razonable: la lectura no debe fallar por un problema de trazabilidad.

## Resultado por operación

| Operación | Evidencia | Resultado |
|---|---|---|
| `GET` (listar) | Fila fresca `id_auditoria_infraestructura=158/159`, `id_usuario=1`, timestamp de esta sesión | ✅ Verificado en vivo |
| `DEACTIVATE` | Fila fresca `id_auditoria_infraestructura=157` (generada en la primera corrida de esta misma colección, antes de corregir el paso de GET), `valores_anteriores`/`valores_nuevos` con `es_activo: true → false` | ✅ Verificado en vivo |
| `CREATE` | 2 filas **históricas** (`id=1`, `id=3`, del 2026-06-21) con estructura correcta (`valores_anteriores: null`, snapshot completo en `valores_nuevos`) | ⚠️ Verificado solo estructuralmente — no se pudo generar una fila fresca porque `POST /configuracion/infraestructuras` está bloqueado por el gap de `modulo9.tipos_area` (ver `TC-M09-G48/NOTA_BLOQUEO.md`) |
| `UPDATE` | 0 filas existentes en toda la tabla | ❌ No verificable — `PATCH` de edición está bloqueado por el mismo gap, y nunca se ha ejecutado con éxito en este entorno |

## Cómo cerrar la verificación completa

Una vez aplicada la migración pendiente de `TC-M09-G48`, reejecutar esta colección y además
correr un `POST`/`PATCH` real para confirmar `CREATE`/`UPDATE` con evidencia fresca (hoy solo
hay evidencia histórica/estructural para `CREATE`, y ninguna para `UPDATE`).

```bash
newman run "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G53/TC-M09-G53.postman_collection.json" \
  -r cli,htmlextra --reporter-htmlextra-export "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G53/Resultados/reporte-TC-M09-G53.html"
```
