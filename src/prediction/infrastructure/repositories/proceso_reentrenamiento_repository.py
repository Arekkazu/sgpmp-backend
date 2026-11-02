# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: persistencia de procesos de reentrenamiento y lecturas de apoyo |
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: días de lecturas contados con sesión de sistema (RLS de telemetrias) |
from __future__ import annotations

import copy
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.proceso_reentrenamiento import DatosAnimalReentrenamiento, ProcesoReentrenamiento
from src.prediction.domain.repositories.proceso_reentrenamiento_repository import ProcesoReentrenamientoRepository
from src.prediction.infrastructure.models.proceso_reentrenamiento_model import ProcesoReentrenamientoModel
from src.shared.db_error_translator import raise_from_db_error

_M = ProcesoReentrenamientoModel

# Tipo de modelo asignado al área del animal y su versión vigente (ACTIVO antes que SOMBRA).
# Con la sesión del usuario: la RLS de activos_biologicos dice si el animal está en su alcance.
_SQL_DATOS_ANIMAL = text("""
    SELECT i.tipo_modelo_asignado::text AS tipo_modelo,
           (SELECT v.id_version_modelo FROM modulo4.versiones_modelos v
             WHERE v.id_activo_biologico = ab.id_activo_biologico
               AND v.estado_version::text IN ('ACTIVO', 'SOMBRA')
             ORDER BY (v.estado_version::text = 'ACTIVO') DESC, v.id_version_modelo DESC
             LIMIT 1) AS id_version_vigente
    FROM modulo2.activos_biologicos ab
    LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
    WHERE ab.id_activo_biologico = :id
""")

# Horas entre la primera y la última lectura válida de los sensores directos del animal en los
# últimos 14 días (lo que baja el motor para calibrar, MAX_HORAS_LECTURAS). Con la sesión de
# sistema: la RLS de telemetrias pide permiso de monitoreo o historial, que quien solicita el
# reentrenamiento puede no tener, y eso daba "lecturas insuficientes" falsas.
_SQL_HORAS_LECTURAS = text("""
    SELECT COALESCE(EXTRACT(EPOCH FROM (max(t.timestamp_captura) - min(t.timestamp_captura))) / 3600.0, 0)
    FROM modulo2.asociaciones_activos_sensores a
    JOIN modulo3.telemetrias t ON t.id_sensor = a.id_sensor
    WHERE a.id_activo_biologico = :id AND a.tipo::text = 'directa' AND a.estado_asociacion = 'ACTIVA'
      AND t.timestamp_captura >= a.fecha_inicio AND (a.fecha_fin IS NULL OR t.timestamp_captura < a.fecha_fin)
      AND t.estado_calidad = 'LECTURA_VALIDA'
      AND t.timestamp_captura >= now() - interval '14 days'
""")


# RF-72: diagnósticos vigentes con la ventana de la inferencia a la que responden
# (el pipeline los alinea con las ventanas de lecturas para la regla de retiro).
_SQL_RETRO_VERIFICADAS = text("""
    SELECT rc.id_retroalimentacion, rc.id_resultado_inferencia, rc.estado_retroalimentacion,
           rc.diagnosticos_reales, rc.fecha_retroalimentacion,
           ri.fecha_inicio_ventana, ri.fecha_fin_ventana, ri.fecha_inferencia
    FROM modulo4.retroalimentaciones_clinicas rc
    JOIN modulo4.resultados_inferencia ri ON ri.id_resultado_inferencia = rc.id_resultado_inferencia
    WHERE rc.id_activo_biologico = :id AND rc.estado_registro = 'ACTIVO'
    ORDER BY ri.fecha_inferencia
""")

_SQL_NOMBRES = text("""
    SELECT ab.id_activo_biologico, ab.identificador, esp.nombre AS especie
    FROM modulo2.activos_biologicos ab
    LEFT JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
    WHERE ab.id_activo_biologico = ANY(:ids)
""")
_SQL_NOMBRES_VERSION = text("""
    SELECT id_version_modelo, nombre_version FROM modulo4.versiones_modelos WHERE id_version_modelo = ANY(:ids)
""")


