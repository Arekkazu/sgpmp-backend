"""RF-52 CA-10: cobertura transversal de rechazos previos a persistencia."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.biological_assets.application.use_cases.gestion._auditoria_rechazos import (
    ejecutar_con_auditoria_de_rechazo,
)
from src.biological_assets.application.use_cases.gestion.registrar_evento_productivo_use_case import (
    RegistrarEventoProductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoAuditoria,
)
from src.biological_assets.domain.repositories.parametros_especie_port import MetricaProductiva
from src.biological_assets.infrastructure.dto.registrar_evento_productivo_dto import (
    RegistrarEventoProductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoSinFase:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo

    def obtener_por_id(self, _id_activo: int) -> ActivoBiologico:
        return self.activo

    def obtener_fase_activa(self, _id_activo: int):
        return None


class ParametrosFake:
    def obtener_metrica_productiva(self, *_args) -> MetricaProductiva:
        return MetricaProductiva(
            id_metrica_produccion=1,
            tipo_producto='LECHE',
            unidad_medida='L',
            aplica_a_tipo_activo='INDIVIDUAL',
        )


class EventoRepoNoDebeGuardar:
    def guardar(self, _evento):
        raise AssertionError('El rechazo temprano no debe intentar persistir el evento.')


class CicloFake:
    def metrica_habilitada_en_ciclo(self, *_args) -> bool:
        return True


class BitacoraFake:
    def __init__(self) -> None:
        self.eventos: list[EventoAuditoria] = []

    def registrar(self, evento: EventoAuditoria) -> None:
        self.eventos.append(evento)


@pytest.mark.parametrize(
    (
        'error',
        'rf_origen',
        'tipo_evento_rechazado',
        'clasificacion',
        'tipos_por_codigo',
        'tipo_evento_esperado',
    ),
    [
        (
            BusinessRuleError('SIN_FASE_ACTIVA', 'El activo no tiene una fase activa.'),
            'RF38',
            'CIERRE_CICLO_RECHAZADO',
            'CONTROL_ESTADO',
            None,
            'CIERRE_CICLO_RECHAZADO',
        ),
        (
            BusinessRuleError('SIN_FASE_ACTIVA', 'El activo no tiene una fase activa.'),
            'RF40',
            'EVENTO_CRECIMIENTO_RECHAZADO',
            'TRANSFORMACION_BIOLOGICA',
            None,
            'EVENTO_CRECIMIENTO_RECHAZADO',
        ),
        (
            BusinessRuleError(
                'SECUENCIA_REPRODUCTIVA_INVALIDA',
                'No se puede registrar un nacimiento sin un evento previo.',
            ),
            'RF42',
            'EVENTO_REPRODUCTIVO_RECHAZADO',
            'TRANSFORMACION_BIOLOGICA',
            {'SECUENCIA_REPRODUCTIVA_INVALIDA': 'SECUENCIA_REPRODUCTIVA_VIOLADA'},
            'SECUENCIA_REPRODUCTIVA_VIOLADA',
        ),
        (
            BusinessRuleError(
                'TIPO_PRODUCTO_NO_CATALOGADO',
                'El producto no está definido para la especie.',
                'tipo_producto',
            ),
            'RF43',
            'EVENTO_PRODUCTIVO_RECHAZADO',
            'TRANSFORMACION_BIOLOGICA',
            None,
            'EVENTO_PRODUCTIVO_RECHAZADO',
        ),
    ],
    ids=['rf38-sin-fase', 'rf40-sin-fase', 'rf42-secuencia', 'rf43-catalogo'],
)
def test_registra_rechazos_tempranos_segun_catalogo_rf52(
    error: BusinessRuleError,
    rf_origen: str,
    tipo_evento_rechazado: str,
    clasificacion: str,
    tipos_por_codigo: dict[str, str] | None,
    tipo_evento_esperado: str,
) -> None:
    db = DbFake()
    bitacora = BitacoraFake()
    activo = ActivoBiologico(
        id_especie=1,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=1,
        id_usuario=2,
        id_activo_biologico=20,
    )

    def operacion():
        raise error

    with pytest.raises(type(error)) as exc:
        ejecutar_con_auditoria_de_rechazo(
            operacion,
            db=db,
            bitacora_repo=bitacora,
            obtener_activo=lambda _id: activo,
            id_activo=20,
            id_usuario=7,
            rf_origen=rf_origen,
            tipo_evento_rechazado=tipo_evento_rechazado,
            clasificacion_biologica=clasificacion,
            tipos_por_codigo=tipos_por_codigo,
        )

    assert exc.value is error
    assert len(bitacora.eventos) == 1
    auditoria = bitacora.eventos[0]
    assert auditoria.rf_origen == rf_origen
    assert auditoria.tipo_evento == tipo_evento_esperado
    assert auditoria.clasificacion_biologica == clasificacion
    assert auditoria.id_activo_biologico == 20
    assert auditoria.resultado == 'RECHAZADO'
    assert auditoria.severidad_log == 'WARNING'
    assert auditoria.detalle_tecnico['error_code'] == error.code
    assert auditoria.detalle_tecnico['causa'] == error.message
    if error.field is None:
        assert 'campo' not in auditoria.detalle_tecnico
    else:
        assert auditoria.detalle_tecnico['campo'] == error.field
    assert db.rollbacks == 1
    assert db.commits == 1


def test_sin_fase_productiva_activa_se_audita_como_rechazado() -> None:
    activo = ActivoBiologico(
        id_especie=1,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=1,
        id_usuario=2,
        id_activo_biologico=20,
    )
    db = DbFake()
    bitacora = BitacoraFake()
    use_case = RegistrarEventoProductivoUseCase(
        db=db,
        activo_repo=ActivoRepoSinFase(activo),
        evento_repo=EventoRepoNoDebeGuardar(),
        parametros_port=ParametrosFake(),
        ciclo_port=CicloFake(),
        bitacora_repo=bitacora,
    )
    dto = RegistrarEventoProductivoDTO(
        tipo_producto='LECHE',
        cantidad_producida=Decimal('2.5'),
        unidad_medida='L',
        fecha_evento=date.today(),
    )

    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(
            20,
            dto,
            UsuarioActual(id_usuario=7, id_token=1, id_rol=2),
        )

    assert exc.value.code == 'SIN_FASE_PRODUCTIVA_ACTIVA'
    assert db.rollbacks == 1
    assert db.commits == 1
    assert len(bitacora.eventos) == 1
    assert bitacora.eventos[0].rf_origen == 'RF43'
    assert bitacora.eventos[0].tipo_evento == 'EVENTO_PRODUCTIVO_RECHAZADO'
    assert bitacora.eventos[0].resultado == 'RECHAZADO'
    assert bitacora.eventos[0].detalle_tecnico['error_code'] == 'SIN_FASE_PRODUCTIVA_ACTIVA'
