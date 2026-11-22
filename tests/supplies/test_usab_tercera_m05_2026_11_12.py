# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-12 | Arekkazu | USAB-M05-M06 N-05/N-07/B-01 y TC-DIS-264: tercera evaluación de usabilidad y accesibilidad |
"""Tercera evaluación de usabilidad M05/M06 (12-11) y TC-DIS-264, sin base de datos.

- N-05: la causa técnica de un fallo del batch se dice en palabras (sin trazas, SQL ni ids).
- N-07: lo que calculó el batch lo firma «Sistema (cálculo automático)», también en el histórico
  que el trigger dejó a nombre del usuario 1.
- TC-DIS-264/259: el Excel tiene los encabezados en la fila 1 y hojas con nombres completos."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from types import SimpleNamespace

from openpyxl import load_workbook

from src.supplies.application.use_cases.exportacion.generador_archivos import Documento, generar_excel
from src.supplies.domain.entities.evento_auditoria_suministro import EventoAuditoriaSuministroConsulta
from src.supplies.infrastructure.repositories import auditoria_suministro_read_repository as auditoria
from src.supplies.infrastructure.schema.eficiencia_schema import causa_legible

_SERVICIO = 89


def test_causa_tecnica_del_fallo_en_palabras():
    psycopg = ("(psycopg2.OperationalError) server closed the connection unexpectedly\n"
               "[SQL: SELECT set_config('app.usuario_id', %(uid)s, true)]")
    assert causa_legible(psycopg).startswith("Se perdió la conexión con la base de datos.")
    assert causa_legible("(psycopg2.errors.QueryCanceled) canceling statement due to statement timeout").startswith(
        "La base de datos tardó demasiado")
    assert causa_legible("ZeroDivisionError: division by zero").startswith("Error interno al calcular el ICA.")
    assert causa_legible("Error interno al calcular el CA para el activo 159. La operación fue revertida.") == (
        "Error interno al calcular el CA. La operación fue revertida.")
    assert causa_legible("Sin pesajes en el período") == "Sin pesajes en el período"
    assert causa_legible(None) == "No se registró la causa del fallo."


def _evento(id_usuario: int, entidad: str = "registro_suministro", datos: dict | None = None):
    return EventoAuditoriaSuministroConsulta(
        id_auditoria_suministro=1, entidad_afectada=entidad, tipo_operacion="INSERT", id_usuario=id_usuario,
        resultado="EXITOSO", fecha_evento=datetime(2026, 11, 12, tzinfo=timezone.utc), datos_anteriores=None,
        datos_nuevos=datos, ip_origen=None, id_sesion=None, fecha_emision=None, id_activo_biologico=None,
        id_ciclo_productivo=None, costo_afectado=None, origen_precio=None, clasificacion_registro=None,
        retencion_aplicable=None, hash_integridad="a" * 64, registro_incompleto=False, detalle_causa=None,
        numero_reintentos=0, fecha_intentos=None, id_gestion_fases=None)


def test_el_calculo_automatico_lo_firma_el_sistema(monkeypatch):
    monkeypatch.setattr(auditoria, "id_usuario_servicio", lambda db: _SERVICIO)
    monkeypatch.setattr(auditoria, "nombres_activos", lambda db, ids: {})
    monkeypatch.setattr(auditoria, "nombres_usuarios", lambda db, ids: {1: "Carlos Rodríguez Pérez", _SERVICIO: "Servicio"})
    repo = auditoria.SqlAlchemyAuditoriaSuministroReadRepository(SimpleNamespace())
    eventos = repo._con_nombres([
        _evento(_SERVICIO, "resultado_ica", {"tipo_calculo": "AUTOMATICO"}),
        _evento(1, "resultado_ica", {"tipo_calculo": "REINTENTO_AUTOMATICO"}),  # histórico firmado con el usuario 1
        _evento(1, "resultado_ica", {"tipo_calculo": "MANUAL"}),
        _evento(1),
    ])
    assert [e.nombre_usuario for e in eventos] == [auditoria.SISTEMA, auditoria.SISTEMA,
                                                   "Carlos Rodríguez Pérez", "Carlos Rodríguez Pérez"]


def test_actores_del_filtro_por_nombre_con_el_sistema_primero(monkeypatch):
    monkeypatch.setattr(auditoria, "id_usuario_servicio", lambda db: _SERVICIO)
    monkeypatch.setattr(auditoria, "nombres_usuarios", lambda db, ids: {1: "Carlos Rodríguez", 7: "Ana Pérez"})
    db = SimpleNamespace(execute=lambda _q: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [7, 1, _SERVICIO, 40])))
    actores = auditoria.SqlAlchemyAuditoriaSuministroReadRepository(db).actores()
    # 40 no se puede ver por nombre (RLS): no se ofrece.
    assert actores == [(_SERVICIO, auditoria.SISTEMA), (7, "Ana Pérez"), (1, "Carlos Rodríguez")]


def test_excel_con_encabezados_en_la_fila_1_y_hojas_completas():
    titulo = "Estado de resultados del período agropecuario"  # 45 caracteres: Excel cortaba el nombre de la hoja
    libro = load_workbook(io.BytesIO(generar_excel(Documento(
        titulo, ["Componente", "Tipo", "Valor"], [["Costos de mantenimiento", "Gasto", "−$ 10"]],
        encabezado=["Versión 2 · Aprobado"], pie=["Resultado neto: +$ 5 (Ganancia)"]))))
    datos, info = libro.worksheets
    assert (datos.title, info.title) == ("Datos", "Información")
    assert [c.value for c in datos[1]] == ["Componente", "Tipo", "Valor"] and datos.freeze_panes == "A2"
    assert [c.value for c in datos[2]] == ["Costos de mantenimiento", "Gasto", "−$ 10"]
    assert not datos.merged_cells.ranges
    assert [r[0].value for r in info.iter_rows()] == [titulo, "Versión 2 · Aprobado", "Resultado neto: +$ 5 (Ganancia)"]
