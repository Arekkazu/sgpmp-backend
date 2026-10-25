# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74..81: reglas de dominio del RF       |
"""Reglas de dominio de M05 que cambiaron para cumplir el RF (sin BD)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.shared.errors import AuthorizationError, BusinessRuleError, GoneError, ValidationError
from src.supplies.application.use_cases.exportacion.generador_archivos import (
    Documento,
    generar_csv,
    generar_excel,
    generar_pdf,
)
from src.supplies.domain.entities.acumulado_ciclo import AcumuladoCiclo
from src.supplies.domain.entities.archivo_exportacion import ArchivoExportacion
from src.supplies.domain.entities.evento_provision_m06 import EstadoEventoProvision, EventoProvisionM06
from src.supplies.domain.entities.historial_suministro import FiltrosHistorialSuministro
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto
from src.supplies.domain.services.calculadora_ica import CalculadoraICA
from src.supplies.domain.services.consolidador_nic41 import construir_consolidado
from src.supplies.domain.value_objects.eficiencia_enums import CausaNoCalculo, EstadoResultadoCA
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import clasificar_retencion
from src.supplies.domain.value_objects.historial_suministro_enums import NivelVolumen, nivel_volumen
from src.supplies.domain.value_objects.justificacion_anulacion import MENSAJE_RF76, JustificacionAnulacion
from src.supplies.domain.value_objects.justificacion_precio import JustificacionPrecio

AHORA = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)


def _registro(costo: str, tipo: str = "ALIMENTO", operacion: str = "REGISTRO") -> RegistroSuministroDirecto:
    return RegistroSuministroDirecto(
        id_activo_biologico=1, id_ciclo_productivo=1, id_gestion_fases=10, tipo_suministro=tipo,
        cantidad=Decimal("10"), unidad_medida="kg", precio_unitario_resuelto=Decimal(costo) / 10,
        costo_registro=Decimal(costo), origen_precio="MANUAL", fecha_aplicacion=date(2026, 10, 1),
        naturaleza_costo="MANTENIMIENTO", id_idempotencia=uuid4(), tipo_operacion=operacion,
        id_registro_suministro=uuid4(),
    )


def _acumulado(total: str) -> AcumuladoCiclo:
    return AcumuladoCiclo(id_activo_biologico=1, id_ciclo_productivo=1, id_gestion_fases=10,
                          acumulado_total_ciclo=Decimal(total))


# ── RF-78 R7/R12/RNF-09: corrección aditiva ───────────────────────────────
def test_consolidado_suma_todas_las_filas_incluidas_las_correcciones():
    registros = [_registro("100"), _registro("-30", operacion="CORRECCION"), _registro("20", "MEDICAMENTO")]
    resultado = construir_consolidado(registros, _acumulado("90"))
    assert resultado.monto_provision == Decimal("90")
    assert resultado.desglose_categoria == {"ALIMENTO": Decimal("70"), "MEDICAMENTO": Decimal("20")}
    assert resultado.es_reporte_potencialmente_incompleto is False


def test_consolidado_incompleto_si_lo_incremental_no_cuadra_o_hay_retenidos():
    registros = [_registro("100")]
    assert construir_consolidado(registros, _acumulado("100"), suma_incremental=Decimal("40")) \
        .es_reporte_potencialmente_incompleto
    assert construir_consolidado(registros, _acumulado("100"), eventos_sin_entregar=1) \
        .es_reporte_potencialmente_incompleto


def test_correccion_que_deja_acumulado_negativo_es_422():
    with pytest.raises(BusinessRuleError):
        _acumulado("50").validar_correccion_no_negativa(Decimal("-60"))
    assert _acumulado("50").validar_correccion_no_negativa(Decimal("-50")) == Decimal("0")


def test_compensacion_neutraliza_el_costo_vigente_exacto():
    original = _registro("123.4567")
    compensacion = RegistroSuministroDirecto.crear_compensacion(
        original=original, costo_compensatorio=Decimal("-123.4567"), motivo_correccion="anulación", id_idempotencia=uuid4()
    )
    assert compensacion.tipo_operacion == "CORRECCION"
    assert compensacion.id_registro_original == original.id_registro_suministro
    assert original.costo_registro + compensacion.costo_registro == 0


# ── RF-79: reintentos de entrega a M06 ────────────────────────────────────
def test_evento_m06_reintenta_5_veces_y_alerta_una_sola_vez():
    evento = EventoProvisionM06.incremental(
        id_activo_biologico=1, id_ciclo_productivo=1, id_gestion_fases=10, id_registro_suministro=uuid4(),
        tipo_suministro="ALIMENTO", tipo_operacion="REGISTRO", costo_registro=Decimal("10"),
        acumulado_total_ciclo=Decimal("10"), acumulado_por_categoria={"ALIMENTO": Decimal("10")}, ahora=AHORA,
    )
    esperas = []
    for _ in range(4):
        assert evento.registrar_fallo(AHORA) is False
        esperas.append((evento.fecha_proximo_intento - AHORA).total_seconds())
    assert esperas == [5, 15, 30, 60]
    assert evento.registrar_fallo(AHORA) is True
    assert evento.estado == EstadoEventoProvision.PROVISION_PENDIENTE.value
    assert evento.registrar_fallo(AHORA) is False  # ya se alertó; sigue reintentando
    assert len(evento.intentos_recientes) == 5
    evento.marcar_entregado(AHORA)
    assert evento.estado == EstadoEventoProvision.ENTREGADO.value


# ── RF-74: score de calidad y PESO_INVALIDO ───────────────────────────────
@pytest.mark.parametrize(
    ("ini", "fin", "alimento", "ini_inv", "fin_inv", "causa", "score"),
    [
        (None, None, None, False, False, CausaNoCalculo.SIN_PESO_INICIAL, 0),
        (Decimal("10"), None, None, False, False, CausaNoCalculo.SIN_PESO_FINAL, 25),
        (Decimal("10"), Decimal("12"), None, False, False, CausaNoCalculo.SIN_REGISTROS_CONSUMO, 50),
        (None, Decimal("12"), Decimal("5"), True, False, CausaNoCalculo.PESO_INVALIDO, 75),
        (Decimal("12"), Decimal("10"), Decimal("5"), False, False, CausaNoCalculo.PESO_SIN_VARIACION_POSITIVA, 100),
    ],
)
def test_calculadora_ica_causa_y_score_del_rf(ini, fin, alimento, ini_inv, fin_inv, causa, score):
    r = CalculadoraICA().calcular(
        alimento_total_kg=alimento, peso_inicial_kg=ini, peso_final_kg=fin, es_poblacional=False,
        cantidad_actual=None, peso_inicial_invalido=ini_inv, peso_final_invalido=fin_inv,
    )
    assert r.estado == EstadoResultadoCA.CA_NO_CALCULABLE
    assert r.causa_no_calculo == causa
    assert r.data_quality_score == score


# ── RF-81: niveles de volumen y filtros ───────────────────────────────────
def test_niveles_de_volumen_del_rf():
    assert nivel_volumen(10_000, 50_000, 200_000) == NivelVolumen.NIVEL_1
    assert nivel_volumen(10_001, 50_000, 200_000) == NivelVolumen.NIVEL_2
    assert nivel_volumen(50_001, 50_000, 200_000) == NivelVolumen.NIVEL_3
    assert nivel_volumen(200_001, 50_000, 200_000) == NivelVolumen.NIVEL_4


def test_cantidad_de_filtros_ignora_los_valores_todos():
    assert FiltrosHistorialSuministro(id_activo_biologico=1).cantidad_filtros == 0
    filtros = FiltrosHistorialSuministro(
        id_activo_biologico=1, id_ciclo_productivo=2, fecha_inicio_filtro=date(2026, 1, 1),
        tipo_suministro_filtro="ALIMENTO", costo_min=Decimal("1"),
    )
    assert filtros.cantidad_filtros == 4


# ── RF-77/RF-81: vigencia de los archivos exportados ──────────────────────
def test_archivo_exportado_solo_para_su_dueno_y_410_al_vencer():
    archivo = ArchivoExportacion.nuevo(origen="RF77", formato="CSV", nombre_archivo="g.csv", contenido=b"x",
                                       total_registros=1, id_usuario=7, ahora=AHORA)
    assert archivo.fecha_expiracion - AHORA == timedelta(hours=24)
    assert archivo.contenido_para(7, AHORA) == b"x"
    with pytest.raises(AuthorizationError):
        archivo.contenido_para(8, AHORA)
    with pytest.raises(GoneError):
        archivo.contenido_para(7, AHORA + timedelta(hours=24))
    historial = ArchivoExportacion.nuevo(origen="RF81", formato="EXCEL", nombre_archivo="h.xlsx", contenido=b"x",
                                         total_registros=1, id_usuario=7, ahora=AHORA)
    assert historial.fecha_expiracion - AHORA == timedelta(hours=72)


def test_generadores_de_archivos():
    filas = [[f"2026-10-{d:02d}", "ALIMENTACION", "Concentrado", "1000", "VALIDADO"] for d in range(1, 31)]
    doc = Documento(titulo="Reporte", columnas=["fecha", "categoria", "descripcion", "monto_cop", "estado"],
                    filas=filas, encabezado=["Activo: 1"], pie=["Total"])
    csv = generar_csv(doc).decode()
    assert csv.splitlines()[0] == "fecha,categoria,descripcion,monto_cop,estado"
    assert len(csv.splitlines()) == 31
    assert generar_pdf(doc, AHORA).startswith(b"%PDF")
    assert generar_excel(doc).startswith(b"PK")


# ── Mensajes y códigos del RF ─────────────────────────────────────────────
def test_justificaciones_con_el_mensaje_y_codigo_de_cada_rf():
    with pytest.raises(ValidationError) as rf76:
        JustificacionAnulacion("corta", MENSAJE_RF76)
    assert "garantizar la trazabilidad del evento" in rf76.value.message
    with pytest.raises(BusinessRuleError):  # RF-78 E2: 422, no 400
        JustificacionPrecio(None)


def test_retencion_por_tipo_de_evento_rf80():
    assert clasificar_retencion("SUMINISTRO_REGISTRADO") == ("NIC41", "5 años")
    assert clasificar_retencion("CONSULTA_HISTORIAL_EJECUTADA") == ("TECNICO", "1 año")
    assert clasificar_retencion("EVENTO_DESCONOCIDO") == ("NIC41", "5 años")
