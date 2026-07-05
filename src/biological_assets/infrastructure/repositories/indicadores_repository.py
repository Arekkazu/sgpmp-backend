from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import (
    DatosConsolidados,
    IndicadorZootecnico,
    ResultadoIndicadores,
    SeccionDatosConsolidados,
)
from src.biological_assets.domain.repositories.indicadores_repository import IndicadoresRepository

_INCLUDE_CRECIMIENTO = {'CRECIMIENTO', 'TODOS'}
_INCLUDE_PRODUCCION = {'PRODUCCION', 'TODOS'}
_INCLUDE_SANITARIO = {'SANITARIO', 'TODOS'}
_INCLUDE_EFICIENCIA = {'EFICIENCIA', 'TODOS'}


class SqlAlchemyIndicadoresRepository(IndicadoresRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── RF-51: Calcular indicadores on-demand ────────────────────────────────

    def calcular_indicadores(
        self,
        id_activo: int,
        tipo_activo: str,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        tipo_indicador: str,
    ) -> ResultadoIndicadores:
        ahora = datetime.now(timezone.utc)
        indicadores: list[IndicadorZootecnico] = []
        advertencias: list[str] = []

        if tipo_indicador in _INCLUDE_CRECIMIENTO:
            ind, aviso = self._calcular_ganancia_peso(id_activo, fecha_inicio, fecha_fin, ahora)
            indicadores.append(ind)
            if aviso:
                advertencias.append(aviso)

        if tipo_indicador in _INCLUDE_PRODUCCION:
            ind, aviso = self._calcular_produccion_promedio(id_activo, fecha_inicio, fecha_fin, ahora)
            indicadores.append(ind)
            if aviso:
                advertencias.append(aviso)

        if tipo_indicador in _INCLUDE_SANITARIO:
            ind_morb, aviso_morb = self._calcular_tasa_morbilidad(id_activo, tipo_activo, fecha_inicio, fecha_fin, ahora)
            ind_mort, aviso_mort = self._calcular_tasa_mortalidad(id_activo, tipo_activo, fecha_inicio, fecha_fin, ahora)
            indicadores.extend([ind_morb, ind_mort])
            if aviso_morb:
                advertencias.append(aviso_morb)
            if aviso_mort:
                advertencias.append(aviso_mort)

        if tipo_indicador in _INCLUDE_EFICIENCIA:
            indicadores.append(IndicadorZootecnico(
                tipo='conversion_alimenticia',
                unidad='kg_alimento/kg_ganancia',
                fecha_calculo=ahora,
                disponible=False,
                variables_usadas={},
            ))
            advertencias.append(
                'REQUIERE_M05: El indicador conversion_alimenticia requiere datos de consumo '
                'de alimento del módulo M05, que aún no está implementado.'
            )

        return ResultadoIndicadores(
            id_activo_biologico=id_activo,
            tipo_activo=tipo_activo,
            indicadores=indicadores,
            advertencias=advertencias,
        )

    def _calcular_ganancia_peso(
        self,
        id_activo: int,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        ahora: datetime,
    ) -> tuple[IndicadorZootecnico, Optional[str]]:
        rows = self.db.execute(
            text(
                'SELECT ec.valor_medicion, ea.fecha '
                'FROM modulo2.eventos_crecimeinto ec '
                'JOIN modulo2.eventos_activos ea ON ec.id_evento = ea.id_eventos '
                'WHERE ea.id_activo_biologico = :id AND lower(ec.tipo_medicion) = \'peso\' '
                'AND (:fi IS NULL OR ea.fecha::date >= :fi) '
                'AND (:ff IS NULL OR ea.fecha::date <= :ff) '
                'ORDER BY ea.fecha'
            ),
            {'id': id_activo, 'fi': fecha_inicio, 'ff': fecha_fin},
        ).fetchall()

        if len(rows) < 2:
            return (
                IndicadorZootecnico(
                    tipo='ganancia_peso',
                    unidad='kg/dia',
                    fecha_calculo=ahora,
                    disponible=False,
                    variables_usadas={'registros_disponibles': len(rows)},
                ),
                'DATOS_INSUFICIENTES: ganancia_peso requiere al menos 2 mediciones de peso.',
            )

        peso_inicial = Decimal(str(rows[0].valor_medicion))
        peso_final = Decimal(str(rows[-1].valor_medicion))
        fecha_primera = rows[0].fecha
        fecha_ultima = rows[-1].fecha
        dias = Decimal(str(max((fecha_ultima - fecha_primera).days, 1)))
        gpd = (peso_final - peso_inicial) / dias

        return (
            IndicadorZootecnico(
                tipo='ganancia_peso',
                valor=gpd.quantize(Decimal('0.0001')),
                unidad='kg/dia',
                periodo_inicio=fecha_primera.date() if hasattr(fecha_primera, 'date') else fecha_primera,
                periodo_fin=fecha_ultima.date() if hasattr(fecha_ultima, 'date') else fecha_ultima,
                fecha_calculo=ahora,
                disponible=True,
                variables_usadas={
                    'peso_inicial_kg': float(peso_inicial),
                    'peso_final_kg': float(peso_final),
                    'dias': int(dias),
                    'total_mediciones': len(rows),
                },
            ),
            None,
        )

    def _calcular_produccion_promedio(
        self,
        id_activo: int,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        ahora: datetime,
    ) -> tuple[IndicadorZootecnico, Optional[str]]:
        row = self.db.execute(
            text(
                'SELECT SUM(ep.cantidad) AS total, COUNT(*) AS n, '
                'MIN(ea.fecha) AS primera, MAX(ea.fecha) AS ultima, '
                'MAX(mp.unidad_medida) AS unidad '
                'FROM modulo2.eventos_productivos ep '
                'JOIN modulo2.eventos_activos ea ON ep.id_evento = ea.id_eventos '
                'LEFT JOIN modulo9.metricas_produccion mp ON mp.id_metrica_produccion = ep.id_metrica_produccion '
                'WHERE ea.id_activo_biologico = :id '
                'AND (:fi IS NULL OR ea.fecha::date >= :fi) '
                'AND (:ff IS NULL OR ea.fecha::date <= :ff)'
            ),
            {'id': id_activo, 'fi': fecha_inicio, 'ff': fecha_fin},
        ).fetchone()

        if not row or not row.total or int(row.n) == 0:
            return (
                IndicadorZootecnico(
                    tipo='produccion_promedio',
                    unidad='unidades/dia',
                    fecha_calculo=ahora,
                    disponible=False,
                    variables_usadas={'registros_disponibles': 0},
                ),
                'DATOS_INSUFICIENTES: no hay eventos productivos en el período solicitado.',
            )

        primera = row.primera
        ultima = row.ultima
        dias = max((ultima - primera).days, 1)
        try:
            total = Decimal(str(row.total))
            promedio = (total / Decimal(str(dias))).quantize(Decimal('0.0001'))
        except (InvalidOperation, ZeroDivisionError):
            promedio = None

        unidad = f'{row.unidad}/dia' if row.unidad else 'unidades/dia'
        return (
            IndicadorZootecnico(
                tipo='produccion_promedio',
                valor=promedio,
                unidad=unidad,
                periodo_inicio=primera.date() if hasattr(primera, 'date') else primera,
                periodo_fin=ultima.date() if hasattr(ultima, 'date') else ultima,
                fecha_calculo=ahora,
                disponible=promedio is not None,
                variables_usadas={
                    'total_producido': float(total),
                    'dias': dias,
                    'total_eventos': int(row.n),
                },
            ),
            None,
        )

    def _calcular_tasa_morbilidad(
        self,
        id_activo: int,
        tipo_activo: str,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        ahora: datetime,
    ) -> tuple[IndicadorZootecnico, Optional[str]]:
        if tipo_activo != 'POBLACIONAL':
            return (
                IndicadorZootecnico(
                    tipo='tasa_morbilidad',
                    unidad='%',
                    fecha_calculo=ahora,
                    disponible=False,
                    variables_usadas={},
                ),
                'NO_APLICA_INDIVIDUAL: tasa_morbilidad solo aplica a activos POBLACIONALES.',
            )

        row_pob = self.db.execute(
            text(
                'SELECT cantidad_inicial FROM modulo2.detalles_activos_biologicos_poblacionales '
                'WHERE id_activo_biologico = :id'
            ),
            {'id': id_activo},
        ).fetchone()

        cantidad_inicial = int(row_pob.cantidad_inicial) if row_pob else 0
        if cantidad_inicial == 0:
            return (
                IndicadorZootecnico(
                    tipo='tasa_morbilidad',
                    unidad='%',
                    fecha_calculo=ahora,
                    disponible=False,
                    variables_usadas={},
                ),
                'DATOS_INSUFICIENTES: tasa_morbilidad requiere cantidad_inicial > 0.',
            )

        row_san = self.db.execute(
            text(
                'SELECT COUNT(DISTINCT ea.id_eventos) AS n_eventos '
                'FROM modulo2.eventos_sanitarios es '
                'JOIN modulo2.eventos_activos ea ON es.id_evento = ea.id_eventos '
                'WHERE ea.id_activo_biologico = :id '
                'AND (:fi IS NULL OR ea.fecha::date >= :fi) '
                'AND (:ff IS NULL OR ea.fecha::date <= :ff)'
            ),
            {'id': id_activo, 'fi': fecha_inicio, 'ff': fecha_fin},
        ).fetchone()

        n_eventos = int(row_san.n_eventos) if row_san and row_san.n_eventos else 0
        tasa = Decimal(str(n_eventos * 100)) / Decimal(str(cantidad_inicial))

        return (
            IndicadorZootecnico(
                tipo='tasa_morbilidad',
                valor=tasa.quantize(Decimal('0.01')),
                unidad='%',
                fecha_calculo=ahora,
                disponible=True,
                variables_usadas={
                    'eventos_sanitarios': n_eventos,
                    'cantidad_inicial': cantidad_inicial,
                },
            ),
            None,
        )

    def _calcular_tasa_mortalidad(
        self,
        id_activo: int,
        tipo_activo: str,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        ahora: datetime,
    ) -> tuple[IndicadorZootecnico, Optional[str]]:
        if tipo_activo != 'POBLACIONAL':
            return (
                IndicadorZootecnico(
                    tipo='tasa_mortalidad',
                    unidad='%',
                    fecha_calculo=ahora,
                    disponible=False,
                    variables_usadas={},
                ),
                'NO_APLICA_INDIVIDUAL: tasa_mortalidad solo aplica a activos POBLACIONALES.',
            )

        row_pob = self.db.execute(
            text(
                'SELECT cantidad_inicial FROM modulo2.detalles_activos_biologicos_poblacionales '
                'WHERE id_activo_biologico = :id'
            ),
            {'id': id_activo},
        ).fetchone()

        cantidad_inicial = int(row_pob.cantidad_inicial) if row_pob else 0
        if cantidad_inicial == 0:
            return (
                IndicadorZootecnico(
                    tipo='tasa_mortalidad',
                    unidad='%',
                    fecha_calculo=ahora,
                    disponible=False,
                    variables_usadas={},
                ),
                'DATOS_INSUFICIENTES: tasa_mortalidad requiere cantidad_inicial > 0.',
            )

        row_baj = self.db.execute(
            text(
                'SELECT COALESCE(SUM(eb.cantidad_afectada), 0) AS total_bajas '
                'FROM modulo2.eventos_bajas eb '
                'JOIN modulo2.eventos_activos ea ON eb.id_evento = ea.id_eventos '
                'WHERE ea.id_activo_biologico = :id '
                'AND (:fi IS NULL OR ea.fecha::date >= :fi) '
                'AND (:ff IS NULL OR ea.fecha::date <= :ff)'
            ),
            {'id': id_activo, 'fi': fecha_inicio, 'ff': fecha_fin},
        ).fetchone()

        total_bajas = int(row_baj.total_bajas) if row_baj else 0
        tasa = Decimal(str(total_bajas * 100)) / Decimal(str(cantidad_inicial))

        return (
            IndicadorZootecnico(
                tipo='tasa_mortalidad',
                valor=tasa.quantize(Decimal('0.01')),
                unidad='%',
                fecha_calculo=ahora,
                disponible=True,
                variables_usadas={
                    'bajas': total_bajas,
                    'cantidad_inicial': cantidad_inicial,
                },
            ),
            None,
        )

    # ── RF-50: Datos consolidados para módulos externos ──────────────────────

    def obtener_datos_consolidados(
        self,
        id_activo: int,
        tipo_dato: str,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        pagina: int,
        page_size: int,
    ) -> DatosConsolidados:
        ahora = datetime.now(timezone.utc)

        row_base = self.db.execute(
            text(
                'SELECT ab.id_activo_biologico, ab.identificador, ab.tipo, '
                'e.nombre AS especie, est.nombre AS estado_actual, '
                'i.nombre AS infraestructura_asociada, '
                'fase.nombre AS fase_productiva_activa '
                'FROM modulo2.activos_biologicos ab '
                'JOIN modulo9.especies e ON e.id_especie = ab.id_especie '
                'JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = ab.id_estado '
                'JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura '
                'LEFT JOIN LATERAL ('
                '  SELECT cp.nombre FROM modulo2.gestiones_fases gf '
                '  JOIN modulo9.ciclos_productivos cp ON cp.id_ciclo_productivo = gf.id_ciclo_productiva '
                '  WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa IS TRUE '
                '  ORDER BY gf.id_gestion_fases DESC LIMIT 1'
                ') fase ON true '
                'WHERE ab.id_activo_biologico = :id'
            ),
            {'id': id_activo},
        ).fetchone()

        secciones = SeccionDatosConsolidados()

        if tipo_dato in ('eventos', 'todos'):
            secciones.historial_eventos = self._obtener_eventos(id_activo, fecha_inicio, fecha_fin)

        if tipo_dato in ('fases', 'todos'):
            secciones.historial_fases = self._obtener_fases(id_activo)

        if tipo_dato in ('estado', 'todos'):
            secciones.historico_estados = self._obtener_historico_estados(id_activo)

        if tipo_dato in ('metricas', 'todos'):
            secciones.metricas_actuales = self._obtener_metricas(id_activo)

        todos_registros = (
            secciones.historial_eventos
            + secciones.historial_fases
            + secciones.historico_estados
        )
        total = len(todos_registros)
        total_paginas = max(1, (total + page_size - 1) // page_size)
        secciones.total_registros = total
        secciones.pagina_actual = pagina
        secciones.total_paginas = total_paginas
        secciones.registros_por_pagina = page_size

        return DatosConsolidados(
            id_activo_biologico=row_base.id_activo_biologico if row_base else id_activo,
            identificador=row_base.identificador if row_base else None,
            tipo_activo=row_base.tipo if row_base else '',
            especie=row_base.especie if row_base else '',
            estado_actual=row_base.estado_actual if row_base else '',
            infraestructura_asociada=row_base.infraestructura_asociada if row_base else None,
            fase_productiva_activa=row_base.fase_productiva_activa if row_base else None,
            fecha_generacion=ahora,
            secciones=secciones,
        )

    def _obtener_eventos(
        self, id_activo: int, fecha_inicio: Optional[date], fecha_fin: Optional[date]
    ) -> list[dict]:
        rows = self.db.execute(
            text(
                'SELECT fecha_evento, categoria, detalle_1, detalle_2, observacion, usuario_responsable '
                'FROM modulo2.vw_rf46_historial_completo_activo '
                'WHERE id_activo_biologico = :id '
                'AND categoria NOT IN (\'ESTADO\', \'FASE_PRODUCTIVA\', \'INDICADOR\') '
                'AND (:fi IS NULL OR fecha_evento::date >= :fi) '
                'AND (:ff IS NULL OR fecha_evento::date <= :ff) '
                'ORDER BY fecha_evento DESC'
            ),
            {'id': id_activo, 'fi': fecha_inicio, 'ff': fecha_fin},
        ).fetchall()
        return [
            {
                'categoria': r.categoria,
                'fecha': r.fecha_evento.isoformat() if r.fecha_evento else None,
                'detalle_1': r.detalle_1,
                'detalle_2': r.detalle_2,
                'observacion': r.observacion,
                'usuario': r.usuario_responsable,
            }
            for r in rows
        ]

    def _obtener_fases(self, id_activo: int) -> list[dict]:
        rows = self.db.execute(
            text(
                'SELECT fecha_evento, detalle_1, detalle_2, observacion, usuario_responsable '
                'FROM modulo2.vw_rf46_historial_completo_activo '
                'WHERE id_activo_biologico = :id AND categoria = \'FASE_PRODUCTIVA\' '
                'ORDER BY fecha_evento DESC'
            ),
            {'id': id_activo},
        ).fetchall()
        return [
            {
                'categoria': 'FASE_PRODUCTIVA',
                'fecha': r.fecha_evento.isoformat() if r.fecha_evento else None,
                'nombre_fase': r.detalle_1,
                'estado': r.detalle_2,
                'observacion': r.observacion,
                'usuario': r.usuario_responsable,
            }
            for r in rows
        ]

    def _obtener_historico_estados(self, id_activo: int) -> list[dict]:
        rows = self.db.execute(
            text(
                'SELECT fecha_evento, detalle_1, detalle_2, observacion, usuario_responsable '
                'FROM modulo2.vw_rf46_historial_completo_activo '
                'WHERE id_activo_biologico = :id AND categoria = \'ESTADO\' '
                'ORDER BY fecha_evento DESC'
            ),
            {'id': id_activo},
        ).fetchall()
        return [
            {
                'categoria': 'ESTADO',
                'fecha': r.fecha_evento.isoformat() if r.fecha_evento else None,
                'estado_anterior': r.detalle_1,
                'estado_nuevo': r.detalle_2,
                'motivo': r.observacion,
                'usuario': r.usuario_responsable,
            }
            for r in rows
        ]

    def _obtener_metricas(self, id_activo: int) -> dict:
        row = self.db.execute(
            text(
                'SELECT peso_actual, unidad_peso, fecha_ultimo_peso, '
                'cantidad_actual, biomasa_total '
                'FROM modulo2.vw_rf47_ficha_integral_activo '
                'WHERE id_activo_biologico = :id'
            ),
            {'id': id_activo},
        ).fetchone()

        indicadores_rows = self.db.execute(
            text(
                'SELECT tipo_indicador, fecha_inicio, fecha_fin, paramtros_calculo '
                'FROM modulo2.vw_rf47_indicadores_zootecnicos_activo '
                'WHERE id_activo_biologico = :id '
                'ORDER BY fecha_inicio DESC LIMIT 10'
            ),
            {'id': id_activo},
        ).fetchall()

        return {
            'peso_actual': float(row.peso_actual) if row and row.peso_actual else None,
            'unidad_peso': row.unidad_peso if row else None,
            'fecha_ultimo_peso': row.fecha_ultimo_peso.isoformat() if row and row.fecha_ultimo_peso else None,
            'cantidad_actual': row.cantidad_actual if row else None,
            'biomasa_total': float(row.biomasa_total) if row and row.biomasa_total else None,
            'indicadores_historicos': [
                {
                    'tipo': r.tipo_indicador,
                    'fecha_inicio': r.fecha_inicio.isoformat() if r.fecha_inicio else None,
                    'fecha_fin': r.fecha_fin.isoformat() if r.fecha_fin else None,
                    'resultado': r.paramtros_calculo,
                }
                for r in indicadores_rows
            ],
        }
