# DEV-08 — Gaps de BD y RBAC: propagar reglas compuestas al Gateway Edge (RF-55, RF-57)

Tarea de Taiga: "[Back-end] RF-55/57: Propagar reglas compuestas al Edge (DEV-08)".
Contrato del broker: BRK-05 (`BROKER-MQTT-SGPMP` PR #33), `origen: "regla_compuesta"`.
Migración: `e3b8c1d9f702_v5_5_0_dev08_sincronizacion_reglas_edge.py` (revisa `3a9d5e7c1b24`).

## Esquema revisado en `sgpmp_dev` (2026-10-19)

- `modulo3.reglas_alertas` ya tiene lo que necesita el comando: `version_regla`
  (la sube el trigger `trg_aux_02_version_regla_alerta`), `es_activa`,
  `tiene_ejecutar_edge`, `es_regla_compuesta`, `id_finca`, `id_especie`.
  No hay ninguna regla compuesta cargada (las 6 reglas son simples).
- `modulo4.sincronizacion_nodos_edge` es de la configuración del motor IA
  (RF-65, DEV-09): su clave es (dispositivo, `tipo_modelo`) y su ENUM
  (`PENDIENTE`, `APLICADA`, `FALLIDA`, `DESINCRONIZADO`) no coincide con los
  veredictos del broker. No sirve para reglas.
- No existe recurso RBAC para la propagación de reglas.

## Gaps y decisión

| Gap | Decisión |
|---|---|
| No hay dónde guardar el estado de la regla por nodo | Tabla `modulo3.sincronizaciones_reglas_edge`, una fila por (regla, Gateway) con la versión intentada, el estado, el mensaje, los intentos y la última confirmación |
| Los veredictos del broker no tienen tipo | ENUM `modulo3.enum_sincronizacion_regla_edge_estado_sincronizacion` (`APLICADA`, `PENDIENTE`, `NO_CONF`) |
| No hay forma de saber a qué Gateway va una regla | Función `modulo3.fn_gateways_edge_por_regla_alerta(id_regla_alertas)`, mismo criterio de áreas que `modulo9.fn_seriales_gateway_edge_por_especie`, filtrado además por la finca de la regla |
| Sin recurso RBAC | Recurso 65 `sincronizacion_reglas_edge`: R y E para Administrador e Ingeniero de Campo |

Sin RLS en la tabla nueva, como el resto de `modulo3`.

## Hallazgo: RLS forzada en `modulo9` y `modulo2`

`modulo9.infraestructuras`, `modulo9.dispositivos_iot` y
`modulo2.activos_biologicos` tienen `FORCE ROW LEVEL SECURITY`, y su dueño
`sgpmp_owner` no tiene `BYPASSRLS`. Una función `SECURITY DEFINER` ya no evita
la RLS: ve lo que ve quien llama. Verificado en dev:

| Identidad | `modulo9.fn_seriales_gateway_edge_por_especie(4)` |
|---|---|
| Administrador | `['DISPOSITIVOCAMARONERA41']` |
| Ingeniero de Campo (id 4, sin fincas asignadas) | `[]` |

Para DEV-08 la búsqueda de destinos corre como el usuario de servicio
(`como_sistema` en `src/shared/database.py`, decisión D1/D4 del DBA: sin
BYPASSRLS), dentro de la misma transacción, y luego se restaura la identidad
del request.

**Fuera de alcance:** la propagación de umbrales de RF-17 tiene el mismo
problema: un Veterinario o Ingeniero sin la finca asignada propaga a cero
Gateway.

## Hallazgo: el trigger de versionamiento de reglas falla

`modulo3.fn_regla_alerta_versionamiento()` asigna
`NEW.fecha_actualizacion := now()::time with time zone`, pero la columna es
`timestamptz`. Cualquier `UPDATE` que cambie `umbral_min`, `umbral_max`,
`umbrales_severdiad`, `ventana_confirmacion_min` o `es_regla_compuesta` falla:

```
InvalidDatetimeFormat: invalid input syntax for type timestamp with time zone: "05:19:10.036232+00"
CONTEXT: PL/pgSQL function modulo3.fn_regla_alerta_versionamiento() line 10 at assignment
```

**Fuera de alcance** (requiere su propia migración): la corrección es `NEW.fecha_actualizacion := now();`.

## Verificación

Contra `sgpmp_dev`, en una transacción revertida: `upgrade` → `downgrade` →
`upgrade` de la migración, y luego los endpoints. dev quedó en `3a9d5e7c1b24`,
sin la tabla ni el recurso 65. La aplicación definitiva queda pendiente de la
aprobación del DBA.

El downgrade no puede borrar los permisos `admin_*` ni, por su FK, el recurso 65
(`trg_fn_proteger_permisos_admin_delete`). Quedan, como en `96621b225009`, y un
upgrade posterior los reutiliza.
