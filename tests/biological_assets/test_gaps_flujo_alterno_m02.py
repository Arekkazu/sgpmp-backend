"""Códigos HTTP de flujo alterno del Módulo 2, fijados contra el texto de cada RF.

Cubre los gaps de `anotaciones/modulo_2/gaps_flujo_alterno_modulo2.md`: casos donde
la regla ya se aplicaba pero salía con otro HTTP (RF-40/41/42/43/44/46), las
salidas propias de RF-51 que caían en el 422 genérico, y lo que no se validaba en
absoluto (RF-47 E-03, outliers de RF-50, RF-52 E1/E2).

La lógica de cada regla está probada en su propio archivo; aquí se fija el
contrato HTTP, que es lo que rompe una revisión de QA. Cada rechazo trae su
contraejemplo cuando el cambio podría volverse un rechazo indiscriminado.
"""
from __future__ import annotations

import contextlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import ProgrammingError

from src.biological_assets.application.use_cases import _registrar_evento_bitacora as bitacora
from src.biological_assets.application.use_cases._registrar_evento_bitacora import registrar_evento_bitacora
from src.biological_assets.application.use_cases.gestion._event_validations import validar_fecha_evento
from src.biological_assets.application.use_cases.gestion.cambiar_estado_use_case import CambiarEstadoUseCase
from src.biological_assets.application.use_cases.gestion.consultar_datos_consolidados_use_case import (
    ConsultarDatosConsolidadosUseCase,
)
from src.biological_assets.application.use_cases.gestion.consultar_ficha_integral_use_case import (
    ConsultarFichaIntegralUseCase,
)
from src.biological_assets.application.use_cases.gestion.consultar_historial_use_case import (
    ConsultarHistorialUseCase,
)
from src.biological_assets.application.use_cases.gestion.consultar_indicadores_use_case import (
    ConsultarIndicadoresUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
    RegistrarEventoCrecimientoUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_productivo_use_case import (
    RegistrarEventoProductivoUseCase,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DatosConsolidados,
    EventoAuditoria,
    IndicadorZootecnico,
    ResultadoIndicadores,
    SeccionDatosConsolidados,
)
from src.biological_assets.domain.repositories.ciclo_consulta_port import CicloProductivoConsulta, FaseCiclo
from src.biological_assets.domain.repositories.parametros_especie_port import MetricaProductiva
from src.biological_assets.infrastructure.dto.cambiar_estado_dto import CambiarEstadoDTO
from src.biological_assets.infrastructure.dto.consultar_historial_dto import ConsultarHistorialDTO
from src.biological_assets.infrastructure.dto.consultar_indicadores_dto import ConsultarIndicadoresDTO
from src.biological_assets.infrastructure.dto.datos_consolidados_dto import DatosConsolidadosDTO
from src.biological_assets.infrastructure.dto.registrar_evento_productivo_dto import RegistrarEventoProductivoDTO
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
    SqlAlchemyBitacoraAuditoriaRepository,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, InfrastructureError, ValidationError

USUARIO = UsuarioActual(id_usuario=7, id_token=1, id_rol=2)
AHORA = datetime.now(timezone.utc)
# +2 días: con +1 un servidor detrás de UTC puede seguir en "hoy" (INC-M02-29-g36).
PASADO_MANANA = AHORA.date() + timedelta(days=2)


class _Db:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _NoDebeLlamarse:
    def __getattr__(self, nombre):
        raise AssertionError(f'No debía consultarse {nombre}: el rechazo va antes de tocar la BD.')


def _activo(id_estado: int = 1, tipo: str = 'INDIVIDUAL') -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=1,
        tipo=tipo,
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=10,
        fecha_inicio_ciclo=date(2026, 1, 1),
        fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class _ActivoRepo:
    def __init__(self, activo: ActivoBiologico | None) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, **_kwargs):
        return self.activo

    def obtener_fase_activa(self, _id: int):
        return SimpleNamespace(
            id_ciclo_productiva=3,
            nombre_ciclo='Lactancia',
            fecha_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc),
            fecha_finalizacion=None,
        )

    def obtener_asociacion_activa(self, _id: int):
        return None


