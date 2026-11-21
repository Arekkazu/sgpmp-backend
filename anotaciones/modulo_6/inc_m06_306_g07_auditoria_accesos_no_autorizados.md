# INC-M06-306-G07 — Los 403 de M06 no quedaban en la auditoría financiera (RF-82, RNF-82-05)

**RF:** RF-82 (RNF-82-05) y RF-94 (auditoría financiera). **Issue:** #993.
**Estado:** corregido. Verificado con PostgreSQL real en una base efímera local; la migración **no** se aplicó en DEV.

## Causa

Un usuario autenticado sin permiso recibía `403 ACCESO_DENEGADO` de `require_permission_sobre`, pero nada
se escribía en `modulo6.auditorias_financieras`: QA vio el conteo sin cambios (reversión 187/188/189,
confirmar 180, sobrescribir costos 160 y precio del producto de RF-85 con Productor, Veterinario e Ingeniero
de campo). Además, `modulo6.enum_auditoria_financiera_tipo_evento` no tenía un tipo para ese intento.
RNF-82-05 exige que el intento sea "rechazado y registrado en el log de auditoría".

## Gap de BD

| Gap | Decisión | SQL |
|---|---|---|
| Sin tipo de evento para el intento | Nuevo valor `ACCESO_NO_AUTORIZADO` (mismo nombre que usa M02 para su RF-52) | `ALTER TYPE modulo6.enum_auditoria_financiera_tipo_evento ADD VALUE IF NOT EXISTS 'ACCESO_NO_AUTORIZADO'` |

Migración `a3c5e7f9b201` (`v5_5_0`, revisa `b7e2d94c1a68`). Ninguna función, trigger ni CHECK de la BD
enumera los tipos de M06. El downgrade no quita el valor (PostgreSQL no lo permite sin recrear el tipo).
**Requiere la autorización del DBA antes de desplegar.** No hay cambios de permisos RBAC.

## Corrección

- `src/financial_valuation/infrastructure/rbac_auditoria.py`: `require_permission_m06` envuelve
  `require_permission_sobre`. Si lanza `AuthorizationError` (`ACCESO_DENEGADO` o `CUENTA_NO_ACTIVA`),
  registra el evento y vuelve a lanzar el mismo 403. La compuerta sigue siendo `modulo1.permisos`.
- `RegistrarAccesoNoAutorizadoUseCase`: escribe el evento (severidad `WARNING`, actor `USUARIO`) y hace
  `commit()` propio, porque la operación pedida no se ejecuta. Si la escritura falla, hace `rollback()`,
  lo deja en el log técnico y **no** cambia el 403 por un 500.
- `m06_router.py`: el alias `permiso` apunta a `require_permission_m06`, así que **todas** las rutas de
  `/finanzas` auditan su rechazo (una prueba lo garantiza para rutas futuras).
- La consulta legible de RF-94 describe el tipo como «Intento de operación sin permiso del rol» y lo acepta
  como filtro `tipo_evento`.

Payload (`datos_nuevos`): `descripcion`, `error_code`, `id_rol`, `recurso`, `id_accion`, `metodo_http`,
`ruta` (plantilla, ej. `/finanzas/reconocimientos/{id_activo_biologico}/reversion`), `id_activo_biologico`
e `id_periodo_contable` de la URL.

## Decisiones

1. **Los ids de la URL van en el payload y no en las columnas `id_activo_biologico` / `id_periodo_contable`.**
   Ambas tienen FK; quien manda la petición no tiene permiso y el id puede no existir. Con la FK, el
   INSERT fallaría y se perdería justo el evento que pide RNF-82-05. Por eso filtrar la auditoría por activo
   no muestra estos intentos; para verlos se filtra por `tipo_evento=ACCESO_NO_AUTORIZADO`.
2. **Se audita todo 403 de M06, incluidas las lecturas.** RNF-82-05 dice "cualquier intento de otro rol" y
   el ticket abarca reconocimiento, costos y precios; es el mismo criterio de M02 (RF-52).
3. **Un token ausente o inválido no se audita**: es un 401 de M01 y no llega a la compuerta RBAC (lo dice el ticket).

## Verificación

- `tests/financial_valuation/test_inc_m06_306_g07_auditoria_rbac.py`: evento y 403 conservado, permiso
  concedido sin evento, `CUENTA_NO_ACTIVA`, fallo al auditar sin reemplazar el 403, contrato HTTP en
  reversión, confirmación, costos y cierre, y que toda ruta del router audite.
- `tests/integration/test_inc_m06_306_g07_auditoria_rbac_bd.py` contra Postgres real (base efímera con
  `alembic upgrade head`): 403, conteo +1, `ACCESO_NO_AUTORIZADO`/`WARNING`/`USUARIO`, hash de 64 calculado
  por `trg_hash_auditoria` con ids de URL inexistentes, y 401 sin evento.
