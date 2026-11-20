# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-19 | usuario-git | TC-M07-G062 (RF-AE02): pytest de G4.5 a G4.8 sobre el ciclo de vida del Anexo (sin BD ni red). |
"""TC-M07-G062 — ciclo de vida del Anexo de mapeo AAEF (RF-AE02 5.8, 5.9, 5.11), verificado contra el codigo.

    G4.5  Pasar a EN_REVISION: es la aprobacion interna del Contador; sin ella no se puede aprobar.
    G4.6  Pasar a APROBADO exige la evidencia de interoperabilidad (ExchangeId y ACK aceptado al 100 %).
    G4.7  Solo BORRADOR -> EN_REVISION -> APROBADO; cualquier otra transicion se rechaza sin cambiar el estado.
    G4.8  Un Anexo APROBADO no se modifica; un cambio es un Anexo nuevo en BORRADOR.

Se ejecuta desde la raiz de sgpmp-backend (lo lanza ejecutar_tc_m07_g62.py):

    python -m pytest tests/Test_Testing/Test_Modulo7/RF-AE01/TC-M07-G062/test_tc_m07_g62_anexo.py
"""
import pytest
from pydantic import ValidationError as ErrorEsquema

from src.accounting_integration.application.use_cases.contratos.gestionar_anexos_use_case import GestionarAnexosUseCase
from src.accounting_integration.domain.entities.contrato import AnexoMapeo
from src.accounting_integration.infrastructure.dto.m07_dto import AprobarAnexoDTO
from src.shared.errors import FlowError

SHA = "a" * 64
EVIDENCIA = {"id_intercambio": "AF-SIGAB-2026-10-0000123", "ack_aceptado": True, "observaciones": None}


class _Contratos:
    def __init__(self, *anexos):
        self.anexos = {}
        for a in anexos:
            self.guardar_anexo(a)
        self.guardados = 0

    def obtener_anexo(self, id_anexo):
        return self.anexos.get(id_anexo)

    def guardar_anexo(self, anexo):
        if anexo.id_mapeo_anexo_aaef is None:
            anexo.id_mapeo_anexo_aaef = max(self.anexos, default=0) + 1
        self.anexos[anexo.id_mapeo_anexo_aaef] = anexo
        self.guardados = getattr(self, "guardados", 0) + 1
        return anexo


class _Auditoria:
    def __init__(self):
        self.eventos = []

    def registrar(self, evento):
        self.eventos.append(evento.tipo_evento)


class _Db:
    def commit(self):
        pass

    def rollback(self):
        pass


def _anexo(estado, id_anexo=1):
    return AnexoMapeo(id_anexo, f"QA-G062-{estado}", "9.9", "docs/qa.md", SHA, estado=estado)


def _caso(*anexos):
    contratos, auditoria = _Contratos(*anexos), _Auditoria()
    return GestionarAnexosUseCase(contratos, auditoria, _Db()), contratos, auditoria


# --- G4.5 ---------------------------------------------------------------------------------------

def test_g4_5_la_aprobacion_interna_pasa_el_borrador_a_revision():
    caso, contratos, auditoria = _caso(_anexo("BORRADOR"))
    anexo = caso.enviar_a_revision(1, 7)
    assert anexo.estado == "EN_REVISION" and anexo.fecha_aprobacion_interna is not None
    assert auditoria.eventos == ["ANEXO_EN_REVISION"]


def test_g4_5_sin_aprobacion_interna_no_se_puede_aprobar():
    caso, contratos, auditoria = _caso(_anexo("BORRADOR"))
    with pytest.raises(FlowError) as exc:
        caso.aprobar(1, EVIDENCIA, 7)
    assert exc.value.code == "TRANSICION_NO_PERMITIDA"
    assert contratos.anexos[1].estado == "BORRADOR" and auditoria.eventos == []


# --- G4.6 ---------------------------------------------------------------------------------------