class _EventoRepo:
    def obtener_ultima_fecha(self, _id: int):
        return None

    def existe_productivo_duplicado(self, *_args) -> bool:
        return False

    def tiene_diagnostico_positivo_previo(self, _id: int) -> bool:
        return True


# --------------------------------------------------------------------------- #
# RF-39/40/41/42 — "Fecha inválida" -> HTTP 400 (función compartida)
# --------------------------------------------------------------------------- #

def test_rf40_41_42_fecha_futura_es_400() -> None:
    with pytest.raises(ValidationError) as error:
        validar_fecha_evento(AHORA + timedelta(days=2), _activo(), _EventoRepo())

    assert error.value.code == 'FECHA_FUTURA'
    assert error.value.status_code == 400


def test_rf40_41_42_fecha_anterior_al_registro_es_400() -> None:
    with pytest.raises(ValidationError) as error:
        validar_fecha_evento(datetime(2025, 12, 31, tzinfo=timezone.utc), _activo(), _EventoRepo())

    assert error.value.status_code == 400


def test_rf40_41_42_fecha_coherente_pasa() -> None:
    validar_fecha_evento(AHORA - timedelta(days=1), _activo(), _EventoRepo())


# --------------------------------------------------------------------------- #
# RF-42 — "Datos obligatorios faltantes" (padre / nº de crías) -> HTTP 400
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ('dto', 'codigo'),
    [
        pytest.param(
            RegistrarEventoReproductivoDTO(categoria='servicio', resultado='exitoso'),
            'PADRE_REQUERIDO',
            id='servicio-sin-padre',
        ),
        pytest.param(
            RegistrarEventoReproductivoDTO(categoria='parto', resultado='exitoso', numero_crias=0),
            'NUMERO_CRIAS_REQUERIDO',
            id='parto-sin-crias',
        ),
    ],
)
def test_rf42_dato_obligatorio_condicional_faltante_es_400(dto, codigo) -> None:
    uc = RegistrarEventoReproductivoUseCase(
        db=_Db(), activo_repo=_ActivoRepo(_activo()), evento_repo=_EventoRepo(), infra_port=None,
    )

    with pytest.raises(ValidationError) as error:
        uc.execute(10, dto, USUARIO)

    assert error.value.code == codigo
    assert error.value.status_code == 400


# --------------------------------------------------------------------------- #
# RF-43 — E-05 fecha, E-06 cantidad, E-07 unidad -> HTTP 422
# --------------------------------------------------------------------------- #

class _Parametros:
    def obtener_metrica_productiva(self, *_args) -> MetricaProductiva:
        return MetricaProductiva(
            id_metrica_produccion=1, tipo_producto='LECHE', unidad_medida='L', aplica_a_tipo_activo='INDIVIDUAL',
        )


class _Ciclo:
    def metrica_habilitada_en_ciclo(self, *_args) -> bool:
        return True


def _registrar_productivo(**campos):
    base = dict(tipo_producto='LECHE', cantidad_producida=Decimal('12'), unidad_medida='L', fecha_evento=date(2026, 2, 1))
    base.update(campos)
    uc = RegistrarEventoProductivoUseCase(
        db=_Db(), activo_repo=_ActivoRepo(_activo()), evento_repo=_EventoRepo(),
        parametros_port=_Parametros(), ciclo_port=_Ciclo(),
    )
    return uc.execute(10, RegistrarEventoProductivoDTO(**base), USUARIO)


@pytest.mark.parametrize(
    ('campos', 'codigo'),
    [
        pytest.param({'fecha_evento': PASADO_MANANA}, 'FECHA_FUTURA', id='E-05-futura'),
        pytest.param({'fecha_evento': date(2025, 12, 1)}, 'FECHA_ANTERIOR_INICIO_ACTIVO', id='E-05-anterior'),
        pytest.param({'cantidad_producida': Decimal('0')}, 'CANTIDAD_INVALIDA', id='E-06-cero'),
        pytest.param({'cantidad_producida': Decimal('-3')}, 'CANTIDAD_INVALIDA', id='E-06-negativa'),
        pytest.param({'unidad_medida': 'kg'}, 'UNIDAD_MEDIDA_INCOMPATIBLE', id='E-07'),
    ],
)
def test_rf43_error_de_validacion_es_422(campos, codigo) -> None:
    with pytest.raises(BusinessRuleError) as error:
        _registrar_productivo(**campos)

    assert error.value.code == codigo
    assert error.value.status_code == 422


