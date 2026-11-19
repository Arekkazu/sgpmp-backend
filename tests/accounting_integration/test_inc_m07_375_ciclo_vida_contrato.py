# | Fecha      | Nombre         | Que se hizo |
# |------------|----------------|-------------|
# | 2026-11-19 | LuisfNarvaez01 | INC-M07-375 RF-98: rechazos auditados con WARNING, MODIFICACION_NO_PERMITIDA y estado antes que anexo |
"""INC-M07-375-G39 (TC-M07-14/15/16): ciclo de vida del contrato AAEF sin base de datos.

- Una transición inválida se rechaza, el estado no cambia, se audita con WARNING en una sesión
  aparte (después del rollback) y se avisa al Administrador.
- Modificar una versión ACTIVO o DEPRECADO responde MODIFICACION_NO_PERMITIDA; una PENDIENTE sí cambia.
- Activar una versión INACTIVO responde REACTIVACION_NO_PERMITIDA aunque no tenga anexo aprobado.
"""
from datetime import date

import pytest

from src.accounting_integration.application.use_cases.contratos.gestionar_contratos_use_case import (
    GestionarContratosUseCase,
)
from src.accounting_integration.domain.entities.contrato import AnexoMapeo, VersionContrato
from src.shared.errors import AppError


class _Db:
    def __init__(self):
        self.commits = self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Contratos:
    def __init__(self, contratos, anexos):
        self.contratos, self.anexos, self.guardados = contratos, anexos, []

    def listar_contratos(self, bloquear=False):
        return self.contratos

    def guardar_contrato(self, contrato):
        self.guardados.append(contrato.estado)
        return contrato

    def guardar_datos_contrato(self, contrato):
        self.guardados.append("DATOS")
        return contrato

    def obtener_anexo(self, id_):
        return self.anexos.get(id_)


class _Auditoria:
    def __init__(self):
        self.eventos = []

    def registrar(self, evento):
        self.eventos.append(evento)


def _contrato(id_, version, estado, anexo=1):
    return VersionContrato(id_, version, "MAJOR", date(2026, 11, 1), anexo, ["COMPRAS"],
                           periodo_gracia_dias=90, estado=estado)


def _caso():
    contratos = _Contratos(
        [_contrato(1, "1.0", "INACTIVO", anexo=None), _contrato(2, "2.0", "DEPRECADO"),
         _contrato(18, "3.0", "ACTIVO"), _contrato(20, "4.0", "PENDIENTE")],
        {1: AnexoMapeo(1, "ANX", "1", "/a.pdf", "x" * 64, estado="APROBADO"),
         2: AnexoMapeo(2, "ANX", "2", "/b.pdf", "y" * 64, estado="APROBADO")})
    aparte, alertas, db, auditoria = [], [], _Db(), _Auditoria()
    uc = GestionarContratosUseCase(contratos, auditoria, db, lambda: True,
                                   lambda m, d: alertas.append(m), registrar_aparte=aparte.append)
    return uc, contratos, aparte, alertas, db, auditoria


@pytest.mark.parametrize("accion, id_, codigo", [
    ("activar", 2, "TRANSICION_NO_PERMITIDA"),    # DEPRECADO -> ACTIVO
    ("activar", 18, "TRANSICION_NO_PERMITIDA"),   # ACTIVO -> ACTIVO
    ("deprecar", 20, "TRANSICION_NO_PERMITIDA"),  # PENDIENTE -> DEPRECADO
    ("activar", 1, "REACTIVACION_NO_PERMITIDA"),  # INACTIVO sin anexo: el estado manda (FA-13)
    ("deprecar", 1, "REACTIVACION_NO_PERMITIDA"),
])
def test_transicion_invalida_se_rechaza_audita_warning_y_avisa(accion, id_, codigo):
    uc, contratos, aparte, alertas, db, auditoria = _caso()
    estados = [c.estado for c in contratos.contratos]
    with pytest.raises(AppError) as exc:
        uc.activar(id_, 7) if accion == "activar" else uc.deprecar(id_, 90, 7)
    assert exc.value.code == codigo
    assert [c.estado for c in contratos.contratos] == estados and contratos.guardados == []
    assert db.rollbacks == 1 and db.commits == 0 and auditoria.eventos == []
    (evento,) = aparte  # fuera de la transacción revertida
    assert (evento.tipo_evento, evento.severidad, evento.codigo_resultado) == ("CONTRATO_TRANSICION_RECHAZADA", "WARNING", codigo)
    assert evento.faltantes() == [] and evento.id_usuario == 7 and evento.codigo_http == 422
    assert len(alertas) == 1 and "RF-" not in alertas[0] and "None" not in alertas[0]


@pytest.mark.parametrize("id_, metodo", [(18, "PATCH"), (18, "PUT"), (2, "PATCH")])
def test_modificar_version_protegida_responde_modificacion_no_permitida(id_, metodo):
    uc, contratos, aparte, alertas, db, _ = _caso()
    with pytest.raises(AppError) as exc:
        uc.modificar(id_, {"descripcion": "cambio"}, 7, metodo)
    assert exc.value.code == "MODIFICACION_NO_PERMITIDA" and exc.value.status_code == 422
    assert contratos.guardados == [] and next(c for c in contratos.contratos if c.id_version_contrato_aaef == id_).descripcion is None
    assert aparte[0].metodo_http == metodo and aparte[0].codigo_resultado == "MODIFICACION_NO_PERMITIDA"
    assert len(alertas) == 1


def test_modificar_version_pendiente_guarda_y_audita():
    uc, contratos, aparte, _, db, auditoria = _caso()
    contrato = uc.modificar(20, {"descripcion": "ajuste", "id_mapeo_anexo_aaef": 2}, 7)
    assert (contrato.descripcion, contrato.id_mapeo_anexo_aaef) == ("ajuste", 2)
    assert contratos.guardados == ["DATOS"] and db.commits == 1 and aparte == []
    assert auditoria.eventos[0].tipo_evento == "CONTRATO_MODIFICADO" and auditoria.eventos[0].faltantes() == []
