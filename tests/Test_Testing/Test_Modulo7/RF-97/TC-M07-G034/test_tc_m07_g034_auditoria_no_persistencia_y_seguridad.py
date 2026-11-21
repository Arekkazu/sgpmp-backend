"""
TC-M07-G034 (RF-97 Fase 8, CA-12, FA-9, RNF-97.3, RNF-97.6, Precondiciones,
CU-11) - "Auditoría, no persistencia y seguridad." Agrupa TC-97-068 a
TC-97-075.

Construido 2026-11-18 contra el código real
(auditoria_integracion_repository.py::registrador_aparte, factoria.py,
gateway_aaef.py). La parte de alcance/inyección y titular inexistente se
verificó en vivo en TEST -- ver RF-97-Verificacion-Live/ficha.md (35/35
assertions en verde, 2026-11-17/18):
  - NIT inexistente -> 404 TITULAR_NO_ENCONTRADO (no un 500 ni un error
    ambiguo).
  - NIT con payload de inyección (`' OR '1'='1`) -> 400 controlado, nunca
    500 (lo rechaza el patrón de FastAPI antes de llegar a la lógica).
  - El acceso de fincas ampliado por el DBA para 901333217 ya no da 403.

Código bajo prueba:
    src/accounting_integration/infrastructure/repositories/auditoria_integracion_repository.py (registrador_aparte)
    src/accounting_integration/infrastructure/factoria.py (auditar_aparte)
    src/accounting_integration/infrastructure/gateway_aaef.py

Cómo se prueba: pytest de unidad para FA-9 (RF-102 caído no bloquea la
respuesta) -- se puede confirmar sin BD viva, simulando una
session_factory que lanza.

NO VERIFICABLE AQUÍ: Burp Suite / fuzzing exhaustivo de payloads de
inyección -- la ficha pide esa herramienta específicamente; aquí solo se
confirma el caso base con `vista-previa` en vivo.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g034_auditoria_no_persistencia_y_seguridad.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G034.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository import registrador_aparte

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoRf102CaidoNoBloqueaLaRespuestaConfirmadoCorrecto:
    def test_una_sesion_de_auditoria_que_falla_no_propaga_la_excepcion(self):
        """FA-9: RF-102 caído durante una generación exitosa -- el envelope se entrega igual."""
        db_que_falla = MagicMock()
        db_que_falla.commit.side_effect = RuntimeError("RF-102 caido simulado")
        alertar = MagicMock()
        registrar = registrador_aparte(lambda: db_que_falla, alertar)
        registrar(EventoIntegracion(tipo_evento="VISTA_AAEF_GENERADA", tipo_actor="USUARIO", id_usuario=1))
        # no lanza -- confirma que FA-9 esta implementado: la excepcion queda contenida aqui

    def test_cuando_falla_se_alerta_al_administrador_y_se_hace_rollback(self):
        db_que_falla = MagicMock()
        db_que_falla.commit.side_effect = RuntimeError("RF-102 caido simulado")
        alertar = MagicMock()
        registrar = registrador_aparte(lambda: db_que_falla, alertar)
        registrar(EventoIntegracion(tipo_evento="VISTA_AAEF_GENERADA", tipo_actor="USUARIO", id_usuario=1))
        db_que_falla.rollback.assert_called_once()
        alertar.assert_called_once()
        db_que_falla.close.assert_called_once()  # la sesion siempre se cierra, incluso tras el fallo


class TestSubCasoRf97NoTieneNingunEndpointPropioSoloInvocableDesdeElGatewayConfirmadoCorrecto:
    def test_ningun_router_de_m07_expone_consultaraaefusecase_fuera_del_gateway(self):
        routers_dir = REPO_ROOT / 'src/accounting_integration/infrastructure/routers'
        for archivo in routers_dir.glob('*.py'):
            texto = archivo.read_text(encoding='utf-8')
            # el router llama a gateway_aaef.atender()/vista_previa(), nunca a ConsultarAaefUseCase directamente
            if 'ConsultarAaefUseCase' in texto:
                assert False, f"{archivo.name} invoca el caso de uso directamente, sin pasar por el gateway"


class TestSubCasoNingunDatoDeM06SePersisteNiSeModificaConfirmadoCorrecto:
    def test_consultar_aaef_use_case_no_contiene_ningun_verbo_sql_de_escritura(self):
        import re
        archivo = REPO_ROOT / (
            'src/accounting_integration/application/use_cases/exportacion/consultar_aaef_use_case.py')
        texto = archivo.read_text(encoding='utf-8')
        assert not re.search(r'\b(INSERT|UPDATE|DELETE)\b', texto, re.IGNORECASE)
