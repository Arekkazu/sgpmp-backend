# | Fecha      | Nombre         | Que se hizo                                                              |
# |------------|----------------|--------------------------------------------------------------------------|
# | 2026-11-12 | LuisfNarvaez01 | INC-M05-352-G18 RF-76: fin de retiro al Veterinario y fallos en auditoría |
# | 2026-11-12 | Arekkazu       | Lote M05/M06 11-12 RF-76: el incidente se lee en palabras, sin códigos  |
"""INC-M05-352-G18 (#1072), TC-M05-G18.

Defecto 1 (S1_03): el job diario que devuelve a ACTIVO los animales con el retiro vencido avisaba
solo al Productor y solo por correo. RF-76 paso 13: «notifica internamente al Veterinario y
Productor». Ahora: correo y bandeja interna a los dos.

Defecto 2 (S3_03): si ``POST /suministros/medicamentos`` falla con 500 (cálculo de
``fecha_fin_retiro``) o 503 (BD no disponible), se revierte todo y el incidente queda en la
bitácora de M05 en una transacción aparte (CU03 FA-09/FA-13)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.supplies.application.use_cases.suministros.revertir_retiros_vencidos_use_case import (
    RevertirRetirosVencidosUseCase,
)
from tests.integration.test_m05_flujo_completo_integration import (  # noqa: F401 (fixtures)
    HOY, _catalogos, _escalar, _escenario, admin, cliente,
)

pytestmark = pytest.mark.integration

_MODULO_CORREO = "src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter.send_email"


def _medicamento(cliente, headers, esc, **cambios):
    cuerpo = {
        "id_activo_biologico": esc["activo"], "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": HOY.isoformat(), "hora_aplicacion": "08:00", "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": "5", "unidad_dosis": "ml", "periodo_retiro_dias": 5,
        "motivo_aplicacion": "Tratamiento de infección respiratoria", "costo_unitario": "2000",
        "nombre_veterinario": "Dra. Prueba",
    }
    cuerpo.update(cambios)
    return cliente.post("/suministros/medicamentos", headers=headers, json=cuerpo)


class _SesionCompartida:
    """El job abre y cierra sus sesiones; en la prueba todas son la de la transacción exterior."""

    def __init__(self, db) -> None:
        self._db = db

    def __getattr__(self, nombre):
        return getattr(self._db, nombre)

    def close(self) -> None:
        pass


def _retiro_vencido_hoy(cliente, db_session, headers, esc, id_veterinario) -> None:
    assert _medicamento(cliente, headers, esc).status_code == 201
    assert _escalar(db_session, "SELECT id_estado FROM modulo2.activos_biologicos WHERE id_activo_biologico = :a",
                    a=esc["activo"]) == 3  # EN_TRATAMIENTO
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    db_session.execute(text("""UPDATE modulo5.registros_medicamentos
                               SET fecha_fin_retiro = :hoy, id_usuario_veterinario = :vet
                               WHERE id_activo_biologico = :a"""),
                       {"hoy": HOY, "vet": id_veterinario, "a": esc["activo"]})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))


def _bandeja_fin_retiro(db_session, usuarios: list[int]) -> dict[int, str]:
    filas = db_session.execute(text("""
        SELECT n.id_usuario, n.mensaje FROM modulo1.notificaciones n
        JOIN modulo1.eventos e ON e.id_evento = n.id_evento
        JOIN modulo1.tipos_eventos t ON t.id_tipo_evento = e.tipo_evento
        WHERE t.nombre = 'FIN_PERIODO_RETIRO' AND n.id_usuario = ANY(:u)"""), {"u": usuarios}).all()
    return {f.id_usuario: f.mensaje for f in filas}


def test_fin_de_retiro_avisa_al_productor_y_al_veterinario(cliente, db_session, admin, crear_usuario_db,
                                                           monkeypatch):
    usuario, headers = admin
    veterinario = crear_usuario_db(id_rol=3, estado=2)
    esc = _escenario(db_session, usuario["id_usuario"])
    _retiro_vencido_hoy(cliente, db_session, headers, esc, veterinario["id_usuario"])
    correos: list[str] = []
    monkeypatch.setattr(_MODULO_CORREO, lambda **kw: correos.append(kw["to"]))

    assert RevertirRetirosVencidosUseCase(lambda: _SesionCompartida(db_session)).ejecutar() >= 1

    assert _escalar(db_session, "SELECT id_estado FROM modulo2.activos_biologicos WHERE id_activo_biologico = :a",
                    a=esc["activo"]) == 1  # ACTIVO por RF-44
    assert set(correos) >= {usuario["correo"], veterinario["correo"]}
    bandeja = _bandeja_fin_retiro(db_session, [usuario["id_usuario"], veterinario["id_usuario"]])
    assert set(bandeja) == {usuario["id_usuario"], veterinario["id_usuario"]}
    mensaje = bandeja[veterinario["id_usuario"]]
    assert f"M05-{esc['activo']}" in mensaje and "None" not in mensaje and "RF" not in mensaje


def test_sin_veterinario_en_el_tratamiento_avisa_a_los_veterinarios_de_la_finca(
        cliente, db_session, admin, crear_usuario_db, monkeypatch):
    usuario, headers = admin
    de_la_finca = crear_usuario_db(id_rol=3, estado=2)
    esc = _escenario(db_session, usuario["id_usuario"])
    db_session.execute(text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"),
                       {"u": de_la_finca["id_usuario"], "f": esc["finca"]})
    _retiro_vencido_hoy(cliente, db_session, headers, esc, None)
    monkeypatch.setattr(_MODULO_CORREO, lambda **kw: None)

    RevertirRetirosVencidosUseCase(lambda: _SesionCompartida(db_session)).ejecutar()

    assert set(_bandeja_fin_retiro(db_session, [usuario["id_usuario"], de_la_finca["id_usuario"]])) == {
        usuario["id_usuario"], de_la_finca["id_usuario"]}


def _incidentes(db_session, id_activo: int) -> list:
    return db_session.execute(text("""
        SELECT resultado::text AS resultado, detalle_causa FROM modulo5.auditorias_suministros
        WHERE tipo_operacion::text = 'REGISTRO_FALLIDO' AND entidad_afectada = 'registros_medicamentos'
          AND id_activo_biologico = :a"""), {"a": id_activo}).all()


def _nada_guardado(db_session, esc) -> None:
    assert _escalar(db_session, "SELECT count(*) FROM modulo5.registros_medicamentos WHERE id_activo_biologico = :a",
                    a=esc["activo"]) == 0
    assert _escalar(db_session, "SELECT id_estado FROM modulo2.activos_biologicos WHERE id_activo_biologico = :a",
                    a=esc["activo"]) == 1


def test_fallo_al_calcular_fin_de_retiro_deja_incidente(cliente, db_session, admin, monkeypatch):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])

    def _falla(*args, **kwargs):
        raise OverflowError("date value out of range")

    monkeypatch.setattr(
        "src.supplies.application.use_cases.suministros.registrar_medicamento_use_case.timedelta", _falla)
    r = _medicamento(cliente, headers, esc)

    assert r.status_code == 500 and r.json()["error_code"] == "ERROR_INTERNO"
    _nada_guardado(db_session, esc)
    [incidente] = _incidentes(db_session, esc["activo"])
    assert incidente.resultado == "FALLIDO" and "error interno del sistema" in incidente.detalle_causa
    assert "OverflowError" not in incidente.detalle_causa  # sin nombres técnicos en la bitácora


def test_bd_no_disponible_al_guardar_deja_incidente(cliente, db_session, admin, monkeypatch):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])
    from src.shared.db_error_translator import raise_from_db_error

    def _sin_bd(self, medicamento):
        raise_from_db_error(OperationalError("INSERT", {}, Exception("server closed the connection")))

    monkeypatch.setattr(
        "src.supplies.infrastructure.repositories.medicamento_repository.SqlAlchemyMedicamentoRepository.guardar",
        _sin_bd)
    r = _medicamento(cliente, headers, esc)

    assert r.status_code == 503, r.text
    _nada_guardado(db_session, esc)
    [incidente] = _incidentes(db_session, esc["activo"])
    assert incidente.resultado == "FALLIDO" and "no estaba disponible" in incidente.detalle_causa
    assert r.json()["error_code"] not in incidente.detalle_causa


def test_un_error_de_validacion_no_es_incidente(cliente, db_session, admin):
    usuario, headers = admin
    esc = _escenario(db_session, usuario["id_usuario"])
    r = _medicamento(cliente, headers, esc, fecha_aplicacion=(HOY + timedelta(days=2)).isoformat())
    assert r.status_code == 400
    assert _incidentes(db_session, esc["activo"]) == []
