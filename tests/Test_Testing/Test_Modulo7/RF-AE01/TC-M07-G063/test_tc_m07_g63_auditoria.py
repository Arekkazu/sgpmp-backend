# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-19 | usuario-git | TC-M07-G063 (RF-AE01 / RF-AE02): pytest de auditoria G5.1 a G5.3 sobre el gateway AAEF y el ciclo de vida del Anexo (sin BD ni red). |
"""TC-M07-G063 — registro en la auditoria RF-102, verificado contra el codigo (sin BD, sin red).

    G5.1  Una consulta exitosa y una fallida dejan su evento con usuario, titular, rango, version, hash y resultado.
    G5.2  Caida de la auditoria durante la consulta: la consulta responde 200 y la falta del registro queda a la vista
          (log tecnico y aviso al Administrador).
    G5.3  Ciclo de vida del Anexo: creacion, validacion automatica, aprobacion interna, evidencia y aprobacion quedan
          registrados con usuario y fecha; la evidencia queda asociada a la version del Anexo.

Se ejecuta desde la raiz de sgpmp-backend (lo lanza ejecutar_tc_m07_g63.py):

    python -m pytest tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G063/test_tc_m07_g63_auditoria.py
"""
import json
import os
from datetime import date
from types import SimpleNamespace

# Importar el gateway construye el engine de SQLAlchemy, que exige DATABASE_URL pero NO conecta. Estas pruebas usan
# dobles y nunca tocan una base de datos: si no hay URL se pone una ficticia que no apunta a nada real.
os.environ.setdefault("DATABASE_URL", "postgresql://qa:qa@127.0.0.1:1/qa_sin_conexion")

import pytest
from starlette.requests import Request

from src.accounting_integration.application.use_cases.contratos.gestionar_anexos_use_case import GestionarAnexosUseCase
from src.accounting_integration.application.use_cases.exportacion.consultar_aaef_use_case import ResultadoAaef
from src.accounting_integration.domain.entities.contrato import AnexoMapeo, VersionContrato
from src.accounting_integration.infrastructure import gateway_aaef
from src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository import registrador_aparte
from src.shared.errors import BusinessRuleError

NIT = "901444215"
ID_USUARIO, ID_CLIENTE = 7, 3
HASH = "c" * 64
RID_OK, RID_ERR = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"


# --- Doble del gateway ----------------------------------------------------------------------------

class _Db:
    def execute(self, *a, **k):
        return None


class _M07:
    """Lo minimo de la factoria M07 que usa gateway_aaef.atender."""

    def __init__(self, auditar, falla=None):
        self.auditar_aparte = auditar
        self._falla = falla
        contrato = VersionContrato(1, "3.0", "MAYOR", date(2026, 1, 1), 1, ["COMPRAS"], estado="ACTIVO")
        self._resultado = ResultadoAaef(b'{"invoices":[]}', HASH, contrato, "AF-SIGAB-2026-09-0000001", 0)

    def verificar_acceso(self):
        acceso = SimpleNamespace(cliente=SimpleNamespace(id_cliente_externo=ID_CLIENTE),
                                 usuario=SimpleNamespace(id_usuario=ID_USUARIO, id_rol=4, nombre_rol="Contador",
                                                         correo="contador@gmail.com"))
        return SimpleNamespace(execute=lambda token, canal, ip: acceso)

    def consultar_aaef(self):
        def ejecutar(solicitud):
            if self._falla:
                raise self._falla
            return self._resultado
        return SimpleNamespace(execute=ejecutar)


def _peticion(rid, desde, hasta):
    return Request({"type": "http", "method": "GET", "path": f"/integracion/aaef/productores/{NIT}",
                    "query_string": f"desde={desde}&hasta={hasta}".encode(), "client": ("127.0.0.1", 5000),
                    "headers": [(b"authorization", b"Bearer token-qa"), (b"x-request-id", rid.encode())]})


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setattr(gateway_aaef, "declarar_identidad", lambda *a, **k: None)
    monkeypatch.setattr(gateway_aaef, "tiene_permiso_sobre", lambda *a, **k: True)

    def preparar(auditar, falla=None):
        monkeypatch.setattr(gateway_aaef, "M07", lambda db: _M07(auditar, falla))
    return preparar


