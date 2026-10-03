"""Códigos HTTP de flujo alterno del Módulo 9, fijados contra el texto de cada RF.

Cubre los gaps de `anotaciones/modulo_9/gaps_flujo_alterno_modulo9.md`: casos donde
la condición de negocio ya se validaba bien pero el HTTP que salía no era el que
el RF pide, más los dos que no se validaban en absoluto (RF-23 y RF-32).

La lógica de cada regla está probada en su propio archivo; aquí se fija únicamente
el contrato HTTP, que es lo que rompe una revisión de QA.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.configuration.application.use_cases.infraestructuras.registrar_infraestructura_use_case import (
    RegistrarInfraestructuraUseCase,
)
from src.configuration.application.use_cases.plantillas.aplicar_plantilla_use_case import (
    AplicarPlantillaUseCase,
)
from src.configuration.application.use_cases.umbrales.registrar_umbral_use_case import _validar_rangos
from src.configuration.domain.entities.contexto_interfaz import ContextoInterfaz
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental
from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.entities.tipo_area import TipoArea
from src.configuration.domain.entities.variable_ambiental import VariableAmbiental
from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.aplicar_plantilla_dto import AplicarPlantillaDTO
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.configuration.infrastructure.dto.registrar_infraestructura_dto import RegistrarInfraestructuraDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ValidationError

USUARIO = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


# --------------------------------------------------------------------------- #
# RF-17 — "Solapamiento de niveles de alerta (Semaforización)" -> HTTP 400
# --------------------------------------------------------------------------- #

VARIABLE = VariableAmbiental(
    id_variable_ambiental=1,
    nombre="Temperatura",
    unidad="°C",
    valor_fisico_min=Decimal("0"),
    valor_fisico_max=Decimal("50"),
    es_activo=True,
)


def _nivel(nivel: str, inferior: str, superior: str) -> NivelAlertaAmbiental:
    return NivelAlertaAmbiental(
        nivel=NivelAlerta.desde_string(nivel),
        limite_inferior=Decimal(inferior),
        limite_superior=Decimal(superior),
    )


@pytest.mark.parametrize(
    "niveles",
    [
        # El rojo empieza antes de que termine el amarillo: solapamiento real.
        pytest.param(
            [_nivel("normal", "20", "30"), _nivel("precaucion", "30", "38"), _nivel("critico", "37.5", "40")],
            id="solapamiento-entre-niveles",
        ),
        # Hueco: el primer nivel no arranca en valor_min.
        pytest.param(
            [_nivel("normal", "22", "30"), _nivel("precaucion", "30", "38"), _nivel("critico", "38", "40")],
            id="no-cubre-el-minimo",
        ),
        # Hueco: el último nivel no llega a valor_max.
        pytest.param(
            [_nivel("normal", "20", "30"), _nivel("precaucion", "30", "38"), _nivel("critico", "38", "39")],
            id="no-cubre-el-maximo",
        ),
    ],
)
def test_rf17_semaforizacion_inconsistente_es_400(niveles) -> None:
    with pytest.raises(ValidationError) as error:
        _validar_rangos(Decimal("20"), Decimal("40"), niveles, VARIABLE)

    assert error.value.code == "SOLAPAMIENTO_NIVELES"
    assert error.value.status_code == 400


def test_rf17_semaforizacion_contigua_y_completa_pasa() -> None:
    _validar_rangos(
        Decimal("20"),
        Decimal("40"),
        [_nivel("normal", "20", "30"), _nivel("precaucion", "30", "38"), _nivel("critico", "38", "40")],
        VARIABLE,
    )


# --------------------------------------------------------------------------- #
# RF-20 — "Tipo de área no reconocido" -> HTTP 400
# --------------------------------------------------------------------------- #

class _DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _FincaActivaFake:
    class _Finca:
        es_activo = True
        id_finca = 1

    def obtener_por_id(self, _id_finca):
        return self._Finca()


class _TipoAreaRepoFake:
    def __init__(self, tipo) -> None:
        self.tipo = tipo

    def obtener_por_nombre(self, _nombre):
        return self.tipo


class _NuncaEscribeFake:
    def __getattr__(self, nombre):
        def _fallar(*_args, **_kwargs):
            raise AssertionError(f"no debía invocarse {nombre} tras el rechazo")

        return _fallar


@pytest.mark.parametrize(
    "tipo",
    [
        pytest.param(None, id="tipo-inexistente"),
        pytest.param(TipoArea(nombre="Galpón", es_activo=False, id_tipo_area=3), id="tipo-desactivado"),
    ],
)
def test_rf20_tipo_de_area_no_reconocido_es_400(tipo) -> None:
    db = _DbFake()
    use_case = RegistrarInfraestructuraUseCase(
        db=db,
        infra_repo=_NuncaEscribeFake(),
        finca_repo=_FincaActivaFake(),
        tipo_area_repo=_TipoAreaRepoFake(tipo),
        auditoria_repo=_NuncaEscribeFake(),
    )
    dto = RegistrarInfraestructuraDTO(
        nombre_infraestructura="Galpón 1",
        tipo_area="Cueva",
        superficie=Decimal("120"),
        finca_id=1,
    )

    with pytest.raises(ValidationError) as error:
        use_case.execute(dto, USUARIO)

    assert error.value.code == "TIPO_AREA_NO_RECONOCIDO"
    assert error.value.status_code == 400
    assert error.value.field == "tipo_area"
    assert db.commits == 0


# --------------------------------------------------------------------------- #
# RF-23 — "Inconsistencia lógica de tiempos" -> HTTP 400
#
# La auditoría marcó este caso como no validado mirando solo `verificar_rango`
# (que compara cada parámetro contra su propio rango por tipo de hardware). La
# regla cruzada sí existe: vive en el `model_validator` del DTO, que es
# justamente lo que produce el 400 que el RF pide.
# --------------------------------------------------------------------------- #

def test_rf23_intervalo_menor_que_la_frecuencia_es_rechazado_por_el_dto() -> None:
    """Ambos valores caben en su rango individual; lo inconsistente es la relación."""
    with pytest.raises(PydanticValidationError) as error:
        ConfigurarRemotamenteDTO(frecuencia_captura=10, intervalo_transmision=5)

    mensaje = str(error.value)
    assert "Conflicto lógico" in mensaje
    assert "no puede ser menor a la frecuencia de captura" in mensaje


def test_rf23_intervalo_igual_a_la_frecuencia_se_acepta() -> None:
    """El RF prohíbe "menor a", no "igual a": transmitir cada medición es válido."""
    dto = ConfigurarRemotamenteDTO(frecuencia_captura=10, intervalo_transmision=10)

    assert dto.intervalo_transmision == 10


# --------------------------------------------------------------------------- #
# RF-25 — "Finca sin especies productivas configuradas" -> HTTP 204
# --------------------------------------------------------------------------- #

def _contexto(**cambios) -> ContextoInterfaz:
    base = dict(
        id_usuario=7,
        nombre_completo="Ana Garcia",
        id_rol=2,
        nombre_rol="Productor",
        id_finca=1,
        finca_activa="Finca El Remanso",
        departamento="Huila",
        especies_configuradas=[],
        modulos_autorizados=["contexto_interfaz"],
        tiene_infraestructura=False,
    )
    base.update(cambios)
    return ContextoInterfaz(**base)


def test_rf25_finca_sin_especies_ni_infraestructura_es_204() -> None:
    assert _contexto().finca_sin_catalogo is True


@pytest.mark.parametrize(
    "cambios",
    [
        pytest.param({"especies_configuradas": ["Tilapia"]}, id="tiene-especies"),
        pytest.param({"tiene_infraestructura": True}, id="tiene-areas"),
        # Sin finca el flujo alterno es el otro: 200 con la vista de bienvenida.
        pytest.param({"id_finca": None}, id="sin-finca-asociada"),
    ],
)
def test_rf25_con_algo_configurado_sigue_siendo_200(cambios) -> None:
    assert _contexto(**cambios).finca_sin_catalogo is False


# --------------------------------------------------------------------------- #
# RF-32 — esquema legacy -> 422 · referencias huérfanas -> 400
# --------------------------------------------------------------------------- #

class _PlantillaRepoFake:
    def __init__(self, snapshot: dict) -> None:
        self.plantilla = Plantilla.crear(
            id_especie=1,
            id_usuario=1,
            template_name="plantilla-test",
            params_snapshot=snapshot,
            version=1,
            fecha_creacion=datetime.now(timezone.utc),
        )

    def obtener_por_id(self, _id):
        return self.plantilla

    def obtener_ultima_version(self, _nombre):
        return self.plantilla


class _EspecieDestinoRepoFake:
    def obtener_por_id(self, _id):
        especie = Especie.crear(
            nombre=NombreEspecie("Tilapia"),
            descripcion=None,
            fecha_creacion=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        especie.id_especie = 5
        especie.fecha_actualizacion = None
        return especie


class _VariableRepoFake:
    def __init__(self, variables: dict[int, VariableAmbiental]) -> None:
        self.variables = variables

    def obtener_por_id(self, id_variable_ambiental: int):
        return self.variables.get(id_variable_ambiental)

    def listar_activas(self):
        return [v for v in self.variables.values() if v.es_activo]


def _use_case_aplicar(snapshot: dict, variables: dict) -> AplicarPlantillaUseCase:
    return AplicarPlantillaUseCase(
        db=_DbFake(),
        plantilla_repo=_PlantillaRepoFake(snapshot),
        especie_repo=_EspecieDestinoRepoFake(),
        ciclo_repo=_NuncaEscribeFake(),
        metrica_repo=_NuncaEscribeFake(),
        umbral_repo=_NuncaEscribeFake(),
        patologia_repo=_NuncaEscribeFake(),
        aplicacion_repo=_NuncaEscribeFake(),
        auditoria_repo=_AuditoriaPlantillaFake(),
        variable_repo=_VariableRepoFake(variables),
    )


class _AuditoriaPlantillaFake:
    """`registrar_intento_fallido` audita todo rechazo en su propia transacción."""

    def registrar(self, **_kwargs) -> None:
        pass


def test_rf32_esquema_legacy_es_422() -> None:
    use_case = _use_case_aplicar({"schema_version": 0}, {})
    dto = AplicarPlantillaDTO(id_especie_destino=5, fecha_actualizacion_especie_destino=None)

    with pytest.raises(BusinessRuleError) as error:
        use_case.execute(1, dto, USUARIO)

    assert error.value.code == "VERSION_SNAPSHOT_INCOMPATIBLE"
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "variables",
    [
        pytest.param({}, id="variable-eliminada-del-catalogo"),
        pytest.param(
            {9: VariableAmbiental(9, "pH", "pH", Decimal("0"), Decimal("14"), es_activo=False)},
            id="variable-desactivada",
        ),
    ],
)
def test_rf32_referencia_huerfana_es_400_y_no_toca_la_especie_destino(variables) -> None:
    """La plantilla apunta a una variable ambiental que ya no está vigente.

    Sin esta comprobación el snapshot se aplicaba directo y el fallo salía abajo
    como violación de FK (409/500), después de haber desactivado la configuración
    anterior de la especie destino — los repos fake fallarían si se llegara ahí.
    """
    snapshot = {
        "schema_version": 1,
        "umbrales_ambientales": [
            {
                "id_variable_ambiental": 9,
                "unidad_medida": "pH",
                "valor_min": "6.0",
                "valor_max": "8.0",
                "niveles": [],
            }
        ],
    }
    use_case = _use_case_aplicar(snapshot, variables)

    with pytest.raises(ValidationError) as error:
        use_case.execute(
            1,
            AplicarPlantillaDTO(id_especie_destino=5, fecha_actualizacion_especie_destino=None),
            USUARIO,
        )

    assert error.value.code == "REFERENCIAS_HUERFANAS"
    assert error.value.status_code == 400
    assert "[9]" in error.value.message
