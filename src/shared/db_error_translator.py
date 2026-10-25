"""Traductor de errores de base de datos a errores de dominio.

Los repositorios SQLAlchemy capturan ``IntegrityError``, ``DataError`` y
``OperationalError`` de psycopg2 y los pasan a ``raise_from_db_error``, que
los convierte en errores del árbol ``AppError``. Esto mantiene la capa de
aplicación libre de dependencias de SQLAlchemy o psycopg2.

Ningún nombre de constraint de PostgreSQL sale hacia el cliente: el ``field``
que viaja en la respuesta es siempre un nombre de columna, derivado por
``_campo`` a partir del diagnóstico de psycopg2.
"""
import re

from psycopg2 import errors as pg_errors
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from src.shared.errors import (
    AppError,
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    InfrastructureError,
    NotFoundError,
    PreconditionFailedError,
    ServiceUnavailableError,
    ValidationError,
)

# RAISE EXCEPTION no rellena schema_name/table_name. El primer frame de
# diag.context identifica la función que lanzó el error, sin leer SQL ni
# parámetros del request. P0001/P0002/P0005 se reutilizan en otros módulos.
_FUNCION_PLPGSQL = re.compile(r"^PL/pgSQL function (\w+(?:\.\w+)?)\(", re.MULTILINE)
_RECHAZOS_TRIGGER = {
    ("P0001", "modulo3.fn_validar_timestamp_telemetria"): (
        ValidationError, "ERROR_TIEMPO",
        "El timestamp_captura es posterior a la hora del servidor.", "timestamp_captura",
    ),
    ("P0002", "modulo3.fn_telemetrias_inmutable"): (
        BusinessRuleError, "TELEMETRIA_INMUTABLE",
        "Los registros de telemetría no pueden ser modificados ni eliminados.", None,
    ),
    ("P0005", "modulo3.fn_alerta_validar_transicion"): (
        BusinessRuleError, "TRANSICION_INVALIDA",
        "La transición de estado solicitada no está permitida para esta alerta.", "nuevo_estado",
    ),
}


def traducir_rechazo_trigger(exc: Exception) -> AppError | None:
    """Traduce exclusivamente triggers conocidos; no controla transacciones.

    Admite el error del driver y la envoltura DBAPIError de SQLAlchemy.
    Sin contexto verificable conserva el tratamiento de error desconocido.
    Nunca devuelve el mensaje, la sentencia ni los parámetros de PostgreSQL.
    """
    original = getattr(exc, "orig", exc)
    diag = getattr(original, "diag", None)
    sqlstate = getattr(diag, "sqlstate", None) or getattr(original, "pgcode", None)
    contexto = getattr(diag, "context", None) or ""
    frame = _FUNCION_PLPGSQL.search(contexto)
    if frame is None:
        return None
    funcion = frame.group(1)
    regla = _RECHAZOS_TRIGGER.get((sqlstate, funcion))
    if regla is not None:
        clase, codigo, mensaje, campo = regla
        return clase(code=codigo, message=mensaje, field=campo)
    if (sqlstate, funcion) == ("P0413", "modulo4.trg_fn_predicciones_version_modelo_activo"):
        # Una misma función/SQLSTATE tiene dos ramas. Las etiquetas son parte
        # estable del trigger; solo discriminan la rama, no se exponen.
        etiqueta = (getattr(diag, "message_primary", None) or "").partition(":")[0]
        if etiqueta == "MODEL_NOT_ACTIVE":
            return PreconditionFailedError(
                code="MODELO_NO_ACTIVO",
                message="Solo se pueden generar predicciones con modelos en producción.",
                field="id_version_modelo",
            )
        if etiqueta == "MODEL_NOT_FOUND":
            return NotFoundError(
                code="VERSION_MODELO_NO_ENCONTRADA",
                message="La versión de modelo especificada no existe.",
                field="id_version_modelo",
            )
    return None


_PREFIJOS_CONSTRAINT = ("uq_", "uk_", "fk_", "ck_", "chk_", "pk_", "idx_", "ix_")

#: SQLSTATE de duplicados que triggers de `modulo9` señalan con
#: `RAISE EXCEPTION ... USING ERRCODE`. Postgres los clasifica como clase
#: `P0` (PL/pgSQL), que psycopg2/SQLAlchemy no mapea a `IntegrityError`
#: (cae a `InternalError` genérico) — sin este mapeo explícito, un choque de
#: nombre entre dos filas activas sale como 500 en vez de 409.
#: P0104 etapa, P0109 métrica, P0125 área productiva (INC-M09-20-G49: el
#: trigger compara sin distinguir mayúsculas y salta antes que el UNIQUE),
#: y los demás duplicados de `modulo9`: P0101 especie, P0107 patología,
#: P0110 umbral, P0119/P0120 finca, P0128 serial de dispositivo.
_ERRCODES_NOMBRE_DUPLICADO = {
    "P0101", "P0104", "P0107", "P0109", "P0110", "P0119", "P0120", "P0125", "P0128",
}

