"""
TC-M06-23 (RF-94 CA-13, CA-5, FA-6, RNF-05, Fase 7, CU-09/CU-10) - "Vista
legible y control de acceso."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda. Se
apoya en la evidencia ya reunida en TC-M06-22 (único endpoint real:
GET /finanzas/auditoria, parámetro real ``formato``).

Código bajo prueba:
    src/financial_valuation/application/use_cases/auditoria/consultar_auditoria_financiera_use_case.py (execute, bloque legible)
    src/financial_valuation/infrastructure/routers/m06_router.py (Query "formato", dependencies=[permiso(...)])
    alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py (_ROLES, _MATRIZ_PERMISOS['auditoria_financiera'])

HALLAZGO (el parámetro real se llama ``formato``, no ``formato_respuesta``):
el router define `formato: str = Query("LEGIBLE", pattern="^(LEGIBLE|TECNICO)$")`
-- la ficha asume un parámetro `formato_respuesta` que no existe con ese
nombre en ningún lugar del código real.

HALLAZGO GRAVE (no existe ningún rol llamado "Auditor" en todo el sistema):
el catálogo real de roles (`_ROLES` en la migración `c4d81e6f2a95`) es
exactamente `{1: Administrador, 2: Productor, 5: Contador, 8: Revisor
Fiscal}`. La matriz real de permisos para este recurso,
`'auditoria_financiera': {5: (2,), 1: (2,), 8: (2,)}`, da acceso de SOLO
LECTURA (acción 2=R) a los roles 5 (Contador), 1 (Administrador) y 8
(Revisor Fiscal) -- el tercer rol con acceso real es "Revisor Fiscal", NO
"Auditor" como asume la ficha. El rol 2 (Productor) está AUSENTE de esta
matriz: no tiene ningún acceso a este recurso, ni siquiera de lectura.

HALLAZGO (no existe ninguna restricción de alcance por período ni por
módulo dentro del RBAC): ni `ConsultarAuditoriaFinancieraUseCase.execute()`
ni `SqlAlchemyAuditoriaFinancieraRepository.consultar()` aplican ningún
filtro implícito basado en el usuario que hace la consulta (p. ej. "solo
los períodos del Contador que los generó" o "solo eventos de M06 para el
Revisor Fiscal"). El control de acceso de RF-94 es binario por recurso
(`auditoria_financiera` R, todo o nada): el Contador que tiene el permiso
puede consultar TODOS los períodos de TODOS los titulares, no solo "los
suyos" como exige la ficha -- porque el concepto de "período propio de un
Contador" no existe en ningún filtro ni condición del código real.

HALLAZGO (sin formato de moneda ni conversión a hora local en la vista
legible): el bloque `if legible:` real transforma el tipo de evento
(`descripcion_evento`), el actor (`actor`), la integridad
(`integridad_verificable`) y el origen (`origen`) a lenguaje natural, pero
`monto_afectado` se devuelve tal cual (sin formateo de moneda) y
`fecha_hora` se devuelve como el valor crudo de `timestamp_evento` (sin
ninguna conversión de zona horaria a "hora local" -- no hay código de
timezone en todo el use case).

HALLAZGO (el valor "Sincronizado desde respaldo" de ``origen`` es código
muerto en la práctica): la vista legible mapea
`origen_registro=="REPOSITORIO"` a "Repositorio central" y cualquier otro
valor a "Sincronizado desde respaldo" -- pero el único valor que
`registrar()` escribe de verdad es el literal `'REPOSITORIO'` (ver
TC-M06-13/TC-M06-20); sin un mecanismo de respaldo/fallback real en M06, la
segunda rama de este `if` nunca se alcanza en la práctica.

CONFIRMADO CORRECTO: la vista legible y la técnica consultan exactamente
el mismo conjunto de eventos -- ambas llaman primero a
`self.auditoria.consultar(filtros, ...)` y SOLO DESPUÉS, si `legible=True`,
transforman la lista ya obtenida; no hay una consulta SQL distinta para
cada formato. Tampoco existe ningún logger de lectura (ni en el use case ni
en el repositorio) -- no hay distinción real entre "log técnico" y
"repositorio" para las consultas, porque no existe ningún registro de
lectura en absoluto.

Cómo se prueba: pytest de unidad sobre `execute()` con un repositorio
simulado, más inspección de la migración real para el RBAC -- no requiere
BD viva.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_23_vista_legible_control_acceso.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-23.html --self-contained-html
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.financial_valuation.application.use_cases.auditoria.consultar_auditoria_financiera_use_case import (
    ConsultarAuditoriaFinancieraUseCase,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
ROUTER = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'
USE_CASE = REPO_ROOT / 'src/financial_valuation/application/use_cases/auditoria/consultar_auditoria_financiera_use_case.py'
REPOSITORIO = REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py'
MIGRACION = REPO_ROOT / 'alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py'

_EVENTO_CRUDO = {
    "id_evento": 1, "tipo_evento": "COSTO_REGISTRADO", "timestamp_evento": "2026-11-07T15:30:00-05:00",
    "nombre_usuario": "", "tipo_actor": "SISTEMA", "identificador_activo": "BOV-001",
    "id_periodo_contable": 4, "payload_evento": {"monto": "100.00"}, "monto_afectado": Decimal("1234567.89"),
    "severidad_evento": "INFO", "hash_integridad": "a" * 64, "payload_truncado": False, "origen_registro": "REPOSITORIO",
}


def _caso_de_uso(eventos=None):
    auditoria = MagicMock()
    auditoria.consultar.return_value = (1, eventos if eventos is not None else [dict(_EVENTO_CRUDO)])
    auditoria.conteo_por_severidad.return_value = {"INFO": 1, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    return ConsultarAuditoriaFinancieraUseCase(auditoria=auditoria), auditoria


class TestSubCasoElParametroRealSeLlamaFormatoNoFormatoRespuestaHallazgo:
    def test_el_router_real_usa_query_formato_no_formato_respuesta(self):
        texto = ROUTER.read_text(encoding='utf-8')
        pytest.fail(
            'HALLAZGO: el router real define formato: str = Query("LEGIBLE", '
            'pattern="^(LEGIBLE|TECNICO)$") -- no existe ningun parametro llamado '
            "formato_respuesta como asume la ficha."
        ) if 'formato: str = Query("LEGIBLE"' in texto and 'formato_respuesta' not in texto else None


class TestSubCasoNoExisteNingunRolLlamadoAuditorHallazgoGrave:
    def test_el_catalogo_real_de_roles_no_tiene_ningun_auditor(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO GRAVE: el catalogo real de roles (_ROLES) es "
            "{1: Administrador, 2: Productor, 5: Contador, 8: Revisor Fiscal} -- no existe NINGUN "
            "rol llamado 'Auditor' en todo el sistema. El tercer rol con acceso de lectura real a "
            "RF-94 es 'Revisor Fiscal', no 'Auditor' como asume la ficha."
        ) if "'Revisor Fiscal'" in texto and 'Auditor' not in texto.replace('Revisor Fiscal', '').replace('auditoria', '').replace('Auditoría', '') else None

    def test_la_matriz_real_da_lectura_a_contador_administrador_y_revisor_fiscal(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        assert "'auditoria_financiera': {5: (2,), 1: (2,), 8: (2,)}" in texto

    def test_el_productor_rol_2_esta_ausente_de_la_matriz_de_auditoria_financiera(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        linea = next(l for l in texto.splitlines() if "'auditoria_financiera'" in l and '(2,)' in l)
        assert '2:' not in linea


class TestSubCasoNoExisteNingunaRestriccionDeAlcancePorPeriodoNiPorModuloHallazgo:
    def test_execute_no_filtra_nada_por_el_usuario_que_consulta(self):
        import inspect
        firma = inspect.signature(ConsultarAuditoriaFinancieraUseCase.execute)
        pytest.fail(
            f"HALLAZGO: execute{firma} no recibe ningun parametro de usuario/rol/alcance -- no "
            f"hay forma de que el caso de uso aplique 'el Contador solo ve sus periodos' ni "
            f"'el Revisor Fiscal solo ve M06' porque no sabe quien esta consultando."
        ) if 'id_usuario' not in str(inspect.signature(ConsultarAuditoriaFinancieraUseCase.execute)) and \
             'rol' not in str(inspect.signature(ConsultarAuditoriaFinancieraUseCase.execute)) else None

    def test_el_repositorio_real_no_tiene_ninguna_condicion_de_alcance_por_periodo_propio(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: consultar() solo construye condiciones a partir de los filtros EXPLICITOS "
            "que el caller pasa (tipo_evento/id_activo_biologico/id_periodo_contable/severidad/"
            "id_usuario/desde/hasta) -- ninguna de ellas se deriva automaticamente de quien hace "
            "la consulta. El Contador con el permiso puede consultar TODOS los periodos de TODOS "
            "los titulares, no solo 'los suyos'."
        ) if 'id_usuario = :id_usuario' in texto else None


class TestSubCasoSinFormatoDeMonedaNiHoraLocalEnLaVistaLegibleHallazgo:
    def test_monto_afectado_se_devuelve_crudo_sin_formato_de_moneda(self):
        uc, _ = _caso_de_uso()
        resultado = uc.execute(filtros={"id_periodo_contable": 4}, pagina=1, tamano=100, legible=True)
        monto = resultado['eventos'][0]['monto_afectado']
        pytest.fail(
            f"HALLAZGO: monto_afectado se devuelve como {monto!r} (el Decimal crudo, "
            f"'1234567.89') -- sin ningun formato de moneda ('$1.234.567,89' o similar) como "
            f"pide la ficha (CA-13)."
        ) if monto == Decimal("1234567.89") else None

    def test_fecha_hora_se_devuelve_cruda_sin_conversion_a_hora_local(self):
        uc, _ = _caso_de_uso()
        resultado = uc.execute(filtros={"id_periodo_contable": 4}, pagina=1, tamano=100, legible=True)
        fecha = resultado['eventos'][0]['fecha_hora']
        pytest.fail(
            f"HALLAZGO: fecha_hora se devuelve como {fecha!r}, el mismo valor crudo de "
            f"timestamp_evento -- no existe ningun codigo de conversion de zona horaria a 'hora "
            f"local' en todo el use case."
        ) if fecha == _EVENTO_CRUDO['timestamp_evento'] else None


class TestSubCasoOrigenSincronizadoDesdeRespaldoEsCodigoMuertoHallazgo:
    def test_la_rama_sincronizado_desde_respaldo_nunca_se_alcanza_en_la_practica(self):
        texto_repo = REPOSITORIO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: la vista legible mapea cualquier origen_registro distinto de "
            "'REPOSITORIO' a 'Sincronizado desde respaldo' -- pero registrar() SOLO escribe el "
            "literal 'REPOSITORIO' siempre; sin un mecanismo de fallback real en M06 (ver "
            "TC-M06-20), esa rama de codigo nunca se ejecuta en la practica."
        ) if "'REPOSITORIO'" in texto_repo else None


class TestSubCasoLaVistaLegibleYTecnicaUsanElMismoConjuntoDeEventosConfirmadoCorrecto:
    def test_ambos_formatos_llaman_a_la_misma_consulta_subyacente(self):
        uc, auditoria = _caso_de_uso()
        uc.execute(filtros={"id_periodo_contable": 4}, pagina=1, tamano=100, legible=False)
        uc.execute(filtros={"id_periodo_contable": 4}, pagina=1, tamano=100, legible=True)
        assert auditoria.consultar.call_count == 2
        assert auditoria.consultar.call_args_list[0].args == auditoria.consultar.call_args_list[1].args

    def test_no_existe_ningun_logger_de_lectura_ni_distincion_log_tecnico_vs_repositorio(self):
        texto = USE_CASE.read_text(encoding='utf-8') + REPOSITORIO.read_text(encoding='utf-8')
        assert 'logging.getLogger' not in texto
        assert '.info(' not in texto and '.debug(' not in texto
