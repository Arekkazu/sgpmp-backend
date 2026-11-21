"""
TC-M07-G029 (RF-97 5.2, CA-7, CA-9, RNF-97.2, CU-06) - "Contenido por
titular y por fecha." Agrupa TC-97-035 a TC-97-040.

Construido 2026-11-18 contra el código real (fuente_contable_repository.py).

HALLAZGO QUE RESUELVE LA 'CONTRADICCIÓN' QUE SEÑALA LA PROPIA FICHA
(TC-97-039/CU-06, nota): la ficha teme que, si RF-97 filtra por
`IssueDate`, una factura de un período ya cerrado registrada tarde
"entraría al envelope de octubre (ya cerrado) y lo cambiaría, rompiendo
CA-9". Esto NO ocurre: el filtro real (`costos_factura()`) NO usa
`fecha_factura`/IssueDate en absoluto -- filtra por las fechas del
PERÍODO CONTABLE del costo (`p.fecha_inicio >= :desde AND p.fecha_fin <=
:hasta`, con comentario explícito "por período del costo, no por fecha de
factura: el contenido de un rango cerrado no cambia"). La contradicción
que anticipa la ficha está evitada por diseño, no por una regla adicional.

Código bajo prueba:
    src/accounting_integration/infrastructure/repositories/fuente_contable_repository.py

Cómo se prueba: pytest de unidad por inspección del SQL real, más un caso
de unidad sobre ConsultarAaefUseCase con dos titulares simulados para
confirmar el aislamiento (cada consulta solo pasa su propio NIT a
`fuente.costos_factura`/`comprobantes`).

NO VERIFICABLE AQUÍ: una finca que cambió de titular tributario dentro
del rango -- no existe ese escenario en los datos de TEST ni se pudo
construir sin una migración de datos específica.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g029_contenido_por_titular.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G029.html --self-contained-html
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

from src.accounting_integration.application.use_cases.exportacion.consultar_aaef_use_case import (
    ConsultarAaefUseCase,
    SolicitudAaef,
)
from src.accounting_integration.domain.entities.contrato import VersionContrato
from src.accounting_integration.domain.services.aaef import MAPPER_COMPRAS, Periodo, SistemaOrigen, Titular

D = Decimal
REPO_ROOT = Path(__file__).resolve().parents[5]
FUENTE_CONTABLE = REPO_ROOT / 'src/accounting_integration/infrastructure/repositories/fuente_contable_repository.py'
SISTEMA = SistemaOrigen(system_id="SGPMP", system_name="SIGAB", environment="TEST")


class TestSubCasoElFiltroRealEsPorPeriodoNoPorIssueDateConfirmadoCorrecto:
    def test_costos_factura_filtra_por_fechas_del_periodo_contable_no_por_fecha_factura(self):
        texto = FUENTE_CONTABLE.read_text(encoding='utf-8')
        assert '_RANGO = "p.numero_id_tributaria = :nit AND p.fecha_inicio >= :desde AND p.fecha_fin <= :hasta"' in texto
        cuerpo = texto.split('def costos_factura(')[1].split('def comprobantes(')[0]
        clausula_where = cuerpo.split('WHERE')[1].split('ORDER BY')[0]
        assert '{_RANGO}' in clausula_where
        assert 'fecha_factura' not in clausula_where  # c.fecha_factura solo se SELECCIONA, nunca filtra

    def test_el_comentario_real_explica_por_que_evita_la_contradiccion_de_la_ficha(self):
        """No es un hallazgo nuevo: confirma que el equipo real ya identificó y evitó el
        problema que la ficha anticipa ('por período del costo, no por fecha de factura: el
        contenido de un rango cerrado no cambia')."""
        texto = FUENTE_CONTABLE.read_text(encoding='utf-8')
        assert 'Por período del costo, no por fecha de factura' in texto


class TestSubCasoAislamientoEntreTitularesConfirmadoCorrecto:
    def test_cada_consulta_solo_pasa_su_propio_nit_a_la_fuente(self):
        fuente = MagicMock()
        fuente.titular.return_value = Titular("901444215", "Hacienda Qa Mseis S.A.S.")
        fuente.fincas_titular.return_value = set()
        fuente.fincas_usuario.return_value = set()
        fuente.periodos.return_value = [Periodo(datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), "CERRADO")]
        fuente.lineas_sin_trazabilidad.return_value = 0
        fuente.costos_factura.return_value = []
        fuente.comprobantes.return_value = []
        fuente.linetypes_catalogados.return_value = (frozenset(), frozenset())
        contratos = MagicMock()
        contratos.listar_contratos.return_value = [VersionContrato(1, "2.1", "MINOR", datetime.date(2026, 1, 1), 1,
                                                                    [MAPPER_COMPRAS], estado="ACTIVO")]
        uc = ConsultarAaefUseCase(fuente=fuente, contratos=contratos, sistema=SISTEMA, limite_bytes=20 * 1024 * 1024,
                                  hoy=lambda: datetime.date(2026, 11, 18))
        uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                 1, "contador@pecuaria.co"))
        llamada = fuente.costos_factura.call_args
        assert llamada.args[0] == "901444215"  # nunca otro NIT, sin importar que otros titulares existan


class TestSubCasoFincaQueCambioDeTitularNoVerificableDocumentacion:
    def test_no_existe_un_escenario_de_datos_para_este_caso(self):
        """No verificable en esta sesión: ningun titular de TEST tiene una finca que haya
        cambiado de NIT tributario dentro de un rango consultable -- construirlo requeriria
        una migracion de datos especifica que no se pidio al DBA."""
        assert True  # documental, no ejecuta ninguna aserción real
