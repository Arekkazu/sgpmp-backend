from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy import exists
from sqlalchemy.orm import Session

import src.biological_assets.infrastructure.models  # noqa: F401 — ensures all ORM models register before mapper resolution

from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetalleIndividual,
    DetallePoblacional,
    GestionFase,
    HistorialInfraestructura,
)
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.infrastructure.models.activo_biologico_model import ActivoBiologicoModel
from src.biological_assets.infrastructure.models.detalle_individual_model import DetalleActivoIndividualModel
from src.biological_assets.infrastructure.models.detalle_poblacional_model import DetalleActivoPoblacionalModel
from src.biological_assets.infrastructure.models.gestion_fase_model import GestionFaseModel
from src.biological_assets.infrastructure.models.historial_infraestructura_activo_model import (
    HistorialInfraestructuraActivoModel,
)
from src.configuration.infrastructure.models.infraestructura_model import InfraestructuraModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyActivoBiologicoRepository(ActivoBiologicoRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Mapeo ORM ↔ dominio ─────────────────────────────────────────────────

    @staticmethod
    def _a_entidad(orm: ActivoBiologicoModel) -> ActivoBiologico:
        detalle_ind: Optional[DetalleIndividual] = None
        detalle_pob: Optional[DetallePoblacional] = None

        if orm.detalle_individual:
            d = orm.detalle_individual
            detalle_ind = DetalleIndividual(
                id_detalle=d.id_detalle_activo_individual,
                raza=d.raza,
                sexo=d.sexo,
                fecha_nacimiento=d.fecha_nacimeinto,  # typo en DB
                peso_inicial=d.peso_inicial,
                fecha_creacion=d.fecha_creacion,
            )

        if orm.detalle_poblacional:
            p = orm.detalle_poblacional
            detalle_pob = DetallePoblacional(
                id_detalle=p.id_detalle_activo_biologico_poblacional,
                cantidad_inicial=p.cantidad_inicial,
                cantidad_actual=p.cantidad_actual,
                peso_promedio_inicial=p.peso_promedio_inicial,
                peso_promedio=p.peso_promedio,
                biomasa_total=p.biomasa_total,
                densidad=p.densidad,
            )

        nombre_estado = orm.estado.nombre if orm.estado else None

        return ActivoBiologico(
            id_activo_biologico=orm.id_activo_biologico,
            id_especie=orm.id_especie,
            tipo=orm.tipo,
            identificador=orm.identificador,
            fecha_inicio_ciclo=orm.fecha_inicio_ciclo,
            detalles_procedencia=orm.detalles_procedencia,
            origen_financiero=orm.origen_financiero,
            costo_adquisicion=orm.costo_adquisicion,
            soporte_documental=orm.soporte_documental,
            descripcion=orm.descripcion,
            id_infraestructura=orm.id_infraestructura,
            atributos_dinamicos=orm.atributos_dinamicos,
            id_estado=orm.id_estado,
            id_usuario=orm.id_usuario,
            fecha_creacion=orm.fecha_creacion,
            nombre_estado=nombre_estado,
            detalle_individual=detalle_ind,
            detalle_poblacional=detalle_pob,
        )

    # ── Operaciones del puerto ───────────────────────────────────────────────

    def guardar(self, activo: ActivoBiologico) -> ActivoBiologico:
        ahora = datetime.now(timezone.utc)
        try:
            # El trigger trg_auditar_activo_biologico requiere esta variable de sesión
            self.db.execute(text("SET LOCAL app.usuario_id = :uid"), {"uid": activo.id_usuario})
            orm = ActivoBiologicoModel(
                id_especie=activo.id_especie,
                tipo=activo.tipo,
                identificador=activo.identificador,
                id_infraestructura=activo.id_infraestructura,
                fecha_inicio_ciclo=activo.fecha_inicio_ciclo,
                id_estado=activo.id_estado,
                descripcion=activo.descripcion,
                origen_financiero=activo.origen_financiero,
                costo_adquisicion=activo.costo_adquisicion,
                atributos_dinamicos=activo.atributos_dinamicos,
                id_usuario=activo.id_usuario,
                fecha_creacion=ahora,
                soporte_documental=activo.soporte_documental,
                detalles_procedencia=activo.detalles_procedencia,
            )
            self.db.add(orm)
            self.db.flush()

            if activo.detalle_individual:
                di = activo.detalle_individual
                self.db.add(DetalleActivoIndividualModel(
                    id_activo_biologico=orm.id_activo_biologico,
                    raza=di.raza,
                    sexo=di.sexo,
                    fecha_nacimeinto=di.fecha_nacimiento,  # typo en DB
                    peso_inicial=di.peso_inicial,
                    fecha_creacion=ahora,
                    id_usuario=activo.id_usuario,
                ))

            if activo.detalle_poblacional:
                dp = activo.detalle_poblacional
                self.db.add(DetalleActivoPoblacionalModel(
                    id_activo_biologico=orm.id_activo_biologico,
                    cantidad_inicial=dp.cantidad_inicial,
                    cantidad_actual=dp.cantidad_actual,
                    peso_promedio_inicial=dp.peso_promedio_inicial,
                ))

            self.db.add(HistorialInfraestructuraActivoModel(
                id_activo_biologico=orm.id_activo_biologico,
                id_infraestructura=activo.id_infraestructura,
                fecha_inicio=ahora,
                fecha_fin=None,
                id_usuario_registro=activo.id_usuario,
            ))

            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                'uq_activo_biologico_identificador': (
                    f"El identificador '{activo.identificador}' ya está registrado en el sistema."
                ),
            })
        return self._a_entidad(orm)

    def obtener_por_id(self, id_activo: int) -> Optional[ActivoBiologico]:
        orm = self.db.get(ActivoBiologicoModel, id_activo)
        return self._a_entidad(orm) if orm else None

    def existe_identificador(self, identificador: str) -> bool:
        return (
            self.db.query(ActivoBiologicoModel)
            .filter(func.lower(ActivoBiologicoModel.identificador) == identificador.lower())
            .first()
        ) is not None

    def obtener_asociacion_activa(self, id_activo: int) -> Optional[HistorialInfraestructura]:
        row = (
            self.db.query(HistorialInfraestructuraActivoModel, InfraestructuraModel)
            .join(
                InfraestructuraModel,
                HistorialInfraestructuraActivoModel.id_infraestructura == InfraestructuraModel.id_infraestructura,
            )
            .filter(
                HistorialInfraestructuraActivoModel.id_activo_biologico == id_activo,
                HistorialInfraestructuraActivoModel.fecha_fin.is_(None),
            )
            .first()
        )
        if not row:
            return None
        hist, infra = row
        return HistorialInfraestructura(
            id_historial=hist.id_historial,
            id_activo_biologico=hist.id_activo_biologico,
            id_infraestructura=hist.id_infraestructura,
            nombre_infraestructura=infra.nombre,
            tipo_infraestructura=infra.tipo,
            fecha_inicio=hist.fecha_inicio,
            fecha_fin=hist.fecha_fin,
        )

    def obtener_historial_infraestructura(self, id_activo: int) -> list[HistorialInfraestructura]:
        rows = (
            self.db.query(HistorialInfraestructuraActivoModel, InfraestructuraModel)
            .join(
                InfraestructuraModel,
                HistorialInfraestructuraActivoModel.id_infraestructura == InfraestructuraModel.id_infraestructura,
            )
            .filter(HistorialInfraestructuraActivoModel.id_activo_biologico == id_activo)
            .order_by(HistorialInfraestructuraActivoModel.fecha_inicio.desc())
            .all()
        )
        return [
            HistorialInfraestructura(
                id_historial=h.id_historial,
                id_activo_biologico=h.id_activo_biologico,
                id_infraestructura=h.id_infraestructura,
                nombre_infraestructura=i.nombre,
                tipo_infraestructura=i.tipo,
                fecha_inicio=h.fecha_inicio,
                fecha_fin=h.fecha_fin,
            )
            for h, i in rows
        ]

    def actualizar_detalle_individual(self, activo: ActivoBiologico) -> ActivoBiologico:
        orm = self.db.get(ActivoBiologicoModel, activo.id_activo_biologico)
        if orm and orm.detalle_individual and activo.detalle_individual:
            di = activo.detalle_individual
            orm.detalle_individual.raza = di.raza
            orm.detalle_individual.sexo = di.sexo
            orm.detalle_individual.fecha_nacimeinto = di.fecha_nacimiento  # typo en DB
            orm.detalle_individual.peso_inicial = di.peso_inicial
        self.db.flush()
        self.db.refresh(orm)
        return self._a_entidad(orm)

    def obtener_gestiones_fases(self, id_activo: int) -> list[GestionFase]:
        rows = self.db.execute(
            text(
                'SELECT gf.id_gestion_fases, gf.id_activo_biologico, gf.id_ciclo_productiva, '
                '       cp.nombre AS nombre_ciclo, '
                '       gf.fecha_inicio, gf.fecha_finalizacion, gf.es_activa, '
                '       gf.id_usuario, gf.motivo_cambio, '
                '       (SELECT COUNT(*) FROM modulo9.ciclos_productivos_biologicos cpb2 '
                '        WHERE cpb2.id_ciclo_productivo = gf.id_ciclo_productiva) AS total_pasos '
                'FROM modulo2.gestiones_fases gf '
                'JOIN modulo9.ciclos_productivos cp ON cp.id_ciclo_productivo = gf.id_ciclo_productiva '
                'WHERE gf.id_activo_biologico = :id '
                'ORDER BY gf.fecha_inicio ASC'
            ),
            {'id': id_activo},
        ).fetchall()

        # Calcular paso_actual y nombre_fase_actual para cada gestión agrupando por ciclo
        ciclo_conteos: dict[int, int] = {}
        fases_cache: dict[int, list] = {}
        result: list[GestionFase] = []

        for r in rows:
            id_ciclo = r.id_ciclo_productiva
            ciclo_conteos[id_ciclo] = ciclo_conteos.get(id_ciclo, 0) + 1
            paso_actual = ciclo_conteos[id_ciclo]

            if id_ciclo not in fases_cache:
                fases_rows = self.db.execute(
                    text(
                        'SELECT cb.nombre AS nombre_fase '
                        'FROM modulo9.ciclos_productivos_biologicos cpb '
                        'JOIN modulo9.ciclos_biologicos cb ON cb.id_ciclo_biologico = cpb.id_ciclo_biologico '
                        'WHERE cpb.id_ciclo_productivo = :id '
                        'ORDER BY cpb.id_ciclos_productivo_biologico ASC'
                    ),
                    {'id': id_ciclo},
                ).fetchall()
                fases_cache[id_ciclo] = [f.nombre_fase for f in fases_rows]

            fases = fases_cache[id_ciclo]
            nombre_fase_actual = fases[paso_actual - 1] if paso_actual <= len(fases) else None

            result.append(GestionFase(
                id_gestion_fases=r.id_gestion_fases,
                id_activo_biologico=r.id_activo_biologico,
                id_ciclo_productiva=r.id_ciclo_productiva,
                nombre_ciclo=r.nombre_ciclo,
                nombre_fase_actual=nombre_fase_actual,
                paso_actual=paso_actual,
                total_pasos=r.total_pasos,
                fecha_inicio=r.fecha_inicio,
                fecha_finalizacion=r.fecha_finalizacion,
                es_activa=r.es_activa,
                id_usuario=r.id_usuario,
                motivo_cambio=r.motivo_cambio,
            ))

        return result

    def cerrar_gestion_activa(self, id_activo: int, fecha_fin: datetime, motivo: str, usuario_id: int) -> None:
        self.db.execute(text('SET LOCAL app.usuario_id = :uid'), {'uid': usuario_id})
        self.db.execute(
            text(
                'UPDATE modulo2.gestiones_fases '
                'SET es_activa = false, fecha_finalizacion = :fecha, motivo_cambio = :motivo '
                'WHERE id_activo_biologico = :id AND es_activa = true'
            ),
            {'id': id_activo, 'fecha': fecha_fin, 'motivo': motivo},
        )

    def actualizar_detalle_poblacional(self, activo: ActivoBiologico) -> ActivoBiologico:
        orm = self.db.get(ActivoBiologicoModel, activo.id_activo_biologico)
        if orm and orm.detalle_poblacional and activo.detalle_poblacional:
            dp = activo.detalle_poblacional
            orm.detalle_poblacional.cantidad_actual = dp.cantidad_actual
            orm.detalle_poblacional.peso_promedio = dp.peso_promedio
            orm.detalle_poblacional.biomasa_total = dp.biomasa_total
            orm.detalle_poblacional.densidad = dp.densidad
        self.db.flush()
        self.db.refresh(orm)
        return self._a_entidad(orm)

    def actualizar_estado(self, id_activo: int, nuevo_id_estado: int) -> None:
        orm = self.db.get(ActivoBiologicoModel, id_activo)
        if orm:
            orm.id_estado = nuevo_id_estado
            self.db.flush()

    def tiene_sensores_activos(self, id_activo: int) -> bool:
        ahora = datetime.now(timezone.utc)
        row = self.db.execute(
            text(
                'SELECT EXISTS ('
                '  SELECT 1 FROM modulo2.asociaciones_activos_sensores '
                '  WHERE id_activo_biologico = :id AND fecha_fin > :ahora'
                ')'
            ),
            {'id': id_activo, 'ahora': ahora},
        ).scalar()
        return bool(row)

    def obtener_fase_activa(self, id_activo: int) -> Optional[GestionFase]:
        orm = (
            self.db.query(GestionFaseModel)
            .filter(
                GestionFaseModel.id_activo_biologico == id_activo,
                GestionFaseModel.es_activa.is_(True),
            )
            .first()
        )
        if orm is None:
            return None
        return GestionFase(
            id_gestion_fases=orm.id_gestion_fases,
            id_activo_biologico=orm.id_activo_biologico,
            id_ciclo_productiva=orm.id_ciclo_productiva,
            nombre_ciclo='',
            fecha_inicio=orm.fecha_inicio,
            es_activa=orm.es_activa,
            id_usuario=orm.id_usuario,
            fecha_finalizacion=orm.fecha_finalizacion,
            motivo_cambio=orm.motivo_cambio,
        )

    def crear_gestion_fase(self, gestion: GestionFase) -> GestionFase:
        try:
            result = self.db.execute(
                text(
                    'INSERT INTO modulo2.gestiones_fases '
                    '(id_activo_biologico, id_ciclo_productiva, fecha_inicio, es_activa, id_usuario, motivo_cambio) '
                    'VALUES (:id_activo, :id_ciclo, :fecha_inicio, true, :id_usuario, :motivo) '
                    'RETURNING id_gestion_fases, fecha_inicio, fecha_finalizacion, es_activa, id_usuario, motivo_cambio'
                ),
                {
                    'id_activo': gestion.id_activo_biologico,
                    'id_ciclo': gestion.id_ciclo_productiva,
                    'fecha_inicio': gestion.fecha_inicio,
                    'id_usuario': gestion.id_usuario,
                    'motivo': gestion.motivo_cambio,
                },
            )
            row = result.fetchone()
        except Exception as exc:
            raise_from_db_error(exc, {
                'uix_gestion_fase_activa_por_activo': 'El activo ya tiene una fase productiva activa.',
            })
        return GestionFase(
            id_gestion_fases=row.id_gestion_fases,
            id_activo_biologico=gestion.id_activo_biologico,
            id_ciclo_productiva=gestion.id_ciclo_productiva,
            nombre_ciclo=gestion.nombre_ciclo,
            nombre_fase_actual=gestion.nombre_fase_actual,
            paso_actual=gestion.paso_actual,
            total_pasos=gestion.total_pasos,
            fecha_inicio=row.fecha_inicio,
            fecha_finalizacion=row.fecha_finalizacion,
            es_activa=row.es_activa,
            id_usuario=row.id_usuario,
            motivo_cambio=row.motivo_cambio,
        )