#: SQLSTATE de reglas de negocio de `modulo9.sensores_areas_asociadas`
#: señaladas por trigger con `RAISE EXCEPTION ... USING ERRCODE`. Misma
#: clase `P0` no mapeada por psycopg2 — sin esto, una condición de carrera
#: que dispare el trigger sale como 500 en vez del error de negocio
#: correspondiente (INC-M09-107-G64).
_ERRCODE_ASOCIACION_YA_ACTIVA = "P0130"
_ERRCODE_SENSOR_FINCA_DISTINTA = "P0140"

#: INC-M09-20-02: `trg_fn_infraestructura_no_desactivar_en_uso` bloquea la
#: desactivación de un área con dispositivos activos o sensores asociados.
#: Sin mapeo, si la validación previa no lo ve salía como 500.
_ERRCODE_AREA_EN_USO = "P0127"

#: INC-M02-76-G55: `trg_fn_evento_reproductivo_secuencia` (modulo2) ya impedía
#: correctamente un evento reproductivo de categoría distinta a "nacimiento"
#: sobre un activo POBLACIONAL, pero su ERRCODE tampoco caía en ninguna clase
#: que psycopg2/SQLAlchemy traduzca — cualquier vía que llegue al trigger sin
#: pasar por la validación de aplicación (`RegistrarEventoReproductivoUseCase`)
#: salía como 500 en vez del 422 de negocio documentado en RF-42.
_ERRCODE_EVENTO_REPRODUCTIVO_TIPO_INVALIDO = "P0220"

#: Arekkazu/SGPMP-FRONT-END-PWA#299: el mismo trigger señala la secuencia
#: reproductiva rota (P0221) y el número de crías inválido (P0222). Sin mapeo,
#: un desfase entre la regla del trigger y la del use case salía como 500
#: "Error inesperado en base de datos" en vez del error de negocio de RF-42.
_ERRCODE_EVENTO_REPRODUCTIVO_SECUENCIA = "P0221"
_ERRCODE_EVENTO_REPRODUCTIVO_NUMERO_CRIAS = "P0222"

#: INC-M02-100-G31: `trg_fn_poblacional_cantidad_inmutable` (modulo2,
#: `detalles_activos_biologicos_poblacionales`) protege `cantidad_inicial`
#: (inmutable) y `cantidad_actual` (no negativa) con `RAISE EXCEPTION ...
#: USING ERRCODE`. Misma clase P0 no mapeada por psycopg2/SQLAlchemy — antes
#: de este mapeo, `POST .../eventos/crecimiento` sobre un lote que disparara
#: el trigger devolvía 500 ERROR_INTERNO en vez del 400 de negocio que ya
#: aplica la restricción CHECK gemela (`chk_poblacional_cantidad_actual_no_negativa`)
#: cuando la violación llega por una vía distinta al CHECK nativo.
_ERRCODE_POBLACIONAL_CANTIDAD_INVALIDA = "P0210"

#: INC-M02-75-G53: `trg_fn_evento_fecha_coherente` (modulo2, cualquier tabla
#: de eventos vía `eventos_activos`) también señala con `RAISE ... USING
#: ERRCODE`, sin mapeo — un cliente que sí mande una fecha inválida (futura o
#: anterior al registro del activo) recibía 500 en vez de 400.
_ERRCODE_EVENTO_FECHA_INVALIDA = "P0215"

#: INC-M02-G34 (RF-37): triggers de `modulo2.gestiones_fases` — fase activa
#: duplicada (P0226), fechas solapadas (P0227) y activo CERRADO/BAJA (P0228).
#: Sin mapeo, cambiar de fase en esos casos salía como 500 en vez de 409.
_ERRCODES_FASE_CONFLICTO = {
    "P0226": "FASE_ACTIVA_DUPLICADA",
    "P0227": "FASE_SOLAPADA",
    "P0228": "ACTIVO_NO_OPERATIVO",
}