def test_rf43_cantidad_invalida_ya_no_la_rechaza_el_dto() -> None:
    dto = RegistrarEventoProductivoDTO(
        tipo_producto='LECHE', cantidad_producida=Decimal('0'), unidad_medida='L', fecha_evento=date(2026, 2, 1),
    )
    assert dto.cantidad_producida == 0


# --------------------------------------------------------------------------- #
# RF-44 — E-05 fecha futura, E-06 motivo vacío, E-07 CERRADO/BAJA -> HTTP 422
# --------------------------------------------------------------------------- #

class _HistoricoRepo:
    def __init__(self) -> None:
        self.registros: list[dict] = []

    def registrar(self, **kwargs):
        self.registros.append(kwargs)
        return SimpleNamespace(id_historico=len(self.registros), **kwargs)


def _cambiar_estado(estado: str = 'INACTIVO', **campos):
    base = dict(estado_nuevo=estado, fecha_cambio_estado=AHORA.date(), motivo_cambio='revisión')
    base.update(campos)
    historico = _HistoricoRepo()
    uc = CambiarEstadoUseCase(db=_Db(), repo=_ActivoRepo(_activo()), historico_repo=historico)
    uc.execute(10, CambiarEstadoDTO(**base), USUARIO)
    return historico


@pytest.mark.parametrize(
    ('estado', 'campos', 'codigo'),
    [
        pytest.param('INACTIVO', {'fecha_cambio_estado': PASADO_MANANA}, 'FECHA_FUTURA', id='E-05'),
        pytest.param('INACTIVO', {'motivo_cambio': '   '}, 'MOTIVO_REQUERIDO', id='E-06'),
        pytest.param('CERRADO', {}, 'VALIDACIONES_PREVIAS_REQUERIDAS', id='E-07-cerrado'),
        pytest.param('BAJA', {}, 'VALIDACIONES_PREVIAS_REQUERIDAS', id='E-07-baja'),
    ],
)
def test_rf44_flujo_alterno_de_validacion_es_422(estado, campos, codigo) -> None:
    with pytest.raises(BusinessRuleError) as error:
        _cambiar_estado(estado, **campos)

    assert error.value.code == codigo
    assert error.value.status_code == 422


def test_rf44_cambio_valido_guarda_el_motivo_sin_espacios() -> None:
    historico = _cambiar_estado('INACTIVO', motivo_cambio='  revisión  ')

    assert historico.registros[0]['motivo'] == 'revisión'


# --------------------------------------------------------------------------- #
# RF-46 — E-03 filtro de fecha inválido -> HTTP 422, sin ejecutar consulta
# --------------------------------------------------------------------------- #

def test_rf46_rango_invertido_es_422_sin_tocar_la_bd() -> None:
    uc = ConsultarHistorialUseCase(db=None, activo_repo=_NoDebeLlamarse(), transferencia_repo=_NoDebeLlamarse())
    dto = ConsultarHistorialDTO(fecha_inicio=date(2026, 9, 10), fecha_fin=date(2026, 9, 9))

    with pytest.raises(BusinessRuleError) as error:
        uc.execute(10, dto, USUARIO)

    assert error.value.code == 'RANGO_FECHAS_INVALIDO'
    assert error.value.status_code == 422


# --------------------------------------------------------------------------- #
# RF-47 — E-03 módulo fuente no disponible -> HTTP 200 con la sección degradada
# --------------------------------------------------------------------------- #

class _DbFicha:
    """La vista de sanitarios falla; todo lo demás responde vacío."""

    def begin_nested(self):
        return contextlib.nullcontext()

    def execute(self, sentencia, _params=None):
        sql = str(sentencia)
        if 'vw_rf46_eventos_sanitarios' in sql:
            raise ProgrammingError(sql, {}, Exception('relation does not exist'))
        if 'vw_rf47_ficha_integral_activo' in sql:
            fila = SimpleNamespace(
                codigo='A-10', tipo='INDIVIDUAL', especie='Bovino', fecha_registro=None, dias_en_sistema=1,
                estado_actual='ACTIVO', infraestructura_asociada=None, fase_productiva_activa=None, raza=None,
                sexo=None, fecha_nacimiento=None, peso_actual=None, unidad_peso=None, fecha_ultimo_peso=None,
                cantidad_actual=None, biomasa_total=None,
            )
            return SimpleNamespace(fetchone=lambda: fila)
        return SimpleNamespace(fetchall=lambda: [])


