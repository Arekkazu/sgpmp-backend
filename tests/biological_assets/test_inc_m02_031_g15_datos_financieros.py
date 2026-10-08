"""TC-M02-031-G15 / #465: protección de datos financieros del activo."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module
from src.identity_access.infrastructure.dependencies import UsuarioActual


class DbFake:
    pass


def _activo(id_activo: int = 51) -> ActivoBiologico:
    return ActivoBiologico(
        id_activo_biologico=id_activo,
        id_especie=2,
        tipo='INDIVIDUAL',
        identificador=f'RF34-{id_activo}',
        fecha_inicio_ciclo=date(2026, 9, 1),
        detalles_procedencia='Compra documentada',
        origen_financiero='COMPRA',
        costo_adquisicion=Decimal('1500000.0000'),
        soporte_documental='soporte_TC-M02-031.pdf',
        descripcion='Activo autorizado para el Ingeniero',
        id_infraestructura=1,
        atributos_dinamicos={},
        id_estado=1,
        nombre_estado='ACTIVO',
        id_usuario=2,
        fecha_creacion=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )


def _usuario(id_rol: int = 4) -> UsuarioActual:
    return UsuarioActual(
        id_usuario=4,
        id_token=1,
        id_rol=id_rol,
        id_estado_cuenta=2,
    )


def test_serializador_oculta_datos_financieros_por_defecto() -> None:
    respuesta = router_module._activo_to_response(_activo())

    assert respuesta.id_activo_biologico == 51
    assert respuesta.identificador == 'RF34-51'
    assert respuesta.costo_adquisicion is None
    assert respuesta.soporte_documental is None


def test_serializador_con_permiso_conserva_datos_financieros() -> None:
    respuesta = router_module._activo_to_response(
        _activo(),
        incluir_datos_financieros=True,
    )

    assert respuesta.costo_adquisicion == Decimal('1500000.0000')
    assert respuesta.soporte_documental == 'soporte_TC-M02-031.pdf'


@pytest.mark.parametrize(
    ('tiene_permiso', 'costo_esperado', 'soporte_esperado'),
    [
        (False, None, None),
        (True, Decimal('1500000.0000'), 'soporte_TC-M02-031.pdf'),
    ],
)
def test_detalle_evalua_permiso_financiero_sin_hardcodear_rol(
    monkeypatch: pytest.MonkeyPatch,
    tiene_permiso: bool,
    costo_esperado: Decimal | None,
    soporte_esperado: str | None,
) -> None:
    monkeypatch.setattr(
        router_module.ConsultarActivoUseCase,
        'execute',
        lambda *args, **kwargs: _activo(),
    )
    monkeypatch.setattr(router_module, '_ids_fincas_alcance', lambda *args: [1])
    consultas_permiso: list[tuple[int, str, int]] = []

    def permiso(_db, id_rol: int, recurso: str, accion: int) -> bool:
        consultas_permiso.append((id_rol, recurso, accion))
        return tiene_permiso

    monkeypatch.setattr(router_module, 'tiene_permiso_sobre', permiso)

    respuesta = router_module.consultar_activo(
        id_activo=51,
        db=DbFake(),
        usuario_actual=_usuario(),
    )

    assert respuesta.costo_adquisicion == costo_esperado
    assert respuesta.soporte_documental == soporte_esperado
    assert consultas_permiso == [(4, 'datos_financieros_activo', 2)]


def test_listado_aplica_el_mismo_permiso_a_todos_los_activos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    activos = [_activo(51), _activo(57)]
    monkeypatch.setattr(
        router_module.ListarActivosUseCase,
        'execute',
        lambda *args, **kwargs: (activos, 2),
    )
    monkeypatch.setattr(router_module, '_ids_fincas_alcance', lambda *args: [1])
    monkeypatch.setattr(router_module, 'tiene_permiso_sobre', lambda *args: False)
    monkeypatch.setattr(router_module, '_completar_nombres_catalogo', lambda *args: None)

    respuesta = router_module.listar_activos(
        tipo=None,
        id_especie=None,
        id_estado=None,
        id_infraestructura=None,
        pagina=1,
        page_size=20,
        db=DbFake(),
        usuario_actual=_usuario(),
    )

    assert respuesta.total_registros == 2
    assert [item.costo_adquisicion for item in respuesta.registros] == [None, None]
    assert [item.soporte_documental for item in respuesta.registros] == [None, None]