def test_g4_6_aprobar_con_evidencia_pasa_a_aprobado():
    caso, contratos, auditoria = _caso(_anexo("EN_REVISION"))
    anexo = caso.aprobar(1, AprobarAnexoDTO(**EVIDENCIA).model_dump(), 7)
    assert anexo.estado == "APROBADO" and anexo.fecha_aprobacion is not None
    assert anexo.evidencia["id_intercambio"] == EVIDENCIA["id_intercambio"] and anexo.evidencia["ack_aceptado"] is True
    assert auditoria.eventos == ["ANEXO_APROBADO"]


@pytest.mark.parametrize("cuerpo", [
    {"id_intercambio": "AF-SIGAB-2026-10-0000123", "ack_aceptado": False},   # SIGCON no acepto el 100 %
    {"id_intercambio": "AF-SIGAB-2026-10-0000123"},                           # sin ACK
    {"ack_aceptado": True},                                                   # sin ExchangeId de la prueba
    {},                                                                       # sin evidencia
], ids=["ack_en_falso", "sin_ack", "sin_exchange_id", "sin_evidencia"])
def test_g4_6_sin_evidencia_completa_se_rechaza_antes_de_aprobar(cuerpo):
    with pytest.raises(ErrorEsquema):
        AprobarAnexoDTO(**cuerpo)


# --- G4.7 ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("origen,operacion", [
    ("APROBADO", "revision"),    # APROBADO -> EN_REVISION
    ("BORRADOR", "aprobar"),     # saltar BORRADOR -> APROBADO
    ("EN_REVISION", "revision"),  # repetir la revision
    ("APROBADO", "aprobar"),     # aprobar otra vez
])
def test_g4_7_transiciones_invalidas_se_rechazan_sin_cambiar_el_estado(origen, operacion):
    caso, contratos, auditoria = _caso(_anexo(origen))
    with pytest.raises(FlowError) as exc:
        caso.enviar_a_revision(1, 7) if operacion == "revision" else caso.aprobar(1, EVIDENCIA, 7)
    assert exc.value.code == "TRANSICION_NO_PERMITIDA"
    assert contratos.anexos[1].estado == origen, "el estado no debe cambiar"
    assert auditoria.eventos == []


def test_g4_7_ninguna_operacion_regresa_un_anexo_a_borrador():
    """No existe en la entidad ni en el caso de uso una operacion que devuelva un Anexo a BORRADOR."""
    publicos = {n for n in dir(AnexoMapeo) if not n.startswith("_")}
    assert not {n for n in publicos if "borrador" in n.lower() or "retroced" in n.lower() or "revert" in n.lower()}
    assert not {n for n in dir(GestionarAnexosUseCase) if "borrador" in n.lower() or "retroced" in n.lower()}


# --- G4.8 ---------------------------------------------------------------------------------------

def test_g4_8_un_anexo_aprobado_no_admite_mas_operaciones_de_estado():
    caso, contratos, _ = _caso(_anexo("APROBADO"))
    antes = (contratos.anexos[1].estado, contratos.anexos[1].evidencia, contratos.anexos[1].sha256_documento)
    for operacion in (lambda: caso.enviar_a_revision(1, 7), lambda: caso.aprobar(1, EVIDENCIA, 7)):
        with pytest.raises(FlowError):
            operacion()
    despues = (contratos.anexos[1].estado, contratos.anexos[1].evidencia, contratos.anexos[1].sha256_documento)
    assert antes == despues


def test_g4_8_un_cambio_se_registra_como_anexo_nuevo_en_borrador_sin_tocar_el_aprobado():
    caso, contratos, auditoria = _caso(_anexo("APROBADO"))
    nuevo = caso.registrar("QA-G062-V2", "9.10", "docs/qa-v2.md", "b" * 64, 7)
    assert nuevo.estado == "BORRADOR" and nuevo.id_mapeo_anexo_aaef != 1
    assert contratos.anexos[1].estado == "APROBADO" and contratos.anexos[1].sha256_documento == SHA
    assert auditoria.eventos == ["ANEXO_REGISTRADO"]