def test_rf47_seccion_caida_no_tumba_la_ficha() -> None:
    uc = ConsultarFichaIntegralUseCase(db=_DbFicha(), activo_repo=_ActivoRepo(_activo()))

    ficha = uc.execute(10, USUARIO)

    assert ficha.eventos_sanitarios == []
    assert ficha.advertencias == ['La sección Eventos sanitarios no pudo cargarse en este momento.']


# --------------------------------------------------------------------------- #
# RF-50 — "Fallo de normalización de datos" -> HTTP 500
# --------------------------------------------------------------------------- #

class _IndicadoresConsolidados:
    def __init__(self, metricas: dict) -> None:
        self.metricas = metricas

    def obtener_datos_consolidados(self, **_kwargs) -> DatosConsolidados:
        return DatosConsolidados(
            id_activo_biologico=10, identificador='A-10', tipo_activo='INDIVIDUAL', especie='Bovino',
            estado_actual='ACTIVO', infraestructura_asociada=None, fase_productiva_activa=None,
            fecha_generacion=AHORA, secciones=SeccionDatosConsolidados(metricas_actuales=self.metricas),
        )


def _consolidar(metricas: dict) -> DatosConsolidados:
    uc = ConsultarDatosConsolidadosUseCase(
        db=None, activo_repo=_ActivoRepo(_activo()), indicadores_repo=_IndicadoresConsolidados(metricas),
    )
    return uc.execute(10, DatosConsolidadosDTO(tipo_dato='metricas'), USUARIO)


@pytest.mark.parametrize('campo', ['peso_actual', 'biomasa_total', 'cantidad_actual'])
def test_rf50_metrica_fisicamente_imposible_es_500(campo) -> None:
    with pytest.raises(InfrastructureError) as error:
        _consolidar({campo: -1})

    assert error.value.code == 'METRICAS_CORRUPTAS'
    assert error.value.status_code == 500


def test_rf50_metricas_validas_o_ausentes_pasan() -> None:
    resultado = _consolidar({'peso_actual': 420.5, 'biomasa_total': None, 'cantidad_actual': 0})

    assert resultado.secciones.metricas_actuales['peso_actual'] == 420.5


# --------------------------------------------------------------------------- #
# RF-51 — división por cero -> 409, outliers -> 500, datos insuficientes -> 422
# --------------------------------------------------------------------------- #

class _IndicadoresNoDisponibles:
    def __init__(self, causa: str | None) -> None:
        self.causa = causa

    def calcular_indicadores(self, **kwargs) -> ResultadoIndicadores:
        return ResultadoIndicadores(
            id_activo_biologico=kwargs['id_activo'],
            tipo_activo=kwargs['tipo_activo'],
            indicadores=[
                IndicadorZootecnico(
                    tipo='conversion_alimenticia', unidad='kg_alimento/kg_ganancia', fecha_calculo=AHORA,
                    disponible=False, causa_no_disponible=self.causa,
                )
            ],
            advertencias=['DATOS_INSUFICIENTES: detalle del repositorio.'],
        )


@pytest.mark.parametrize(
    ('causa', 'clase', 'codigo', 'http'),
    [
        pytest.param('CONSUMO_CERO', ConflictError, 'CONSUMO_ALIMENTO_CERO', 409, id='division-por-cero'),
        pytest.param('OUTLIER_CRITICO', InfrastructureError, 'OUTLIER_CRITICO', 500, id='outlier'),
        pytest.param(None, BusinessRuleError, 'INDICADOR_NO_DISPONIBLE', 422, id='datos-insuficientes'),
    ],
)
def test_rf51_cada_causa_tiene_su_http(causa, clase, codigo, http) -> None:
    uc = ConsultarIndicadoresUseCase(
        db=None, activo_repo=_ActivoRepo(_activo()), indicadores_repo=_IndicadoresNoDisponibles(causa),
        historico_repo=_NoDebeLlamarse(),
    )

    with pytest.raises(clase) as error:
        uc.execute(10, ConsultarIndicadoresDTO(tipo_indicador='EFICIENCIA'), USUARIO)

    assert error.value.code == codigo
    assert error.value.status_code == http


