"""Propagar una regla compuesta a los Gateway Edge (DEV-08, RF-55 Restricción 4, RF-57 E14/E15).

Mismo patrón que los umbrales de RF-17 (``sincronizar_umbral_edge``): se
resuelven los Gateway Edge de las áreas de la finca y especie de la regla, el
broker le envía la regla a cada uno con ``origen: "regla_compuesta"`` (BRK-05,
``tipo_comando = REGLA_COMPUESTA``) y espera su ``ACK_REGLA``. El veredicto de
cada Gateway queda en ``modulo3.sincronizaciones_reglas_edge``.

El Edge guarda la regla junto a sus umbrales y la evalúa con prevalencia sobre
la regla simple (RF-57 E14/E15). ``version_regla`` (la sube el trigger
``trg_aux_02_version_regla_alerta``) le deja descartar una versión vieja que
llegue tarde, y ``es_activa = False`` le pide retirarla.

Hoy no hay CRUD de reglas: las reglas se cargan por SQL, así que la
propagación se dispara con ``POST /iot/reglas-alertas/{id}/sincronizar-edge``.
Cuando exista el CRUD, su caso de uso debe llamar este después de su commit.

Consolidación (un estado por regla, además del de cada Gateway):

| Resultados por Gateway                  | Estado     |
|-----------------------------------------|------------|
| todos APLICADA                          | APLICADA   |
| alguno NO_CONF                          | NO_CONF    |
| ninguno falló, alguno PENDIENTE         | PENDIENTE  |
| la regla no tiene Gateway Edge destino  | PENDIENTE  |

A diferencia de RF-17, un Gateway sin confirmar no es un 500: el resultado es
lo que se pidió consultar, y queda por nodo para reintentar.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError, NotFoundError
from src.telemetry.domain.entities.alerta import ReglaAlerta
from src.telemetry.domain.entities.sincronizacion_regla_edge import (
    ESTADO_APLICADA,
    ESTADO_NO_CONF,
    ESTADO_PENDIENTE,
    ResultadoSincronizacionRegla,
    SincronizacionReglaEdge,
)
from src.telemetry.domain.repositories.regla_alerta_repository import ReglaAlertaRepository
from src.telemetry.domain.repositories.regla_compuesta_edge_port import ReglaCompuestaEdgePort
from src.telemetry.domain.repositories.sincronizacion_regla_edge_repository import (
    SincronizacionReglaEdgeRepository,
)

MOTIVO_SIN_GATEWAY_EDGE = (
    "Ningún Gateway Edge activo atiende las áreas de la finca y especie de esta regla. "
    "Se propagará cuando se vuelva a sincronizar con un Gateway asignado."
)


def payload_regla_compuesta(regla: ReglaAlerta) -> dict:
    """Cuerpo del comando ``origen: "regla_compuesta"`` del broker (sin ``origen``/``serial``)."""
    return {
        "id_regla_alerta": regla.id_regla_alertas,
        "version_regla": regla.version_regla,
        "es_activa": regla.es_activa,
        "regla": {
            "nombre": regla.nombre,
            "descripcion": regla.descripcion,
            "tipo_sensor": regla.tipo_sensor,
            "categoria_variable": regla.categoria_variable,
            "umbral_min": _texto(regla.umbral_min),
            "umbral_max": _texto(regla.umbral_max),
            "umbrales_severidad": regla.umbrales_severidad,
            "ventana_confirmacion_min": _texto(regla.ventana_confirmacion_min),
            "lectura_confirmacion_max": _texto(regla.lectura_confirmacion_max),
            "mensaje": regla.mensaje,
            "id_finca": regla.id_finca,
            "id_especie": regla.id_especie,
            # RF-57 E14/E15: ante la misma lectura, la compuesta gana a la simple.
            "prevalece_sobre_regla_simple": True,
        },
    }


def _texto(valor: Optional[Decimal]) -> Optional[str]:
    # Igual que el payload de umbrales: el Decimal viaja como texto, sin perder precisión.
    return str(valor) if valor is not None else None


def consolidar(nodos: list[SincronizacionReglaEdge]) -> tuple[str, str]:
    if not nodos:
        return ESTADO_PENDIENTE, MOTIVO_SIN_GATEWAY_EDGE
    estados = {n.estado_sincronizacion for n in nodos}
    if ESTADO_NO_CONF in estados:
        return ESTADO_NO_CONF, _detalle(nodos, ESTADO_NO_CONF)
    if ESTADO_PENDIENTE in estados:
        return ESTADO_PENDIENTE, _detalle(nodos, ESTADO_PENDIENTE)
    return ESTADO_APLICADA, f"Confirmada por {len(nodos)} Gateway Edge."


def _detalle(nodos: list[SincronizacionReglaEdge], estado: str) -> str:
    return " | ".join(f"{n.serial}: {n.mensaje}" for n in nodos if n.estado_sincronizacion == estado)


class SincronizarReglaEdgeUseCase:

    def __init__(
        self,
        db: Session,
        regla_repo: ReglaAlertaRepository,
        sincronizacion_repo: SincronizacionReglaEdgeRepository,
        edge_port: ReglaCompuestaEdgePort,
    ) -> None:
        self.db = db
        self.regla_repo = regla_repo
        self.sincronizacion_repo = sincronizacion_repo
        self.edge_port = edge_port

    def execute(self, id_regla_alertas: int, id_usuario: Optional[int]) -> ResultadoSincronizacionRegla:
        regla = self.regla_repo.obtener_por_id(id_regla_alertas)
        if regla is None:
            raise NotFoundError(code="REGLA_ALERTA_NO_ENCONTRADA", message="La regla de alerta no existe.")
        if not regla.es_regla_compuesta:
            raise BusinessRuleError(
                code="REGLA_NO_COMPUESTA",
                message="Solo las reglas compuestas se propagan al Gateway Edge con REGLA_COMPUESTA.",
            )
        if not regla.tiene_ejecutar_edge:
            raise BusinessRuleError(
                code="REGLA_SIN_EJECUCION_EDGE",
                message="La regla no está marcada para ejecutarse en el Gateway Edge (tiene_ejecutar_edge).",
            )

        gateways = self.sincronizacion_repo.listar_gateways_destino(id_regla_alertas)
        nodos: list[SincronizacionReglaEdge] = []
        if gateways:
            resultados = self.edge_port.propagar_regla(
                [g.serial for g in gateways], payload_regla_compuesta(regla)
            )
            ahora = datetime.now(timezone.utc)
            try:
                for gateway in gateways:
                    resultado = resultados[gateway.serial]
                    nodos.append(
                        self.sincronizacion_repo.registrar_intento(
                            id_regla_alertas=id_regla_alertas,
                            gateway=gateway,
                            version_regla=regla.version_regla,
                            estado_sincronizacion=resultado.estado_persistible(),
                            mensaje=resultado.mensaje,
                            fecha_intento=ahora,
                            id_usuario=id_usuario,
                        )
                    )
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

        estado, mensaje = consolidar(nodos)
        return ResultadoSincronizacionRegla(
            id_regla_alertas=id_regla_alertas,
            version_regla=regla.version_regla,
            estado=estado,
            mensaje=mensaje,
            nodos=nodos,
        )
