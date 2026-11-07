# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-11-02 | Arekkazu | AJF-01 RF-46: historial con alertas IoT, cambios de riesgo, diagnósticos clínicos y contagio alto |
"""Implementación SQLAlchemy de ``TransferenciaRepository``: transferencias (RF-48) e
historial consolidado (RF-46).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import PaginaHistorial, RegistroHistorial, Transferencia
from src.biological_assets.domain.repositories.transferencia_repository import TransferenciaRepository
from src.biological_assets.infrastructure.models.movimiento_model import MovimientoModel
from src.shared.db_error_translator import raise_from_db_error
from src.shared.fechas import fecha_usuario


# AJF-01: el historial del activo solo unía M02. Se suman los eventos de M03/M04 que le
# importan a quien revisa el animal, sin inundarlo (una inferencia cada pocos minutos):
#   ALERTA_IOT          alertas del animal (siempre) y alertas ambientales CRÍTICAS del área
#                       donde estaba el animal en esa fecha (P-1, propuesta del plan).
#   PREDICCION          solo cuando cambia el nivel de riesgo respecto a la inferencia
#                       anterior del mismo animal, o cuando generó alerta.
#   DIAGNOSTICO_CLINICO retroalimentaciones clínicas vigentes (estado_registro ACTIVO).
#   CONTAGIO            cálculos de riesgo de contagio del activo (lote) en nivel ALTO (P-2).
# Una consulta por categoría, merge por fecha (mismo patrón que vw_rf46_*). Las tablas de
# M03/M04 tienen RLS por finca: el usuario solo ve lo de sus fincas.
CATEGORIAS_M03_M04 = frozenset({'ALERTA_IOT', 'PREDICCION', 'DIAGNOSTICO_CLINICO', 'CONTAGIO'})

_SQL_ALERTAS_ACTIVO = text("""
    SELECT a.id_alerta, a.tipo_alerta, a.severidad, a.estado_alerta, a.tipo_variable, a.valor, a.unidad,
           a.fecha_generacion, a.id_activo_biologico IS NOT NULL AS es_del_animal, i.nombre AS nombre_area
    FROM modulo3.alertas a
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = :id
    LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
    WHERE a.tipo_alerta <> 'TECNICA'
      AND (
        a.id_activo_biologico = :id
        OR (a.id_activo_biologico IS NULL AND a.severidad = 'CRITICO'
            AND a.id_infraestructura = COALESCE(
                (SELECT m.id_infraestructura_destino FROM modulo2.movimientos m
                  WHERE m.id_activo_biologico = :id AND m.fecha_transferencia <= a.fecha_generacion
                  ORDER BY m.fecha_transferencia DESC LIMIT 1),
                (SELECT m.id_infraestructura_origen FROM modulo2.movimientos m
                  WHERE m.id_activo_biologico = :id AND m.fecha_transferencia > a.fecha_generacion
                  ORDER BY m.fecha_transferencia ASC LIMIT 1),
                ab.id_infraestructura))
      )
""")

_SQL_PREDICCIONES_CAMBIO = text("""
    SELECT x.id_resultado_inferencia, x.fecha_inferencia, x.nivel_riesgo, x.nivel_anterior, x.tipo_modelo,
           x.confianza_global, x.tiene_alerta_generada, x.id_alerta_generada, x.modo_sombra, p.nombre AS nombre_patologia
    FROM (
        SELECT r.*, LAG(r.nivel_riesgo) OVER (ORDER BY r.fecha_inferencia, r.id_resultado_inferencia) AS nivel_anterior
        FROM modulo4.resultados_inferencia r
        WHERE r.id_activo_biologico = :id
    ) x
    LEFT JOIN modulo9.patologias p ON p.id_patologia = x.id_patologia
    WHERE x.nivel_anterior IS DISTINCT FROM x.nivel_riesgo OR x.tiene_alerta_generada
""")

_SQL_DIAGNOSTICOS = text("""
    SELECT rc.id_retroalimentacion, rc.fecha_retroalimentacion, rc.estado_retroalimentacion,
           rc.observaciones_clinicas, rc.fuente_diagnostico, rc.id_resultado_inferencia,
           (SELECT string_agg(p.nombre, ', ' ORDER BY p.nombre) FROM modulo9.patologias p
             WHERE p.id_patologia = ANY(rc.diagnosticos_reales)) AS diagnosticos,
           COALESCE(CONCAT_WS(' ', u.nombre, u.apellidos), 'Sin usuario') AS usuario
    FROM modulo4.retroalimentaciones_clinicas rc
    LEFT JOIN modulo1.usuarios u ON u.id_usuario = rc.id_usuario_veterinario
    WHERE rc.id_activo_biologico = :id AND rc.estado_registro = 'ACTIVO'