def test_rf51_con_todos_no_se_rechaza_por_un_indicador() -> None:
    uc = ConsultarIndicadoresUseCase(
        db=None, activo_repo=_ActivoRepo(_activo()), indicadores_repo=_IndicadoresNoDisponibles('OUTLIER_CRITICO'),
        historico_repo=_NoDebeLlamarse(),
    )

    resultado = uc.execute(10, ConsultarIndicadoresDTO(tipo_indicador='TODOS'), USUARIO)

    assert resultado.advertencias


# --------------------------------------------------------------------------- #
# RF-52 E2 — evento con esquema incompleto: se persiste marcado, no se rechaza
# --------------------------------------------------------------------------- #

class _SesionQueGuarda:
    def __init__(self) -> None:
        self.filas: list = []

    def add(self, fila) -> None:
        self.filas.append(fila)

    def flush(self) -> None:
        pass


def _evento(**campos) -> EventoAuditoria:
    base = dict(
        rf_origen='RF43', tipo_evento='EVENTO_PRODUCTIVO_REGISTRADO',
        clasificacion_biologica='TRANSFORMACION_BIOLOGICA', timestamp_evento=AHORA, id_activo_biologico=10,
    )
    base.update(campos)
    return EventoAuditoria(**base)


def test_rf52_e2_evento_sin_activo_se_persiste_como_incompleto() -> None:
    sesion = _SesionQueGuarda()

    SqlAlchemyBitacoraAuditoriaRepository(sesion).registrar(_evento(id_activo_biologico=None))

    fila = sesion.filas[0]
    assert fila.registro_incompleto is True
    assert 'activo_biologico_id' in fila.detalle_tecnico['causas_registro_incompleto'][0]


@pytest.mark.parametrize(
    'evento',
    [
        pytest.param(_evento(), id='transformacion-con-activo'),
        pytest.param(
            _evento(clasificacion_biologica='GESTION_OPERATIVA', id_activo_biologico=None),
            id='operativo-sin-activo',
        ),
    ],
)
def test_rf52_e2_evento_completo_no_se_marca(evento) -> None:
    sesion = _SesionQueGuarda()

    SqlAlchemyBitacoraAuditoriaRepository(sesion).registrar(evento)

    assert sesion.filas[0].registro_incompleto is False


# --------------------------------------------------------------------------- #
# RF-52 E1 — bitácora caída: buffer y recuperación en orden, sin pérdida
# --------------------------------------------------------------------------- #

class _BitacoraCaida:
    def registrar(self, _evento) -> None:
        raise RuntimeError('bitácora no disponible')


class _Bitacora:
    def __init__(self, falla_en_llamada: int | None = None) -> None:
        self.eventos: list[EventoAuditoria] = []
        self.falla_en_llamada = falla_en_llamada

    def registrar(self, evento: EventoAuditoria) -> None:
        if len(self.eventos) + 1 == self.falla_en_llamada:
            raise RuntimeError('se cayó otra vez')
        self.eventos.append(evento)


def test_rf52_e1_al_recuperarse_persiste_el_buffer_en_orden_cronologico() -> None:
    db = _Db()
    tarde = _evento(tipo_evento='TARDE', timestamp_evento=AHORA - timedelta(minutes=1))
    temprano = _evento(tipo_evento='TEMPRANO', timestamp_evento=AHORA - timedelta(minutes=5))
    registrar_evento_bitacora(_BitacoraCaida(), db, tarde)
    registrar_evento_bitacora(_BitacoraCaida(), db, temprano)
    assert bitacora._buffer().exists()

    repo = _Bitacora()
    registrar_evento_bitacora(repo, db, _evento(tipo_evento='ACTUAL'))

    assert [e.tipo_evento for e in repo.eventos] == ['ACTUAL', 'TEMPRANO', 'TARDE', 'INDISPONIBILIDAD_AUDITORIA']
    periodo = repo.eventos[-1].detalle_tecnico
    assert periodo['eventos_recuperados'] == 2
    assert periodo['desde'] < periodo['hasta']
    assert not bitacora._buffer().exists()
    assert not bitacora._en_proceso().exists()


