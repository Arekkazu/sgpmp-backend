"""
TC-M02-G56 (TC-M02-105) - Reintento 2 (2026-09-26) - Control de acceso a datos
genealogicos de activos de otra finca (Seguridad - OWASP API1 BOLA).

RECTIFICACION sobre el archivo original (test_tc_m02_g56_bola_activo_relacionado_otra_finca.py,
que queda intacto como evidencia historica): el hallazgo original -- "cualquier id_padre de
otra finca es aceptado sin validar pertenencia" -- fue reportado el 2026-09-19/22, ANTES de que
`origin/test` mergeara (2026-09-26, commit del merge en esta rama) el fix INC-M02-77-G56.

Con el codigo actual de registrar_evento_reproductivo_use_case.py, `_validar_activo_relacionado()`
(lineas 226-255) SI valida la finca del padre/madre contra la del activo objetivo -- pero la
comparacion es por `id_finca` (via `infra_port.obtener_activa(id_infraestructura).id_finca`),
NO por `id_infraestructura` directamente. Esto importa porque dos infraestructuras distintas
pueden pertenecer a la MISMA finca -- el mock original de este TC (que solo parcheaba
`activo_repo` y comparaba implicitamente por id_infraestructura, sin `infra_port` en absoluto)
ya no representa el comportamiento real del use case: hoy ese mock haria que
`self.infra_port.obtener_activa(...)` devuelva un MagicMock cualquiera (atributo `id_finca`
tambien un MagicMock), y la comparacion `!=` entre dos MagicMock distintos siempre es True ->
el mock original pasaria por "casualidad" (siempre rechaza), no porque pruebe la logica real.

Este reintento 2 corrige el doble de prueba para incluir `infra_port` explicitamente y agrega
el escenario que el reporte original nunca cubrio: padre en OTRA infraestructura pero la MISMA
finca (debe aceptarse, no es BOLA) vs. padre en una finca genuinamente distinta (debe rechazarse
por diseño, HTTP 404 con el mismo mensaje que "no existe" -- anti-enumeracion, ver docstring del
use case).

Veredicto revisado: el BOLA original de este TC esta CERRADO por el fix INC-M02-77-G56. Se deja
como regresion positiva (Pytest en verde documentando el comportamiento correcto), no como
hallazgo abierto.

Como correrlo (desde la raiz del repo; en Windows hace falta el stub de fcntl -- el buffer de
auditoria RF-52 E1/E3 importa fcntl sin guardia de plataforma):
    $env:PYTHONPATH = "_win_fcntl_stub"
    python -m pytest <ruta>\\test_tc_m02_g56_bola_activo_relacionado_otra_finca_reintento2.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M02-G56_reintento2.html --self-contained-html
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoActivo,
    EventoReproductivo,
)
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import RegistrarEventoReproductivoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_ACTIVO_MADRE = 200
ID_INFRAESTRUCTURA_PROPIA = 3       # finca 1
ID_ACTIVO_PADRE_MISMA_FINCA = 700   # otra infraestructura, MISMA finca (no debe rechazarse)
ID_INFRAESTRUCTURA_HERMANA = 5      # distinta infraestructura, finca 1 tambien
ID_ACTIVO_PADRE_AJENO = 900         # activo de OTRA finca, fuera del alcance del usuario
ID_INFRAESTRUCTURA_AJENA = 4        # finca 2


def _activo(id_activo_biologico: int, id_infraestructura: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=10,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=id_infraestructura,
        id_estado=1,  # ACTIVO
        id_usuario=1,
        id_activo_biologico=id_activo_biologico,
        fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _infra(id_infraestructura: int, id_finca: int) -> InfraestructuraConsulta:
    return InfraestructuraConsulta(
        id_infraestructura=id_infraestructura,
        nombre=f'infra-{id_infraestructura}',
        tipo='POTRERO',
        es_activo=True,
        id_finca=id_finca,
    )


# Mapa infraestructura -> finca usado por todos los escenarios:
#   3 (propia)  -> finca 1
#   5 (hermana) -> finca 1  (misma finca, otra infraestructura)
#   4 (ajena)   -> finca 2  (finca distinta)
_FINCA_POR_INFRAESTRUCTURA = {
    ID_INFRAESTRUCTURA_PROPIA: 1,
    ID_INFRAESTRUCTURA_HERMANA: 1,
    ID_INFRAESTRUCTURA_AJENA: 2,
}


def _infra_port_doble():
    infra_port = MagicMock()
    infra_port.obtener_activa.side_effect = lambda id_infra: _infra(id_infra, _FINCA_POR_INFRAESTRUCTURA[id_infra])
    return infra_port


class TestTCM02G56Reintento2FincaVsInfraestructura:
    """Suite reintento2 -- TC-M02-105, comportamiento correcto post INC-M02-77-G56."""

    def test_use_case_acepta_padre_de_otra_infraestructura_misma_finca(self):
        """No es BOLA: dos infraestructuras distintas de la MISMA finca deben poder
        relacionarse genealogicamente."""
        madre = _activo(ID_ACTIVO_MADRE, ID_INFRAESTRUCTURA_PROPIA)
        padre = _activo(ID_ACTIVO_PADRE_MISMA_FINCA, ID_INFRAESTRUCTURA_HERMANA)

        def _obtener_por_id(id_activo, ids_fincas_permitidas=None):
            return {ID_ACTIVO_MADRE: madre, ID_ACTIVO_PADRE_MISMA_FINCA: padre}.get(id_activo)

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.side_effect = _obtener_por_id
        activo_repo.obtener_fase_activa.return_value = MagicMock()  # fase activa presente

        evento_guardado = EventoActivo(
            id_activo_biologico=ID_ACTIVO_MADRE,
            fecha=datetime(2026, 9, 26, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=601,
            reproductivo=EventoReproductivo(
                categoria='servicio', resultado='exitoso', id_padre=ID_ACTIVO_PADRE_MISMA_FINCA,
            ),
        )
        evento_repo = MagicMock()
        evento_repo.obtener_ultima_fecha.return_value = None
        evento_repo.guardar.return_value = evento_guardado

        use_case = RegistrarEventoReproductivoUseCase(
            db=MagicMock(),
            activo_repo=activo_repo,
            evento_repo=evento_repo,
            infra_port=_infra_port_doble(),
            bitacora_repo=MagicMock(),
        )
        dto = RegistrarEventoReproductivoDTO(categoria='servicio', resultado='exitoso', id_padre=ID_ACTIVO_PADRE_MISMA_FINCA)
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=2, id_estado_cuenta=2)

        resultado = use_case.execute(ID_ACTIVO_MADRE, dto, usuario_actual)

        assert resultado is evento_guardado
        evento_repo.guardar.assert_called_once()

    def test_use_case_rechaza_padre_de_finca_genuinamente_distinta(self):
        """BOLA cerrado: un padre de una finca distinta debe rechazarse con
        ACTIVO_RELACIONADO_NO_ENCONTRADO (mismo codigo que 'no existe', por diseño anti-enumeracion)."""
        madre = _activo(ID_ACTIVO_MADRE, ID_INFRAESTRUCTURA_PROPIA)
        padre_ajeno = _activo(ID_ACTIVO_PADRE_AJENO, ID_INFRAESTRUCTURA_AJENA)

        def _obtener_por_id(id_activo, ids_fincas_permitidas=None):
            return {ID_ACTIVO_MADRE: madre, ID_ACTIVO_PADRE_AJENO: padre_ajeno}.get(id_activo)

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.side_effect = _obtener_por_id
        activo_repo.obtener_fase_activa.return_value = MagicMock()

        evento_repo = MagicMock()
        evento_repo.obtener_ultima_fecha.return_value = None

        use_case = RegistrarEventoReproductivoUseCase(
            db=MagicMock(),
            activo_repo=activo_repo,
            evento_repo=evento_repo,
            infra_port=_infra_port_doble(),
            bitacora_repo=MagicMock(),
        )
        dto = RegistrarEventoReproductivoDTO(categoria='servicio', resultado='exitoso', id_padre=ID_ACTIVO_PADRE_AJENO)
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=2, id_estado_cuenta=2)

        with pytest.raises(Exception) as excinfo:
            use_case.execute(ID_ACTIVO_MADRE, dto, usuario_actual)

        assert getattr(excinfo.value, 'code', None) == 'ACTIVO_RELACIONADO_NO_ENCONTRADO', (
            f'se esperaba ACTIVO_RELACIONADO_NO_ENCONTRADO, se obtuvo: {excinfo.value!r}'
        )
        evento_repo.guardar.assert_not_called()

    def test_endpoint_rechaza_padre_de_finca_distinta_con_404(self):
        """Mismo escenario que arriba, pero via TestClient contra el router real (con
        InfraestructuraM09Adapter.obtener_activa parcheado, ya que el router la instancia
        directamente con la sesion de BD en vez de recibirla por Depends)."""
        from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import (
            InfraestructuraM09Adapter,
        )
        from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
            SqlAlchemyActivoBiologicoRepository,
        )
        from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
            SqlAlchemyBitacoraAuditoriaRepository,
        )
        from src.biological_assets.infrastructure.repositories.evento_activo_repository import (
            SqlAlchemyEventoActivoRepository,
        )
        from src.biological_assets.infrastructure.routers.activo_biologico_router import (
            router as activo_biologico_router,
        )
        from src.identity_access.infrastructure.dependencies import get_current_user
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        madre = _activo(ID_ACTIVO_MADRE, ID_INFRAESTRUCTURA_PROPIA)
        padre_ajeno = _activo(ID_ACTIVO_PADRE_AJENO, ID_INFRAESTRUCTURA_AJENA)

        def _obtener_por_id(id_activo, ids_fincas_permitidas=None):
            return {ID_ACTIVO_MADRE: madre, ID_ACTIVO_PADRE_AJENO: padre_ajeno}.get(id_activo)

        fake_db = MagicMock()
        app = FastAPI()
        register_error_handlers(app)
        app.include_router(activo_biologico_router)

        app.dependency_overrides[get_db] = lambda: (yield fake_db)
        app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
            id_usuario=1, id_token=1, id_rol=2, id_estado_cuenta=2,
        )

        with (
            patch.object(SqlAlchemyActivoBiologicoRepository, 'obtener_por_id', side_effect=_obtener_por_id),
            patch.object(SqlAlchemyActivoBiologicoRepository, 'obtener_fase_activa', return_value=MagicMock()),
            patch.object(SqlAlchemyEventoActivoRepository, 'obtener_ultima_fecha', return_value=None),
            patch.object(SqlAlchemyBitacoraAuditoriaRepository, 'registrar', return_value=None),
            patch.object(
                InfraestructuraM09Adapter, 'obtener_activa',
                side_effect=lambda self_id_infra: _infra(self_id_infra, _FINCA_POR_INFRAESTRUCTURA[self_id_infra]),
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"/activos-biologicos/{ID_ACTIVO_MADRE}/eventos/reproductivo",
                json={"categoria": "servicio", "resultado": "exitoso", "id_padre": ID_ACTIVO_PADRE_AJENO},
            )

        assert response.status_code == 404, (
            f'se esperaba 404 ACTIVO_RELACIONADO_NO_ENCONTRADO; se obtuvo {response.status_code}: {response.text}'
        )
        cuerpo = response.json()
        assert cuerpo['error_code'] == 'ACTIVO_RELACIONADO_NO_ENCONTRADO'
        # Anti-enumeracion: el mensaje solo debe mencionar el id ya conocido por el
        # solicitante (id_padre=900, el mismo que envio en el payload) -- nunca su
        # id_infraestructura/finca real (eso confirmaria que el recurso SI existe
        # fuera de su alcance, la fuga que el diseño busca evitar).
        assert str(ID_INFRAESTRUCTURA_AJENA) not in cuerpo['message']
        assert str(ID_ACTIVO_PADRE_AJENO) in cuerpo['message']

        app.dependency_overrides.clear()
