# INC-M03-165-G71 — Tipos de evento de bitácora del ciclo de la alerta (TC-M03-G71, G74, G79)

**RF:** RF-63 (catálogo de tipos de evento) y RF-57 (E4, E14 y "Registro en bitácora"). **Issue:** #743.
**Depende de:** G71 E14 (#742), que agrega `REGLAS_MULTIPLES_CORRELACIONADAS`; esta rama parte de esa.
**Estado:** corregido y verificado con PostgreSQL real.

## Causa: el RF usa dos nombres para los mismos eventos

| Nombre que busca QA | Dónde lo dice el RF | Lo que registra el backend | Dónde lo dice el RF |
|---|---|---|---|
| `EVENTO_CORRELACIONADO` | RF-57 E4 ("Se registra el evento en bitácora como EVENTO_CORRELACIONADO") | `DUPLICADO_ALERTA_CORRELACIONADO` (`actualizar_deduplicacion`) | **Catálogo de RF-63**, tabla "RF Origen / Tipos de Evento", fila RF-57 |
| `ESTADO_CAMBIADO` | RF-57 "Registro en bitácora": "tipo_evento (ALERTA_GENERADA, NOTIFICACION_ENVIADA, ESTADO_CAMBIADO, ALERTA_DESCARTADA, **etc.**)" | `ALERTA_RECONOCIDA`, `ALERTA_RESUELTA`, `ALERTA_DESCARTADA` y `ALERTA_VENCIDA` | Catálogo de RF-63 |
| `REGLAS_MULTIPLES_CORRELACIONADAS` | RF-57 E14 | No existía; lo agrega G71 E14 | — |

El backend sí registraba los eventos, pero con los nombres del **catálogo oficial de RF-63**. Eso coincide
con lo que dice QA en G79: "la trazabilidad existe". Quien consultaba por el nombre del texto de RF-57 no
los encontraba.

## Solución

El ticket ofrece dos salidas: "el tipo ESTADO_CAMBIADO del catálogo en cada cambio de estado, **o
actualizar el catálogo con los tipos usados**". Se tomó la segunda, sin renombrar ni duplicar la
evidencia:

- **Se conserva el catálogo de RF-63.** Los eventos se siguen registrando con el nombre del catálogo, y la
  evidencia histórica queda intacta. Escribir un segundo evento por cada transición rompería la regla
  "un evento por hecho" y la integridad por hash.
- **`GET /iot/auditoria?tipo_evento=`** (y su exportación) aceptan los dos nombres
  (`tipos_evento_equivalentes`, en `evento_auditoria_iot.py`):

| Consulta | Encuentra |
|---|---|
| `EVENTO_CORRELACIONADO` o `DUPLICADO_ALERTA_CORRELACIONADO` | Ambos tipos |
| `ESTADO_CAMBIADO` | `ESTADO_CAMBIADO` (también lo usan RF-60 y M02), `ALERTA_RECONOCIDA`, `ALERTA_RESUELTA`, `ALERTA_DESCARTADA` y `ALERTA_VENCIDA` |
| Cualquier otro tipo | Coincidencia exacta, como antes |

- **`REGLAS_MULTIPLES_CORRELACIONADAS`:** lo escribe G71 E14 al crear la compuesta con una lectura
  compañera y en cada consolidación de otro sensor del área.

**Para Análisis:** conviene unificar el RF. El texto de RF-57 (E4 y "Registro en bitácora") debería usar
los nombres del catálogo de RF-63, o el catálogo debería incluir `EVENTO_CORRELACIONADO`,
`ESTADO_CAMBIADO` y `REGLAS_MULTIPLES_CORRELACIONADAS` en la fila de RF-57.

## Cambios

- `src/telemetry/domain/entities/evento_auditoria_iot.py`: `TIPOS_EVENTO_EQUIVALENTES` y
  `tipos_evento_equivalentes`.
- `src/telemetry/infrastructure/repositories/bitacora_auditoria_iot_repository.py`: el filtro `tipo_evento`
  usa `IN` sobre las equivalencias.

## Evidencia

`tests/integration/test_inc_m03_165_g71_tipos_bitacora_alertas.py`: los eventos se generan con
`POST /iot/alertas` y `PATCH /iot/alertas/{id}/estado` reales, y se consultan con `GET /iot/auditoria`
(JWT de administrador), como QA.

| Caso de QA | Prueba | Resultado |
|---|---|---|
| G74: evento CRITICO del mismo sensor y variable, consolidado por E4 | `test_g74_evento_consolidado_por_e4_se_encuentra_como_evento_correlacionado` | 0 antes; después, 1 por `EVENTO_CORRELACIONADO` y 1 por `DUPLICADO_ALERTA_CORRELACIONADO` |
| G79: EN_ATENCION y RESUELTA por el administrador | `test_g79_cambios_de_estado_se_encuentran_como_estado_cambiado` | `ESTADO_CAMBIADO` da 2 (`ALERTA_RECONOCIDA` y `ALERTA_RESUELTA`); `ALERTA_RESUELTA` sigue dando 1 |
| G79: descarte | `test_g79_descarte_tambien_es_estado_cambiado` | `ESTADO_CAMBIADO` encuentra `ALERTA_DESCARTADA` |
| G71: correlación y consolidación | `test_g71_correlacion_y_consolidacion_dejan_reglas_multiples_correlacionadas` | 1 entrada al crear y 2 tras consolidar el otro sensor (`consolidada` false y true) |
| Control | `test_tipo_sin_equivalencia_se_filtra_exacto` | `ALERTA_GENERADA` da 1; un tipo inexistente da 0 |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g71b_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
tests/integration/test_inc_m03_165_g71_tipos_bitacora_alertas.py                       5 passed
Integración de bitácora y alertas (DEV-47, filtros RF-63, G71, G70, G68, DEV-30/41/49, DEV-17)   135 passed, 8 skipped
Unitarias que usan la bitácora (DEV-30/38/39/47/49, G42, G29)                          121 passed
Suite completa (sin red): 2355 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Para QA

- **TC-M03-G74 y G79:** se pueden consultar por el nombre de RF-57 o por el del catálogo.
- **TC-M03-G71:** `REGLAS_MULTIPLES_CORRELACIONADAS` aparece cuando la compuesta se crea con la lectura
  del otro sensor y en cada consolidación. El escenario sin compuesta aplicable sigue bloqueado (ver G71 E14).
