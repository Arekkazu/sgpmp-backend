# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-308-G12 RF-83: alerta MEDICION_PENDIENTE al Contador por medición estimada |
# | 2026-11-08 | destroyerban | INC-M06-312-G14 RF-83: fakes con período abierto y evento no encolado |
# | 2026-11-10 | Arekkazu | Lote M05/M06: fakes al día con el lote integrado (elegibilidad, alertas, período cerrado, referencia documental) |
"""INC-M06-308-G12 / RF-83 restricción 3 y salida 4: una medición estimada (sin precio vigente, con el último
precio conocido) registra ``MEDICION_CON_ESTIMACION`` y además alerta al Contador con ``MEDICION_PENDIENTE``.
La alerta sale después del ``commit()`` y no sale si la transacción se revierte."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.services.medidor import Medidor
from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import (
    ProcesarEventosM02UseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.services.precios import Precio

D = Decimal
PERIODO = Periodo(id_periodo_contable=3, numero_id_tributaria="900", tipo_cierre="MENSUAL",
                  fecha_inicio=date(2026, 11, 1), fecha_fin=date(2026, 11, 30), estado="ABIERTO")
# Último precio conocido, vencido antes del día medido: la medición es estimada (RF-83 FA-1).
PRECIO_VENCIDO = Precio(id_precio_mercado=1, id_especie=2, categoria="PESO_KG", precio_unitario=D("10"),
                        unidad_medida="kg", fuente="MERCADO_ACTIVO", fecha_vigencia=date(2026, 9, 1),
                        fecha_vencimiento=date(2026, 10, 31))
ACTIVO = SimpleNamespace(estado="ACTIVO", es_valorable=True, id_activo_biologico=7, identificador="BOV-007", especie="Bovino", id_especie=2, id_finca=4,
                         numero_id_tributaria="900", id_dispositivo_iot=None)


def _calculo(magnitud: str, neto: str, *, estimado: bool = False, id_calculo=None) -> CalculoValor:
    return CalculoValor(
        id_activo_biologico=7, id_precio_mercado=1, id_periodo_contable=3, magnitud=D(magnitud), unidad_magnitud="kg",
        precio_unitario=D("10"), valor_razonable_bruto=D(neto), costo_transporte=D(0), costo_comisiones=D(0),
        costo_impuestos_transaccion=D(0), otros_costos_disposicion=D(0), valor_neto=D(neto), metodo_costo="PARAMETRIZADO",
        json_metodo_costo={}, id_usuario=1, tiene_valor_estimado=estimado, id_calculo_valor_razonable=id_calculo,
    )


class ValoracionesFake:
    def __init__(self, anterior) -> None:
        self.anterior = anterior

    def ultimo_calculo(self, _id):
        return self.anterior

    def valoracion_costo_activa(self, _id):
        return None

    def agregar_calculo(self, _c):
        return 101

    def agregar_medicion(self, _m):
        return 201

    def agregar_variacion(self, _v):
        return 301


class ContabilizadorFake:
    def __init__(self) -> None:
        self.eventos = []

    def periodo_para(self, *_a):
        return PERIODO

    def periodo_cerrado_en(self, *_a):
        return None

    def asentar(self, linea, _id_usuario):
        return linea

    def auditar(self, evento):
        self.eventos.append(evento)


def _medidor(nuevo=None, *, valido: bool = True, anterior=None):
    resultado = SimpleNamespace(es_valido=True, calculo=nuevo, precio=PRECIO_VENCIDO) if valido \
        else SimpleNamespace(es_valido=False, motivo="SIN_PRECIO", mensaje="No hay precio de mercado para la especie.")
    valorador = SimpleNamespace(valorar=lambda *a, **k: resultado)
    contabilizador = ContabilizadorFake()
    medidor = Medidor(valorador, ValoracionesFake(anterior or _calculo("400", "4000", id_calculo=90)), contabilizador)
    return medidor, contabilizador


def _medir(medidor):
    return medidor.medir(ACTIVO, PERIODO, date(2026, 11, 8), origen="EVENTO", id_usuario=1, id_usuario_auditoria=None,
                         id_evento=55)


def test_medicion_estimada_audita_medicion_pendiente_y_deja_alerta() -> None:
    medidor, contabilizador = _medidor(_calculo("410", "4100", estimado=True))

    assert _medir(medidor).estado == "MEDIDO"

    tipos = [e.tipo_evento for e in contabilizador.eventos]
    assert tipos[-2:] == ["MEDICION_CON_ESTIMACION", "MEDICION_PENDIENTE"]
    pendiente = contabilizador.eventos[-1]
    assert pendiente.severidad == "WARNING"
    assert pendiente.payload["motivo"] == "PRECIO_ESTIMADO" and pendiente.payload["id_medicion"] == 201
    assert pendiente.id_activo_biologico == 7 and pendiente.id_referencia == 201
    [alerta] = medidor.tomar_alertas()
    assert alerta.id_finca == 4
    assert "BOV-007" in alerta.mensaje and "2026-11-08" in alerta.mensaje and "Bovino" in alerta.mensaje
    assert "None" not in alerta.mensaje and "RF-" not in alerta.mensaje
    assert alerta.detalle["id_activo_biologico"] == 7 and alerta.detalle["fecha"] == "2026-11-08"
    assert medidor.tomar_alertas() == []  # la cola se vacía


def test_medicion_con_precio_vigente_no_alerta() -> None:
    medidor, contabilizador = _medidor(_calculo("410", "4100"))

    _medir(medidor)

    assert "MEDICION_PENDIENTE" not in [e.tipo_evento for e in contabilizador.eventos]
    assert medidor.tomar_alertas() == []


def test_medicion_pendiente_sin_precio_tambien_alerta() -> None:
    medidor, contabilizador = _medidor(valido=False)

    assert _medir(medidor).estado == "PENDIENTE"

    assert [e.tipo_evento for e in contabilizador.eventos] == ["MEDICION_PENDIENTE"]
    assert contabilizador.eventos[0].payload["mensaje"] == "No hay precio de mercado para la especie."
    [alerta] = medidor.tomar_alertas()
    assert alerta.mensaje == ("La medición del activo BOV-007 quedó pendiente: "
                              "No hay precio de mercado para la especie.")


class DbFake:
    def __init__(self) -> None:
        self.orden = []

    def commit(self):
        self.orden.append("commit")

    def rollback(self):
        self.orden.append("rollback")


class NotificadorFake:
    def __init__(self, db: DbFake) -> None:
        self.db, self.avisos = db, []

    def a_contadores(self, tipo_evento, mensaje, detalle, id_finca=None):
        self.db.orden.append("aviso")
        self.avisos.append((tipo_evento, mensaje, id_finca))


class EventosFake:
    def __init__(self, falla_registro: bool = False) -> None:
        self.falla_registro = falla_registro

    def pendientes(self, _limite):
        return [SimpleNamespace(id_evento=55, tipo="CRECIMIENTO", id_activo_biologico=7, datos={},
                                fecha=datetime(2026, 11, 8, 15, tzinfo=timezone.utc), encolado_en_cierre=False,
                                sin_reconocimiento=False)]

    def registrar_procesamiento(self, _id, resultado, _detalle):
        if self.falla_registro and resultado != "ERROR":
            raise RuntimeError("fallo de BD")


@pytest.mark.parametrize("falla, esperado", [(False, ["commit", "aviso"]), (True, ["rollback", "commit"])])
def test_procesador_avisa_despues_del_commit_y_descarta_si_revierte(falla, esperado) -> None:
    medidor, contabilizador = _medidor(_calculo("410", "4100", estimado=True))
    db = DbFake()
    notificador = NotificadorFake(db)
    caso = ProcesarEventosM02UseCase(db, EventosFake(falla), SimpleNamespace(obtener=lambda _id: ACTIVO),
                                     medidor.valoraciones, None, medidor, contabilizador, 1, notificador)

    caso.execute()

    assert db.orden == esperado
    if not falla:
        [(tipo, mensaje, finca)] = notificador.avisos
        assert tipo == "ALERTA_FINANCIERA_NIC41" and finca == 4 and "precio estimado" in mensaje
    assert medidor.tomar_alertas() == []
