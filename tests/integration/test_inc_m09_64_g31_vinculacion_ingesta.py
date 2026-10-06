"""INC-M09-64-G31 (#494, RF-61 → RF-17): toda lectura nueva deja su vinculación.

Antes, la vinculación automática usaba un stub que siempre devolvía "sin
activos" y la fila resultante (INDIVIDUAL sin activo, SIN_VINCULAR) violaba
`chk_vinculacion_modelo`: rollback, warning descartado e ingesta 201 sin fila.
Sin fila no había nada que resolver, ni activo, ni especie, ni umbral RF-17.

Con la migración 0618e6f7b308 y el adaptador real de M02:
- área sin activos operativos → SIN_VINCULAR (fila válida, resoluble después);
- un activo → VINCULADA a ese animal, o a su lote si es POBLACIONAL;
- varios → AMBIGUA;
- una SIN_VINCULAR se resuelve (RF-61 C1) y dispara la reclasificación RF-17.
"""
from __future__ import annotations

import importlib
import pkgutil
import random
import string
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src
from src.telemetry.application.use_cases.infraestructura.resolver_vinculacion_use_case import (
    ResolverVinculacionUseCase,
)
from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import (
    VincularLecturaActivoUseCase,
)
from src.telemetry.infrastructure.adapters.activo_biologico_m02_adapter import ActivoBiologicoM02Adapter
from src.telemetry.infrastructure.dto.resolver_vinculacion_dto import ResolverVinculacionDTO
from src.telemetry.infrastructure.repositories.vinculacion_lectura_repository import (
    SqlAlchemyVinculacionLecturaRepository,
)

pytestmark = pytest.mark.integration

# Los repositorios necesitan todos los mappers configurados (FKs entre módulos).
for _modulo in pkgutil.walk_packages(src.__path__, "src."):
    if ".infrastructure.models." in _modulo.name:
        importlib.import_module(_modulo.name)

_ACTIVO, _EN_TRATAMIENTO, _CERRADO, _BAJA = 1, 3, 5, 6


def _letras(n: int = 10) -> str:
    return ''.join(random.choices(string.ascii_letters, k=n))


def _area(db: Session, id_usuario: int) -> int:
    sid = uuid.uuid4().int % (10**9)
    db.execute(text("SELECT set_config('app.usuario_id', :u, true)"), {'u': str(id_usuario)})
    db.execute(
        text(
            """
            INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h,
                fecha_actualizacion, fecha_creacion, es_activo)
            VALUES (:id, :nombre, '{}', 10, now(), now(), TRUE)
            """
        ),
        {'id': sid, 'nombre': f'Finca G Treinta Uno {_letras()}'},
    )
    db.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca,
                superficie, es_activo, tipo)
            VALUES (:id, :nombre, :id, 100, TRUE, 'Estanque')
            """
        ),
        {'id': sid, 'nombre': f'Estanque G31 {_letras()}'},
    )
    return sid


def _activo(db: Session, id_area: int, id_usuario: int, *, tipo: str = 'INDIVIDUAL', estado: int = _ACTIVO) -> int:
    # `pruebas` trae el catálogo; una BD vacía no. Todo activo nace ACTIVO (trigger)
    # y solo cambia de estado por historicos_estados_activos (RF-44).
    db.execute(
        text(
            """
            INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
            VALUES (1, 'ACTIVO'), (2, 'INACTIVO'), (3, 'EN_TRATAMIENTO'), (4, 'AISLADO'),
                   (5, 'CERRADO'), (6, 'BAJA')
            ON CONFLICT (id_estado_activo_biologico) DO NOTHING
            """
        )
    )
    id_activo = db.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (
                id_especie, identificador, id_infraestructura, tipo, fecha_inicio_ciclo,
                id_estado, descripcion, origen_financiero, costo_adquisicion,
                atributos_dinamicos, id_usuario, fecha_creacion, soporte_documental,
                detalles_procedencia
            ) VALUES (
                2, :identificador, :area, CAST(:tipo AS modulo2.enum_activo_biologico_tipo),
                current_date, :estado, 'Fixture INC-M09-64-G31',
                CAST('compra' AS modulo2.enum_activo_biologico_origen_financiero), 100, '{}',
                :usuario, now(), 'doc', ''
            )
            RETURNING id_activo_biologico
            """
        ),
        {
            # Un lote POBLACIONAL no lleva identificador individual (trigger de coherencia).
            'identificador': None if tipo == 'POBLACIONAL' else f'G31-{uuid.uuid4().hex[:12]}',
            'area': id_area,
            'tipo': tipo,
            'estado': _ACTIVO,
            'usuario': id_usuario,
        },
    ).scalar_one()
    if estado != _ACTIVO:
        db.execute(
            text(
                """
                INSERT INTO modulo2.historicos_estados_activos (id_activo_biologico, id_estado_nuevo,
                    id_estado_anterior, fecha_cambio, motivo_cambio, modulo_origen, id_usuario)
                VALUES (:a, :nuevo, 1, now(), 'Fixture INC-M09-64-G31', 'MANUAL', :u)
                """
            ),
            {'a': id_activo, 'nuevo': estado, 'u': id_usuario},
        )
    return id_activo


