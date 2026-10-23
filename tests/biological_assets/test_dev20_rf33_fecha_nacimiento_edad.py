# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-20 RF-33: fecha_nacimiento opcional y advertencia de edad (RFC-014) |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DEV-20/23: el puerto falso cubre la validación de capacidad |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""DEV-20 (RF-33 1.4, RFC-014): fecha_nacimiento opcional y advertencia de edad del activo.

Los 4 casos de RFC-014: especie sin esperanza de vida (no advierte), activo joven (no
advierte), edad ≥ esperanza (201 + advertencia) y sin fecha (no advierte). Nunca rechaza.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.biological_assets.application.use_cases.gestion.consultar_indicadores_use_case import (
    ConsultarIndicadoresUseCase,
)
from src.biological_assets.application.use_cases.registro import registrar_activo_use_case as uc_mod
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, DetalleIndividual
from src.biological_assets.domain.repositories.especie_consulta_port import EspecieConsulta
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.services.edad_activo import evaluar_edad
from src.configuration.domain.services.capacidad_area import EspecieDelArea
from src.biological_assets.infrastructure.dto.actualizar_activo_individual_dto import ActualizarActivoIndividualDTO
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.biological_assets.infrastructure.routers.activo_biologico_router import _activo_to_response
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.fechas import hoy_usuario

HOY = date(2026, 10, 23)


# --- Regla pura -------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fecha, esperanza, advierte",
    [
        (datetime(2010, 1, 1), None, False),                 # especie sin esperanza de vida
        (datetime(2026, 1, 1), 3650, False),                 # activo joven
        (datetime(2010, 1, 1), 3650, True),                  # edad ≥ esperanza
        (None, 3650, False),                                 # sin fecha de nacimiento
        (HOY - timedelta(days=3650), 3650, True),            # justo en el límite: alcanza
        (HOY - timedelta(days=3649), 3650, False),           # un día antes del límite
    ],
    ids=["sin_esperanza", "joven", "edad_supera", "sin_fecha", "limite_exacto", "un_dia_antes"],
)
def test_evaluar_edad(fecha, esperanza, advierte):
    resultado = evaluar_edad(fecha, esperanza, HOY)
    assert (resultado is not None) is advierte
    if advierte:
        assert resultado.edad_dias >= esperanza
        assert resultado.mensaje == (
            f"La edad del activo ({resultado.edad_dias} días) alcanza o supera la esperanza de vida "
            f"de la especie ({esperanza} días). Verifique la fecha de nacimiento."
        )


def test_la_edad_usa_el_dia_en_colombia(en_colombia):
    # 2026-10-23 03:00 UTC es todavía 22-oct en Colombia: 1 día de edad al 23, no 0.
    assert evaluar_edad(datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc), 1, HOY).edad_dias == 1


# --- DTO de registro y de edición -------------------------------------------------------

def _dto(**cambios) -> RegistrarActivoBiologicoDTO:
    base = dict(
        tipo_activo="INDIVIDUAL", id_especie=1, fecha_inicio_ciclo=date(2024, 1, 1), origen_financiero="compra",
        costo_adquisicion=100, soporte_documental="factura.pdf", id_infraestructura=1, identificador="BOV-200",
        raza="Angus", sexo="M",
    )
    base.update(cambios)
    return RegistrarActivoBiologicoDTO(**base)


def test_individual_sin_fecha_de_nacimiento_es_valido():
    assert _dto().fecha_nacimiento is None


def test_fecha_de_nacimiento_futura_se_rechaza():
    manana = datetime.combine(hoy_usuario() + timedelta(days=1), datetime.min.time())
    with pytest.raises(PydanticValidationError, match="fecha_nacimiento no puede ser futura"):
        _dto(fecha_nacimiento=manana)
    with pytest.raises(PydanticValidationError, match="fecha_nacimiento no puede ser futura"):
        ActualizarActivoIndividualDTO(fecha_nacimiento=manana)


def test_poblacional_sigue_sin_admitir_fecha_de_nacimiento():
    with pytest.raises(PydanticValidationError, match="no aplican para activos de tipo POBLACIONAL"):
        _dto(tipo_activo="POBLACIONAL", identificador=None, raza=None, sexo=None, cantidad_inicial=10,
             fecha_nacimiento=datetime(2025, 1, 1))


# --- Caso de uso: 201 + advertencia y constancia en la bitácora -------------------------

class _Db:
    def commit(self): pass
    def rollback(self): pass


class _Repo:
    def existe_identificador(self, identificador): return False

    def guardar(self, activo):
        activo.id_activo_biologico = 500
        return activo

    def registrar_historial(self, historial):
        historial.id_historial_activo = 1
        return historial


class _Especie:
    def __init__(self, esperanza): self.esperanza = esperanza

    def obtener_activa(self, id_especie):
        return EspecieConsulta(id_especie=id_especie, nombre="Bovino", es_activo=True,
                               esperanza_vida_dias=self.esperanza)


