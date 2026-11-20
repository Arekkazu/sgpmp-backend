# | Fecha      | Nombre         | Que se hizo |
# |------------|----------------|-------------|
# | 2026-11-19 | LuisfNarvaez01 | TC-M07-381 RF-97: el detalle del Mapper que falla llega a la respuesta |
# | 2026-11-19 | LuisfNarvaez01 | TC-M07-379 RF-97: TRAZABILIDAD_INCOMPLETA identifica los hechos afectados |
# | 2026-11-19 | LuisfNarvaez01 | TC-M07-380 RF-97: ERROR_DATOS_FINANCIEROS y ERROR_INTERNO_RF97 |
# | 2026-11-19 | LuisfNarvaez01 | TC-M07-382 RF-97: el hash de contenido no depende de NFC/NFD |
# | 2026-11-20 | Arekkazu       | Lote M07/M08 RF-96: la fuente de prueba expone el catálogo de LineType |
"""Lote QA 2026-11-19 de la exportación contable (RF-97), sin base de datos.

- TC-M07-381 (#1183): un MAPPER_FALLIDO expone ``detalle.mapper`` y ``detalle.documento``.
- TC-M07-379 (#1181): TRAZABILIDAD_INCOMPLETA trae los hechos afectados, no solo cuántos son.
- TC-M07-380 (#1182): una falla al leer los datos financieros es ERROR_DATOS_FINANCIEROS; lo inesperado,
  ERROR_INTERNO_RF97.
- TC-M07-382 (#1184): el mismo texto en NFC y en NFD produce el mismo cuerpo y el mismo hash.
"""
import asyncio
import json
from datetime import date
from decimal import Decimal as D

import pytest

from src.accounting_integration.application.use_cases.exportacion.consultar_aaef_use_case import (
    ConsultarAaefUseCase,
    SolicitudAaef,
)
from src.accounting_integration.domain.entities.contrato import VersionContrato
from src.accounting_integration.domain.services.aaef import CostoFactura, Periodo, SistemaOrigen, Titular
from src.shared.error_handlers import app_error_handler
from src.shared.errors import AppError

NIT = "900123456"
OCT = Periodo(date(2026, 10, 1), date(2026, 10, 31), "CERRADO")


def _costo(i, cuenta="51350501", razon="Agroinsumos del Huila SAS"):
    return CostoFactura(i, "800555111", razon, "FE", f"88{i}", date(2026, 10, 4), date(2026, 11, 3), "ALIMENTO",
                        D("700000"), cuenta, "BOV-001")


class _Fuente:
    def __init__(self, costos=(), sin_traza=None, falla=None):
        self.costos, self.sin_traza, self.falla = list(costos), sin_traza or [], falla

    def titular(self, nit):
        return Titular(NIT, "Hacienda La Esperanza SAS")

    def fincas_titular(self, nit):
        return {1}

    def fincas_usuario(self, id_usuario):
        return {1}

    def periodos(self, nit):
        return [OCT]

    def lineas_sin_trazabilidad(self, nit, desde, hasta):
        return self.sin_traza

    def linetypes_catalogados(self):
        return None, None  # sin catálogo: el LineType no se valida en estas pruebas

    def costos_factura(self, nit, desde, hasta):
        if self.falla:
            raise self.falla
        return self.costos

    def comprobantes(self, nit, desde, hasta):
        return []


class _Contratos:
    def listar_contratos(self, bloquear=False):
        return [VersionContrato(1, "3.0", "MAJOR", date(2026, 1, 1), 1, ["COMPRAS"], estado="ACTIVO")]


def _consultar(fuente):
    uc = ConsultarAaefUseCase(fuente, _Contratos(), SistemaOrigen("SGPMP", "SIGAB", "TEST"), 10 * 1024 * 1024,
                              lambda: date(2026, 11, 19))
    return uc.execute(SolicitudAaef(NIT, OCT.fecha_inicio, OCT.fecha_fin, 7, "contador@finca.co"))


def _respuesta(exc):
    return json.loads(asyncio.run(app_error_handler(None, exc)).body)