def _lectura(db: Session, id_area: int) -> tuple[int, datetime]:
    id_dispositivo = db.execute(
        text(
            """
            INSERT INTO modulo9.dispositivos_iot (serial, descripcion, es_activo, fecha_creacion,
                id_infraestructura, id_tipo_dispositivo)
            VALUES (:serial, 'Sensor G31', TRUE, now(), :area, 3)
            RETURNING id_dispositivo_iot
            """
        ),
        {'serial': f'G31-{uuid.uuid4().hex[:10]}', 'area': id_area},
    ).scalar_one()
    id_sensor = db.execute(
        text(
            "INSERT INTO modulo9.sensores (id_dispositivo_iot, es_activo, nombre) "
            "VALUES (:d, TRUE, 'Temperatura G31') RETURNING id_sensores"
        ),
        {'d': id_dispositivo},
    ).scalar_one()
    captura = datetime.now(timezone.utc) - timedelta(minutes=1)
    id_telemetria = db.execute(
        text(
            """
            INSERT INTO modulo3.telemetrias (id_sensor, id_variable, id_dispositivo_iot, valor_crudo,
                valor_ajustado, timestamp_captura, timestamp_procesamiento, origen, estado_calidad,
                metadatos, categoria_variable, unidad_medida)
            VALUES (:s, 1, :d, 15, 15, :captura, now(), 'TIEMPO_REAL', 'LECTURA_VALIDA', '{}',
                'HIDRICA', '°C')
            RETURNING id_telemetria
            """
        ),
        {'s': id_sensor, 'd': id_dispositivo, 'captura': captura},
    ).scalar_one()
    return id_telemetria, captura


def _vincular(db: Session, id_telemetria: int, id_area: int, captura: datetime):
    return VincularLecturaActivoUseCase(
        db=db,
        vinculacion_repo=SqlAlchemyVinculacionLecturaRepository(db),
        activo_port=ActivoBiologicoM02Adapter(db),
    ).execute(id_telemetria=id_telemetria, id_infraestructura=id_area, timestamp_captura=captura)


@pytest.fixture
def usuario(crear_usuario_db) -> int:
    return crear_usuario_db(id_rol=1)['id_usuario']


def _filas(db: Session, id_telemetria: int) -> list:
    return db.execute(
        text(
            "SELECT estado_vinculacion::text AS estado, id_activo_biologico, modelo_manejo::text AS modelo "
            "FROM modulo3.vinculaciones_lecturas WHERE id_telemetria = :t"
        ),
        {'t': id_telemetria},
    ).fetchall()


def test_area_sin_activos_deja_una_fila_sin_vincular(db_session: Session, usuario: int) -> None:
    area = _area(db_session, usuario)
    # Activos fuera de operación no ocupan el área (RF-61 E4).
    _activo(db_session, area, usuario, estado=_CERRADO)
    _activo(db_session, area, usuario, estado=_BAJA)
    id_telemetria, captura = _lectura(db_session, area)

    vinculacion = _vincular(db_session, id_telemetria, area, captura)

    assert vinculacion.estado_vinculacion == 'SIN_VINCULAR'
    assert [(f.estado, f.id_activo_biologico) for f in _filas(db_session, id_telemetria)] == [
        ('SIN_VINCULAR', None),
    ]


