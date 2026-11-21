# | Fecha      | Nombre       | Que se hizo                                                                  |
# |------------|--------------|------------------------------------------------------------------------------|
# | 2026-11-21 | destroyerban | INC-M08-380-G002 RF-103: el Productor ve el valor del inventario de su finca |
"""INC-M08-380-G002 (#1196) contra PostgreSQL con RLS (rol ``sgpmp_app``).

El widget «Valor del inventario» del Productor salía en $0: los reconocimientos y valoraciones de
``modulo6`` solo los deja leer la RLS a quien lee la valoración en Finanzas. El widget los lee ahora
como sistema y los acota a las fincas del usuario.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.infrastructure.repositories.dashboard_layout_repository import SqlAlchemyDashboardLayoutRepository
from src.configuration.infrastructure.repositories.widget_repository import SqlAlchemyWidgetRepository
from src.financial_valuation.infrastructure.repositories.valoracion_repository import SqlAlchemyValoracionRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.reporting.application.use_cases.dashboard.obtener_datos_widget_use_case import ObtenerDatosWidgetUseCase
from src.reporting.infrastructure.repositories.datos_widget_repository import SqlAlchemyDatosWidgetRepository
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import declarar_identidad
from src.shared.errors import AuthorizationError

pytestmark = pytest.mark.integration

FINCA, OTRA_FINCA, AREA, OTRA_AREA, ESPECIE, ANIMAL, OTRO_ANIMAL, PERIODO = (
    8201, 8202, 8201, 8202, 8201, 8201, 8202, 8201)
NIT = "901999777"


def _sembrar(db: Session) -> None:
    """Un animal valorado en la finca del Productor y otro en una finca ajena."""
    db.execute(text("SET LOCAL session_replication_role = replica"))
    sql = f"""
    INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
        VALUES (1, 'ACTIVO') ON CONFLICT DO NOTHING;
    INSERT INTO modulo9.fincas (id_finca, nombre, razon_social, numero_id_tributaria, dv, es_activo, tipo_id_tributaria,
        ubicacion, tamano_h, fecha_creacion, fecha_actualizacion) VALUES
        ({FINCA}, 'Finca Propia', 'Agro Propia SAS', '{NIT}', '3', true, 'NIT', '{{}}', 5, now(), now()),
        ({OTRA_FINCA}, 'Finca Ajena', 'Agro Propia SAS', '{NIT}', '3', true, 'NIT', '{{}}', 5, now(), now());
    INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, es_activo, tipo, superficie) VALUES
        ({AREA}, 'Galpón P', {FINCA}, true, 'GALPON', 50), ({OTRA_AREA}, 'Galpón A', {OTRA_FINCA}, true, 'GALPON', 50);
    INSERT INTO modulo9.especies (id_especie, nombre, es_activo, fecha_creacion) VALUES ({ESPECIE}, 'Especie V', true, now());
    INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie, identificador, id_infraestructura, tipo,
        fecha_inicio_ciclo, id_estado, atributos_dinamicos, id_usuario, fecha_creacion, origen_financiero) VALUES
        ({ANIMAL}, {ESPECIE}, 'BOV-P', {AREA}, 'INDIVIDUAL', current_date - 200, 1, '{{}}', 1, now(), 'compra'),
        ({OTRO_ANIMAL}, {ESPECIE}, 'BOV-A', {OTRA_AREA}, 'INDIVIDUAL', current_date - 200, 1, '{{}}', 1, now(), 'compra');
    INSERT INTO modulo6.periodos_contables (id_periodo_contable, tipo_cierre, fecha_inicio, fecha_fin, estado,
        numero_id_tributaria, fecha_creacion, id_usuario) VALUES
        ({PERIODO}, 'MENSUAL', date_trunc('month', current_date)::date,
         (date_trunc('month', current_date) + interval '1 month - 1 day')::date, 'ABIERTO', '{NIT}', now(), 1);
    INSERT INTO modulo6.calculos_valor_razonable (id_calculo_valor_razonable, id_activo_biologico, id_precio_mercado,
        metodo_costo, valor_razonable_bruto, costo_transporte, valor_neto, estado, fecha_calculo, id_periodo_contable,
        id_usuario) VALUES
        ({ANIMAL}, {ANIMAL}, 1, 'PARAMETRIZADO', 1400000, 34527.70, 1365472.30, 'CALCULADO', now() - interval '1 day', {PERIODO}, 1),
        ({OTRO_ANIMAL}, {OTRO_ANIMAL}, 1, 'PARAMETRIZADO', 900000, 0, 900000, 'CALCULADO', now() - interval '1 day', {PERIODO}, 1);
    INSERT INTO modulo6.reconocimientos_iniciales (id_activo_biologico, clasificacion, indicador_valoracion,
        valor_razonable_neto_inicial, estado, id_usuario, id_periodo_contable, id_calculo_valor_razonable) VALUES
        ({ANIMAL}, 'PRODUCCION', 'VALOR_RAZONABLE', 1365472.30, 'CONFIRMADO', 1, {PERIODO}, {ANIMAL}),
        ({OTRO_ANIMAL}, 'PRODUCCION', 'VALOR_RAZONABLE', 900000, 'CONFIRMADO', 1, {PERIODO}, {OTRO_ANIMAL})
    """
    for sentencia in (s.strip() for s in sql.split(";")):
        if sentencia:
            db.execute(text(sentencia))
    db.execute(text("SET LOCAL session_replication_role = origin"))
    db.flush()


def _como(db: Session, usuario: dict, rol: str) -> UsuarioActual:
    """Sesión con la identidad del usuario, sujeta a RLS como en un request."""
    db.execute(text("SET LOCAL ROLE sgpmp_app"))
    declarar_identidad(db, usuario["id_usuario"], rol)
    db.connection().execute(text("SELECT set_config('app.current_user_id', :u, true), "
                                 "set_config('app.current_role', :r, true)"),
                            {"u": str(usuario["id_usuario"]), "r": rol})
    return UsuarioActual(id_usuario=usuario["id_usuario"], id_token=1, id_rol=usuario["id_rol"], id_estado_cuenta=2)


def _widget(db: Session, usuario: UsuarioActual, id_finca):
    return ObtenerDatosWidgetUseCase(
        widget_repo=SqlAlchemyWidgetRepository(db),
        dashboard_repo=SqlAlchemyDashboardLayoutRepository(db),
        datos_repo=SqlAlchemyDatosWidgetRepository(db),
        alcance=AlcanceFincaAdapter(db),
    ).execute("valor_inventario", id_finca, usuario)


def test_productor_ve_el_valor_de_su_finca_aunque_no_lea_la_valoracion(db_session: Session, crear_usuario_db):
    _sembrar(db_session)
    productor = crear_usuario_db(id_rol=2)
    db_session.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca, es_activo, fecha_creacion) "
                            "VALUES (:u, :f, true, now())"), {"u": productor["id_usuario"], "f": FINCA})
    db_session.flush()
    usuario = _como(db_session, productor, "Productor")

    # La premisa del ticket: con su sesión, la RLS de Finanzas le oculta los reconocimientos.
    assert SqlAlchemyValoracionRepository(db_session).activos_valorados() == []

    resultado = _widget(db_session, usuario, FINCA)
    assert resultado.estado == "OK"
    assert resultado.datos == {"vista": "TOTAL", "valor_total": 1365472.3, "activos": 1, "moneda": "COP"}

    # Sin finca activa: solo las fincas asignadas, nunca la ajena aunque sea del mismo titular.
    sin_finca = _widget(db_session, usuario, None)
    assert sin_finca.datos["valor_total"] == 1365472.3 and sin_finca.datos["activos"] == 1

    # Y la identidad del usuario vuelve después de la lectura como sistema.
    assert SqlAlchemyValoracionRepository(db_session).activos_valorados() == []
    db_session.execute(text("RESET ROLE"))


def test_finca_ajena_responde_403(db_session: Session, crear_usuario_db):
    _sembrar(db_session)
    productor = crear_usuario_db(id_rol=2)
    db_session.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca, es_activo, fecha_creacion) "
                            "VALUES (:u, :f, true, now())"), {"u": productor["id_usuario"], "f": FINCA})
    db_session.flush()
    usuario = _como(db_session, productor, "Productor")
    with pytest.raises(AuthorizationError):
        _widget(db_session, usuario, OTRA_FINCA)
    db_session.execute(text("RESET ROLE"))
