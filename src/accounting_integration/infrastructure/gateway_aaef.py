# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-95 / RF-AE01: Gateway de la consulta contable de AgroFusion |
"""Gateway de la consulta AAEF (RF-95 v2.0): las cinco responsabilidades y nada más.

1. Forma de la solicitud (400) y credenciales en la URL (400 + evento de seguridad).
2. Autenticación por token de canal y cliente (401/403/429, RF-101) y RBAC del usuario (403).
3. Delegación en el caso de uso (alcance, versión y envelope) con tiempo máximo (503).
4. Auditoría de toda solicitud en RF-102, en sesión propia: si falla, la respuesta sale igual (FA-9).
5. Respuesta sin tocar el envelope, con ``X-Request-Id``, ``X-Version-Contrato-AAEF`` y ``X-Content-SHA256``.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import date
from typing import Optional

from fastapi import Request, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.accounting_integration.application.use_cases.exportacion.consultar_aaef_use_case import (
    ResultadoAaef,
    SolicitudAaef,
)
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.infrastructure import configuracion
from src.accounting_integration.infrastructure.factoria import M07
from src.shared.database import declarar_identidad
from src.shared.errors import AppError, AuthorizationError, ServiceUnavailableError, ValidationError
from src.shared.rbac import tiene_permiso_sobre


CANAL = "CONSULTA_AAEF"
RECURSO = "exportacion_contable"
_LEER = 2
_CREDENCIALES = {"client_id", "client_secret", "api_key", "apikey", "token", "access_token"}
_NIT = re.compile(r"^[0-9]{6,15}$")
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PG_CONSULTA_CANCELADA = "57014"
_TIEMPO_MAXIMO = text("SELECT set_config('statement_timeout', :ms, true)")  # solo para esta transacción


def _fecha(valor: Optional[str], campo: str) -> date:
    try:
        if valor and _FECHA.match(valor):
            return date.fromisoformat(valor)
    except ValueError:
        pass
    raise ValidationError(code="PARAMETROS_INVALIDOS", field=campo,
                          message=f"El parámetro «{campo}» es obligatorio y debe tener el formato AAAA-MM-DD, por ejemplo 2026-10-01.")


def _id_solicitud(request: Request) -> str:
    try:
        return str(uuid.UUID(request.headers.get("X-Request-Id", "")))
    except ValueError:
        return str(uuid.uuid4())


def _cabeceras(resultado: ResultadoAaef, id_solicitud: str) -> dict[str, str]:
    cabeceras = {"X-Request-Id": id_solicitud, "X-Version-Contrato-AAEF": resultado.contrato.contrato_version,
                 "X-Content-SHA256": resultado.hash_contenido}
    if resultado.contrato.estado == "DEPRECADO" and resultado.contrato.fecha_inactivacion:  # RF-98 CA-25
        cabeceras["Deprecation"] = "true"
        cabeceras["Sunset"] = resultado.contrato.fecha_inactivacion.strftime("%a, %d %b %Y %H:%M:%S GMT")
    return cabeceras


def atender(request: Request, db: Session, nit: str, desde: Optional[str], hasta: Optional[str]) -> Response:
    """``GET /integracion/aaef/productores/{nit}`` llamado por AgroFusion con el token de canal."""
    m07 = M07(db)
    inicio = time.monotonic()
    id_solicitud = _id_solicitud(request)
    ip = request.client.host if request.client else None
    evento = dict(tipo_actor="CLIENTE_EXTERNO", id_solicitud=id_solicitud, endpoint="/integracion/aaef/productores/{nit}",
                  metodo_http="GET", ip_origen=ip, numero_id_tributaria=nit if _NIT.match(nit or "") else None)
    try:
        if _CREDENCIALES & {clave.lower() for clave in request.query_params}:  # RF-95 5.2, FA-2
            evento["tipo_evento"] = "CREDENCIALES_EN_URL"
            raise ValidationError(code="CREDENCIALES_EN_URL", message=(
                "La dirección de la consulta no puede llevar credenciales. Envíe la credencial en el encabezado Authorization."))
        if not _NIT.match(nit or ""):
            raise ValidationError(code="PARAMETROS_INVALIDOS", field="nit",
                                  message="El NIT debe tener solo dígitos, sin dígito de verificación.")
        fecha_desde, fecha_hasta = _fecha(desde, "desde"), _fecha(hasta, "hasta")
        evento.update(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
        if fecha_desde > fecha_hasta:
            raise ValidationError(code="PARAMETROS_INVALIDOS", field="hasta",
                                  message="La fecha «hasta» no puede ser anterior a la fecha «desde».")
        autorizacion = request.headers.get("Authorization", "")
        token = autorizacion[7:] if autorizacion.startswith("Bearer ") else None
        acceso = m07.verificar_acceso().execute(token, CANAL, ip)
        evento.update(id_cliente_externo=acceso.cliente.id_cliente_externo, id_usuario=acceso.usuario.id_usuario)
        declarar_identidad(db, acceso.usuario.id_usuario, acceso.usuario.nombre_rol)  # antes de leer permisos (RLS)
        if not tiene_permiso_sobre(db, acceso.usuario.id_rol, RECURSO, _LEER):  # RF-95 5.3 c, FA-5
            raise AuthorizationError(code="PERMISO_INSUFICIENTE", message=(
                "Su usuario del SGPMP no tiene permiso para la exportación contable. Solicítelo al administrador."))
        db.execute(_TIEMPO_MAXIMO, {"ms": str(configuracion.TIMEOUT_SEGUNDOS * 1000)})
        resultado = m07.consultar_aaef().execute(SolicitudAaef(
            nit, fecha_desde, fecha_hasta, acceso.usuario.id_usuario, acceso.usuario.correo,
            request.headers.get("Accept-Version")))
    except AppError as exc:
        evento.setdefault("tipo_evento", "RATE_LIMIT_EXCEDIDO" if exc.status_code == 429 else "SOLICITUD_RECHAZADA")
        _auditar(m07, evento, inicio, exc.status_code, exc.code, "WARNING" if exc.status_code < 500 else "ERROR")
        raise
    except OperationalError as exc:
        if getattr(exc.orig, "pgcode", None) != _PG_CONSULTA_CANCELADA:
            _auditar(m07, {**evento, "tipo_evento": "SOLICITUD_RECHAZADA"}, inicio, 500, "ERROR_INTERNO", "ERROR")
            raise
        _auditar(m07, {**evento, "tipo_evento": "SOLICITUD_RECHAZADA"}, inicio, 503, "SERVICIO_NO_DISPONIBLE", "ERROR")
        raise ServiceUnavailableError(code="SERVICIO_NO_DISPONIBLE", original_error=exc, message=(
            "La consulta contable tardó más de lo permitido. Intente de nuevo en unos minutos.")) from exc
    except Exception:
        _auditar(m07, {**evento, "tipo_evento": "SOLICITUD_RECHAZADA"}, inicio, 500, "ERROR_INTERNO", "ERROR")
        raise
    _auditar(m07, {**evento, "tipo_evento": "PAQUETE_AAEF_CONSULTADO", "version_contrato": resultado.contrato.contrato_version,
                   "hash_contenido": resultado.hash_contenido, "id_intercambio": resultado.id_intercambio,
                   "tamano_payload_bytes": len(resultado.cuerpo), "json_detalle": {"documentos": resultado.documentos}},
             inicio, 200, "OK", "INFO")
    return Response(content=resultado.cuerpo, media_type="application/json", headers=_cabeceras(resultado, id_solicitud))


def vista_previa(request: Request, db: Session, nit: str, desde: date, hasta: date, id_usuario: int, correo: str) -> Response:
    """La misma generación con la sesión web del Contador, para revisar antes de AgroFusion (RF-AE02 5.10)."""
    m07 = M07(db)
    resultado = m07.consultar_aaef().execute(SolicitudAaef(nit, desde, hasta, id_usuario, correo,
                                                           request.headers.get("Accept-Version")))
    id_solicitud = _id_solicitud(request)
    m07.auditar_aparte(EventoIntegracion(
        tipo_evento="VISTA_AAEF_GENERADA", tipo_actor="USUARIO", id_usuario=id_usuario, id_solicitud=id_solicitud,
        numero_id_tributaria=nit, fecha_desde=desde, fecha_hasta=hasta,
        version_contrato=resultado.contrato.contrato_version, hash_contenido=resultado.hash_contenido,
        id_intercambio=resultado.id_intercambio, tamano_payload_bytes=len(resultado.cuerpo),
        json_detalle={"documentos": resultado.documentos}))
    return Response(content=resultado.cuerpo, media_type="application/json", headers=_cabeceras(resultado, id_solicitud))


def _auditar(m07: M07, evento: dict, inicio: float, codigo_http: int, codigo: str, severidad: str) -> None:
    m07.auditar_aparte(EventoIntegracion(**evento, codigo_http=codigo_http, codigo_resultado=codigo, severidad=severidad,
                                         latencia_ms=int((time.monotonic() - inicio) * 1000)))
