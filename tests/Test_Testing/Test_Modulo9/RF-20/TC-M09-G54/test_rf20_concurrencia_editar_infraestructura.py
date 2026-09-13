"""RF-20 — TC-M09-G54 (TC-M09-106): dos ediciones simultáneas sobre la misma
área productiva.

`EditarInfraestructuraUseCase` aplica concurrencia optimista (FA-14) comparando
el `fecha_actualizacion` del DTO contra el valor real en BD -mismo mecanismo
que TC-M09-G39 verificó para RF-18-. Pero a diferencia de esa prueba, aquí
**ninguna de las dos ediciones concurrentes llega a completarse**: el propio
`EditarInfraestructuraUseCase` revalida `tipo_area` contra
`modulo9.tipos_area` (línea 73) *después* del chequeo de concurrencia pero
*antes* de persistir, y esa tabla no existe en el servidor de test compartido
(mismo gap que bloquea TC-M09-G48/TC-M09-50, ver
`tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G48/NOTA_BLOQUEO.md`).

Esta prueba reproduce dos solicitudes reales concurrentes -dos `Session` de
SQLAlchemy independientes, mismo patrón que TC-M09-G39- para confirmar
exactamente qué pasa hoy: como la primera edición nunca llega a persistir
(revienta en la validación de `tipo_area`), el `fecha_actualizacion` de la
fila nunca avanza, así que la segunda edición ve la misma marca de tiempo
"vigente" que la primera y *también* pasa el chequeo de concurrencia -para
después reventar en el mismo punto-. El resultado observable hoy es que
**ambas** ediciones fallan con el mismo error de esquema, no que una gane y
la otra reciba 412: el control de concurrencia en sí no se puede ejercitar
mientras el catálogo de tipos de área no exista en este entorno.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _hay_tabla_tipos_area(db_session: Session) -> bool:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'modulo9' AND table_name = 'tipos_area'")
    ).first()
    return existe is not None


def _preparar_finca_e_infraestructura(db_session: Session, id_usuario: int):
    """Inserta una finca y un área productiva directamente por SQL -evita
    `RegistrarFincaUseCase`/`RegistrarInfraestructuraUseCase` porque el
    segundo está bloqueado por el mismo gap que esta prueba investiga."""
    id_finca = db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo, id_usuario)
            VALUES (:nombre, CAST(:ubicacion AS jsonb), 10.00, now(), now(), true, :id_usuario)
            RETURNING id_finca
            """
        ),
        {
            "nombre": "Finca Concurrencia Infraestructura",
            "ubicacion": '{"departamento": "Huila", "municipio": "Neiva", "vereda": "El Centro", "latitud": "2.93", "longitud": "-75.28"}',
            "id_usuario": id_usuario,
        },
    ).scalar_one()

    id_infraestructura = db_session.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (nombre, tipo, superficie, id_finca, descripcion, es_activo, fecha_actualizacion)
            VALUES (:nombre, CAST(:tipo AS modulo9.enum_tipo_infraestructura), :superficie, :id_finca, :descripcion, true, NULL)
            RETURNING id_infraestructura
            """
        ),
        {
            "nombre": "Area Concurrencia Test",
            "tipo": "galpon",
            "superficie": 100.00,
            "id_finca": id_finca,
            "descripcion": "Area de prueba para TC-M09-106",
        },
    ).scalar_one()

    db_session.flush()
    return id_infraestructura


def test_TC_M09_106_ambas_ediciones_concurrentes_fallan_por_el_gap_de_tipos_area(
    db_session: Session, crear_usuario_db
) -> None:
    from src.configuration.application.use_cases.infraestructuras.editar_infraestructura_use_case import (
        EditarInfraestructuraUseCase,
    )
    from src.configuration.infrastructure.dto.editar_infraestructura_dto import EditarInfraestructuraDTO
    from src.configuration.infrastructure.repositories.auditoria_infraestructura_repository import (
        SqlAlchemyAuditoriaInfraestructuraRepository,
    )
    from src.configuration.infrastructure.repositories.finca_repository import SqlAlchemyFincaRepository
    from src.configuration.infrastructure.repositories.infraestructura_repository import (
        SqlAlchemyInfraestructuraRepository,
    )
    from src.configuration.infrastructure.repositories.tipo_area_repository import SqlAlchemyTipoAreaRepository
    from src.identity_access.infrastructure.dependencies import UsuarioActual

    if _hay_tabla_tipos_area(db_session):
        pytest.skip(
            "modulo9.tipos_area ya existe en esta base -el gap de TC-M09-G48 fue resuelto-; "
            "esta prueba quedó escrita para el escenario bloqueado y debe reescribirse para "
            "ejercer la concurrencia real una vez la migración esté aplicada."
        )

    admin1 = crear_usuario_db(id_rol=1, estado=2)
    admin2 = crear_usuario_db(id_rol=1, estado=2)
    id_infraestructura = _preparar_finca_e_infraestructura(db_session, id_usuario=admin1["id_usuario"])
    db_session.commit()

    def _armar_use_case(session: Session) -> EditarInfraestructuraUseCase:
        return EditarInfraestructuraUseCase(
            db=session,
            infra_repo=SqlAlchemyInfraestructuraRepository(session),
            finca_repo=SqlAlchemyFincaRepository(session),
            tipo_area_repo=SqlAlchemyTipoAreaRepository(session),
            auditoria_repo=SqlAlchemyAuditoriaInfraestructuraRepository(session),
        )

    # Ambas "solicitudes" parten del mismo fecha_actualizacion (None: el area
    # nunca ha sido editada), como si dos administradores hubieran abierto la
    # pantalla de edicion al mismo tiempo.
    sesion_a = Session(bind=db_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint")
    dto_a = EditarInfraestructuraDTO(
        nombre_infraestructura="Area Editada Admin A", tipo_area="galpon", superficie="150.00", fecha_actualizacion=None
    )
    usuario_a = UsuarioActual(id_usuario=admin1["id_usuario"], id_token=1, id_rol=1)

    with pytest.raises(ProgrammingError, match="tipos_area"):
        _armar_use_case(sesion_a).execute(id_infraestructura, dto_a, usuario_a)
    sesion_a.rollback()

    sesion_b = Session(bind=db_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint")
    dto_b = EditarInfraestructuraDTO(
        nombre_infraestructura="Area Editada Admin B", tipo_area="galpon", superficie="200.00", fecha_actualizacion=None
    )
    usuario_b = UsuarioActual(id_usuario=admin2["id_usuario"], id_token=2, id_rol=1)

    # Si el control de concurrencia funcionara de forma aislada del gap de
    # tipos_area, aqui esperariamos 412 (la "primera" ya habria avanzado el
    # timestamp). En cambio, como A nunca persistio nada, B ve el mismo
    # fecha_actualizacion=None y TAMBIEN pasa el chequeo de concurrencia,
    # revientando en el mismo punto que A.
    with pytest.raises(ProgrammingError, match="tipos_area"):
        _armar_use_case(sesion_b).execute(id_infraestructura, dto_b, usuario_b)
    sesion_b.rollback()

    # Ninguna de las dos edito nada: el area sigue con sus valores originales.
    fila = db_session.execute(
        text("SELECT nombre, superficie FROM modulo9.infraestructuras WHERE id_infraestructura = :id"),
        {"id": id_infraestructura},
    ).one()
    assert fila.nombre == "Area Concurrencia Test"
    assert str(fila.superficie) == "100.00"
