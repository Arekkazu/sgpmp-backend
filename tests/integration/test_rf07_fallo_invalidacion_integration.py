"""TC-M01-038: persistencia real y contrato HTTP frente a fallos de sesiones."""
import bcrypt
import pytest
from sqlalchemy import text

from src.identity_access.infrastructure.repositories.sesion_repository import SqlAlchemySesionRepository
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.shared.notificacion_service import NotificacionService

pytestmark = pytest.mark.integration

MENSAJE = (
    "Contraseña actualizada, pero ocurrió un error al cerrar las sesiones "
    "en otros dispositivos. Se recomienda cerrar sesión manualmente en "
    "todos sus equipos para garantizar la seguridad."
)


@pytest.mark.parametrize("fallo", ["antes", "despues_flush", "sql", "commit", None])
def test_contrasena_persistida_y_sesiones_atomicas(client, db_session, crear_usuario_db, crear_auth_headers, monkeypatch, fallo):
    usuario = crear_usuario_db()
    headers = crear_auth_headers(usuario)
    notificaciones = []
    monkeypatch.setattr(NotificacionService, "notificar", lambda *a, **kw: notificaciones.append(kw))
    original = SqlAlchemySesionRepository.invalidar_todas_sesiones
    commit_original = db_session.commit

    def invalidar(repo, cuenta):
        if fallo == "antes":
            raise RuntimeError("proveedor privado caido")
        original(repo, cuenta)
        if fallo == "despues_flush":
            raise RuntimeError("fallo despues de modificar tokens")
        if fallo == "sql":
            repo.db.execute(text("SELECT 1 / 0"))
        if fallo == "commit":
            def commit_fallido():
                monkeypatch.setattr(db_session, "commit", commit_original)
                raise RuntimeError("fallo al confirmar sesiones")
            monkeypatch.setattr(db_session, "commit", commit_fallido)

    monkeypatch.setattr(SqlAlchemySesionRepository, "invalidar_todas_sesiones", invalidar)
    response = client.put(f"/contrasena/usuarios/{usuario['id_usuario']}", headers=headers, json={
        "contrasena_actual": "Inicial1!", "nueva_contrasena": "Nueva5678#", "confirmar_nueva_contrasena": "Nueva5678#",
    })
    assert response.status_code == (500 if fallo else 200), response.text
    if fallo:
        assert response.json()["message"] == MENSAJE
        assert response.json()["error_code"] == "CAMBIO_CONTRASENA_INVALIDACION_FALLIDA"
    db_session.expire_all()
    hash_actual = db_session.execute(text("SELECT contrasena_cifrada FROM modulo1.usuarios WHERE id_usuario=:id"), {"id": usuario["id_usuario"]}).scalar_one()
    assert bcrypt.checkpw(b"Nueva5678#", hash_actual.encode())
    assert not bcrypt.checkpw(b"Inicial1!", hash_actual.encode())
    estado = db_session.execute(text("SELECT s.es_activa, t.fecha_uso FROM modulo1.sesiones s JOIN modulo1.tokens t USING (id_token) WHERE id_cuenta_usuario=:id"), {"id": usuario["id_cuenta_usuario"]}).one()
    assert estado.es_activa is bool(fallo)
    assert (estado.fecha_uso is None) is bool(fallo)
    assert db_session.execute(text("SELECT count(*) FROM modulo1.eventos WHERE id_usuario=:id AND tipo_evento=6 AND resultado::text='exitoso'"), {"id": usuario["id_usuario"]}).scalar_one() == 1
    assert len(notificaciones) == 1