def test_rf52_e1_si_la_recuperacion_falla_el_buffer_se_conserva() -> None:
    db = _Db()
    registrar_evento_bitacora(_BitacoraCaida(), db, _evento(tipo_evento='PENDIENTE'))

    # La escritura actual entra; la recuperación del pendiente vuelve a fallar.
    registrar_evento_bitacora(_Bitacora(falla_en_llamada=2), db, _evento(tipo_evento='ACTUAL'))

    pendientes = [json.loads(l)['evento']['tipo_evento'] for l in bitacora._en_proceso().read_text().splitlines()]
    assert pendientes == ['PENDIENTE']

    # El siguiente intento lo recupera junto con lo que se haya encolado después.
    registrar_evento_bitacora(_BitacoraCaida(), db, _evento(tipo_evento='OTRO_PENDIENTE'))
    repo = _Bitacora()
    bitacora.procesar_buffer_bitacora(repo, db)
    assert [e.tipo_evento for e in repo.eventos][:2] == ['PENDIENTE', 'OTRO_PENDIENTE']


# --------------------------------------------------------------------------- #
# RF-52 E3 — tormenta de eventos: INFO a la cola, lo prioritario inmediato
# --------------------------------------------------------------------------- #

class _Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _con_umbral(monkeypatch, umbral: float = 1.0) -> _Reloj:
    """Ventana de 1 s y umbral de 1 evento/s: el segundo evento del mismo instante ya es tormenta."""
    reloj = _Reloj()
    monkeypatch.setattr(bitacora, '_control', bitacora.ControlCarga(umbral=umbral, ventana_segundos=1.0, reloj=reloj))
    return reloj


def _info(tipo: str) -> EventoAuditoria:
    return _evento(tipo_evento=tipo, clasificacion_biologica='ACCESO_DATOS', severidad_log='INFO')


def test_rf52_e3_carga_normal_escribe_todo_en_el_momento(monkeypatch) -> None:
    reloj = _con_umbral(monkeypatch)
    repo = _Bitacora()

    for i in range(3):
        reloj.t = i * 2.0  # un evento cada 2 s: siempre por debajo de 1/s
        registrar_evento_bitacora(repo, _Db(), _info(f'INFO_{i}'))

    assert [e.tipo_evento for e in repo.eventos] == ['INFO_0', 'INFO_1', 'INFO_2']
    assert not bitacora._buffer().exists()


def test_rf52_e3_tormenta_encola_info_y_escribe_lo_prioritario(monkeypatch) -> None:
    _con_umbral(monkeypatch)
    repo = _Bitacora()
    db = _Db()

    registrar_evento_bitacora(repo, db, _info('INFO_1'))
    registrar_evento_bitacora(repo, db, _info('INFO_2'))  # supera el umbral: empieza la tormenta
    registrar_evento_bitacora(repo, db, _evento(tipo_evento='TRANSFORMACION'))
    registrar_evento_bitacora(repo, db, _evento(
        tipo_evento='ERROR_OPERATIVO', clasificacion_biologica='GESTION_OPERATIVA', severidad_log='ERROR',
    ))

    assert [e.tipo_evento for e in repo.eventos] == [
        'INFO_1', 'ALTA_CARGA_AUDITORIA_INICIO', 'TRANSFORMACION', 'ERROR_OPERATIVO',
    ]
    encolados = [json.loads(l) for l in bitacora._buffer().read_text().splitlines()]
    assert [(l['evento']['tipo_evento'], l['motivo']) for l in encolados] == [('INFO_2', 'ALTA_CARGA')]


