# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-98/RF-AE02: persistencia de contratos AAEF y anexos |
"""Versiones del contrato (``modulo7.versiones_contrato_aaef``) y anexos (``mapeos_anexos_aaef``).
Los triggers 03/04/05 de ``modulo7`` son la última defensa de las transiciones; el caso de uso las
valida antes con mensajes legibles."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.accounting_integration.domain.entities.contrato import AnexoMapeo, VersionContrato
from src.accounting_integration.domain.repositories.contrato_repository import ContratoRepository
from src.financial_valuation.infrastructure.repositories.sql import a_json, escribir, fila, filas

_CONTRATO = """
    SELECT id_version_contrato_aaef, contrato_version, tipo_cambio::text AS tipo_cambio, fecha_vigencia,
           id_mapeo_anexo_aaef, json_mapeadores AS mapeadores, endpoint_asociado, periodo_gracia_dias, descripcion,
           estado::text AS estado, fecha_activacion, fecha_deprecacion, fecha_inactivacion
    FROM modulo7.versiones_contrato_aaef
"""
_ANEXO = """
    SELECT id_mapeo_anexo_aaef, codigo_anexo, version_anexo, direccion_pdf AS ruta_documento,
           canonical_sha256 AS sha256_documento, estado::text AS estado, fecha_aprobacion_interna,
           fecha_aprobacion_agrofusion AS fecha_aprobacion, json_evidencia AS evidencia
    FROM modulo7.mapeos_anexos_aaef
"""


class SqlAlchemyContratoRepository(ContratoRepository):
    def __init__(self, db: Session):
        self.db = db

    def listar_contratos(self, bloquear: bool = False) -> list[VersionContrato]:
        bloqueo = " FOR UPDATE" if bloquear else ""
        return [VersionContrato(**f) for f in filas(self.db, f"{_CONTRATO} ORDER BY id_version_contrato_aaef{bloqueo}")]

    def guardar_contrato(self, contrato: VersionContrato) -> VersionContrato:
        params = {**contrato.__dict__, "mapeadores": a_json(contrato.mapeadores)}
        if contrato.id_version_contrato_aaef is None:
            contrato.id_version_contrato_aaef = escribir(self.db, """
                INSERT INTO modulo7.versiones_contrato_aaef (contrato_version, estado, descripcion, fecha_vigencia,
                    tipo_cambio, endpoint_asociado, id_mapeo_anexo_aaef, json_mapeadores, periodo_gracia_dias)
                VALUES (:contrato_version, 'PENDIENTE', :descripcion, :fecha_vigencia,
                    CAST(:tipo_cambio AS modulo7.enum_version_contrato_aaef_tipo_cambio), :endpoint_asociado,
                    :id_mapeo_anexo_aaef, CAST(:mapeadores AS jsonb), :periodo_gracia_dias)
                RETURNING id_version_contrato_aaef
            """, params, {"uix_version_contrato": f"La versión {contrato.contrato_version} ya está registrada."})
        else:
            escribir(self.db, """
                UPDATE modulo7.versiones_contrato_aaef
                SET estado = CAST(:estado AS modulo7.enum_versiones_contrato_aaef_estado), fecha_activacion = :fecha_activacion,
                    fecha_deprecacion = :fecha_deprecacion, fecha_inactivacion = :fecha_inactivacion
                WHERE id_version_contrato_aaef = :id_version_contrato_aaef
            """, params)
        return contrato

    def obtener_anexo(self, id_mapeo_anexo_aaef: int) -> Optional[AnexoMapeo]:
        f = fila(self.db, f"{_ANEXO} WHERE id_mapeo_anexo_aaef = :id", {"id": id_mapeo_anexo_aaef})
        return AnexoMapeo(**f) if f else None

    def listar_anexos(self) -> list[AnexoMapeo]:
        return [AnexoMapeo(**f) for f in filas(self.db, f"{_ANEXO} ORDER BY id_mapeo_anexo_aaef")]

    def guardar_anexo(self, anexo: AnexoMapeo) -> AnexoMapeo:
        params = {**anexo.__dict__, "evidencia": a_json(anexo.evidencia)}
        if anexo.id_mapeo_anexo_aaef is None:
            anexo.id_mapeo_anexo_aaef = escribir(self.db, """
                INSERT INTO modulo7.mapeos_anexos_aaef (codigo_anexo, version_anexo, estado, direccion_pdf, canonical_sha256)
                VALUES (:codigo_anexo, :version_anexo, 'BORRADOR', :ruta_documento, :sha256_documento)
                RETURNING id_mapeo_anexo_aaef
            """, params, {"uix_mapeos_anexos_codigo_anexo": f"El anexo {anexo.codigo_anexo} ya está registrado."})
        else:
            escribir(self.db, """
                UPDATE modulo7.mapeos_anexos_aaef
                SET estado = CAST(:estado AS modulo7.enum_mapeos_anexos_aaef_estado),
                    fecha_aprobacion_interna = :fecha_aprobacion_interna, fecha_aprobacion_agrofusion = :fecha_aprobacion,
                    json_evidencia = CAST(:evidencia AS jsonb)
                WHERE id_mapeo_anexo_aaef = :id_mapeo_anexo_aaef
            """, params)
        return anexo
