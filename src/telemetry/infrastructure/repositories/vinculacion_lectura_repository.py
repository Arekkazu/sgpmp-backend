# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: guarda contexto y serializa vinculaciones |
# | 2026-10-25 | Arekkazu | USAB-M03 T-18 RF-61: nombres de activo, área, finca, variable y usuario (read-model) |
# | 2026-10-26 | Arekkazu | USAB-M03 T-18 RF-61: SQL literal en text() para el SAST (CWE-89) |
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from src.configuration.infrastructure.models.infraestructura_model import InfraestructuraModel
from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository
from src.telemetry.infrastructure.models.vinculacion_lectura_model import VinculacionLecturaModel


class SqlAlchemyVinculacionLecturaRepository(VinculacionLecturaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, vinculacion: VinculacionLectura) -> VinculacionLectura:
        try:
            orm = VinculacionLecturaModel(
                id_telemetria=vinculacion.id_telemetria,
                modelo_manejo=vinculacion.modelo_manejo,
                id_activo_biologico=vinculacion.id_activo_biologico,
                id_infraestructura=vinculacion.id_infraestructura,
                fecha_inicio_vinculacion=vinculacion.fecha_inicio_vinculacion,
                fecha_fin_vinculacion=vinculacion.fecha_fin_vinculacion,
                mecanismo_vinculacion=vinculacion.mecanismo_vinculacion,
                estado_vinculacion=vinculacion.estado_vinculacion,
                id_usuario=vinculacion.id_usuario,
                motivo_correcion=vinculacion.motivo_correccion,
                id_vinculacion_remplazada=vinculacion.id_vinculacion_reemplazada,
                fecha_creacion=vinculacion.fecha_creacion,
                causa=vinculacion.causa,
                contexto_activo=vinculacion.contexto_activo,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_por_id(
        self,
        id_vinculacion_lectura: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[VinculacionLectura]:
        orm = self.db.get(VinculacionLecturaModel, id_vinculacion_lectura, populate_existing=True)
        if orm is None:
            return None
        if ids_fincas_permitidas is not None:
            id_finca = (
                self.db.execute(
                    select(InfraestructuraModel.id_finca).where(
                        InfraestructuraModel.id_infraestructura == orm.id_infraestructura
                    )
                ).scalar_one_or_none()
            )
            if id_finca not in ids_fincas_permitidas:
                return None
        return self._con_nombres([self._a_entidad(orm)])[0]

    def actualizar(self, vinculacion: VinculacionLectura) -> VinculacionLectura:
        try:
            orm = self.db.get(VinculacionLecturaModel, vinculacion.id_vinculacion_lectura)
            orm.estado_vinculacion = vinculacion.estado_vinculacion
            orm.mecanismo_vinculacion = vinculacion.mecanismo_vinculacion
            orm.id_activo_biologico = vinculacion.id_activo_biologico
            orm.modelo_manejo = vinculacion.modelo_manejo
            orm.id_usuario = vinculacion.id_usuario
            orm.motivo_correcion = vinculacion.motivo_correccion
            orm.fecha_fin_vinculacion = vinculacion.fecha_fin_vinculacion
            orm.causa = vinculacion.causa
            orm.contexto_activo = vinculacion.contexto_activo
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar(
        self,
        id_telemetria: Optional[int] = None,
        estado_vinculacion: Optional[str] = None,
        mecanismo_vinculacion: Optional[str] = None,
        id_infraestructura: Optional[int] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        pagina: int = 1,
        por_pagina: int = 50,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
        modelo_manejo: Optional[str] = None,
    ) -> Tuple[List[VinculacionLectura], int]:
        q = select(VinculacionLecturaModel)
        if ids_fincas_permitidas is not None:
            q = q.join(
                InfraestructuraModel,
                VinculacionLecturaModel.id_infraestructura
                == InfraestructuraModel.id_infraestructura,
            ).where(InfraestructuraModel.id_finca.in_(ids_fincas_permitidas))
        if id_telemetria is not None:
            q = q.where(VinculacionLecturaModel.id_telemetria == id_telemetria)
        if estado_vinculacion:
            q = q.where(VinculacionLecturaModel.estado_vinculacion == estado_vinculacion)
        if mecanismo_vinculacion:
            q = q.where(VinculacionLecturaModel.mecanismo_vinculacion == mecanismo_vinculacion)
        if id_infraestructura is not None:
            q = q.where(VinculacionLecturaModel.id_infraestructura == id_infraestructura)
        if modelo_manejo:
            q = q.where(VinculacionLecturaModel.modelo_manejo == modelo_manejo)
        if fecha_desde is not None:
            q = q.where(VinculacionLecturaModel.fecha_creacion >= fecha_desde)
        if fecha_hasta is not None:
            q = q.where(VinculacionLecturaModel.fecha_creacion <= fecha_hasta)

        total = self.db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
        rows = self.db.execute(
            q.order_by(VinculacionLecturaModel.fecha_creacion.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        ).scalars().all()
        return self._con_nombres([self._a_entidad(r) for r in rows]), total

    def _con_nombres(self, vinculaciones: List[VinculacionLectura]) -> List[VinculacionLectura]:
        """T-18: nombres de activo, ubicación, lectura y usuario en una consulta por tabla y página."""
        def ids(campo):
            return list({getattr(v, campo) for v in vinculaciones if getattr(v, campo) is not None})

        def filas(consulta, campo):
            valores = ids(campo)
            return {f[0]: f[1:] for f in self.db.execute(consulta, {'ids': valores}).all()} if valores else {}

        activos = filas(text('SELECT a.id_activo_biologico, a.identificador, e.nombre FROM modulo2.activos_biologicos a '
                        'LEFT JOIN modulo9.especies e ON e.id_especie = a.id_especie '
                        'WHERE a.id_activo_biologico = ANY(:ids)'), 'id_activo_biologico')
        infra = filas(text('SELECT i.id_infraestructura, i.nombre, f.nombre FROM modulo9.infraestructuras i '
                      'JOIN modulo9.fincas f ON f.id_finca = i.id_finca WHERE i.id_infraestructura = ANY(:ids)'),
                      'id_infraestructura')
        lecturas = filas(text('SELECT t.id_telemetria, va.nombre, s.nombre, coalesce(t.valor_ajustado, t.valor_crudo), '
                         'coalesce(va.unidad, t.unidad_medida), t.timestamp_captura FROM modulo3.telemetrias t '
                         'LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable '
                         'LEFT JOIN modulo9.sensores s ON s.id_sensores = t.id_sensor '
                         'WHERE t.id_telemetria = ANY(:ids)'), 'id_telemetria')
        usuarios = filas(text("SELECT id_usuario, trim(nombre || ' ' || coalesce(apellidos, '')) FROM modulo1.usuarios "
                         'WHERE id_usuario = ANY(:ids)'), 'id_usuario')
        for v in vinculaciones:
            v.nombre_activo, v.especie_activo = activos.get(v.id_activo_biologico, (None, None))
            v.nombre_infraestructura, v.nombre_finca = infra.get(v.id_infraestructura, (None, None))
            (v.nombre_variable, v.nombre_sensor, valor, v.unidad_lectura,
             v.fecha_lectura) = lecturas.get(v.id_telemetria, (None,) * 5)
            v.valor_lectura = float(valor) if valor is not None else None
            v.nombre_usuario = (usuarios.get(v.id_usuario) or (None,))[0]
        return vinculaciones

    @staticmethod
    def _a_entidad(orm: VinculacionLecturaModel) -> VinculacionLectura:
        return VinculacionLectura(
            id_vinculacion_lectura=orm.id_vinculacion_lectura,
            id_telemetria=orm.id_telemetria,
            modelo_manejo=orm.modelo_manejo,
            id_activo_biologico=orm.id_activo_biologico,
            id_infraestructura=orm.id_infraestructura,
            fecha_inicio_vinculacion=orm.fecha_inicio_vinculacion,
            fecha_fin_vinculacion=orm.fecha_fin_vinculacion,
            mecanismo_vinculacion=orm.mecanismo_vinculacion,
            estado_vinculacion=orm.estado_vinculacion,
            id_usuario=orm.id_usuario,
            motivo_correccion=orm.motivo_correcion,
            id_vinculacion_reemplazada=orm.id_vinculacion_remplazada,
            fecha_creacion=orm.fecha_creacion,
            causa=orm.causa,
            contexto_activo=orm.contexto_activo,
        )

    def bloquear_lectura(self, identificador):
        # Mismo orden de locks que DEV-05: lectura y despues dispositivo.
        dispositivo=self.db.execute(text('SELECT id_dispositivo_iot FROM modulo3.telemetrias WHERE id_telemetria=:id FOR UPDATE'),{'id':identificador}).scalar_one()
        self.db.execute(text('SELECT pg_advisory_xact_lock(3505,:id)'),{'id':dispositivo})

    def vigente(self, identificador):
        orm=self.db.execute(select(VinculacionLecturaModel).where(
            VinculacionLecturaModel.id_telemetria==identificador,
            VinculacionLecturaModel.fecha_fin_vinculacion.is_(None),
            VinculacionLecturaModel.estado_vinculacion!='SUPERADA').order_by(
                VinculacionLecturaModel.id_vinculacion_lectura.desc())).scalars().first()
        return self._a_entidad(orm) if orm else None

    def ultima(self,identificador):
        orm=self.db.execute(select(VinculacionLecturaModel).where(
            VinculacionLecturaModel.id_telemetria==identificador).order_by(
                VinculacionLecturaModel.id_vinculacion_lectura.desc()).execution_options(populate_existing=True)).scalars().first()
        return self._a_entidad(orm) if orm else None

    def contexto_lectura(self, identificador, captura):
        lectura=self.db.execute(text('SELECT id_sensor,id_dispositivo_iot FROM modulo3.telemetrias WHERE id_telemetria=:id'),{'id':identificador}).mappings().one()
        areas=list(self.db.execute(text('''SELECT DISTINCT id_infraestructura FROM modulo9.sensores_areas_asociadas
            WHERE id_sensor=:sensor AND id_dispositivo_iot=:dispositivo
              AND (fecha_finalizacion IS NOT NULL OR tiene_estado)
              AND fecha_asociacion<=:captura AND (fecha_finalizacion IS NULL OR fecha_finalizacion>:captura)'''),
            {'sensor':lectura['id_sensor'],'dispositivo':lectura['id_dispositivo_iot'],'captura':captura}).scalars())
        directos=list(self.db.execute(text('''SELECT DISTINCT id_activo_biologico FROM modulo2.asociaciones_activos_sensores
            WHERE id_sensor=:sensor AND fecha_inicio<=:captura
              AND (fecha_fin IS NULL OR fecha_fin>:captura)'''),{'sensor':lectura['id_sensor'],'captura':captura}).scalars())
        return dict(lectura)|{'areas':areas,'activos_directos':directos}
