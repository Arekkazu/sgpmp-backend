# INC-M03-168-G76 — `umbral_confianza_edge_ia` no cargado en TEST (TC-M03-142, 143 y N18)

**RF:** RF-57 E12 (conflicto de severidad) y E13 (conflicto de tipo): "El umbral de confianza (**0.85**) es
configurable por el administrador (rango permitido: 0.70–0.95)". **Issue:** #747.
**Depende de:** G75 (#745), que parte de G73 (#744). El endpoint cubre también los parámetros que agregan
esas ramas.
**Estado:** corregido y verificado con PostgreSQL real.

## Causa

1. **El parámetro no estaba cargado en TEST.** DEV-14 había decidido que `umbral_confianza_edge_ia` no
   tuviera valor de respaldo, así que, si falta, responde 503 `PARAMETRO_CONFIGURACION_AUSENTE`. En TEST la
   fila no existe, y por eso **todo** evento de `POST /iot/alertas` con un conflicto Edge/IA respondía 503
   y no se creaba la alerta.
2. **No había forma de cargarlo por API.** Solo existía el script offline
   `scripts/configurar_parametros_dev14.py`, que corre contra la BD. QA no podía cargar ni cambiar el
   umbral, así que N18 no era ejecutable.

## Solución

1. **Valor base:** si falta el parámetro, se usa **0.85**, el valor que publica el RF. Es el mismo criterio
   que G73 (0.75) y G75 (60 min). Un valor **inválido** sigue respondiendo 503, como manda DEV-14. Con esto,
   TEST funciona sin cargar ningún dato.
2. **Endpoint de administración**, con el recurso 21 (`configuraciones_globales`), igual que los
   parámetros operativos de RF-18:
   - `GET /configuracion/parametros-alertas` (acción R): lista los parámetros de RF-57 con su valor
     efectivo, el configurado, el valor base, la `fuente` (`CONFIGURADO`, `VALOR_BASE` o `SIN_CONFIGURAR`) y
     el rango.
   - `PATCH /configuracion/parametros-alertas` (acción U), con cuerpo
     `{"parametros": {"umbral_confianza_edge_ia": 0.80}}`. Reutiliza
     `ConfigurarParametrosMLOpsUseCase.execute`: el mismo lock, la misma validación de DEV-14 (fuera de
     0.70–0.95 responde 400) y el autor queda en `id_usuario_modificador`. Un nombre que no sea de RF-57
     responde 400 `PARAMETRO_ALERTAS_INVALIDO`.

| Parámetro | Valor base | Uso |
|---|---|---|
| `umbral_confianza_edge_ia` | 0.85 | E12/E13 |
| `rf57_umbral_confianza_minimo` | 0.75 | CA-2 (G73) |
| `rf57_ventana_reevaluacion_min` | 60 | E16 (G75) |
| `rf57_tormenta_alertas_por_minuto` / `_unidad` | — (sin configurar no agrupa) | E8 (DEV-32) |

```bash
curl -X PATCH "$API/configuracion/parametros-alertas" -H "Authorization: Bearer $JWT_ADMIN" \
  -H "Content-Type: application/json" -d '{"parametros": {"umbral_confianza_edge_ia": 0.80}}'
```

## Cambios

- `parametro_mlops.py`: `RF57_CONFIANZA_BASE`.
- `parametros_alertas_mlops_adapter.py`: si falta el parámetro, usa el valor base.
- **Nuevos:**
  - `configuration/application/use_cases/configuracion_global/parametros_alertas_use_case.py`
  - `configuration/infrastructure/dto/actualizar_parametros_alertas_dto.py`
  - `configuration/infrastructure/schema/parametros_alertas_schema.py`
  - `configuration/infrastructure/routers/parametros_alertas_router.py`
- `main.py`: registra el router.
- `anotaciones/modulo_9/dev14_parametros_operativos.md`: el valor base y el endpoint.

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_168_g76_umbral_confianza_edge_ia.py`, sin BD:
- **Adaptador:** sin cargar devuelve 0.85; cargado devuelve 0.8; con un valor inválido (0.5, 0.99 o
  `"alto"`), 503.
- **Consulta:** devuelve las tres fuentes (`CONFIGURADO`, `VALOR_BASE` y `SIN_CONFIGURAR`).
- **Actualización:** solo admite parámetros de RF-57.

**Pruebas de integración.** `tests/integration/test_inc_m03_168_g76_umbral_confianza_edge_ia.py`: routers
reales, PostgreSQL real y **sin la fila del parámetro** (como en TEST).

| Caso de QA | Prueba | Resultado |
|---|---|---|
| TC-M03-142, E12 | `test_142_conflicto_de_severidad_sin_parametro_cargado[...]` | LEVE/CRITICO 0.84 → MODERADO `SEVERIDAD_COMPROMISO`; 0.85 → CRITICO `SEVERIDAD_MAXIMA`; MODERADO/CRITICO 0.80 → CRITICO; CRITICO/LEVE 0.50 → CRITICO |
| TC-M03-143, E13 | `test_143_conflicto_de_tipo_sin_parametro_cargado[...]` | 0.84 → `EDGE_PREVALECE`; 0.85 y 0.86 → `IA_PREVALECE` |
| TC-M03-N18 | `test_n18_el_administrador_consulta_y_cambia_el_umbral_por_api` | GET muestra `VALOR_BASE` 0.85. PATCH a 0.80 deja `CONFIGURADO` y el autor registrado. Después, 0.82 ya da `IA_PREVALECE` |
| N18, validación | `test_n18_valores_fuera_de_rango_o_ajenos_son_400[...]` | 0.60, 0.96 y `rf62_k` → 400 |
| RBAC | `test_solo_el_administrador_cambia_el_umbral` | Veterinario → 403; sin token → 401 |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g76_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Unitarias (G76 + G75 + G73 + DEV-14)                                      83 passed
Integración (G76 + G75 + G73 + DEV-14, DEV-49, DEV-30)                    66 passed, 6 skipped
Suite completa (sin red): 2305 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Para QA y despliegue

- **TC-M03-142 y 143:** funcionan en TEST sin cargar datos, con el valor base 0.85.
- **TC-M03-N18:** se ejecuta con `GET` y `PATCH /configuracion/parametros-alertas`, usando un usuario
  Administrador.
- **Opcional:** cargar el valor explícito en TEST y PROD con el `PATCH` para que quede `CONFIGURADO`, con el
  autor registrado.
