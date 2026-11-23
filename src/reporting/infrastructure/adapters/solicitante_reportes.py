# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: reportes permitidos por RBAC y alcance del solicitante |
# | 2026-11-19 | Arekkazu | M08 RF-104: rol de quien genera, para el encabezado del reporte |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Quién pide un reporte: los tipos que su rol puede generar (permiso Ejecutar sobre ``reporte_<tipo>`` en
``modulo1.permisos``), sus fincas y su nombre (para la firma del Contador). Una sola consulta de permisos."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.financial_valuation.infrastructure.repositories.sql import nombres_usuarios
from src.reporting.application.use_cases.reportes.generacion import Solicitante
from src.reporting.domain.reportes.catalogo import CATALOGO
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import sesion_sistema

_SQL_PERMITIDOS = text("""
    SELECT rc.nombre_recurso FROM modulo1.permisos p
    JOIN modulo1.recursos rc ON rc.id_recurso = p.id_recurso
    JOIN modulo1.acciones a ON a.id_accion = p.id_accion
    WHERE p.id_rol = :rol AND p.es_activo AND a.codigo = 'E' AND rc.nombre_recurso = ANY(:recursos)
""")
_SQL_ROL = text("SELECT id_rol FROM modulo1.usuarios WHERE id_usuario = :id")
_SQL_NOMBRE_ROL = text("SELECT nombre_rol FROM modulo1.roles WHERE id_rol = :rol")
_RECURSOS = {d.recurso: d.tipo for d in CATALOGO.values()}


def construir_solicitante(db: Session, id_usuario: int, id_rol: int, zona_horaria: str) -> Solicitante:
    """Arma el solicitante con los reportes permitidos y las fincas del usuario."""
    permitidos = {_RECURSOS[f.nombre_recurso] for f in db.execute(
        _SQL_PERMITIDOS, {"rol": id_rol, "recursos": list(_RECURSOS)})}
    return Solicitante(
        id_usuario=id_usuario, nombre=nombres_usuarios(db, [id_usuario]).get(id_usuario) or "",
        permitidos=permitidos, fincas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(id_usuario, id_rol),
        zona_horaria=zona_horaria, rol=db.execute(_SQL_NOMBRE_ROL, {"rol": id_rol}).scalar() or "")


def solicitante_en_segundo_plano(id_usuario: int, zona_horaria: str) -> Solicitante:
    """El solicitante con el rol y las fincas que tiene hoy (no los del momento en que pidió el reporte)."""
    db = sesion_sistema()
    try:
        id_rol = db.execute(_SQL_ROL, {"id": id_usuario}).scalar()
        return construir_solicitante(db, id_usuario, id_rol, zona_horaria)
    finally:
        db.close()