# --- G5.1 ---------------------------------------------------------------------------------------

def test_g5_1_una_consulta_exitosa_deja_su_evento_completo(gateway):
    eventos = []
    gateway(eventos.append)
    r = gateway_aaef.atender(_peticion(RID_OK, "2026-09-01", "2026-10-31"), _Db(), NIT, "2026-09-01", "2026-10-31")
    assert r.status_code == 200
    (e,) = eventos
    assert e.tipo_evento == "PAQUETE_AAEF_CONSULTADO" and e.codigo_http == 200 and e.codigo_resultado == "OK"
    assert (e.id_usuario, e.id_cliente_externo, e.numero_id_tributaria) == (ID_USUARIO, ID_CLIENTE, NIT)
    assert (e.fecha_desde, e.fecha_hasta) == (date(2026, 9, 1), date(2026, 10, 31))
    assert e.version_contrato == "3.0" and e.hash_contenido == HASH and e.id_solicitud == RID_OK
    assert e.faltantes() == [], "el evento cumple los campos obligatorios de RF-102 8.2"
    assert e.hash_integridad, "el evento lleva su hash de integridad"


def test_g5_1_una_consulta_fallida_deja_su_evento_con_el_resultado_de_error(gateway):
    eventos = []
    gateway(eventos.append, falla=BusinessRuleError(code="RANGO_NO_ALINEADO", message="El rango no esta alineado.", field="desde"))
    with pytest.raises(BusinessRuleError):
        gateway_aaef.atender(_peticion(RID_ERR, "2026-10-05", "2026-10-31"), _Db(), NIT, "2026-10-05", "2026-10-31")
    (e,) = eventos
    assert e.tipo_evento == "SOLICITUD_RECHAZADA" and e.severidad == "WARNING"
    assert e.codigo_http == 422 and e.codigo_resultado == "RANGO_NO_ALINEADO" and e.id_solicitud == RID_ERR
    assert (e.id_usuario, e.numero_id_tributaria) == (ID_USUARIO, NIT)
    assert (e.fecha_desde, e.fecha_hasta) == (date(2026, 10, 5), date(2026, 10, 31))
    assert e.faltantes() == []


# --- G5.2 ---------------------------------------------------------------------------------------

class _SesionCaida:
    """Una sesion de BD que ya no responde."""
    cerrada = False

    def execute(self, *a, **k):
        raise ConnectionError("la base de la auditoria no responde")

    def commit(self):
        raise ConnectionError("commit imposible")

    def rollback(self):
        pass

    def close(self):
        self.cerrada = True


def test_g5_2_la_caida_de_la_auditoria_no_bloquea_la_consulta_y_alerta_al_administrador(gateway):
    alertas = []
    registrar = registrador_aparte(_SesionCaida, lambda mensaje, detalle: alertas.append((mensaje, detalle)))
    gateway(registrar)
    r = gateway_aaef.atender(_peticion(RID_OK, "2026-09-01", "2026-10-31"), _Db(), NIT, "2026-09-01", "2026-10-31")
    assert r.status_code == 200 and r.body == b'{"invoices":[]}', "la consulta responde con normalidad"
    assert r.headers["X-Content-SHA256"] == HASH
    assert len(alertas) == 1, "la falta del registro queda a la vista"
    assert "auditoría" in alertas[0][0] and alertas[0][1]["tipo_evento"] == "PAQUETE_AAEF_CONSULTADO"
    assert alertas[0][1]["id_solicitud"] == RID_OK


def test_g5_2_la_caida_tampoco_oculta_el_error_de_una_consulta_fallida(gateway):
    alertas = []
    gateway(registrador_aparte(_SesionCaida, lambda m, d: alertas.append(m)),
            falla=BusinessRuleError(code="RANGO_NO_ALINEADO", message="x", field="desde"))
    with pytest.raises(BusinessRuleError) as exc:  # sigue saliendo el error de negocio, no el de la auditoria
        gateway_aaef.atender(_peticion(RID_ERR, "2026-10-05", "2026-10-31"), _Db(), NIT, "2026-10-05", "2026-10-31")
    assert exc.value.code == "RANGO_NO_ALINEADO" and len(alertas) == 1


