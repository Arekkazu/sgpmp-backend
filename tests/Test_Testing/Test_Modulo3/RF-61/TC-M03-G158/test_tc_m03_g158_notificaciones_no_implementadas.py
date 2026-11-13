"""
TC-M03-G158 (RF-61 v1.2 Salida 4/E1/E3/E4/E6, CU-15) - "Notificaciones de
resolución manual requerida."

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE (origin/test, 2026-10-29,
DEV-44 Leandro) -- HALLAZGO PRINCIPAL COMPLETAMENTE INVERTIDO. La lista
de archivos de la ronda anterior no incluía
`procesar_avisos_vinculacion_use_case.py` ni
`destinatarios_vinculacion_m01_adapter.py` -- ambos nuevos, ambos reales
y ambos cableados en producción:

- `ProcesarAvisosVinculacionUseCase` (constructor: `vinculaciones, avisos,
  destinatarios`) SÍ dispara un aviso cuando `causa=='CONFIGURACION_INCOMPLETA'`
  o `estado_vinculacion in ('AMBIGUA','PENDIENTE_REVISION')`: resuelve
  destinatarios reales (ver abajo), calcula una CLAVE DE DEDUPLICACIÓN
  explícita (`f'RF61:{id_vinculacion}:CONFIGURACION_INCOMPLETA'` o
  `'...:AMBIGUEDAD'`) y exige que el canal de avisos CONFIRME el envío
  (`avisos.ambiguedad(...)`/`avisos.configuracion_incompleta(...)` deben
  devolver `True`) -- si no hay destinatarios, o el canal no confirma, o
  no hay canal/destinatarios inyectados, lanza `ServiceUnavailableError`
  en vez de fingir que el aviso se envió.
- `DestinatariosVinculacionM01Adapter` resuelve destinatarios reales
  consultando permisos y alcance de finca en M01 (`modulo1.usuarios`,
  `modulo1.permisos`, `modulo9.usuarios_fincas`) -- sin roles quemados.
- `postcommit_worker.py` tiene una etapa dedicada
  (`EtapaPostcommit.RF61_AVISOS`) que invoca
  `ProcesarAvisosVinculacionUseCase` con ambos componentes reales -- es
  producción, no un experimento ni código muerto.

(a)-(f) HALLAZGO INVERTIDO: SÍ existe un concepto real de "notificación
de resolución manual requerida", con deduplicación explícita y
confirmación obligatoria del canal. Lo que NO se verificó esta ronda es
el contenido/implementación concreta del `avisos_vinculacion` (el objeto
que expone `.ambiguedad()`/`.configuracion_incompleta()` se inyecta
externamente a `construir_procesador()` y no se localizó su
implementación por defecto en este repo) ni la matriz de destinatarios
en vivo.

Cómo se prueba: inspección directa de
`procesar_avisos_vinculacion_use_case.py`,
`destinatarios_vinculacion_m01_adapter.py` y
`postcommit_worker.py` (wiring real).

Como correrlo:
    python -m pytest <ruta>\\test_tc_m03_g158_notificaciones_no_implementadas.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G158.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]

from src.telemetry.application.use_cases.infraestructura.procesar_avisos_vinculacion_use_case import (  # noqa: E402
    ProcesarAvisosVinculacionUseCase,
)


class TestHallazgoPrincipalInvertidoSiExisteUnSistemaRealDeAvisos:
    def test_el_worker_postcommit_si_tiene_una_etapa_dedicada_de_avisos_rf61(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/workers/postcommit_worker.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO: postcommit_worker.py SI tiene una etapa real "
            "'EtapaPostcommit.RF61_AVISOS' que invoca ProcesarAvisosVinculacionUseCase con "
            "DestinatariosVinculacionM01Adapter -- la ronda anterior (codigo stale/lista de "
            "archivos incompleta) no encontro ningun sistema de notificacion para RF-61."
        ) if 'RF61_AVISOS' in texto and 'ProcesarAvisosVinculacionUseCase' in texto else None

    def test_destinatarios_se_resuelven_por_permisos_y_finca_sin_roles_quemados(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/adapters/destinatarios_vinculacion_m01_adapter.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO: DestinatariosVinculacionM01Adapter.obtener() SI resuelve "
            "destinatarios reales via permisos de modulo1 y alcance de finca de modulo9 -- "
            "sin ids de rol fijos en el codigo."
        ) if 'modulo1.permisos' in texto and 'usuarios_fincas' in texto else None

    @pytest.mark.parametrize('causa,estado,metodo_esperado', [
        ('CONFIGURACION_INCOMPLETA', 'SIN_VINCULAR', 'configuracion_incompleta'),
        (None, 'AMBIGUA', 'ambiguedad'),
        (None, 'PENDIENTE_REVISION', 'ambiguedad'),
    ])
    def test_dispara_el_aviso_correcto_segun_causa_o_estado(self, causa, estado, metodo_esperado):
        vinculacion = MagicMock(id_vinculacion_lectura=158, id_infraestructura=6, causa=causa, estado_vinculacion=estado)
        vinculaciones = MagicMock()
        vinculaciones.vigente.return_value = vinculacion
        avisos = MagicMock()
        getattr(avisos, metodo_esperado).return_value = True
        destinatarios = MagicMock()
        destinatarios.obtener.return_value = [1, 2]
        uc = ProcesarAvisosVinculacionUseCase(vinculaciones, avisos, destinatarios)
        uc.execute(158)
        getattr(avisos, metodo_esperado).assert_called_once()

    def test_sin_canal_de_avisos_inyectado_no_finge_el_envio_lanza_error(self):
        from src.shared.errors import ServiceUnavailableError
        vinculacion = MagicMock(id_vinculacion_lectura=158, id_infraestructura=6, causa=None, estado_vinculacion='AMBIGUA')
        vinculaciones = MagicMock()
        vinculaciones.vigente.return_value = vinculacion
        uc = ProcesarAvisosVinculacionUseCase(vinculaciones, avisos=None, destinatarios=None)
        with pytest.raises(ServiceUnavailableError) as exc:
            uc.execute(158)
        assert exc.value.code == 'AVISO_VINCULACION_NO_DISPONIBLE'

    def test_sin_destinatarios_reales_lanza_error_en_vez_de_enviar_al_vacio(self):
        from src.shared.errors import ServiceUnavailableError
        vinculacion = MagicMock(id_vinculacion_lectura=158, id_infraestructura=6, causa=None, estado_vinculacion='AMBIGUA')
        vinculaciones = MagicMock()
        vinculaciones.vigente.return_value = vinculacion
        avisos = MagicMock()
        destinatarios = MagicMock()
        destinatarios.obtener.return_value = []
        uc = ProcesarAvisosVinculacionUseCase(vinculaciones, avisos, destinatarios)
        with pytest.raises(ServiceUnavailableError) as exc:
            uc.execute(158)
        assert exc.value.code == 'DESTINATARIOS_VINCULACION_AUSENTES'

    def test_la_clave_de_deduplicacion_es_explicita_y_distingue_causa_de_ambiguedad(self):
        fuente = (
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/procesar_avisos_vinculacion_use_case.py'
        ).read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO: SI existe una clave de deduplicacion explicita "
            "('RF61:{id}:CONFIGURACION_INCOMPLETA' / '...:AMBIGUEDAD') -- la ronda anterior "
            "afirmo que no habia ningun concepto de deduplicacion para avisos de RF-61."
        ) if "clave=f'RF61:" in fuente else None

    def test_implementacion_por_defecto_del_canal_de_avisos_no_se_localizo_en_este_repo(self):
        """No confundir con el HALLAZGO INVERTIDO de arriba: el MECANISMO (quien
        llama a quien, deduplicacion, destinatarios) es real; lo que no se
        verifico es que exista una implementacion concreta no-mock de
        `avisos_vinculacion.ambiguedad/configuracion_incompleta` conectada por
        defecto en construir_procesador() (el parametro llega en None salvo que
        algo externo lo inyecte)."""
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/workers/postcommit_worker.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'avisos_vinculacion=None' in texto
