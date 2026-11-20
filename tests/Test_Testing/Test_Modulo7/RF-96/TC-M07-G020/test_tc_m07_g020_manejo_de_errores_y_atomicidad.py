"""
TC-M07-G020 (RF-96 Fase 5, FA-1 a FA-5, RNF-96.4, CU-08) - "Manejo de
errores y atomicidad." Agrupa TC-96-053 a TC-96-058.

Construido 2026-11-18 contra el código real (aaef.py,
consultar_aaef_use_case.py, gateway_aaef.py).

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py (mapear_compras)
    src/accounting_integration/application/use_cases/exportacion/consultar_aaef_use_case.py
    src/accounting_integration/infrastructure/gateway_aaef.py (_auditar)

Cómo se prueba: pytest de unidad -- la atomicidad es una propiedad natural
de Python (una excepción no retorna nada), no requiere mocks de BD para
confirmarla.

NO VERIFICABLE AQUÍ: "el mensaje en pantalla no muestra códigos internos"
depende del frontend (Playwright), fuera del alcance de este pytest de
backend.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g020_manejo_de_errores_y_atomicidad.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G020.html --self-contained-html
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from src.accounting_integration.domain.services.aaef import AaefError, CostoFactura, mapear_compras

D = Decimal


def _costo(id_registro_costo: int, completo: bool = True) -> CostoFactura:
    return CostoFactura(
        id_registro_costo=id_registro_costo, tercero_nit="900777571" if completo else None,
        tercero_razon_social="Concentrados La Pradera S.A.S.", factura_prefijo="CP",
        factura_numero=f"{1100 + id_registro_costo}", fecha_factura=datetime.date(2026, 10, 8),
        fecha_vencimiento_factura=datetime.date(2026, 11, 7), subtipo_costo="ALIMENTO",
        monto_costo=D("1000"), cuenta_debito="158405", activo=f"activo-{id_registro_costo}",
    )


class TestSubCasoElErrorEnElDocumento2De10DetieneElLote:
    def test_un_error_en_el_segundo_costo_impide_que_se_entregue_el_primero(self):
        lote = [_costo(1), _costo(2, completo=False)] + [_costo(i) for i in range(3, 11)]
        with pytest.raises(AaefError):
            mapear_compras(lote)
        # mapear_compras no tiene "return" parcial: la excepcion se propaga antes de
        # construir ningun documento, confirmado por diseño del lenguaje (no hay salida).


class TestSubCasoElErrorEnElUltimoDocumentoTambienDescartaTodo:
    def test_un_error_en_el_decimo_costo_tambien_bloquea_los_nueve_anteriores(self):
        lote = [_costo(i) for i in range(1, 10)] + [_costo(10, completo=False)]
        with pytest.raises(AaefError):
            mapear_compras(lote)


class TestSubCasoElOrdenDelErrorReportadoEsDeterministaConfirmadoCorrecto:
    def test_el_mismo_lote_siempre_reporta_el_mismo_costo_como_causante(self):
        lote = [_costo(1), _costo(2), _costo(3, completo=False), _costo(4, completo=False)]
        mensajes = set()
        for _ in range(5):
            with pytest.raises(AaefError) as exc_info:
                mapear_compras(list(lote))
            mensajes.add(exc_info.value.mensaje)
        assert len(mensajes) == 1  # siempre el mismo costo (el 3, primero en orden de iteracion)
        assert "El costo 3" in next(iter(mensajes))


class TestSubCasoRf97CancelaTodaLaGeneracionAnteUnErrorDeMapperDocumentacion:
    def test_consultar_aaef_use_case_envuelve_aaeferror_en_businessruleerror_sin_entregar_resultado(self):
        """Confirmado por lectura directa: ConsultarAaefUseCase.execute() envuelve
        CUALQUIER AaefError (de cualquiera de los dos Mappers) en BusinessRuleError y lo
        re-lanza -- no hay ningun camino que devuelva un ResultadoAaef parcial."""
        from pathlib import Path
        archivo = Path(__file__).resolve().parents[5] / (
            'src/accounting_integration/application/use_cases/exportacion/consultar_aaef_use_case.py')
        texto = archivo.read_text(encoding='utf-8')
        assert 'except AaefError as exc:' in texto
        assert 'raise BusinessRuleError(code=exc.codigo' in texto

    def test_el_gateway_real_registra_la_solicitud_rechazada_en_rf_102_con_el_codigo_del_error(self):
        """Confirmado por lectura directa de gateway_aaef.py: cualquier AppError (incluido
        el BusinessRuleError del Mapper) se audita como SOLICITUD_RECHAZADA con su
        exc.code -- RF-102 siempre recibe el Mapper/campo vía ese codigo y mensaje."""
        from pathlib import Path
        archivo = Path(__file__).resolve().parents[5] / 'src/accounting_integration/infrastructure/gateway_aaef.py'
        texto = archivo.read_text(encoding='utf-8')
        assert '"SOLICITUD_RECHAZADA"' in texto
        assert 'exc.status_code, exc.code' in texto
