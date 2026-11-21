# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-102 Fases 6-9: consulta y exportación de la auditoría con verificación de integridad |
"""Consulta de la auditoría de integración (RF-102).

Cada registro se verifica al leerlo: si el hash recalculado no coincide se marca ``CORRUPTO`` y se
alerta al Administrador (FA-3). La vista restringida (auditor externo, 4.3) solo trae los eventos AAEF
exitosos y oculta la IP y los detalles de rechazo; quién la recibe lo decide el permiso, no el rol."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, replace
from typing import Callable

from src.accounting_integration.domain.entities.evento_integracion import TIPOS_AUDITOR, EventoIntegracion
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import (
    AuditoriaIntegracionRepository,
    FiltrosAuditoria,
)
from src.shared.errors import AuthorizationError

TAMANO_MAXIMO = 100  # RF-102 4.7
_LIMITE_EXPORTACION = 50_000


class ConsultarAuditoriaIntegracionUseCase:
    def __init__(self, auditoria: AuditoriaIntegracionRepository, alertar: Callable[[str, dict], None]):
        self.auditoria = auditoria
        self.alertar = alertar

    def _filtros(self, filtros: FiltrosAuditoria, restringida: bool) -> FiltrosAuditoria:
        if not restringida:
            return filtros
        if filtros.tipos_evento and set(filtros.tipos_evento) - set(TIPOS_AUDITOR):  # FA-7
            raise AuthorizationError(code="ACCESO_AUDITORIA_DENEGADO",
                                     message="Solo puede consultar las consultas contables y las activaciones del contrato.")
        return replace(filtros, tipos_evento=filtros.tipos_evento or TIPOS_AUDITOR, solo_exitosos=True)

    def _presentar(self, filas: list[tuple[EventoIntegracion, str, dict]], restringida: bool) -> list[dict]:
        resultado, corruptos = [], []
        for evento, hash_guardado, legibles in filas:
            integro = evento.hash_integridad == hash_guardado
            if not integro:
                corruptos.append(evento.id_evento_integracion)
            fila = {**asdict(evento), **legibles, "integridad": "INTEGRO" if integro else "CORRUPTO"}
            if restringida:
                fila.update(ip_origen=None, json_detalle=None)
            resultado.append(fila)
        if corruptos:
            self.alertar("Se detectaron registros alterados en la auditoría de la integración contable.",
                         {"id_eventos": corruptos[:20], "total": len(corruptos)})
        return resultado

    def execute(self, filtros: FiltrosAuditoria, pagina: int, tamano: int, restringida: bool) -> dict:
        tamano = max(1, min(tamano, TAMANO_MAXIMO))
        filtros = self._filtros(filtros, restringida)
        filas, total = self.auditoria.consultar(filtros, pagina, tamano)
        return {"items": self._presentar(filas, restringida), "pagina": pagina, "tamano": tamano, "total": total}

    def exportar(self, filtros: FiltrosAuditoria, formato: str) -> bytes:
        """RF-102 CA-17: CSV o JSON, solo para quien tiene el permiso de exportar."""
        filas, _ = self.auditoria.consultar(filtros, 1, _LIMITE_EXPORTACION)
        registros = self._presentar(filas, restringida=False)
        if formato == "json":
            return json.dumps(registros, ensure_ascii=False, default=str).encode("utf-8")
        salida = io.StringIO()
        if registros:
            escritor = csv.DictWriter(salida, fieldnames=list(registros[0].keys()))
            escritor.writeheader()
            escritor.writerows({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v) for k, v in r.items()}
                               for r in registros)
        return salida.getvalue().encode("utf-8-sig")
