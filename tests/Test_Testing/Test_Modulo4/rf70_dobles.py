"""Dobles para el contrato Dev de RF-70: solo consulta de despliegues.

No inician OTA, no descargan artefactos y no hablan con Edge.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.prediction.domain.entities.despliegue_ota import DespliegueOta


class SesionNula:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class AuditoriaMemoria:
    def __init__(self) -> None:
        self.eventos: list[dict] = []

    def registrar(self, **kw) -> None:
        self.eventos.append(kw)


class VersionPortOta:
    def __init__(self, estados: Optional[dict[int, str]] = None) -> None:
        self.estados = estados or {3: "ACTIVO"}

    def obtener_estado(self, id_version: int):
        return self.estados.get(id_version)

    def obtener_llave(self, id_version: int):
        estado = self.estados.get(id_version)
        if estado is None:
            return None
        return (estado, "MODELO_ESPECIES_GRANDES", None)


class DespliegueRepoMemoria:
    def __init__(self, items: Optional[list[DespliegueOta]] = None) -> None:
        self.items = items or []

    def obtener_por_version(
        self,
        id_version: int,
        id_dispositivo: Optional[int] = None,
        estado: Optional[str] = None,
    ) -> list[DespliegueOta]:
        out = [d for d in self.items if d.id_version_modelo == id_version]
        if id_dispositivo is not None:
            out = [d for d in out if d.id_dispositivo_iot == id_dispositivo]
        if estado is not None:
            out = [d for d in out if d.estado_despliegue == estado]
        return out

    def listar(
        self,
        id_version: Optional[int] = None,
        id_dispositivo: Optional[int] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DespliegueOta], int]:
        out = list(self.items)
        if id_version is not None:
            out = [d for d in out if d.id_version_modelo == id_version]
        if id_dispositivo is not None:
            out = [d for d in out if d.id_dispositivo_iot == id_dispositivo]
        if estado is not None:
            out = [d for d in out if d.estado_despliegue == estado]
        total = len(out)
        return out[offset : offset + limit], total

    def obtener_por_id(self, id_despliegue: int) -> Optional[DespliegueOta]:
        for d in self.items:
            if d.id_despliegue_ota == id_despliegue:
                return d
        return None


def despliegue(
    *,
    id_despliegue_ota: int = 1,
    id_version_modelo: int = 3,
    id_dispositivo_iot: int = 12,
    estado_despliegue: str = "EXITOSO",
    modo_distribucion: str = "INMEDIATO",
    hash_modelo_sha256: str = "a" * 64,
    rollback_ejecutado: bool = False,
    motivo_fallo: Optional[str] = None,
    tamano_descargado_bytes: Optional[int] = 100,
) -> DespliegueOta:
    ahora = datetime.now(timezone.utc)
    return DespliegueOta(
        id_despliegue_ota=id_despliegue_ota,
        id_version_modelo=id_version_modelo,
        id_dispositivo_iot=id_dispositivo_iot,
        tipo_modelo="MODELO_ESPECIES_GRANDES",
        modo_distribucion=modo_distribucion,
        estado_despliegue=estado_despliegue,
        hash_modelo_sha256=hash_modelo_sha256,
        resultado_validacion_hash=True if estado_despliegue == "EXITOSO" else None,
        id_version_modelo_anterior=2,
        rollback_ejecutado=rollback_ejecutado,
        intentos_descarga=1,
        max_reintentos=3,
        tamano_modelo_bytes=100,
        tamano_descargado_bytes=tamano_descargado_bytes,
        duracion_proceso_ms=1000,
        ventana_inicio=None,
        ventana_fin=None,
        nivel_bateria_al_inicio=None,
        fecha_inicio=ahora,
        fecha_fin=ahora if estado_despliegue in {"EXITOSO", "FALLIDO", "SIN_CAMBIOS"} else None,
        motivo_fallo=motivo_fallo,
    )