# --- G5.3 ---------------------------------------------------------------------------------------

class _Contratos:
    def __init__(self):
        self.anexos = {}

    def obtener_anexo(self, id_anexo):
        return self.anexos.get(id_anexo)

    def guardar_anexo(self, anexo):
        if anexo.id_mapeo_anexo_aaef is None:
            anexo.id_mapeo_anexo_aaef = max(self.anexos, default=0) + 1
        self.anexos[anexo.id_mapeo_anexo_aaef] = anexo
        return anexo


class _Auditoria:
    def __init__(self):
        self.eventos = []

    def registrar(self, evento):
        self.eventos.append(evento)


class _DbTx:
    def commit(self):
        pass

    def rollback(self):
        pass


EVIDENCIA = {"id_intercambio": "AF-SIGAB-2026-10-0000123", "ack_aceptado": True, "observaciones": None}


def _ciclo():
    contratos, auditoria = _Contratos(), _Auditoria()
    caso = GestionarAnexosUseCase(contratos, auditoria, _DbTx())
    anexo = caso.registrar("QA-G063", "9.9", "docs/qa.md", "d" * 64, ID_USUARIO)
    caso.enviar_a_revision(anexo.id_mapeo_anexo_aaef, ID_USUARIO)
    caso.aprobar(anexo.id_mapeo_anexo_aaef, EVIDENCIA, ID_USUARIO)
    return auditoria.eventos


def test_g5_3_cada_hecho_del_ciclo_queda_registrado_con_usuario_y_fecha():
    eventos = _ciclo()
    assert [e.tipo_evento for e in eventos] == ["ANEXO_REGISTRADO", "ANEXO_EN_REVISION", "ANEXO_APROBADO"]
    for e in eventos:
        assert e.id_usuario == ID_USUARIO and e.tipo_actor == "USUARIO" and e.codigo_resultado == "OK"
        assert e.fecha_evento is not None and e.hash_integridad
        assert e.json_detalle["codigo_anexo"] == "QA-G063" and e.json_detalle["version_anexo"] == "9.9"


def test_g5_3_creacion_validacion_automatica_y_aprobacion_interna():
    registrado, en_revision, _ = _ciclo()
    assert registrado.json_detalle["sha256_documento"] == "d" * 64                      # creacion
    assert en_revision.json_detalle["validacion_automatica"] == "OK"                    # validacion automatica
    # la aprobacion interna es el propio paso a revision: el evento lleva al Contador y la fecha


def test_g5_3_la_evidencia_de_interoperabilidad_queda_asociada_a_la_version_del_anexo():
    *_, aprobado = _ciclo()
    ev = aprobado.json_detalle["evidencia"]
    assert ev["id_intercambio"] == EVIDENCIA["id_intercambio"] and ev["ack_aceptado"] is True
    assert aprobado.json_detalle["version_anexo"] == "9.9"


def test_g5_3_una_validacion_fallida_tambien_queda_registrada(monkeypatch):
    from src.accounting_integration.application.use_cases.contratos import gestionar_anexos_use_case as uc
    monkeypatch.setattr(uc, "validar_con_datos_de_prueba", lambda: ["estructura"])
    contratos, auditoria = _Contratos(), _Auditoria()
    contratos.guardar_anexo(AnexoMapeo(None, "QA-G063-F", "9.8", "docs/qa.md", "e" * 64))
    with pytest.raises(BusinessRuleError):
        GestionarAnexosUseCase(contratos, auditoria, _DbTx()).enviar_a_revision(1, ID_USUARIO)
    (e,) = auditoria.eventos
    assert e.tipo_evento == "ANEXO_VALIDACION_FALLIDA" and e.severidad == "ERROR" and e.id_usuario == ID_USUARIO
    assert e.json_detalle["fallas"] == ["estructura"]