#: INC-M02-56-G31 (#456): triggers de estado y de bajas de `modulo2`. Sin
#: mapeo, `POST .../eventos/baja` sobre un activo con historial de estados
#: desincronizado salía como 500 en vez de un error controlado. Los códigos
#: y clases coinciden con los que ya lanza el dominio para las mismas reglas
#: (`ActivoBiologico.cambiar_estado`, `RegistrarEventoBajaUseCase`).
_ERRCODE_ESTADO_HISTORIAL_INCONSISTENTE = "P0212"
_ERRCODE_BAJA_CANTIDAD_INVALIDA = "P0224"
_ERRCODE_BAJA_SUPERA_EXISTENCIA = "P0225"

#: CU-M09-03: `trg_fn_niveles_alerta_solapamiento` rechaza un nivel de alerta
#: que se solapa con otro del mismo umbral (P0113). La aplicación ya valida que
#: los niveles sean contiguos; si aun así llega aquí, es una regla de negocio
#: (422), no un 500.
_ERRCODE_NIVELES_SOLAPADOS = "P0113"

#: P0211 lo comparten dos triggers de `modulo2` con etiquetas distintas
#: (prefijo del mensaje). Solo `INVALID_TRANSITION` y `REDUNDANT_TRANSITION`
#: son reglas de negocio; `MISSING_FIELD` y `DIRECT_STATE_CHANGE` delatan un
#: bug de la propia aplicación y deben seguir siendo 500, no un 4xx.
_ERRCODE_TRANSICION_ESTADO = "P0211"
_TRANSICIONES_ESTADO = {
    "INVALID_TRANSITION": (BusinessRuleError, "TRANSICION_INVALIDA"),
    "REDUNDANT_TRANSITION": (ConflictError, "ESTADO_REDUNDANTE"),
}

#: Triggers de `modulo1` que protegen el rol `es_protegido` (Administrador)
#: señalan con `RAISE ... USING ERRCODE = 'P0004'`, que psycopg2 trae como
#: `AssertFailure` (un `InternalError`) y caía al 500 "Error inesperado en
#: base de datos". Caso reportado: un admin cambia el rol de otro usuario
#: Administrador y `trg_fn_proteger_reasignacion_rol_admin` lo bloquea.
#: `rol_repository` ya traduce PROTECTED_ROLE por su cuenta (mismo código y
#: clase); aquí queda cubierta cualquier otra vía.
_ERRCODE_ROL_PROTEGIDO = "P0004"
_ROL_PROTEGIDO = {
    "PROTECTED_ADMIN": (BusinessRuleError, "ROL_ADMIN_PROTEGIDO"),
    "PROTECTED_ROLE": (AuthorizationError, "ROL_PROTEGIDO"),
}

#: SQLSTATE cuyo significado depende de la etiqueta del mensaje
#: (`ETIQUETA: texto`). Una etiqueta que no esté en el mapa sigue siendo 500.
_REGLAS_POR_ETIQUETA = {
    _ERRCODE_TRANSICION_ESTADO: _TRANSICIONES_ESTADO,
    _ERRCODE_ROL_PROTEGIDO: _ROL_PROTEGIDO,
}

#: INC-M02-57-G06: psycopg2 rechaza un byte nulo embebido en un parámetro de
#: texto con un ValueError de Python plano (no una subclase de psycopg2.Error),
#: en la adaptación del parámetro, antes de que SQLAlchemy pueda envolverlo en
#: IntegrityError/DataError/OperationalError. `BaseDTO` ya lo rechaza en la
#: frontera para todo DTO de entrada; esto es la red de seguridad para
#: cualquier valor que llegue a la base de datos por otra vía.
#: CU-M09-03: el 500 decía "Error inesperado en base de datos", que no le dice
#: al usuario qué hacer y delata la capa que falló. El detalle técnico sigue en
#: el log (`original_error`); al cliente le llega el mismo texto que da el
#: manejador global para cualquier error no controlado.
_MENSAJE_ERROR_INTERNO = (
    "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, "
    "contacta al equipo de soporte."
)

_MENSAJE_BYTE_NULO_PSYCOPG2 = "A string literal cannot contain NUL (0x00) characters."


def _campo(diag) -> str | None:
    """Deriva el nombre de columna a partir del diagnóstico de psycopg2.

    Prefiere ``column_name``, que PostgreSQL rellena en varios casos. Si no está,
    limpia el nombre del constraint quitando el prefijo de tipo y el de tabla, de
    modo que ``uq_usuario_correo`` sobre la tabla ``usuario`` sale como
    ``correo``. Sin esto el frontend recibe el nombre crudo del constraint y lo
    muestra al usuario como "Uq usuario correo".

    Args:
        diag: Objeto ``Diagnostics`` de psycopg2, o ``None``.

    Returns:
        Nombre de columna, o ``None`` si no se pudo derivar ninguno.
    """
    if diag is None:
        return None

    if diag.column_name:
        return diag.column_name

    nombre = diag.constraint_name
    if not nombre:
        return None

    for prefijo in _PREFIJOS_CONSTRAINT:
        if nombre.startswith(prefijo):
            nombre = nombre[len(prefijo):]
            break

    tabla = diag.table_name
    if tabla and nombre.startswith(f"{tabla}_"):
        nombre = nombre[len(tabla) + 1:]

    return nombre or None