""")

_SQL_CONTAGIO_ALTO = text("""
    SELECT r.id_resultado_contagio, r.fecha_calculo, r.probabilidad_contagio, r.nivel_riesgo_contagio,
           r.id_alerta_generada
    FROM modulo4.resultados_riesgo_contagio r
    WHERE r.id_activo_biologico = :id AND r.nivel_riesgo_contagio = 2
""")

_NIVEL_RIESGO = {0: 'Normal', 1: 'Bajo', 2: 'Moderado', 3: 'Alto'}


def _numero(v) -> Optional[str]:
    return None if v is None else str(v)


class SqlAlchemyTransferenciaRepository(TransferenciaRepository):
    """Persiste movimientos y une eventos, estados, fases y movimientos en el historial
    paginado.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, transferencia: Transferencia) -> Transferencia:
        ahora = datetime.now(timezone.utc)
        try:
            orm = MovimientoModel(
                id_activo_biologico=transferencia.id_activo_biologico,
                id_infraestructura_origen=transferencia.id_infraestructura_origen,
                id_infraestructura_destino=transferencia.id_infraestructura_destino,
                fecha_transferencia=transferencia.fecha_transferencia,
                tipo='salida',
                id_usuario=transferencia.id_usuario,
                motivo_transferencia=transferencia.motivo_transferencia,
                fecha_registro=ahora,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return Transferencia(
            id_movimiento=orm.id_movimiento,
            id_activo_biologico=orm.id_activo_biologico,
            id_infraestructura_origen=orm.id_infraestructura_origen,
            id_infraestructura_destino=orm.id_infraestructura_destino,
            nombre_infra_origen=transferencia.nombre_infra_origen,
            nombre_infra_destino=transferencia.nombre_infra_destino,
            fecha_transferencia=orm.fecha_transferencia,
            motivo_transferencia=orm.motivo_transferencia or '',
            id_usuario=orm.id_usuario,
            fecha_registro=orm.fecha_registro,
        )

    def hay_transferencia_en_progreso(self, id_activo: int) -> bool:
        """Adquiere lock exclusivo sobre el activo para prevenir transferencias simultáneas.

        Usa SELECT FOR UPDATE NOWAIT: si otro transaction ya bloqueó el registro, lanza
        excepción inmediatamente (no espera). El caller interpreta eso como E-01.
        """
        try:
            self.db.execute(
                text(
                    'SELECT id_activo_biologico FROM modulo2.activos_biologicos '
                    'WHERE id_activo_biologico = :id FOR UPDATE NOWAIT'
                ),
                {'id': id_activo},
            )
            return False
        except Exception:
            return True

    def consultar_historial(
        self,
        id_activo: int,
        fecha_inicio: Optional[object] = None,
        fecha_fin: Optional[object] = None,
        categoria: Optional[str] = None,
        pagina: int = 1,
        page_size: int = 20,
    ) -> PaginaHistorial:
        registros: list[RegistroHistorial] = []

        categorias_a_consultar = {
            'CREACION', 'ESTADO', 'FASE_PRODUCTIVA', 'SANITARIO', 'CRECIMIENTO',
            'PRODUCTIVO', 'REPRODUCTIVO', 'INDICADOR', 'BAJA', 'TRANSFERENCIA', 'INGRESO',
            *CATEGORIAS_M03_M04,
        }
        if categoria:
            cat_upper = categoria.upper()
            # El RF usa FASE, el código usa FASE_PRODUCTIVA
            if cat_upper == 'FASE':
                cat_upper = 'FASE_PRODUCTIVA'
            categorias_a_consultar = {cat_upper}

        # ── CREACION (RF-33: snapshot inicial — Evento 0)
        if 'CREACION' in categorias_a_consultar:
            rows = self.db.execute(
                text(
                    'SELECT ha.fecha_evento, ha.json_snapshot, '
                    '  COALESCE(CONCAT_WS(\' \', u.nombre, u.apellidos), \'Sin usuario\') AS usuario '
                    'FROM modulo2.historial_activos ha '
                    'LEFT JOIN modulo1.usuarios u ON u.id_usuario = ha.id_usuario '
                    'WHERE ha.id_activo_biologico = :id AND ha.tipo_evento = \'CREACION\''
                ),
                {'id': id_activo},
            ).fetchall()
            for r in rows:
                registros.append(RegistroHistorial(
                    categoria='CREACION',
                    fecha_evento=r.fecha_evento,
                    descripcion='Registro inicial del activo biológico',
                    detalle_especifico=r.json_snapshot,
                    usuario_responsable=r.usuario,
                    modulo_origen='modulo2',
                ))

        # ── Historial consolidado (vista cubre ESTADO, FASE, SANITARIO, CRECIMIENTO, PRODUCTIVO, REPRODUCTIVO, INDICADOR, INGRESO)
        vista_cats = categorias_a_consultar - {'BAJA', 'TRANSFERENCIA', 'CREACION'}
        if vista_cats:
            rows = self.db.execute(
                text(
                    'SELECT fecha_evento, categoria, detalle_1, detalle_2, observacion, usuario_responsable '
                    'FROM modulo2.vw_rf46_historial_completo_activo '
                    'WHERE id_activo_biologico = :id '
                    'AND categoria = ANY(:cats)'
                ),
                {'id': id_activo, 'cats': list(vista_cats)},
            ).fetchall()
            for r in rows:
                registros.append(RegistroHistorial(
                    categoria=r.categoria,
                    fecha_evento=r.fecha_evento,
                    descripcion=r.observacion or '',
                    detalle_especifico={'detalle_1': r.detalle_1, 'detalle_2': r.detalle_2},
                    usuario_responsable=r.usuario_responsable or 'Sin usuario',
                    modulo_origen='modulo2',
                ))

        # ── BAJA
        if 'BAJA' in categorias_a_consultar:
            rows = self.db.execute(
                text(
                    'SELECT fecha, tipo, cantidad_afectada, detalles, usuario, modulo_origen '
                    'FROM modulo2.vw_rf46_eventos_bajas '
                    'WHERE id_activo_biologico = :id'
                ),
                {'id': id_activo},
            ).fetchall()
            for r in rows:
                registros.append(RegistroHistorial(
                    categoria='BAJA',
                    fecha_evento=r.fecha,
                    descripcion=r.detalles or '',
                    detalle_especifico={'tipo': r.tipo, 'cantidad_afectada': r.cantidad_afectada},
                    usuario_responsable=r.usuario or 'Sin usuario',
                    modulo_origen=r.modulo_origen or 'modulo2',
                ))

        # ── TRANSFERENCIA
        if 'TRANSFERENCIA' in categorias_a_consultar:
            rows = self.db.execute(
                text(
                    'SELECT m.fecha_transferencia, m.motivo_transferencia, '
                    '  io.nombre AS infra_origen, ides.nombre AS infra_destino, '
                    '  COALESCE(CONCAT_WS(\' \', u.nombre, u.apellidos), \'Sin usuario\') AS usuario '
                    'FROM modulo2.movimientos m '
                    'JOIN modulo9.infraestructuras io ON io.id_infraestructura = m.id_infraestructura_origen '
                    'JOIN modulo9.infraestructuras ides ON ides.id_infraestructura = m.id_infraestructura_destino '
                    'LEFT JOIN modulo1.usuarios u ON u.id_usuario = m.id_usuario '
                    'WHERE m.id_activo_biologico = :id'
                ),
                {'id': id_activo},
            ).fetchall()
            for r in rows:
                registros.append(RegistroHistorial(
                    categoria='TRANSFERENCIA',
                    fecha_evento=r.fecha_transferencia,
                    descripcion=r.motivo_transferencia or '',
                    detalle_especifico={
                        'infraestructura_origen': r.infra_origen,
                        'infraestructura_destino': r.infra_destino,
                    },
                    usuario_responsable=r.usuario,
                    modulo_origen='modulo2',
                ))

        # ── AJF-01: eventos relevantes de telemetría (M03) y predicción (M04)
        registros.extend(self._eventos_m03_m04(id_activo, categorias_a_consultar))

        # ── Filtros de fecha: días calendario del usuario, no del UTC
        if fecha_inicio:
            registros = [r for r in registros if fecha_usuario(r.fecha_evento) >= fecha_inicio]
        if fecha_fin:
            registros = [r for r in registros if fecha_usuario(r.fecha_evento) <= fecha_fin]

        # ── Ordenar cronológicamente ascendente
        registros.sort(key=lambda r: r.fecha_evento)

        total = len(registros)
        total_paginas = max(1, (total + page_size - 1) // page_size)
        inicio = (pagina - 1) * page_size
        pagina_registros = registros[inicio: inicio + page_size]

        return PaginaHistorial(
            registros=pagina_registros,
            total_registros=total,
            pagina_actual=pagina,
            total_paginas=total_paginas,
            registros_por_pagina=page_size,
        )

    def _eventos_m03_m04(self, id_activo: int, categorias: set) -> list[RegistroHistorial]:
        """AJF-01: alertas IoT, cambios de riesgo, diagnósticos clínicos y contagio alto del activo."""
        registros: list[RegistroHistorial] = []
        if 'ALERTA_IOT' in categorias:
            for r in self.db.execute(_SQL_ALERTAS_ACTIVO, {'id': id_activo}).fetchall():
                valor = f' · {r.valor} {r.unidad or ""}'.rstrip() if r.valor is not None else ''
                registros.append(RegistroHistorial(
                    categoria='ALERTA_IOT',
                    fecha_evento=r.fecha_generacion,
                    descripcion=(f'Alerta {r.tipo_alerta}{valor}' if r.es_del_animal
                                 else f'Alerta ambiental crítica en {r.nombre_area or "su área"}: {r.tipo_alerta}'),
                    detalle_especifico={
                        'id_alerta': r.id_alerta, 'tipo_alerta': r.tipo_alerta, 'severidad': r.severidad,
                        'estado_alerta': r.estado_alerta, 'tipo_variable': r.tipo_variable,
                        'valor': _numero(r.valor), 'unidad': r.unidad,
                        'ambito': 'ANIMAL' if r.es_del_animal else 'AREA', 'nombre_area': r.nombre_area,
                    },
                    usuario_responsable='Sistema',
                    modulo_origen='modulo3',
                ))
        if 'PREDICCION' in categorias:
            for r in self.db.execute(_SQL_PREDICCIONES_CAMBIO, {'id': id_activo}).fetchall():
                nivel = _NIVEL_RIESGO.get(r.nivel_riesgo, str(r.nivel_riesgo))
                anterior = _NIVEL_RIESGO.get(r.nivel_anterior) if r.nivel_anterior is not None else None
                descripcion = (f'Riesgo pasó de {anterior} a {nivel}' if anterior and r.nivel_anterior != r.nivel_riesgo
                               else f'Predicción de riesgo {nivel}')
                registros.append(RegistroHistorial(
                    categoria='PREDICCION',
                    fecha_evento=r.fecha_inferencia,
                    descripcion=descripcion + (' (de prueba, no generó alerta)' if r.modo_sombra else ''),
                    detalle_especifico={
                        'id_resultado_inferencia': str(r.id_resultado_inferencia), 'tipo_modelo': r.tipo_modelo,
                        'nivel_riesgo': r.nivel_riesgo, 'nivel_anterior': r.nivel_anterior,
                        'confianza_global': _numero(r.confianza_global), 'nombre_patologia': r.nombre_patologia,
                        'tiene_alerta_generada': r.tiene_alerta_generada, 'id_alerta_generada': r.id_alerta_generada,
                        'modo_sombra': r.modo_sombra,
                    },
                    usuario_responsable='Motor de IA',
                    modulo_origen='modulo4',
                ))
        if 'DIAGNOSTICO_CLINICO' in categorias:
            for r in self.db.execute(_SQL_DIAGNOSTICOS, {'id': id_activo}).fetchall():
                registros.append(RegistroHistorial(
                    categoria='DIAGNOSTICO_CLINICO',
                    fecha_evento=r.fecha_retroalimentacion,
                    descripcion=f'Diagnóstico clínico: {r.diagnosticos or r.estado_retroalimentacion}',
                    detalle_especifico={
                        'id_retroalimentacion': str(r.id_retroalimentacion), 'estado': r.estado_retroalimentacion,
                        'diagnosticos': r.diagnosticos, 'fuente_diagnostico': r.fuente_diagnostico,
                        'observaciones': r.observaciones_clinicas,
                        'id_resultado_inferencia': str(r.id_resultado_inferencia) if r.id_resultado_inferencia else None,
                    },
                    usuario_responsable=r.usuario,
                    modulo_origen='modulo4',
                ))
        if 'CONTAGIO' in categorias:
            for r in self.db.execute(_SQL_CONTAGIO_ALTO, {'id': id_activo}).fetchall():
                registros.append(RegistroHistorial(
                    categoria='CONTAGIO',
                    fecha_evento=r.fecha_calculo,
                    descripcion=f'Riesgo de contagio alto ({round(float(r.probabilidad_contagio) * 100)} %)',
                    detalle_especifico={
                        'id_resultado_contagio': r.id_resultado_contagio,
                        'probabilidad_contagio': _numero(r.probabilidad_contagio),
                        'id_alerta_generada': r.id_alerta_generada,
                    },
                    usuario_responsable='Motor de IA',
                    modulo_origen='modulo4',
                ))
        return registros