def _a_entidad(orm: ProcesoReentrenamientoModel) -> ProcesoReentrenamiento:
    return ProcesoReentrenamiento(
        id_proceso_reentrenamiento=orm.id_proceso_reentrenamiento, tipo_modelo=orm.tipo_modelo,
        id_activo_biologico=orm.id_activo_biologico, disparador=orm.disparador,
        modo_generacion=orm.modo_generacion, estado=orm.estado, fase_actual=orm.fase_actual,
        porcentaje_progreso=orm.porcentaje_progreso, fases=copy.deepcopy(orm.json_fases or []),
        porcentaje_cpu=orm.porcentaje_cpu, memoria_ram_mb=orm.memoria_ram_mb, codigo_error=orm.codigo_error,
        motivos=orm.json_motivos, id_version_modelo_referencia=orm.id_version_modelo_referencia,
        id_version_modelo_resultante=orm.id_version_modelo_resultante,
        id_usuario_solicitante=orm.id_usuario_solicitante, fecha_solicitud=orm.fecha_solicitud,
        fecha_inicio=orm.fecha_inicio, fecha_fin=orm.fecha_fin, fecha_ultimo_latido=orm.fecha_ultimo_latido,
    )


def _volcar(p: ProcesoReentrenamiento, orm: ProcesoReentrenamientoModel) -> None:
    orm.tipo_modelo = p.tipo_modelo
    orm.id_activo_biologico = p.id_activo_biologico
    orm.disparador = p.disparador
    orm.modo_generacion = p.modo_generacion
    orm.estado = p.estado
    orm.fase_actual = p.fase_actual
    orm.porcentaje_progreso = p.porcentaje_progreso
    orm.json_fases = copy.deepcopy(p.fases)
    orm.porcentaje_cpu = p.porcentaje_cpu
    orm.memoria_ram_mb = p.memoria_ram_mb
    orm.codigo_error = p.codigo_error
    orm.json_motivos = p.motivos
    orm.id_version_modelo_referencia = p.id_version_modelo_referencia
    orm.id_version_modelo_resultante = p.id_version_modelo_resultante
    orm.id_usuario_solicitante = p.id_usuario_solicitante
    orm.fecha_solicitud = p.fecha_solicitud
    orm.fecha_inicio = p.fecha_inicio
    orm.fecha_fin = p.fecha_fin
    orm.fecha_ultimo_latido = p.fecha_ultimo_latido


