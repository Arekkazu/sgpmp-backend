"""INC-M02-34-G29/G31 v2.0 (RF-36): la bitácora
`modulo2.bitacora_auditoria_m02` registraba toda consulta de activo
(individual o poblacional) con `rf_origen='RF35'` / `tipo_evento=
'ACTIVO_INDIVIDUAL_CONSULTA'`, sin distinguir tipo_activo. Un lote
POBLACIONAL debe auditarse con RF-36, no con el rf_origen/tipo_evento de
RF-35 (gestión individual).
"""
from __future__ import annotations

from dataclasses import dataclass

from src.biological_assets.application.use_cases.gestion.consultar_activo_use_case import (
    ConsultarActivoUseCase,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual


@dataclass
class _ActivoFake:
    tipo: str


class ActivoRepoFake:
    def __init__(self, activo) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        return self.activo


class BitacoraFake:
    def __init__(self) -> None:
        self.eventos = []

    def registrar(self, evento) -> None:
        self.eventos.append(evento)


class DbFake:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def _consultar(tipo_activo: str):
    bitacora = BitacoraFake()
    uc = ConsultarActivoUseCase(db=DbFake(), repo=ActivoRepoFake(_ActivoFake(tipo=tipo_activo)), bitacora_repo=bitacora)
    uc.execute(8, UsuarioActual(id_usuario=1, id_token=1, id_rol=1))
    return bitacora.eventos[0]


def test_consulta_poblacional_se_audita_con_rf36():
    evento = _consultar('POBLACIONAL')
    assert evento.rf_origen == 'RF36'
    assert evento.tipo_evento == 'ACTIVO_POBLACIONAL_CONSULTA'


def test_consulta_individual_conserva_rf35():
    evento = _consultar('INDIVIDUAL')
    assert evento.rf_origen == 'RF35'
    assert evento.tipo_evento == 'ACTIVO_INDIVIDUAL_CONSULTA'