def test_fallo_auditoria_revierte_contrasena(client, db_session, crear_usuario_db, crear_auth_headers, monkeypatch):
    usuario = crear_usuario_db()
    headers = crear_auth_headers(usuario)
    def fallar(*args, **kwargs):
        raise RuntimeError("auditoria caida")
    monkeypatch.setattr(SqlAlchemyEventoRepository, "registrar", fallar)
    # El caso de uso conserva la excepción previa: aquí comprobamos la transacción.
    with pytest.raises(RuntimeError, match="auditoria caida"):
        client.put(f"/contrasena/usuarios/{usuario['id_usuario']}", headers=headers, json={
            "contrasena_actual": "Inicial1!", "nueva_contrasena": "Nueva5678#", "confirmar_nueva_contrasena": "Nueva5678#",
        })
    hash_actual = db_session.execute(text("SELECT contrasena_cifrada FROM modulo1.usuarios WHERE id_usuario=:id"), {"id": usuario["id_usuario"]}).scalar_one()
    assert bcrypt.checkpw(b"Inicial1!", hash_actual.encode())


def test_rf09_conserva_rollback_de_contrasena_y_token(client, db_session, crear_usuario_db, crear_auth_headers, monkeypatch):
    from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token

    usuario = crear_usuario_db()
    crear_auth_headers(usuario)
    token_hash = calcular_hash_token("token-rf09-regresion")
    db_session.execute(text("UPDATE modulo1.cuentas_usuarios SET token_activacion_actual=:token, fecha_cambio_estado=now() WHERE id_usuario=:id"), {"token": token_hash, "id": usuario["id_usuario"]})
    db_session.commit()
    original = SqlAlchemySesionRepository.invalidar_todas_sesiones
    def fallar(repo, cuenta):
        original(repo, cuenta)
        raise RuntimeError("fallo rf09")
    monkeypatch.setattr(SqlAlchemySesionRepository, "invalidar_todas_sesiones", fallar)
    with pytest.raises(RuntimeError, match="fallo rf09"):
        client.post("/contrasena/restablecer", json={"token": "token-rf09-regresion", "nueva_contrasena": "Nueva5678#", "confirmar_contrasena": "Nueva5678#"})
    fila = db_session.execute(text("SELECT contrasena_cifrada, token_activacion_actual FROM modulo1.usuarios JOIN modulo1.cuentas_usuarios USING (id_usuario) WHERE id_usuario=:id"), {"id": usuario["id_usuario"]}).one()
    assert bcrypt.checkpw(b"Inicial1!", fila.contrasena_cifrada.encode())
    assert fila.token_activacion_actual == token_hash


@pytest.mark.parametrize("caso,status", [
    ("actual_incorrecta", 401),
    pytest.param("reuso", 409, marks=pytest.mark.xfail(
        strict=True, raises=AssertionError,
        reason="Brecha previa reproducida en dev 9a57da7: el trigger compara hashes bcrypt con salt distinto; ver anotación INC-M01-08-38",
    )),
    ("confirmacion", 400), ("politica", 400), ("otro_usuario", 403),
])
def test_validaciones_no_modifican_la_contrasena(client, db_session, crear_usuario_db, crear_auth_headers, monkeypatch, caso, status):
    usuario = crear_usuario_db()
    headers = crear_auth_headers(usuario)
    monkeypatch.setattr(NotificacionService, "notificar", lambda *a, **kw: None)
    dto = {"contrasena_actual": "Inicial1!", "nueva_contrasena": "Nueva5678#", "confirmar_nueva_contrasena": "Nueva5678#"}
    destino = usuario["id_usuario"]
    if caso == "actual_incorrecta":
        dto["contrasena_actual"] = "Incorrecta1!"
    elif caso == "reuso":
        dto["nueva_contrasena"] = dto["confirmar_nueva_contrasena"] = "Inicial1!"
    elif caso == "confirmacion":
        dto["confirmar_nueva_contrasena"] = "Otra123!"
    elif caso == "politica":
        dto["nueva_contrasena"] = dto["confirmar_nueva_contrasena"] = "debil"
    else:
        destino = crear_usuario_db()["id_usuario"]
    response = client.put(f"/contrasena/usuarios/{destino}", headers=headers, json=dto)
    assert response.status_code == status, response.text
    hash_actual = db_session.execute(text("SELECT contrasena_cifrada FROM modulo1.usuarios WHERE id_usuario=:id"), {"id": usuario["id_usuario"]}).scalar_one()
    assert bcrypt.checkpw(b"Inicial1!", hash_actual.encode())
