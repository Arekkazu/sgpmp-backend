from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import FichaIntegral
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ConsultarFichaIntegralUseCase:

    def __init__(
        self,
        db: Session,
        activo_repo: ActivoBiologicoRepository,
    ) -> None:
        self.db = db
        self.activo_repo = activo_repo

    def execute(self, id_activo: int, usuario: UsuarioActual) -> FichaIntegral:
        # E-01: el activo debe existir
        activo = self.activo_repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con id {id_activo} no fue encontrado en el sistema.',
            )

        advertencias: list[str] = []

        # ── Secciones 1-4, 7: datos base via vista
        ficha_row = self.db.execute(
            text('SELECT * FROM modulo2.vw_rf47_ficha_integral_activo WHERE id_activo_biologico = :id'),
            {'id': id_activo},
        ).fetchone()

        # ── Sección 5: últimos 5 eventos por categoría
        eventos_sanitarios = self._ultimos_sanitarios(id_activo)
        eventos_productivos = self._ultimos_productivos(id_activo)
        eventos_crecimiento = self._ultimos_crecimiento(id_activo)
        eventos_reproductivos = self._ultimos_reproductivos(id_activo)

        # ── Sección 6: indicadores zootécnicos
        indicadores = self._indicadores(id_activo)

        # ── Verificación de consistencia estado vs fase (E-04)
        if ficha_row:
            estado = (ficha_row.estado_actual or '').upper()
            fase = ficha_row.fase_productiva_activa
            if estado in ('CERRADO', 'BAJA') and fase is not None:
                advertencias.append(
                    f'Se detectó una inconsistencia: el activo está en estado {estado} '
                    f'pero aún tiene una fase productiva activa ({fase}). '
                    'Verifique el estado o la fase del activo.'
                )

        if ficha_row:
            return FichaIntegral(
                id_activo_biologico=id_activo,
                identificador=ficha_row.codigo,
                tipo=str(ficha_row.tipo),
                especie=ficha_row.especie,
                fecha_registro=ficha_row.fecha_registro,
                dias_en_sistema=ficha_row.dias_en_sistema,
                estado_actual=ficha_row.estado_actual,
                infraestructura_asociada=ficha_row.infraestructura_asociada,
                fase_productiva_activa=ficha_row.fase_productiva_activa,
                raza=ficha_row.raza,
                sexo=ficha_row.sexo,
                fecha_nacimiento=ficha_row.fecha_nacimiento,
                peso_actual=Decimal(str(ficha_row.peso_actual)) if ficha_row.peso_actual else None,
                unidad_peso=ficha_row.unidad_peso,
                fecha_ultimo_peso=ficha_row.fecha_ultimo_peso,
                cantidad_actual=ficha_row.cantidad_actual,
                biomasa_total=Decimal(str(ficha_row.biomasa_total)) if ficha_row.biomasa_total else None,
                densidad=None,
                eventos_sanitarios=eventos_sanitarios,
                eventos_productivos=eventos_productivos,
                eventos_crecimiento=eventos_crecimiento,
                eventos_reproductivos=eventos_reproductivos,
                indicadores=indicadores,
                advertencias=advertencias,
            )

        # Fallback si la vista no devuelve fila pero el activo existe
        return FichaIntegral(
            id_activo_biologico=id_activo,
            identificador=activo.identificador,
            tipo=activo.tipo,
            especie='',
            fecha_registro=None,
            dias_en_sistema=None,
            estado_actual='',
            infraestructura_asociada=None,
            fase_productiva_activa=None,
            raza=None,
            sexo=None,
            fecha_nacimiento=None,
            peso_actual=None,
            unidad_peso=None,
            fecha_ultimo_peso=None,
            cantidad_actual=None,
            biomasa_total=None,
            densidad=None,
            eventos_sanitarios=[],
            eventos_productivos=[],
            eventos_crecimiento=[],
            eventos_reproductivos=[],
            indicadores=[],
            advertencias=['No se pudo cargar la información completa del activo.'],
        )

    def _ultimos_sanitarios(self, id_activo: int) -> list[dict]:
        rows = self.db.execute(
            text(
                'SELECT fecha, categoria AS tipo_evento, medicamento, diagnostico '
                'FROM modulo2.vw_rf46_eventos_sanitarios '
                'WHERE id_activo_biologico = :id '
                'ORDER BY fecha DESC LIMIT 5'
            ),
            {'id': id_activo},
        ).fetchall()
        return [
            {'tipo_evento': r.tipo_evento, 'medicamento': r.medicamento,
             'diagnostico': r.diagnostico, 'fecha': r.fecha.isoformat() if r.fecha else None}
            for r in rows
        ]

    def _ultimos_productivos(self, id_activo: int) -> list[dict]:
        rows = self.db.execute(
            text(
                'SELECT fecha, metrica_produccion AS tipo_producto, cantidad '
                'FROM modulo2.vw_rf46_eventos_productivos '
                'WHERE id_activo_biologico = :id '
                'ORDER BY fecha DESC LIMIT 5'
            ),
            {'id': id_activo},
        ).fetchall()
        return [
            {'tipo_producto': r.tipo_producto, 'cantidad': str(r.cantidad),
             'fecha': r.fecha.isoformat() if r.fecha else None}
            for r in rows
        ]

    def _ultimos_crecimiento(self, id_activo: int) -> list[dict]:
        rows = self.db.execute(
            text(
                'SELECT fecha, tipo_medicion, valor_medicion, unidad_medida '
                'FROM modulo2.vw_rf46_eventos_crecimiento '
                'WHERE id_activo_biologico = :id '
                'ORDER BY fecha DESC LIMIT 5'
            ),
            {'id': id_activo},
        ).fetchall()
        return [
            {'variable': r.tipo_medicion, 'valor': str(r.valor_medicion),
             'unidad': r.unidad_medida, 'fecha': r.fecha.isoformat() if r.fecha else None}
            for r in rows
        ]

    def _ultimos_reproductivos(self, id_activo: int) -> list[dict]:
        rows = self.db.execute(
            text(
                'SELECT fecha, categoria_reproductiva AS tipo_evento, resultado '
                'FROM modulo2.vw_rf46_eventos_reproductivos '
                'WHERE id_activo_biologico = :id '
                'ORDER BY fecha DESC LIMIT 5'
            ),
            {'id': id_activo},
        ).fetchall()
        return [
            {'tipo_evento': r.tipo_evento, 'resultado': r.resultado,
             'fecha': r.fecha.isoformat() if r.fecha else None}
            for r in rows
        ]

    def _indicadores(self, id_activo: int) -> list[dict]:
        rows = self.db.execute(
            text(
                'SELECT tipo_indicador, fecha_inicio, fecha_fin, paramtros_calculo '
                'FROM modulo2.vw_rf47_indicadores_zootecnicos_activo '
                'WHERE id_activo_biologico = :id '
                'ORDER BY fecha_inicio DESC LIMIT 10'
            ),
            {'id': id_activo},
        ).fetchall()
        return [
            {'tipo': r.tipo_indicador,
             'fecha_inicio': r.fecha_inicio.isoformat() if r.fecha_inicio else None,
             'fecha_fin': r.fecha_fin.isoformat() if r.fecha_fin else None,
             'parametros': r.paramtros_calculo}
            for r in rows
        ]
