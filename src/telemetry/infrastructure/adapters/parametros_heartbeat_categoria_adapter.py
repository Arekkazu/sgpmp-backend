# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-04 RF-60: lee parámetros de heartbeat y ventanas de visión sin inventar valores |
from __future__ import annotations

from sqlalchemy import text

from src.configuration.domain.entities.parametros_heartbeat import (
    COBERTURA, DURACION, INACTIVIDAD, INTERVALO_CAMARA, INTERVALOS_TIPO, MARGEN, VENTANAS,
)
from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.parametros_heartbeat_categoria import ConfiguracionHeartbeatLeida, VentanaObservada
from src.telemetry.domain.repositories.parametros_heartbeat_categoria_port import ParametrosHeartbeatCategoriaPort
from decimal import Decimal, InvalidOperation


def _entero(parametros, nombre):
    p = parametros.get(nombre)
    try:
        return int(p.valor) if p is not None and p.valor is not None else None
    except (TypeError, ValueError):
        return None


def _decimal(parametros, nombre):
    p = parametros.get(nombre)
    try:
        return Decimal(str(p.valor)) if p is not None and p.valor is not None else None
    except (InvalidOperation, ValueError):
        return None


class ParametrosHeartbeatCategoriaAdapter(ParametrosHeartbeatCategoriaPort):
    """A diferencia de ``ParametrosHeartbeatMLOpsAdapter`` (que responde 503 si falta algo,
    porque decide estados), esta lectura es para mostrar: lo ausente viaja como None."""

    def __init__(self, db) -> None:
        self.db = db
        self._parametros = SqlAlchemyParametrosMLOpsRepository(db)
        self._configuracion = SqlAlchemyConfiguracionGlobalRepository(db)

    def leer_configuracion(self) -> ConfiguracionHeartbeatLeida:
        valores = self._parametros.obtener((INTERVALOS_TIPO, INTERVALO_CAMARA, MARGEN, INACTIVIDAD))
        crudo = valores.get(INTERVALOS_TIPO)
        intervalos = {}
        if crudo is not None and isinstance(crudo.valor, dict):
            intervalos = {str(k): int(v) for k, v in crudo.valor.items() if isinstance(v, int) and v > 0}
        configuracion = self._configuracion.obtener_activo()
        try:
            categorias = tuple(c for (c,) in self.db.execute(text(
                'SELECT DISTINCT categoria::text FROM modulo9.tipos_dispositivo_iot WHERE categoria IS NOT NULL')).all())
        except Exception as exc:
            raise_from_db_error(exc)
        return ConfiguracionHeartbeatLeida(
            intervalos_por_tipo=intervalos,
            intervalo_camara_seg=_entero(valores, INTERVALO_CAMARA),
            frecuencia_muestreo_seg=configuracion.frecuencia_muestreo.valor * 60 if configuracion else None,
            margen_tolerancia_seg=_entero(valores, MARGEN),
            inactividad_extendida_seg=_entero(valores, INACTIVIDAD),
            categorias=categorias,
        )

    def parametros_ventanas(self):
        valores = self._parametros.obtener((VENTANAS, COBERTURA, DURACION))
        return _entero(valores, VENTANAS), _decimal(valores, COBERTURA), _entero(valores, DURACION)

    def categoria_dispositivo(self, id_dispositivo_iot, ids_fincas):
        try:
            fila = self.db.execute(text('''
                SELECT t.categoria::text
                FROM modulo9.dispositivos_iot d
                JOIN modulo9.tipos_dispositivo_iot t ON t.id_tipo_dispositivo = d.id_tipo_dispositivo
                JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
                WHERE d.id_dispositivo_iot = :id
                  AND (CAST(:fincas AS int[]) IS NULL OR i.id_finca = ANY(CAST(:fincas AS int[])))
            '''), {'id': id_dispositivo_iot, 'fincas': ids_fincas}).first()
        except Exception as exc:
            raise_from_db_error(exc)
        return fila[0] if fila else None

    def ventanas_recientes(self, id_dispositivo_iot, cantidad):
        try:
            filas = self.db.execute(text('''
                SELECT id_observacion_vision, fecha_inicio_ventana, fecha_observacion, cobertura_ventana,
                       n_individuos_observados
                FROM modulo3.observaciones_vision
                WHERE id_dispositivo_iot = :id
                ORDER BY fecha_observacion DESC, id_observacion_vision DESC
                LIMIT :cantidad
            '''), {'id': id_dispositivo_iot, 'cantidad': cantidad}).all()
        except Exception as exc:
            raise_from_db_error(exc)
        return [VentanaObservada(*f) for f in filas]
