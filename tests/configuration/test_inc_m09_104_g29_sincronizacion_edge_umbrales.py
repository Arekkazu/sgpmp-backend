"""[INC-M09-104-G29][RF-17] TC-M09-62/TC-M09-63 — la creación/edición de un
umbral ambiental terminaba en persistencia + auditoría, sin ningún intento de
propagarlo hacia el Nodo Edge ni forma de saber si esa propagación ocurrió.

No hay ninguna relación ya modelada en el sistema de (id_especie,
id_variable_ambiental) hacia dispositivos/sensores concretos (M03 tampoco
consume umbrales todavía), así que se registra un único estado de
sincronización lógico por umbral -- no uno por dispositivo destino. El
contrato real de publicación hacia el broker (topic, payload, ACK) queda
pendiente de definición por el equipo de IoT; mientras tanto,
EdgeSincronizacionStubAdapter degrada siempre a PENDIENTE, nunca lanza y
nunca bloquea el flujo de negocio -- mismo espíritu que MqttHttpAdapter
(RF-23) cuando el broker real no está disponible.

RF-17 (flujo alterno "Error de sincronización con el Nodo Edge") exige que,
si la propagación no queda confirmada como APLICADA, el sistema marque la
configuración como "Pendiente de Sincronización" (ya persistida) y responda
HTTP 500 con el mensaje del contrato -- a diferencia de ConfiguracionRemota
(RF-23), que sí tolera el broker no disponible como resultado válido. Se
respeta la redacción literal del RF: el 500 llega después de que el umbral
y su estado de sincronización ya quedaron confirmados en base de datos.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.configuration.application.use_cases.umbrales.editar_umbral_use_case import EditarUmbralUseCase
from src.configuration.application.use_cases.umbrales.registrar_umbral_use_case import RegistrarUmbralUseCase
from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental
from src.configuration.domain.entities.variable_ambiental import VariableAmbiental
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt
from src.configuration.infrastructure.adapters.edge_sincronizacion_stub_adapter import EdgeSincronizacionStubAdapter
from src.configuration.infrastructure.dto.editar_umbral_dto import EditarUmbralDTO
from src.configuration.infrastructure.dto.nivel_dto import NivelDTO
from src.configuration.infrastructure.dto.registrar_umbral_dto import RegistrarUmbralDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import InfrastructureError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class UmbralRepoFake:
    def __init__(self, existente: UmbralAmbiental | None = None) -> None:
        self.existente = existente
        self.guardado: UmbralAmbiental | None = None
        self.actualizado: UmbralAmbiental | None = None
        self.estados_sincronizacion_persistidos: list[UmbralAmbiental] = []

    def obtener_por_especie_y_variable(self, id_especie, id_variable_ambiental):
        return None

    def obtener_por_id(self, id_umbral_ambiental):
        return self.existente

    def guardar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        umbral.id_umbral_ambiental = 1
        self.guardado = umbral
        return umbral

    def actualizar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        self.actualizado = umbral
        return umbral

    def actualizar_estado_sincronizacion(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        self.estados_sincronizacion_persistidos.append(umbral)
        return umbral


class EdgePortFake:
    def __init__(self, resultado: ResultadoEnvioMqtt) -> None:
        self.resultado = resultado
        self.llamadas: list[tuple[int, int, dict]] = []

    def propagar_umbral(self, id_especie: int, id_variable_ambiental: int, payload: dict) -> ResultadoEnvioMqtt:
        self.llamadas.append((id_especie, id_variable_ambiental, payload))
        return self.resultado


class AuditoriaRepoFake:
    def registrar(self, **kwargs) -> None:
        pass


class EspecieRepoFake:
    def obtener_por_id(self, _id):
        return SimpleNamespace(es_activo=True)


class VariableRepoFake:
    def obtener_por_id(self, id_variable_ambiental):
        return VariableAmbiental(
            id_variable_ambiental=id_variable_ambiental,
            nombre='Temperatura',
            unidad='°C',
            valor_fisico_min=Decimal('-10'),
            valor_fisico_max=Decimal('50'),
            es_activo=True,
        )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


def _niveles_dto() -> list[NivelDTO]:
    return [
        NivelDTO(nivel='normal', limite_inferior=Decimal('20'), limite_superior=Decimal('30')),
        NivelDTO(nivel='precaucion', limite_inferior=Decimal('30'), limite_superior=Decimal('35')),
        NivelDTO(nivel='critico', limite_inferior=Decimal('35'), limite_superior=Decimal('40')),
    ]


def _registrar_dto() -> RegistrarUmbralDTO:
    return RegistrarUmbralDTO(
        id_especie=1,
        id_variable_ambiental=1,
        valor_min=Decimal('20'),
        valor_max=Decimal('40'),
        niveles=_niveles_dto(),
    )


def _umbral_existente() -> UmbralAmbiental:
    from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental
    from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta

    return UmbralAmbiental(
        id_umbral_ambiental=1,
        id_especie=1,
        id_variable_ambiental=1,
        unidad_medida='°C',
        valor_min=Decimal('20'),
        valor_max=Decimal('40'),
        es_activo=True,
        niveles=[
            NivelAlertaAmbiental(nivel=NivelAlerta.normal, limite_inferior=Decimal('20'), limite_superior=Decimal('30')),
            NivelAlertaAmbiental(nivel=NivelAlerta.precaucion, limite_inferior=Decimal('30'), limite_superior=Decimal('35')),
            NivelAlertaAmbiental(nivel=NivelAlerta.critico, limite_inferior=Decimal('35'), limite_superior=Decimal('40')),
        ],
        fecha_actualizacion=None,
    )


class TestRegistrarUmbralPropagacionEdge:
    def _uc(self, edge_port, umbral_repo=None):
        return RegistrarUmbralUseCase(
            db=DbFake(),
            umbral_repo=umbral_repo or UmbralRepoFake(),
            especie_repo=EspecieRepoFake(),
            variable_repo=VariableRepoFake(),
            auditoria_repo=AuditoriaRepoFake(),
            edge_port=edge_port,
        )

    def test_llama_al_edge_port_con_el_payload_del_umbral_creado(self) -> None:
        edge_port = EdgePortFake(ResultadoEnvioMqtt(estado='APLICADA', mensaje='ok'))
        uc = self._uc(edge_port)

        uc.execute(_registrar_dto(), _usuario())

        assert len(edge_port.llamadas) == 1
        id_especie, id_variable, payload = edge_port.llamadas[0]
        assert id_especie == 1
        assert id_variable == 1
        assert payload['valor_min'] == '20'
        assert payload['valor_max'] == '40'
        assert len(payload['niveles']) == 3

    def test_estado_pendiente_se_persiste_y_luego_responde_500(self) -> None:
        edge_port = EdgePortFake(ResultadoEnvioMqtt(estado='PENDIENTE', mensaje='broker no disponible'))
        repo = UmbralRepoFake()
        uc = self._uc(edge_port, repo)

        with pytest.raises(InfrastructureError) as exc_info:
            uc.execute(_registrar_dto(), _usuario())

        assert exc_info.value.code == 'FALLO_SINCRONIZACION_EDGE'
        assert 'nodos Edge' in exc_info.value.message
        persistido = repo.estados_sincronizacion_persistidos[0]
        assert persistido.estado_sincronizacion == 'PENDIENTE'
        assert persistido.motivo_fallo_sincronizacion == 'broker no disponible'
        assert len(repo.estados_sincronizacion_persistidos) == 1

    def test_estado_aplicada_marca_fecha_de_sincronizacion(self) -> None:
        edge_port = EdgePortFake(ResultadoEnvioMqtt(estado='APLICADA', mensaje='ok'))
        uc = self._uc(edge_port)

        resultado = uc.execute(_registrar_dto(), _usuario())

        assert resultado.estado_sincronizacion == 'APLICADA'
        assert resultado.fecha_ultima_sincronizacion is not None
        assert resultado.motivo_fallo_sincronizacion is None

    def test_estado_no_conf_produce_500_tras_persistir(self) -> None:
        """RF-17 exige HTTP 500 cuando la propagación no queda confirmada --
        el umbral y su estado 'NO_CONF' ya quedaron guardados, pero la
        respuesta al cliente debe reflejar que el Edge no confirmó."""
        edge_port = EdgePortFake(ResultadoEnvioMqtt(estado='NO_CONF', mensaje='sin ACK a tiempo'))
        repo = UmbralRepoFake()
        uc = self._uc(edge_port, repo)

        with pytest.raises(InfrastructureError):
            uc.execute(_registrar_dto(), _usuario())

        persistido = repo.estados_sincronizacion_persistidos[0]
        assert persistido.estado_sincronizacion == 'NO_CONF'
        assert persistido.motivo_fallo_sincronizacion == 'sin ACK a tiempo'

    def test_el_umbral_ya_quedo_guardado_antes_de_responder_500(self) -> None:
        """El guardado del umbral (primer commit) y el registro del estado de
        sincronización (segundo commit) ocurren ambos antes de que se lance
        el 500 -- el umbral nunca se pierde aunque la respuesta HTTP sea de
        error."""
        edge_port = EdgePortFake(ResultadoEnvioMqtt(estado='PENDIENTE', mensaje='x'))
        repo = UmbralRepoFake()
        db = DbFake()
        uc = RegistrarUmbralUseCase(
            db=db,
            umbral_repo=repo,
            especie_repo=EspecieRepoFake(),
            variable_repo=VariableRepoFake(),
            auditoria_repo=AuditoriaRepoFake(),
            edge_port=edge_port,
        )

        with pytest.raises(InfrastructureError):
            uc.execute(_registrar_dto(), _usuario())

        assert repo.guardado is not None
        assert db.commits == 2  # guardado + actualizar_estado_sincronizacion
        assert db.rollbacks == 0


class TestEditarUmbralPropagacionEdge:
    def _uc(self, edge_port, repo):
        return EditarUmbralUseCase(
            db=DbFake(),
            umbral_repo=repo,
            variable_repo=VariableRepoFake(),
            auditoria_repo=AuditoriaRepoFake(),
            edge_port=edge_port,
        )

    def test_reenvia_el_umbral_editado_al_edge_port(self) -> None:
        existente = _umbral_existente()
        repo = UmbralRepoFake(existente=existente)
        edge_port = EdgePortFake(ResultadoEnvioMqtt(estado='PENDIENTE', mensaje='pendiente'))
        uc = self._uc(edge_port, repo)

        dto = EditarUmbralDTO(
            valor_min=Decimal('15'),
            valor_max=Decimal('45'),
            niveles=[
                NivelDTO(nivel='normal', limite_inferior=Decimal('15'), limite_superior=Decimal('25')),
                NivelDTO(nivel='precaucion', limite_inferior=Decimal('25'), limite_superior=Decimal('35')),
                NivelDTO(nivel='critico', limite_inferior=Decimal('35'), limite_superior=Decimal('45')),
            ],
            fecha_actualizacion=None,
        )

        with pytest.raises(InfrastructureError):
            uc.execute(1, dto, _usuario())

        assert len(edge_port.llamadas) == 1
        _, _, payload = edge_port.llamadas[0]
        assert payload['valor_min'] == '15'
        assert repo.actualizado.estado_sincronizacion == 'PENDIENTE'

    def test_reenvia_el_umbral_editado_y_confirma_sin_error(self) -> None:
        existente = _umbral_existente()
        repo = UmbralRepoFake(existente=existente)
        edge_port = EdgePortFake(ResultadoEnvioMqtt(estado='APLICADA', mensaje='ok'))
        uc = self._uc(edge_port, repo)

        dto = EditarUmbralDTO(
            valor_min=Decimal('15'),
            valor_max=Decimal('45'),
            niveles=[
                NivelDTO(nivel='normal', limite_inferior=Decimal('15'), limite_superior=Decimal('25')),
                NivelDTO(nivel='precaucion', limite_inferior=Decimal('25'), limite_superior=Decimal('35')),
                NivelDTO(nivel='critico', limite_inferior=Decimal('35'), limite_superior=Decimal('45')),
            ],
            fecha_actualizacion=None,
        )

        resultado = uc.execute(1, dto, _usuario())

        assert resultado.estado_sincronizacion == 'APLICADA'


def test_stub_adapter_siempre_degrada_a_pendiente_y_nunca_lanza() -> None:
    adapter = EdgeSincronizacionStubAdapter()

    resultado = adapter.propagar_umbral(1, 2, {'valor_min': '1'})

    assert resultado.estado == 'PENDIENTE'
    assert 'IoT' in resultado.mensaje or 'pendiente' in resultado.mensaje.lower()


class TestEntidadUmbralAmbiental:
    def test_marcar_sincronizado_limpia_el_motivo_de_fallo(self) -> None:
        umbral = _umbral_existente()
        umbral.marcar_fallo_sincronizacion('fallo previo')

        ahora = datetime.datetime.now(datetime.timezone.utc)
        umbral.marcar_sincronizado(ahora)

        assert umbral.estado_sincronizacion == 'APLICADA'
        assert umbral.fecha_ultima_sincronizacion == ahora
        assert umbral.motivo_fallo_sincronizacion is None

    def test_marcar_fallo_sincronizacion_guarda_el_motivo(self) -> None:
        umbral = _umbral_existente()

        umbral.marcar_fallo_sincronizacion('sin ACK a tiempo')

        assert umbral.estado_sincronizacion == 'NO_CONF'
        assert umbral.motivo_fallo_sincronizacion == 'sin ACK a tiempo'

    def test_estado_por_defecto_de_un_umbral_nuevo_es_pendiente(self) -> None:
        umbral = UmbralAmbiental.crear(
            id_especie=1,
            id_variable_ambiental=1,
            unidad_medida='°C',
            valor_min=Decimal('20'),
            valor_max=Decimal('40'),
            niveles=[],
            id_usuario=1,
        )

        assert umbral.estado_sincronizacion == 'PENDIENTE'