class _Infra:
    # DEV-23: la entrada al área valida capacidad; el área ya aloja la especie con
    # densidad, sin ocupación, para que la prueba se centre en la edad (RFC-014).
    def obtener_activa(self, id_infraestructura):
        return InfraestructuraConsulta(id_infraestructura=id_infraestructura, nombre="Potrero 1", tipo="potrero",
                                       es_activo=True, superficie=Decimal("500"), id_finca=5,
                                       especies=[EspecieDelArea(1, "Bovino", "ESPECIES_GRANDES", Decimal("2"))])

    def bloquear_capacidad(self, id_infraestructura): pass
    def calcular_ocupacion(self, id_infraestructura): return 0
    def asociar_especie(self, id_infraestructura, id_especie): pass


class _Parametros:
    def listar_por_especie(self, id_especie, tipo_activo): return []
    def obtener_densidad_maxima(self, id_especie): return None


@pytest.fixture
def eventos(monkeypatch):
    capturados = []
    monkeypatch.setattr(uc_mod, "registrar_evento_bitacora", lambda repo, db, evento: capturados.append(evento))
    return capturados


def _registrar(esperanza, fecha_nacimiento):
    uc = uc_mod.RegistrarActivoBiologicoUseCase(
        db=_Db(), repo=_Repo(), especie_port=_Especie(esperanza), infra_port=_Infra(),
        parametros_port=_Parametros(), bitacora_repo=object(),
    )
    return uc.execute(_dto(fecha_nacimiento=fecha_nacimiento), UsuarioActual(id_usuario=7, id_token=1, id_rol=2))


HACE_20_ANOS = datetime(2006, 1, 1)
HACE_UN_ANO = datetime.combine(hoy_usuario() - timedelta(days=365), datetime.min.time())


@pytest.mark.parametrize(
    "esperanza, fecha, advierte",
    [(None, HACE_20_ANOS, False), (3650, HACE_UN_ANO, False), (3650, HACE_20_ANOS, True), (3650, None, False)],
    ids=["especie_sin_esperanza", "activo_joven", "edad_supera_esperanza", "sin_fecha"],
)
def test_rfc014_registro_nunca_rechaza_y_advierte_solo_si_la_edad_alcanza(eventos, esperanza, fecha, advierte):
    activo = _registrar(esperanza, fecha)

    assert activo.id_activo_biologico == 500  # se registró en los 4 casos
    [evento] = eventos
    assert evento.tipo_evento == "ACTIVO_REGISTRADO" and evento.resultado == "EXITOSO"
    if advierte:
        assert activo.advertencia_edad.startswith("La edad del activo (")
        assert "(3650 días)" in activo.advertencia_edad
        assert evento.severidad_log == "WARNING"
        assert evento.detalle_tecnico["advertencia_edad"]["mensaje"] == activo.advertencia_edad
        assert evento.detalle_tecnico["advertencia_edad"]["esperanza_vida_dias"] == 3650
    else:
        assert activo.advertencia_edad is None
        assert evento.severidad_log == "INFO"
        assert "advertencia_edad" not in evento.detalle_tecnico


def test_la_respuesta_del_registro_lleva_la_advertencia(eventos):
    activo = _registrar(3650, HACE_20_ANOS)
    activo.fecha_creacion = datetime.now(timezone.utc)
    respuesta = _activo_to_response(activo)
    assert respuesta.advertencia_edad == activo.advertencia_edad
    assert respuesta.detalle_individual.fecha_nacimiento == HACE_20_ANOS.replace(tzinfo=timezone.utc)  # sin zona entra como UTC


def test_la_respuesta_admite_activo_sin_fecha_de_nacimiento(eventos):
    respuesta = _activo_to_response(_registrar(3650, None))
    assert respuesta.detalle_individual.fecha_nacimiento is None
    assert respuesta.advertencia_edad is None


# --- Lecturas que antes asumían la fecha no nula ----------------------------------------

def test_indicadores_con_activo_sin_fecha_de_nacimiento():
    activo = SimpleNamespace(
        detalle_individual=DetalleIndividual(raza="Angus", sexo="M", fecha_nacimiento=None),
        fecha_inicio_ciclo=date(2024, 1, 1),
        id_estado=1,  # ACTIVO: sin fecha de cierre que acote el rango
    )
    # Sin fecha de nacimiento solo se valida contra el inicio de ciclo.
    ConsultarIndicadoresUseCase._validar_rango_dentro_del_ciclo_de_vida(None, activo, date(2024, 6, 1), None)


def test_snapshot_de_activo_sin_fecha_de_nacimiento():
    activo = ActivoBiologico.crear(_dto(), id_usuario=7)
    assert activo._snapshot()["detalle_individual"]["fecha_nacimiento"] is None