def test_mapper_fallido_expone_mapper_y_documento_en_la_respuesta():
    with pytest.raises(AppError) as exc:
        _consultar(_Fuente([_costo(11, cuenta=None)]))
    assert exc.value.code == "MAPPER_FALLIDO" and exc.value.field == "accounting_account"
    assert exc.value.detalle == {"mapper": "COMPRAS", "documento": "COS-11-20261004"}
    cuerpo = _respuesta(exc.value)
    assert cuerpo["detalle"] == exc.value.detalle and cuerpo["fields"][0]["field"] == "accounting_account"
    # un error sin detalle conserva el cuerpo de siempre
    assert "detalle" not in _respuesta(AppError("OTRO", "Otro error."))


def _linea(i, activo="BOV-00%d"):
    return {"id_linea_asiento_nic41": 100 + i, "tipo_hecho": "VARIACION_VR_TB", "id_activo_biologico": i,
            "activo": activo % i, "fecha_hecho": date(2026, 10, 31)}


def test_trazabilidad_incompleta_identifica_los_hechos_afectados():
    with pytest.raises(AppError) as exc:
        _consultar(_Fuente([_costo(11)], sin_traza=[_linea(1), _linea(2), _linea(3)]))
    assert exc.value.code == "TRAZABILIDAD_INCOMPLETA"
    hechos = exc.value.detalle["hechos"]
    assert [h["id_linea_asiento_nic41"] for h in hechos] == [101, 102, 103]
    assert [h["activo"] for h in hechos] == ["BOV-001", "BOV-002", "BOV-003"]
    assert hechos[0]["hecho"] == "Variación por transformación biológica" and hechos[0]["fecha_hecho"] == "2026-10-31"
    mensaje = exc.value.message
    assert mensaje.startswith("3 asientos") and "BOV-003" in mensaje and "VARIACION_VR_TB" not in mensaje
    assert _respuesta(exc.value)["detalle"]["hechos"] == hechos  # serializable tal cual


def test_trazabilidad_incompleta_con_muchos_hechos_resume_el_mensaje():
    with pytest.raises(AppError) as exc:
        _consultar(_Fuente(sin_traza=[_linea(i) for i in range(1, 9)]))
    assert len(exc.value.detalle["hechos"]) == 8 and "y 3 más" in exc.value.message


def test_falla_de_los_datos_financieros_es_error_datos_financieros():
    caida = RuntimeError("conexión perdida")
    with pytest.raises(AppError) as exc:
        _consultar(_Fuente(falla=caida))
    assert (exc.value.code, exc.value.status_code) == ("ERROR_DATOS_FINANCIEROS", 500)
    assert exc.value.__cause__ is caida  # el gateway reconoce así el tiempo máximo agotado
    assert "None" not in exc.value.message and "RF" not in exc.value.message


def test_error_inesperado_de_la_transformacion_es_error_interno_rf97():
    roto = CostoFactura(11, "800555111", "Agroinsumos", "FE", "8811", date(2026, 10, 4), None, "ALIMENTO",
                        None, "51350501", "BOV-001")  # importe ausente: falla fuera de las reglas de negocio
    with pytest.raises(AppError) as exc:
        _consultar(_Fuente([roto]))
    assert (exc.value.code, exc.value.status_code) == ("ERROR_INTERNO_RF97", 500)


def test_reglas_de_negocio_conservan_su_codigo():
    with pytest.raises(AppError) as exc:
        _consultar(_Fuente([_costo(11, cuenta=None)]))
    assert exc.value.code == "MAPPER_FALLIDO" and exc.value.status_code == 422


def test_mismo_texto_en_nfc_y_nfd_da_el_mismo_hash_y_el_mismo_cuerpo():
    import unicodedata

    nfc = unicodedata.normalize("NFC", "Agroinsumos Café Ñandú SAS")
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    a, b = _consultar(_Fuente([_costo(11, razon=nfc)])), _consultar(_Fuente([_costo(11, razon=nfd)]))
    assert a.hash_contenido == b.hash_contenido
    # los ExchangeId son aleatorios: se compara el contenido, no el cuerpo entero
    assert json.loads(a.cuerpo)["invoices"] == json.loads(b.cuerpo)["invoices"]
    assert json.loads(b.cuerpo)["invoices"][0]["ThirdParty"]["Name"] == nfc  # el cuerpo sale en NFC