class SqlAlchemyProcesoReentrenamientoRepository(ProcesoReentrenamientoRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def crear(self, proceso):
        try:
            orm = ProcesoReentrenamientoModel()
            _volcar(proceso, orm)
            self._db.add(orm)
            self._db.flush()
            self._db.refresh(orm)
            return _a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener(self, id_proceso):
        try:
            orm = self._db.get(_M, id_proceso)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._con_nombres([_a_entidad(orm)])[0] if orm else None

    def abierto_de(self, id_activo_biologico):
        try:
            orm = self._db.execute(select(_M).where(
                _M.id_activo_biologico == id_activo_biologico, _M.estado.in_(("PENDIENTE", "EN_CURSO")))).scalars().first()
        except Exception as exc:
            raise_from_db_error(exc)
        return _a_entidad(orm) if orm else None

    def tomar_siguiente(self):
        try:
            orm = self._db.execute(
                select(_M).where(_M.estado == "PENDIENTE").order_by(_M.fecha_solicitud, _M.id_proceso_reentrenamiento)
                .limit(1).with_for_update(skip_locked=True)).scalars().first()
        except Exception as exc:
            raise_from_db_error(exc)
        return _a_entidad(orm) if orm else None

    def guardar(self, proceso):
        try:
            orm = self._db.get(_M, proceso.id_proceso_reentrenamiento)
            _volcar(proceso, orm)
            self._db.flush()
            self._db.refresh(orm)
            return _a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar(self, *, tipo_modelo, id_activo_biologico, estado, desde, hasta, pagina, por_pagina):
        q = select(_M)
        if tipo_modelo:
            q = q.where(_M.tipo_modelo == tipo_modelo)
        if id_activo_biologico is not None:
            q = q.where(_M.id_activo_biologico == id_activo_biologico)
        if estado:
            q = q.where(_M.estado == estado)
        if desde is not None:
            q = q.where(_M.fecha_solicitud >= desde)
        if hasta is not None:
            q = q.where(_M.fecha_solicitud <= hasta)
        try:
            total = self._db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
            filas = self._db.execute(q.order_by(_M.fecha_solicitud.desc(), _M.id_proceso_reentrenamiento)
                                     .offset((pagina - 1) * por_pagina).limit(por_pagina)).scalars().all()
        except Exception as exc:
            raise_from_db_error(exc)
        return self._con_nombres([_a_entidad(o) for o in filas]), total

    def en_curso(self):
        try:
            return [_a_entidad(o) for o in self._db.execute(select(_M).where(_M.estado == "EN_CURSO")).scalars().all()]
        except Exception as exc:
            raise_from_db_error(exc)

    def datos_animal(self, id_activo_biologico):
        try:
            f = self._db.execute(_SQL_DATOS_ANIMAL, {"id": id_activo_biologico}).mappings().first()
        except Exception as exc:
            raise_from_db_error(exc)
        if f is None:
            return None
        return DatosAnimalReentrenamiento(f["tipo_modelo"], f["id_version_vigente"])

    def horas_de_lecturas(self, id_activo_biologico):
        try:
            return float(self._db.execute(_SQL_HORAS_LECTURAS, {"id": id_activo_biologico}).scalar() or 0)
        except Exception as exc:
            raise_from_db_error(exc)

    def version_de_proceso(self, id_proceso):
        try:
            return self._db.execute(text(
                "SELECT id_version_modelo FROM modulo4.versiones_modelos WHERE id_proceso_rf71 = :id "
                "ORDER BY id_version_modelo DESC LIMIT 1"), {"id": id_proceso}).scalar()
        except Exception as exc:
            raise_from_db_error(exc)

    def retroalimentaciones_verificadas(self, id_activo_biologico):
        try:
            filas = self._db.execute(_SQL_RETRO_VERIFICADAS, {"id": id_activo_biologico}).mappings().all()
        except Exception as exc:
            raise_from_db_error(exc)
        return [{
            "id_retroalimentacion": str(f["id_retroalimentacion"]),
            "id_resultado_inferencia": str(f["id_resultado_inferencia"]),
            "estado_retroalimentacion": f["estado_retroalimentacion"],
            "diagnosticos_reales": list(f["diagnosticos_reales"] or []),
            "fecha_retroalimentacion": f["fecha_retroalimentacion"].isoformat(),
            "fecha_inicio_ventana": f["fecha_inicio_ventana"].isoformat() if f["fecha_inicio_ventana"] else None,
            "fecha_fin_ventana": f["fecha_fin_ventana"].isoformat() if f["fecha_fin_ventana"] else None,
        } for f in filas]

    def _con_nombres(self, procesos: list[ProcesoReentrenamiento]) -> list[ProcesoReentrenamiento]:
        """Código del animal y nombre de la versión resultante, para mostrar (una consulta por página)."""
        if not procesos:
            return procesos
        try:
            animales = {f.id_activo_biologico: f for f in self._db.execute(
                _SQL_NOMBRES, {"ids": list({p.id_activo_biologico for p in procesos})}).all()}
            ids_v = list({p.id_version_modelo_resultante for p in procesos if p.id_version_modelo_resultante})
            versiones = dict(self._db.execute(_SQL_NOMBRES_VERSION, {"ids": ids_v}).all()) if ids_v else {}
        except Exception as exc:
            raise_from_db_error(exc)
        for p in procesos:
            animal = animales.get(p.id_activo_biologico)
            p.identificador_activo = animal.identificador if animal else None
            p.nombre_especie = animal.especie if animal else None
            p.nombre_version_resultante = versiones.get(p.id_version_modelo_resultante)
        return procesos
