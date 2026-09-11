from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import PaginaHistorial, RegistroHistorial, Transferencia
from src.biological_assets.domain.repositories.transferencia_repository import TransferenciaRepository
from src.biological_assets.infrastructure.models.movimiento_model import MovimientoModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyTransferenciaRepository(TransferenciaRepository):

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
            'ESTADO', 'FASE_PRODUCTIVA', 'SANITARIO', 'CRECIMIENTO',
            'PRODUCTIVO', 'REPRODUCTIVO', 'INDICADOR', 'BAJA', 'TRANSFERENCIA',
        }
        if categoria:
            cat_upper = categoria.upper()
            # El RF usa FASE, el código usa FASE_PRODUCTIVA
            if cat_upper == 'FASE':
                cat_upper = 'FASE_PRODUCTIVA'
            categorias_a_consultar = {cat_upper}

        # ── Historial consolidado (vista cubre ESTADO, FASE, SANITARIO, CRECIMIENTO, PRODUCTIVO, REPRODUCTIVO, INDICADOR)
        vista_cats = categorias_a_consultar - {'BAJA', 'TRANSFERENCIA'}
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

        # ── Filtros de fecha
        if fecha_inicio:
            registros = [r for r in registros if r.fecha_evento.date() >= fecha_inicio]
        if fecha_fin:
            registros = [r for r in registros if r.fecha_evento.date() <= fecha_fin]

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
