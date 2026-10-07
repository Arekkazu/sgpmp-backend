"""TC-M02-G12 (#460), RF-16 / RFC-004 — el rango `valor_min`/`valor_max` de una
métrica ya existía en BD y en el ORM (y RF-33 lo consume para validar los
`atributos_dinamicos`), pero `GET /configuracion/metricas` no lo devolvía y
POST/PATCH no permitían configurarlo: QA no podía demostrar por API que un valor
estaba fuera de rango.

Reglas del RF-16 que se fijan aquí:
  - el rango solo aplica a tipo_dato NUMERICO/ENTERO;
  - si ambos límites existen, valor_min <= valor_max;
  - en la edición, omitir el rango lo conserva y enviarlo como null lo elimina;
  - al pasar a TEXTO/BOOLEANO el rango "debe quedar nulo".
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.configuration.application.use_cases.metricas.editar_metrica_use_case import EditarMetricaUseCase
from src.configuration.application.use_cases.metricas.registrar_metrica_use_case import RegistrarMetricaUseCase
from src.configuration.domain.entities.metrica_produccion import MetricaProduccion, validar_rango_metrica
from src.configuration.domain.value_objects.aplica_tipo_activo import AplicaTipoActivo
from src.configuration.domain.value_objects.nombre_metrica import NombreMetrica
from src.configuration.domain.value_objects.tipo_dato_atributo import TipoDatoAtributo
from src.configuration.domain.value_objects.tipo_medicion import TipoMedicion
from src.configuration.infrastructure.dto.editar_metrica_dto import EditarMetricaDTO
from src.configuration.infrastructure.dto.registrar_metrica_dto import RegistrarMetricaDTO
from src.configuration.infrastructure.schema.metrica_schema import MetricaProduccionResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ValidationError

D = Decimal
TS = datetime(2026, 9, 1, tzinfo=timezone.utc)
USUARIO = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


# --- dobles -------------------------------------------------------------------


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class AuditoriaFake:
    def __init__(self) -> None:
        self.eventos: list[dict] = []

    def registrar(self, **kw) -> None:
        self.eventos.append(kw)


class MetricasRepoFake:
    def __init__(self, existente: MetricaProduccion | None = None) -> None:
        self.existente = existente
        self.guardada: MetricaProduccion | None = None
        self.actualizada: MetricaProduccion | None = None

    def obtener_por_id(self, _id, **_):
        return self.existente

    def obtener_por_nombre_y_especie(self, _nombre, _id_especie):
        return None

    def guardar(self, metrica: MetricaProduccion) -> MetricaProduccion:
        metrica.id_metrica_produccion = 7
        self.guardada = metrica
        return metrica

    def actualizar(self, metrica: MetricaProduccion) -> MetricaProduccion:
        self.actualizada = metrica
        return metrica


class EspeciesRepoFake:
    def obtener_por_id(self, _id, **_):
        return SimpleNamespace(es_activo=True)


def _metrica(tipo_dato=TipoDatoAtributo.NUMERICO, valor_min=D("20"), valor_max=D("40")) -> MetricaProduccion:
    return MetricaProduccion(
        id_metrica_produccion=7,
        nombre=NombreMetrica("peso_destete"),
        unidad_medida="kg",
        tipo_medicion=TipoMedicion.PESO,
        aplica_a_tipo_activo=AplicaTipoActivo.AMBOS,
        tipo_dato=tipo_dato,
        es_obligatorio=False,
        id_especie=4,
        es_activo=True,
        fecha_actualizacion=TS,
        valor_min=valor_min,
        valor_max=valor_max,
    )


def _registrar(dto: RegistrarMetricaDTO):
    db, repo, auditoria = DbFake(), MetricasRepoFake(), AuditoriaFake()
    uc = RegistrarMetricaUseCase(db=db, metricas_repo=repo, especies_repo=EspeciesRepoFake(), auditoria_repo=auditoria)
    return uc, db, repo, auditoria


def _editar(existente: MetricaProduccion, **campos):
    db, repo, auditoria = DbFake(), MetricasRepoFake(existente), AuditoriaFake()
    base = dict(
        nombre="peso_destete", unidad_medida="kg", tipo_medicion="PESO",
        aplica_a_tipo_activo="AMBOS", fecha_actualizacion=TS,
    )
    dto = EditarMetricaDTO(**{**base, **campos})
    uc = EditarMetricaUseCase(db=db, metricas_repo=repo, auditoria_repo=auditoria)
    return uc, dto, db, repo, auditoria


def _dto_registro(**campos) -> RegistrarMetricaDTO:
    base = dict(id_especie=4, nombre="peso_destete", unidad_medida="kg", tipo_medicion="PESO", tipo_dato="NUMERICO")
    return RegistrarMetricaDTO(**{**base, **campos})


# --- regla de dominio ---------------------------------------------------------


@pytest.mark.parametrize("tipo", [TipoDatoAtributo.NUMERICO, TipoDatoAtributo.ENTERO])
def test_rango_valido_en_tipos_numericos(tipo) -> None:
    validar_rango_metrica(tipo, D("20"), D("40"))
    validar_rango_metrica(tipo, D("20"), D("20"))  # min == max se permite
    validar_rango_metrica(tipo, D("20"), None)     # un solo límite
    validar_rango_metrica(tipo, None, D("40"))


@pytest.mark.parametrize("tipo", list(TipoDatoAtributo))
def test_sin_rango_es_valido_en_cualquier_tipo(tipo) -> None:
    validar_rango_metrica(tipo, None, None)


def test_min_mayor_que_max_es_400_con_campo() -> None:
    with pytest.raises(ValidationError) as exc:
        validar_rango_metrica(TipoDatoAtributo.NUMERICO, D("40"), D("20"))
    assert exc.value.code == "RANGO_METRICA_INVALIDO"
    assert exc.value.status_code == 400
    assert exc.value.field == "valor_min"


@pytest.mark.parametrize("tipo", [TipoDatoAtributo.TEXTO, TipoDatoAtributo.BOOLEANO])
def test_rango_en_tipo_no_numerico_se_rechaza(tipo) -> None:
    with pytest.raises(ValidationError) as exc:
        validar_rango_metrica(tipo, D("1"), None)
    assert exc.value.code == "RANGO_METRICA_NO_APLICA"
    assert exc.value.field == "valor_min"

    with pytest.raises(ValidationError) as exc:
        validar_rango_metrica(tipo, None, D("9"))
    assert exc.value.field == "valor_max"


def test_la_entidad_valida_al_crear_y_al_actualizar() -> None:
    with pytest.raises(ValidationError):
        MetricaProduccion.crear(
            nombre=NombreMetrica("color_pelaje"), unidad_medida="n/a", tipo_medicion=TipoMedicion.OTRO,
            aplica_a_tipo_activo=AplicaTipoActivo.AMBOS, tipo_dato=TipoDatoAtributo.TEXTO,
            es_obligatorio=False, id_especie=4, valor_min=D("1"),
        )

    metrica = _metrica()
    with pytest.raises(ValidationError):
        metrica.actualizar(
            nombre=metrica.nombre, unidad_medida="kg", tipo_medicion=TipoMedicion.PESO,
            aplica_a_tipo_activo=AplicaTipoActivo.AMBOS, tipo_dato=TipoDatoAtributo.NUMERICO,
            es_obligatorio=False, fecha_actualizacion=TS, valor_min=D("50"), valor_max=D("10"),
        )
    # una edición rechazada no debe haber mutado la entidad
    assert (metrica.valor_min, metrica.valor_max) == (D("20"), D("40"))


def test_snapshot_de_auditoria_incluye_el_rango_serializable() -> None:
    snap = _metrica()._snapshot()
    assert snap["valor_min"] == "20" and snap["valor_max"] == "40"
    assert _metrica(valor_min=None, valor_max=None)._snapshot()["valor_min"] is None


# --- DTOs ---------------------------------------------------------------------


def test_dto_registrar_acepta_rango_decimal_y_es_opcional() -> None:
    assert _dto_registro(valor_min="20", valor_max="40.5").valor_max == D("40.5")
    dto = _dto_registro()
    assert dto.valor_min is None and dto.valor_max is None


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "-Infinity", "1.23456", "12345678.0"])
def test_dto_rechaza_valores_no_finitos_o_que_no_caben_en_numeric_10_4(valor) -> None:
    """La columna es NUMERIC(10,4): mejor un 400 claro que un DataError de la BD."""
    with pytest.raises(PydanticValidationError):
        _dto_registro(valor_min=valor)


def test_dto_editar_distingue_omitido_de_null_explicito() -> None:
    base = dict(nombre="abc", unidad_medida="kg", tipo_medicion="PESO", aplica_a_tipo_activo="AMBOS")
    omitido = EditarMetricaDTO(**base)
    nulo = EditarMetricaDTO(**base, valor_min=None)
    assert "valor_min" not in omitido.model_fields_set
    assert "valor_min" in nulo.model_fields_set and nulo.valor_min is None


def test_los_dtos_aceptan_guion_bajo_igual_que_el_dominio() -> None:
    """`peso_destete` (la métrica de QA, creada por SQL) no se podía editar por PATCH:
    `NombreMetrica` ya aceptaba `_` pero los DTOs lo rechazaban."""
    assert _dto_registro().nombre == "peso_destete"
    assert EditarMetricaDTO(
        nombre="peso_destete", unidad_medida="kg", tipo_medicion="PESO", aplica_a_tipo_activo="AMBOS",
    ).nombre == "peso_destete"


# --- registrar ----------------------------------------------------------------


def test_registrar_persiste_y_audita_el_rango() -> None:
    uc, db, repo, auditoria = _registrar(_dto_registro(valor_min="20", valor_max="40"))

    resultado = uc.execute(_dto_registro(valor_min="20", valor_max="40"), USUARIO)

    assert (repo.guardada.valor_min, repo.guardada.valor_max) == (D("20"), D("40"))
    assert auditoria.eventos[0]["valores_nuevos"]["valor_min"] == "20"
    assert db.commits == 1 and resultado.id_metrica_produccion == 7


def test_registrar_texto_con_rango_se_rechaza_sin_commit() -> None:
    dto = _dto_registro(tipo_medicion="OTRO", unidad_medida="n/a", tipo_dato="TEXTO", valor_min="1")
    uc, db, repo, _ = _registrar(dto)

    with pytest.raises(ValidationError) as exc:
        uc.execute(dto, USUARIO)

    assert exc.value.code == "RANGO_METRICA_NO_APLICA"
    assert repo.guardada is None and db.commits == 0


def test_registrar_min_mayor_que_max_se_rechaza() -> None:
    dto = _dto_registro(valor_min="40", valor_max="20")
    uc, db, repo, _ = _registrar(dto)

    with pytest.raises(ValidationError) as exc:
        uc.execute(dto, USUARIO)

    assert exc.value.code == "RANGO_METRICA_INVALIDO"
    assert repo.guardada is None and db.commits == 0


# --- editar -------------------------------------------------------------------


def test_editar_sin_enviar_el_rango_lo_conserva() -> None:
    uc, dto, db, repo, _ = _editar(_metrica())

    uc.execute(7, dto, USUARIO)

    assert (repo.actualizada.valor_min, repo.actualizada.valor_max) == (D("20"), D("40"))
    assert db.commits == 1


def test_editar_con_valores_nuevos_reemplaza_el_rango() -> None:
    uc, dto, _, repo, auditoria = _editar(_metrica(), valor_min="25", valor_max="35")

    uc.execute(7, dto, USUARIO)

    assert (repo.actualizada.valor_min, repo.actualizada.valor_max) == (D("25"), D("35"))
    ev = auditoria.eventos[0]
    assert ev["valores_anteriores"]["valor_min"] == "20" and ev["valores_nuevos"]["valor_min"] == "25"


def test_editar_con_null_explicito_elimina_el_rango() -> None:
    uc, dto, _, repo, _ = _editar(_metrica(), valor_min=None, valor_max=None)

    uc.execute(7, dto, USUARIO)

    assert (repo.actualizada.valor_min, repo.actualizada.valor_max) == (None, None)


def test_editar_solo_valor_max_se_valida_contra_el_valor_min_guardado() -> None:
    uc, dto, db, repo, _ = _editar(_metrica(), valor_max="10")  # el min guardado es 20

    with pytest.raises(ValidationError) as exc:
        uc.execute(7, dto, USUARIO)

    assert exc.value.code == "RANGO_METRICA_INVALIDO"
    assert repo.actualizada is None and db.commits == 0


def test_editar_a_texto_sin_enviar_rango_limpia_el_rango_previo() -> None:
    """RFC-004: para TEXTO/BOOLEANO valor_min/valor_max "deben quedar nulos"."""
    uc, dto, _, repo, _ = _editar(_metrica(), tipo_dato="TEXTO", tipo_medicion="OTRO", unidad_medida="n/a")

    uc.execute(7, dto, USUARIO)

    assert repo.actualizada.tipo_dato is TipoDatoAtributo.TEXTO
    assert (repo.actualizada.valor_min, repo.actualizada.valor_max) == (None, None)


def test_editar_a_texto_enviando_rango_explicito_se_rechaza() -> None:
    uc, dto, db, repo, _ = _editar(
        _metrica(), tipo_dato="TEXTO", tipo_medicion="OTRO", unidad_medida="n/a", valor_min="1",
    )

    with pytest.raises(ValidationError) as exc:
        uc.execute(7, dto, USUARIO)

    assert exc.value.code == "RANGO_METRICA_NO_APLICA"
    assert repo.actualizada is None and db.commits == 0


# --- respuesta ----------------------------------------------------------------


def test_respuesta_expone_valor_min_y_valor_max() -> None:
    """Lo que QA no podía ver: GET /configuracion/metricas debe incluir el rango."""
    resp = MetricaProduccionResponse.model_validate(_metrica())
    assert (resp.valor_min, resp.valor_max) == (D("20"), D("40"))

    sin_rango = MetricaProduccionResponse.model_validate(_metrica(valor_min=None, valor_max=None))
    assert (sin_rango.valor_min, sin_rango.valor_max) == (None, None)
    assert "valor_min" in sin_rango.model_dump()
