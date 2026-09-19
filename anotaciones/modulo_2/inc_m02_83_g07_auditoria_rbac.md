# INC-M02-83-G07 / RF-52 - Auditoría de rechazos RBAC

Fecha de verificación: 2026-09-11
Rama: `fix/rf52-inc-m02-83-g07-auditoria-rbac`

## Incidencia reproducida

El flujo de `TC-M02-249` consulta la bitácora, autentica un usuario con rol
Contador e intenta registrar un evento productivo sobre el activo 80. El RBAC
responde correctamente con `403 / ACCESO_DENEGADO`, pero antes de esta
corrección `src/shared/rbac.py` solo lanzaba `AuthorizationError` y no persistía
el rechazo en `modulo2.bitacora_auditoria_m02`.

La aserción del artefacto QA que esperaba que el conteo permaneciera igual
documentaba el defecto. Después de desplegar la corrección debe esperar un
incremento de una fila con `tipo_evento = ACCESO_NO_AUTORIZADO`.

## Solución

- Se conserva `src.shared.rbac.require_permission` como única implementación de
  la decisión RBAC.
- `require_permission_m02` envuelve esa dependencia y, al capturar un
  `AuthorizationError`, ejecuta el caso de uso de auditoría y vuelve a lanzar la
  misma excepción. Por tanto, no cambia el contrato HTTP original.
- El evento persistido contiene el RF de origen, usuario, activo cuando existe
  en la ruta, recurso, acción, método, plantilla de ruta y código/causa del
  rechazo. Sus valores funcionales son:
  `ACCESO_NO_AUTORIZADO`, `ACCESO_DATOS`, `RECHAZADO` y `WARNING`.
- Si la escritura de auditoría falla, el caso de uso revierte esa transacción,
  deja el error en el log técnico y conserva el `403` original, como exige RF-52.
- Las 23 operaciones protegidas del router M02 usan la dependencia auditada y
  declaran explícitamente su RF de origen (RF33-RF52, según la operación).

No se requiere migración ni cambio de datos.

## Verificación de base de datos

La inspección de `sgpmp_dev` se realizó con `member_dev` sobre el puerto 5447,
forzando la sesión a solo lectura y finalizando con rollback.

- La identidad de conexión correspondió a `sgpmp_dev / member_dev` y
  `transaction_read_only = on`.
- `modulo2.bitacora_auditoria_m02` tiene las 18 columnas que usa la entidad,
  incluidos `detalle_tecnico` JSONB, `resultado`, `severidad_log` y
  `hash_integridad` obligatorio.
- Existen los recursos RBAC 29 (`activos_biologicos`), 30
  (`asociacion_sensor_activo`) y 31 (`bitacora_auditoria_m02`).
- El rol Contador tiene lectura del recurso 31 y no tiene creación sobre el
  recurso 29, que es la precondición del caso reportado.
- El conteo oficial de `ACCESO_NO_AUTORIZADO` era 0 antes del despliegue.
- La consulta terminó con `ROLLBACK_OK`; no se ejecutó DDL ni DML en la base
  oficial.

## Pruebas

- `tests/biological_assets/test_rf52_auditoria_rbac.py`: 6 aprobadas.
- Regresión de `biological_assets`, `configuration`, `identity_access` y
  `shared`: 541 aprobadas.
- `tests/integration/test_inc_m02_83_g07_auditoria_rbac_integration.py` contra
  `pruebas-integrador`: 1 aprobada.
- La integración verificó el `403`, el incremento transitorio de la bitácora y
  todos los campos relevantes del evento. La transacción exterior revirtió el
  caso: 14 filas antes y 14 filas después.

Las dos advertencias observadas no corresponden a la corrección: deprecación
de `TestClient` por Starlette y falta de permiso para crear `.pytest_cache`.