def test_un_activo_operativo_vincula_automaticamente(db_session: Session, usuario: int) -> None:
    area = _area(db_session, usuario)
    animal = _activo(db_session, area, usuario, estado=_EN_TRATAMIENTO)
    id_telemetria, captura = _lectura(db_session, area)

    _vincular(db_session, id_telemetria, area, captura)

    assert [(f.estado, f.id_activo_biologico, f.modelo) for f in _filas(db_session, id_telemetria)] == [
        ('VINCULADA', animal, 'INDIVIDUAL'),
    ]


def test_un_lote_poblacional_vincula_la_lectura_al_lote(db_session: Session, usuario: int) -> None:
    area = _area(db_session, usuario)
    lote = _activo(db_session, area, usuario, tipo='POBLACIONAL')
    id_telemetria, captura = _lectura(db_session, area)

    _vincular(db_session, id_telemetria, area, captura)

    assert [(f.estado, f.id_activo_biologico, f.modelo) for f in _filas(db_session, id_telemetria)] == [
        ('VINCULADA', lote, 'POBLACIONAL'),
    ]


def test_varios_activos_dejan_la_lectura_ambigua(db_session: Session, usuario: int) -> None:
    area = _area(db_session, usuario)
    _activo(db_session, area, usuario)
    _activo(db_session, area, usuario)
    id_telemetria, captura = _lectura(db_session, area)

    _vincular(db_session, id_telemetria, area, captura)

    assert [(f.estado, f.id_activo_biologico) for f in _filas(db_session, id_telemetria)] == [
        ('AMBIGUA', None),
    ]


class _ReclasificarSpy:
    def __init__(self) -> None:
        self.llamadas: list[tuple[int, int]] = []

    def execute(self, *, id_telemetria: int, id_activo_biologico: int) -> None:
        self.llamadas.append((id_telemetria, id_activo_biologico))


def test_sin_vincular_se_resuelve_y_dispara_la_reclasificacion_rf17(db_session: Session, usuario: int) -> None:
    area = _area(db_session, usuario)
    id_telemetria, captura = _lectura(db_session, area)
    pendiente = _vincular(db_session, id_telemetria, area, captura)
    animal = _activo(db_session, area, usuario)
    reclasificar = _ReclasificarSpy()

    resuelta = ResolverVinculacionUseCase(
        db=db_session,
        vinculacion_repo=SqlAlchemyVinculacionLecturaRepository(db_session),
        reclasificar_semaforo_use_case=reclasificar,
    ).execute(
        pendiente.id_vinculacion_lectura,
        ResolverVinculacionDTO(id_activo_biologico=animal, modelo_manejo='INDIVIDUAL'),
        id_usuario=usuario,
    )

    assert (resuelta.estado_vinculacion, resuelta.mecanismo_vinculacion) == ('VINCULADA', 'MANUAL')
    assert reclasificar.llamadas == [(id_telemetria, animal)]
    assert [(f.estado, f.id_activo_biologico) for f in _filas(db_session, id_telemetria)] == [
        ('VINCULADA', animal),
    ]


def test_una_vinculacion_individual_vigente_sigue_exigiendo_su_activo(db_session: Session, usuario: int) -> None:
    area = _area(db_session, usuario)
    id_telemetria, captura = _lectura(db_session, area)

    with pytest.raises(IntegrityError, match='ck_vinculacion_lectura_modelo_manejo'):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    """
                    INSERT INTO modulo3.vinculaciones_lecturas (id_telemetria, modelo_manejo,
                        id_activo_biologico, id_infraestructura, fecha_inicio_vinculacion,
                        mecanismo_vinculacion, estado_vinculacion)
                    VALUES (:t, 'INDIVIDUAL', NULL, :area, :captura, 'AUTOMATICA', 'VINCULADA')
                    """
                ),
                {'t': id_telemetria, 'area': area, 'captura': captura},
            )