def raise_from_db_error(
    exc: Exception,
    conflict_messages: dict[str, str] | None = None,
) -> None:
    """Convierte una excepción de base de datos en un error de dominio y lo lanza.

    Mapeo de excepciones:

    - ``UniqueViolation`` → ``ConflictError`` (HTTP 409). El mensaje se
      personaliza por nombre de constraint usando ``conflict_messages``.
    - ``CheckViolation`` → ``ValidationError`` (HTTP 400).
    - ``ForeignKeyViolation`` → ``ConflictError`` (HTTP 409) si el registro está
      referenciado por otros, o ``ValidationError`` (HTTP 400) si el referenciado
      no existe. En ambos casos el origen es el dato que mandó el cliente, no un
      fallo del servidor.
    - ``DataError`` → ``ValidationError`` (HTTP 400).
    - ``OperationalError`` → ``ServiceUnavailableError`` (HTTP 503).
    - ``ValueError`` de psycopg2 por byte nulo embebido → ``ValidationError`` (HTTP 400).
    - Cualquier otro caso → ``InfrastructureError`` (HTTP 500).

    Debe llamarse desde el bloque ``except`` del repositorio, antes de que
    la excepción salga de la capa de infraestructura.

    Ejemplo de uso en un repositorio::

        try:
            self.db.flush()
        except IntegrityError as exc:
            raise_from_db_error(exc, {"uq_usuario_correo": "El correo ya está registrado."})

    Args:
        exc: Excepción capturada de SQLAlchemy o psycopg2.
        conflict_messages: Diccionario ``{nombre_constraint: mensaje_usuario}``
            para personalizar el mensaje de ``ConflictError`` según el
            constraint violado. Si el constraint no está en el diccionario,
            se usa el mensaje genérico.

    Raises:
        ConflictError: Por violación de unicidad, o por FK que impide borrar.
        ValidationError: Por violación de check, FK inexistente o dato fuera de rango.
        ServiceUnavailableError: Por fallo de conectividad con la base de datos.
        InfrastructureError: Por cualquier otro error de base de datos no mapeado.
    """
    if isinstance(exc, ValueError) and str(exc) == _MENSAJE_BYTE_NULO_PSYCOPG2:
        raise ValidationError(
            code="VALOR_NO_PERMITIDO",
            message="El texto no puede contener caracteres nulos.",
        )

    rechazo = traducir_rechazo_trigger(exc)
    if rechazo is not None:
        raise rechazo from exc

    original = getattr(exc, "orig", exc)
    diag_generico = getattr(original, "diag", None)
    sqlstate = getattr(diag_generico, "sqlstate", None) or getattr(original, "pgcode", None)

    if sqlstate in _ERRCODES_NOMBRE_DUPLICADO:
        mensaje = diag_generico.message_primary or "Ya existe un registro con ese nombre."
        raise ConflictError(code="RECURSO_DUPLICADO", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_ASOCIACION_YA_ACTIVA:
        mensaje = diag_generico.message_primary or "El sensor ya tiene una asociación activa en otra área."
        raise ConflictError(code="ASOCIACION_YA_ACTIVA", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_SENSOR_FINCA_DISTINTA:
        mensaje = diag_generico.message_primary or "El área productiva pertenece a una finca distinta a la del dispositivo."
        raise BusinessRuleError(code="SENSOR_FINCA_DISTINTA", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_AREA_EN_USO:
        mensaje = diag_generico.message_primary or "El área tiene recursos asociados."
        raise BusinessRuleError(code="INFRAESTRUCTURA_CON_DEPENDENCIAS", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_EVENTO_REPRODUCTIVO_TIPO_INVALIDO:
        mensaje = diag_generico.message_primary or "Los activos de tipo LOTE solo pueden registrar eventos de tipo nacimiento."
        raise BusinessRuleError(code="EVENTO_NO_PERMITIDO_LOTE", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_EVENTO_REPRODUCTIVO_SECUENCIA:
        mensaje = diag_generico.message_primary or "La secuencia reproductiva del activo no permite este evento."
        raise BusinessRuleError(code="SECUENCIA_REPRODUCTIVA_INVALIDA", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_EVENTO_REPRODUCTIVO_NUMERO_CRIAS:
        mensaje = diag_generico.message_primary or "El número de crías debe ser mayor o igual a 1."
        raise ValidationError(code="NUMERO_CRIAS_REQUERIDO", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_EVENTO_FECHA_INVALIDA:
        mensaje = diag_generico.message_primary or "La fecha del evento es inválida."
        raise ValidationError(code="FECHA_INVALIDA", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_POBLACIONAL_CANTIDAD_INVALIDA:
        mensaje = diag_generico.message_primary or "La cantidad del lote no es válida."
        raise ValidationError(code="VALOR_NO_PERMITIDO", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_NIVELES_SOLAPADOS:
        mensaje = diag_generico.message_primary or "Los niveles de alerta del umbral se solapan."
        raise BusinessRuleError(code="NIVELES_SOLAPADOS", message=mensaje.split(": ", 1)[-1], field="niveles")

    if sqlstate in _ERRCODES_FASE_CONFLICTO:
        mensaje = diag_generico.message_primary or "El cambio de fase entra en conflicto con el historial del activo."
        raise ConflictError(code=_ERRCODES_FASE_CONFLICTO[sqlstate], message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_ESTADO_HISTORIAL_INCONSISTENTE:
        mensaje = diag_generico.message_primary or "El historial de estados del activo está desincronizado."
        raise ConflictError(code="ESTADO_ACTIVO_INCONSISTENTE", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_BAJA_CANTIDAD_INVALIDA:
        mensaje = diag_generico.message_primary or "La cantidad afectada de la baja no es válida."
        raise ValidationError(code="VALOR_NO_PERMITIDO", message=mensaje.split(": ", 1)[-1])

    if sqlstate == _ERRCODE_BAJA_SUPERA_EXISTENCIA:
        mensaje = diag_generico.message_primary or "La cantidad a dar de baja supera la existencia del lote."
        raise BusinessRuleError(code="CANTIDAD_BAJA_SUPERIOR_EXISTENCIA", message=mensaje.split(": ", 1)[-1])

    if sqlstate in _REGLAS_POR_ETIQUETA:
        mensaje = diag_generico.message_primary or ""
        etiqueta = mensaje.split(":", 1)[0]
        reglas = _REGLAS_POR_ETIQUETA[sqlstate]
        if etiqueta in reglas:
            clase, codigo = reglas[etiqueta]
            raise clase(code=codigo, message=mensaje.split(": ", 1)[-1])

    if isinstance(exc, IntegrityError):
        diag = getattr(exc.orig, "diag", None)
        constraint = getattr(diag, "constraint_name", None)

        if isinstance(exc.orig, pg_errors.UniqueViolation):
            message = (conflict_messages or {}).get(
                constraint, "Ya existe un registro con esos datos."
            )
            raise ConflictError(code="RECURSO_DUPLICADO", message=message, field=_campo(diag))

        if isinstance(exc.orig, pg_errors.CheckViolation):
            raise ValidationError(
                code="VALOR_NO_PERMITIDO",
                message="El valor no cumple con las restricciones permitidas",
                field=_campo(diag),
            )

        if isinstance(exc.orig, pg_errors.ForeignKeyViolation):
            # ponytail: heurística sobre el texto de PostgreSQL para distinguir
            # "no puedo borrar, hay quien me referencia" de "el referenciado no
            # existe". Si el mensaje cambia, cae al 400 genérico.
            mensaje_pg = getattr(diag, "message_primary", "") or ""
            if "still referenced" in mensaje_pg:
                raise ConflictError(
                    code="REFERENCIA_EN_USO",
                    message="No se puede eliminar: otros registros dependen de este.",
                )
            raise ValidationError(
                code="REFERENCIA_INVALIDA",
                message="El registro relacionado que indicaste no existe.",
                field=_campo(diag),
            )

        raise InfrastructureError(
            code="ERROR_INTERNO",
            message=_MENSAJE_ERROR_INTERNO,
            original_error=exc,
        )

    if isinstance(exc, DataError):
        raise ValidationError(
            code="VALOR_FUERA_DE_RANGO",
            message="El valor excede el tamaño o formato permitido por la base de datos",
        )

    if isinstance(exc, OperationalError):
        raise ServiceUnavailableError(
            code="BD_NO_DISPONIBLE",
            message=(
                "El servicio no está disponible temporalmente. "
                "Intenta de nuevo en unos momentos."
            ),
            original_error=exc,
        )

    raise InfrastructureError(
        code="ERROR_INTERNO",
        message=_MENSAJE_ERROR_INTERNO,
        original_error=exc,
    )
