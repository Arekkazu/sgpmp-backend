# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-23 RF-33/34/36/48: capacidad efectiva del área (RFC-012) |
"""DEV-23 (RFC-012 v1.1): capacidad efectiva del área en registro, altas y transferencias.

Casos del ticket: en el límite cabe y +1 → 422; grupo distinto → 422; especie sin
densidad → 422; entrante con menor densidad → 422 sin tocar lo alojado (H-12.3).
Fakes en memoria; la regla es la de ``capacidad_area`` (DEV-22).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.biological_assets.application.use_cases._capacidad_area import admite_entrada, validar_entrada_al_area
from src.biological_assets.application.use_cases.gestion.registrar_transferencia_use_case import (
    RegistrarTransferenciaUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetallePoblacional,
    HistorialInfraestructura,
    Transferencia,
)
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_transferencia_dto import RegistrarTransferenciaDTO
from src.configuration.domain.services.capacidad_area import EspecieDelArea
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError

TILAPIA = EspecieDelArea(1, 'Tilapia', 'PECES', Decimal('2'))
CACHAMA = EspecieDelArea(2, 'Cachama', 'PECES', Decimal('1'))      # mismo grupo, menor densidad
BOVINO = EspecieDelArea(3, 'Bovino', 'RUMIANTES', Decimal('0.1'))  # otro grupo
SIN_DENSIDAD = EspecieDelArea(4, 'Bagre', 'PECES', None)


class Puerto:
    def __init__(self, ocupacion=0, especies=(TILAPIA, CACHAMA, BOVINO, SIN_DENSIDAD)):
        self.ocupacion = ocupacion
        self.especies = {e.id_especie: e for e in especies}
        self.llamadas: list[str] = []
        self.asociadas: list[tuple[int, int]] = []

    def bloquear_capacidad(self, id_infraestructura):
        self.llamadas.append('bloquear')

    def calcular_ocupacion(self, id_infraestructura):
        self.llamadas.append('ocupacion')
        return self.ocupacion

    def obtener_especie(self, id_especie):
        return self.especies.get(id_especie)

    def asociar_especie(self, id_infraestructura, id_especie):
        self.asociadas.append((id_infraestructura, id_especie))


def _area(*especies, superficie=Decimal('50')):
    return InfraestructuraConsulta(id_infraestructura=7, nombre='Estanque 7', tipo='Estanque', es_activo=True,
                                   superficie=superficie, id_finca=1, especies=list(especies))


def _validar(puerto, area, id_especie, entrantes):
    return validar_entrada_al_area(puerto, area, id_especie=id_especie, entrantes=entrantes, field='id_infraestructura')


# --- La regla, tal como la aplican RF-33, RF-36 y RF-48 -----------------------------------

def test_en_el_limite_cabe_y_uno_mas_es_422():
    # Tilapia 2 ind/m² × 50 m² = 100. Hay 90 alojados.
    assert _validar(Puerto(ocupacion=90), _area(TILAPIA), 1, 10) is False  # 100: cabe
    with pytest.raises(BusinessRuleError) as exc:
        _validar(Puerto(ocupacion=90), _area(TILAPIA), 1, 11)              # 101: no cabe
    assert exc.value.status_code == 422
    assert exc.value.code == 'CAPACIDAD_EXCEDIDA'
    assert exc.value.field == 'id_infraestructura'


def test_otra_especie_del_mismo_grupo_se_asocia():
    assert _validar(Puerto(), _area(TILAPIA), 2, 10) is True


def test_grupo_de_manejo_distinto_es_422():
    with pytest.raises(BusinessRuleError) as exc:
        _validar(Puerto(), _area(TILAPIA), 3, 1)
    assert exc.value.code == 'GRUPOS_MANEJO_INCOMPATIBLES'
    assert exc.value.field == 'id_infraestructura'


@pytest.mark.parametrize("area", [_area(TILAPIA), _area(SIN_DENSIDAD)], ids=["entrante_sin_densidad", "alojada_sin_densidad"])
def test_especie_sin_densidad_es_422(area):
    id_entrante = 4 if area.especies[0] is TILAPIA else 1
    with pytest.raises(BusinessRuleError) as exc:
        _validar(Puerto(), area, id_entrante, 1)
    assert exc.value.code == 'ESPECIE_SIN_DENSIDAD'


def test_entrante_que_baja_el_minimo_se_rechaza_aunque_quepa_con_el_minimo_anterior():
    # H-12.3: con solo Tilapia, 90 + 10 = 100 ≤ 100. Con Cachama (1 ind/m²) el MIN baja y la
    # capacidad pasa a 50: se rechaza al entrante.
    with pytest.raises(BusinessRuleError) as exc:
        _validar(Puerto(ocupacion=90), _area(TILAPIA), 2, 10)
    assert exc.value.code == 'CAPACIDAD_EXCEDIDA'
    assert '50 individuos' in exc.value.message


def test_bloquea_el_area_antes_de_contar_la_ocupacion():
    puerto = Puerto()
    _validar(puerto, _area(TILAPIA), 1, 1)
    assert puerto.llamadas == ['bloquear', 'ocupacion']


def test_area_sin_especies_toma_la_capacidad_de_la_entrante():
    assert _validar(Puerto(), _area(), 2, 50) is True  # Cachama: floor(1 × 50) = 50
    with pytest.raises(BusinessRuleError):
        _validar(Puerto(), _area(), 2, 51)


def test_listado_aplica_la_misma_regla_sin_errores():
    area = _area(TILAPIA)
    assert admite_entrada(area, TILAPIA, ocupacion=90, entrantes=10) is True
    assert admite_entrada(area, TILAPIA, ocupacion=90, entrantes=11) is False
    assert admite_entrada(area, CACHAMA, ocupacion=40, entrantes=10) is True    # 50 con el nuevo MIN
    assert admite_entrada(area, CACHAMA, ocupacion=41, entrantes=10) is False
    assert admite_entrada(area, BOVINO, ocupacion=0, entrantes=1) is False      # otro grupo
    assert admite_entrada(area, SIN_DENSIDAD, ocupacion=0, entrantes=1) is False


# --- RF-48: el destino no se toca si el entrante no cabe ----------------------------------

class _Db:
    def __init__(self):
        self.ejecutados, self.commits = [], 0

    def execute(self, stmt, params=None):
        self.ejecutados.append((str(stmt), params))

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class _Activos:
    def __init__(self, activo):
        self.activo = activo

    def obtener_por_id(self, _id):
        return self.activo

    def obtener_asociacion_activa(self, _id):
        return HistorialInfraestructura(id_historial=1, id_activo_biologico=30, id_infraestructura=6,
                                        nombre_infraestructura='Origen', tipo_infraestructura='Estanque',
                                        fecha_inicio=None, fecha_fin=None)


class _Transferencias:
    def hay_transferencia_en_progreso(self, _id):
        return False

    def guardar(self, t: Transferencia):
        t.id_movimiento = 1
        return t


class _PuertoTransferencia(Puerto):
    def __init__(self, destino, **kw):
        super().__init__(**kw)
        self.areas = {6: _area(CACHAMA), 7: destino}
        self.areas[6].id_infraestructura = 6

    def obtener_activa(self, id_infraestructura):
        return self.areas.get(id_infraestructura)

    def es_tipo_compatible(self, tipo, id_especie):
        return True


def _transferir(destino, ocupacion_destino, cantidad):
    activo = ActivoBiologico(
        id_especie=2, tipo='POBLACIONAL', origen_financiero='compra', id_infraestructura=6,
        id_estado=EstadoActivo.ACTIVO, id_usuario=1, id_activo_biologico=30,
        detalle_poblacional=DetallePoblacional(cantidad_inicial=cantidad, cantidad_actual=cantidad),
    )
    db, puerto = _Db(), _PuertoTransferencia(destino, ocupacion=ocupacion_destino)
    uc = RegistrarTransferenciaUseCase(db=db, activo_repo=_Activos(activo), transferencia_repo=_Transferencias(),
                                       infra_port=puerto, parametros_port=None)
    dto = RegistrarTransferenciaDTO(infraestructura_origen_id=6, infraestructura_destino_id=7,
                                    fecha_transferencia=date(2026, 10, 1), motivo_transferencia='Traslado de prueba DEV-23')
    return uc, dto, db, puerto


def test_transferencia_entrante_con_menor_densidad_es_422_sin_tocar_lo_alojado():
    # Destino con Tilapia (100 de capacidad) y 90 alojados; entran 10 Cachamas: el MIN
    # baja a 1 ind/m² → capacidad 50 < 100 → 422. Ni asociación ni escrituras.
    uc, dto, db, puerto = _transferir(_area(TILAPIA), ocupacion_destino=90, cantidad=10)
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(30, dto, UsuarioActual(id_usuario=1, id_token=1, id_rol=1))
    assert exc.value.code == 'CAPACIDAD_EXCEDIDA'
    assert exc.value.field == 'infraestructura_destino_id'
    assert puerto.asociadas == [] and db.ejecutados == [] and db.commits == 0


def test_transferencia_asocia_la_especie_al_destino_si_cabe():
    uc, dto, db, puerto = _transferir(_area(TILAPIA), ocupacion_destino=30, cantidad=10)
    uc.execute(30, dto, UsuarioActual(id_usuario=1, id_token=1, id_rol=1))
    assert puerto.asociadas == [(7, 2)]
    assert db.commits == 1


def test_transferencia_a_destino_de_otro_grupo_es_422():
    uc, dto, db, puerto = _transferir(_area(BOVINO), ocupacion_destino=0, cantidad=1)
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(30, dto, UsuarioActual(id_usuario=1, id_token=1, id_rol=1))
    assert exc.value.code == 'GRUPOS_MANEJO_INCOMPATIBLES'
    assert puerto.asociadas == [] and db.commits == 0


# --- RF-34: capacidad_maxima derivada en la asociación vigente ----------------------------

def test_rf34_asociacion_vigente_lleva_la_capacidad_derivada_del_area():
    from datetime import datetime, timezone

    from src.biological_assets.application.use_cases.registro.consultar_asociacion_use_case import (
        ConsultarAsociacionUseCase,
    )
    from src.biological_assets.infrastructure.routers.activo_biologico_router import _historial_to_response

    vigente = HistorialInfraestructura(id_historial=1, id_activo_biologico=30, id_infraestructura=7,
                                       nombre_infraestructura='Estanque 7', tipo_infraestructura='Estanque',
                                       fecha_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc), fecha_fin=None)

    class _Repo:
        def obtener_por_id(self, _id, **kw): return object()
        def obtener_asociacion_activa(self, _id): return vigente
        def obtener_asociacion_en_fecha(self, _id, _f): return vigente
        def obtener_historial_infraestructura(self, _id): return [vigente]

    class _Infra:
        def listar_sensores_activos(self, _id): return []
        def obtener_activa(self, _id):
            area = _area(TILAPIA, CACHAMA)
            area.capacidad_maxima = 50  # derivada: floor(MIN(2, 1) × 50)
            return area

    uc = ConsultarAsociacionUseCase(db=_Db(), repo=_Repo(), infra_port=_Infra())
    resultado = uc.execute(30, 'ACTIVA', usuario=UsuarioActual(id_usuario=1, id_token=1, id_rol=1))
    assert resultado.capacidad_maxima == 50

    # En una fecha pasada no se reconstruye la capacidad de entonces.
    pasada = uc.execute(30, 'ACTIVA', fecha_referencia=datetime(2026, 2, 1, tzinfo=timezone.utc))
    assert pasada.capacidad_maxima is None

    # La respuesta HTTP la expone en asociacion_activa.
    respuesta = _historial_to_response(vigente).model_copy(update={'capacidad_maxima': resultado.capacidad_maxima})
    assert respuesta.capacidad_maxima == 50
