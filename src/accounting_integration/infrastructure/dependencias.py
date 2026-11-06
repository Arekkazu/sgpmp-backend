# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-SSO02 / RF-101: dependencia FastAPI de acceso por token de canal |
"""Dependencia para los endpoints que AgroFusion llama con el token de canal (RF-SSO02, RF-101 Fase 3).

Si se rechaza, queda en la auditoría de integración (RF-101 5.10) antes de responder; si se acepta,
declara la identidad del usuario del token para RLS."""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.accounting_integration.application.use_cases.canal.verificar_acceso_canal_use_case import AccesoCanal
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.infrastructure.factoria import M07
from src.shared.database import declarar_identidad, get_db
from src.shared.errors import AppError


def requerir_canal(canal: str) -> Callable[..., AccesoCanal]:
    def dependencia(request: Request, db: Session = Depends(get_db)) -> AccesoCanal:
        m07 = M07(db)
        ip = request.client.host if request.client else None
        autorizacion = request.headers.get("Authorization", "")
        try:
            acceso = m07.verificar_acceso().execute(
                autorizacion[7:] if autorizacion.startswith("Bearer ") else None, canal, ip)
        except AppError as exc:
            m07.auditar_aparte(EventoIntegracion(
                tipo_evento="TOKEN_CANAL_RECHAZADO", severidad="WARNING", tipo_actor="CLIENTE_EXTERNO",
                endpoint=getattr(request.scope.get("route"), "path", None) or request.url.path,
                metodo_http=request.method, codigo_http=exc.status_code, codigo_resultado=exc.code, ip_origen=ip))
            raise
        declarar_identidad(db, acceso.usuario.id_usuario, acceso.usuario.nombre_rol)
        return acceso

    return dependencia