def test_rf52_e3_la_tarea_periodica_persiste_el_lote_y_cierra_el_episodio(monkeypatch) -> None:
    reloj = _con_umbral(monkeypatch)
    repo = _Bitacora()
    db = _Db()
    for i in range(4):
        registrar_evento_bitacora(repo, db, _info(f'INFO_{i}'))

    reloj.t = 10.0  # la ráfaga pasó
    bitacora.procesar_buffer_bitacora(repo, db)

    tipos = [e.tipo_evento for e in repo.eventos]
    assert tipos[:2] == ['INFO_0', 'ALTA_CARGA_AUDITORIA_INICIO']
    assert tipos[2] == 'ALTA_CARGA_AUDITORIA_FIN'
    assert repo.eventos[2].detalle_tecnico['eventos_encolados'] == 3
    assert sorted(tipos[3:]) == ['INFO_1', 'INFO_2', 'INFO_3']
    assert 'INDISPONIBILIDAD_AUDITORIA' not in tipos  # encolar por carga no es una caída
    assert not bitacora._buffer().exists()


# --------------------------------------------------------------------------- #
# RF-52 E5 (llave) — cada fila del historial RF-46 queda referenciada en la bitácora
# --------------------------------------------------------------------------- #

class _EventoRepoQueGuarda(_EventoRepo):
    def guardar(self, evento):
        evento.id_eventos = 77
        return evento


def test_rf52_e5_el_evento_registrado_lleva_la_llave_de_su_fila_rf46() -> None:
    bitacora_repo = _Bitacora()
    uc = RegistrarEventoProductivoUseCase(
        db=_Db(), activo_repo=_ActivoRepo(_activo()), evento_repo=_EventoRepoQueGuarda(),
        parametros_port=_Parametros(), ciclo_port=_Ciclo(), bitacora_repo=bitacora_repo,
    )

    uc.execute(10, RegistrarEventoProductivoDTO(
        tipo_producto='LECHE', cantidad_producida=Decimal('12'), unidad_medida='L', fecha_evento=date(2026, 2, 1),
    ), USUARIO)

    registrado = next(e for e in bitacora_repo.eventos if e.tipo_evento == 'EVENTO_PRODUCTIVO_REGISTRADO')
    assert registrado.detalle_tecnico['registros_rf46'] == [{'tabla': 'eventos_activos', 'id': 77}]


class _ActivoRepoConFases(_ActivoRepo):
    def obtener_gestiones_fases(self, _id: int):
        return [SimpleNamespace(id_ciclo_productiva=3)]

    def cerrar_gestion_activa(self, *_args) -> None:
        pass

    def crear_gestion_fase(self, gestion):
        gestion.id_gestion_fases = 55
        return gestion


class _CicloConFases:
    def obtener_ciclo_con_fases(self, _id: int) -> CicloProductivoConsulta:
        return CicloProductivoConsulta(id_ciclo_productivo=3, nombre='Engorde', fases=[
            FaseCiclo(id_ciclos_productivo_biologico=1, id_ciclo_biologico=1, nombre_fase='Juvenil', duracion_dias=30),
            FaseCiclo(id_ciclos_productivo_biologico=2, id_ciclo_biologico=2, nombre_fase='Adulto', duracion_dias=60),
        ])


def test_rf52_e5_el_avance_automatico_de_fase_queda_en_la_bitacora() -> None:
    """Antes, el avance de fase disparado por un evento de crecimiento creaba la fila
    de gestiones_fases (historial RF-46) sin ningún registro en la bitácora."""
    bitacora_repo = _Bitacora()
    uc = RegistrarEventoCrecimientoUseCase(
        db=_Db(), activo_repo=_ActivoRepoConFases(_activo()), evento_repo=None, infra_port=None,
        parametros_port=None, ciclo_port=_CicloConFases(), bitacora_repo=bitacora_repo,
    )
    fase = SimpleNamespace(id_ciclo_productiva=3, fecha_inicio=datetime(2026, 1, 1, tzinfo=timezone.utc))

    avanzo = uc._evaluar_avance_fase(10, fase, datetime(2026, 3, 1, tzinfo=timezone.utc), USUARIO)

    assert avanzo is True
    [evento] = bitacora_repo.eventos
    assert evento.tipo_evento == 'FASE_AVANZADA_AUTOMATICAMENTE'
    assert evento.detalle_tecnico['registros_rf46'] == [{'tabla': 'gestiones_fases', 'id': 55}]
