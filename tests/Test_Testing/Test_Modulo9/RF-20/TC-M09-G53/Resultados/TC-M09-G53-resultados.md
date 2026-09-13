# TC-M09-G53 (TC-M09-105) — Auditoría de operaciones sobre infraestructura productiva

**RF-20 / CU-04 — Gestionar Infraestructura Productiva**
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
