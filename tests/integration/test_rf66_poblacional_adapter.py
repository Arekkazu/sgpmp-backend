# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: lecturas del puntaje de anomalía contra PostgreSQL real |
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: flujo completo observación → resultado → RF-68 |
"""El adaptador de RF-66 POBLACIONAL contra PostgreSQL real, como el usuario de servicio del worker."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from src.prediction.infrastructure.adapters.observacion_poblacional_m03_m09_adapter import (
    ObservacionPoblacionalM03M09Adapter,
)
from src.prediction.infrastructure.disparos_automaticos import evaluar_anomalia_poblacional
from src.shared.database import declarar_identidad_sistema
from tests.integration.test_control_acceso_f4_aislamiento import _finca_con_activo

pytestmark = pytest.mark.integration

FIN = datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def area(db_session, crear_usuario_db):
    db = db_session
    usuario = crear_usuario_db(id_rol=3)["id_usuario"]
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text("INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre) "
                    "VALUES (1, 'ACTIVO') ON CONFLICT DO NOTHING"))
    _, id_area, _ = _finca_con_activo(db, usuario)
    db.execute(text("UPDATE modulo9.infraestructuras SET tipo_modelo_asignado = 'MODELO_PORCINOS' WHERE id_infraestructura = :a"),
               {"a": id_area})
    lote = db.execute(text(
        "INSERT INTO modulo2.activos_biologicos (id_especie, identificador, id_infraestructura, tipo, fecha_inicio_ciclo, "
        "id_estado, descripcion, origen_financiero, costo_adquisicion, atributos_dinamicos, id_usuario, fecha_creacion, "
        "soporte_documental, detalles_procedencia) VALUES (2, :i, :a, 'POBLACIONAL', current_date, 1, 'cerdos', 'compra', 1, "
        "'{}', :u, now(), 'doc', '') RETURNING id_activo_biologico"),
        {"i": f"PORC-{uuid.uuid4().hex[:8]}", "a": id_area, "u": usuario}).scalar_one()
    obs = db.execute(text(
        "INSERT INTO modulo3.observaciones_vision (id_dispositivo_iot, id_infraestructura, fecha_observacion, "
        "cobertura_ventana, cantidad_tracks, cantidad_tracks_perdidos, fps_efectivo, estado_calibracion, json_vector, "
        "es_apto_para_ia, es_confianza_baja, fecha_inicio_ventana, n_individuos_observados, origen, indice_calidad_vision, "
        "clasificacion_calidad, json_flags_detectados, fecha_evaluacion_calidad) VALUES (1, :a, :fin, 1, 100, 80, 4, 'CALIBRADO', "
        "'{\"tasa_movimiento\": 0.024}', true, true, :ini, 2, 'TIEMPO_REAL', 75, 'DEGRADADA', '{}', now()) "
        "RETURNING id_observacion_vision"), {"a": id_area, "fin": FIN, "ini": FIN - timedelta(minutes=1)}).scalar_one()
    db.execute(text("INSERT INTO modulo9.lineas_base_vision (id_infraestructura, id_especie, id_calibracion_vision, json_valor, "
                    "fecha_publicacion) VALUES (:a, 2, 1, '{\"valores\": {\"tasa_movimiento\": 0.13}}', now())"), {"a": id_area})
    # RF-69 (detector en SOMBRA) y RF-65 (umbral del puntaje y configuración del contagio).
    db.execute(text("INSERT INTO modulo4.versiones_modelos (nombre_version, tipo_modelo, estado_version, componente) "
                    "VALUES (:n, 'MODELO_PORCINOS', 'SOMBRA', 'DETECTOR')"), {"n": f"PORCINOS_{uuid.uuid4().hex[:8]}"})
    db.execute(text("UPDATE modulo4.configuraciones_motor_ia SET es_activa = false "
                    "WHERE tipo_modelo IN ('MODELO_PORCINOS', 'MODELO_RIESGO_CONTAGIO')"))
    db.execute(text("INSERT INTO modulo4.configuraciones_motor_ia (tipo_modelo, umbral_score_anomalia, es_activa, "
                    "id_usuario_responsable) VALUES ('MODELO_PORCINOS', 0.5, true, :u)"), {"u": usuario})
    db.execute(text("INSERT INTO modulo4.configuraciones_motor_ia (tipo_modelo, umbral_riesgo_alto, umbral_alerta_critica, "
                    "w_factor_sanitario, w_factor_ambiental, w_factor_densidad, temp_min_config, temp_max_config, "
                    "hr_min_config, hr_max_config, densidad_maxima_config, es_activa, id_usuario_responsable) VALUES "
                    "('MODELO_RIESGO_CONTAGIO', 0.7, 0.7, 0.5, 0.3, 0.2, 10, 30, 40, 80, 0.2, true, :u)"), {"u": usuario})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    declarar_identidad_sistema(db)
    return dict(area=id_area, lote=lote, obs=obs)


def test_lee_observacion_lotes_linea_base_e_idempotencia(db_session, area):
    port = ObservacionPoblacionalM03M09Adapter(db_session)
    obs = port.obtener(area["obs"])
    assert (obs.id_area, obs.vector, obs.apto_para_ia, obs.confianza_baja, obs.fecha_fin) == (
        area["area"], {"tasa_movimiento": 0.024}, True, True, FIN)
    [lote] = port.lotes(area["area"])
    assert (lote.id_activo, lote.id_especie, lote.tipo_modelo) == (area["lote"], 2, "MODELO_PORCINOS")
    assert port.linea_base(area["area"], 2) == {"tasa_movimiento": 0.13}
    assert port.linea_base(area["area"], 99) is None
    assert port.obtener(10**9) is None
    assert port.ya_evaluado(area["lote"], "MODELO_PORCINOS", FIN) is False



def test_observacion_apta_deja_resultado_poblacional_y_contagio(db_session, area):
    evaluar_anomalia_poblacional(db_session, area["obs"])
    fila = db_session.execute(text(
        "SELECT nivel_riesgo, probabilidad_riesgo, modo_sombra, tipo_modelo::text, fecha_fin_ventana "
        "FROM modulo4.resultados_inferencia WHERE id_activo_biologico = :l"), {"l": area["lote"]}).one()
    # |0,024 − 0,13| / 0,13 = 0,8154 ≥ (1 + 0,5) / 2 → crítico
    assert fila[:4] == (3, {"score_anomalia": 0.8154, "umbral_score_anomalia": 0.5}, True, "MODELO_PORCINOS")
    assert fila[4] == FIN
    contagio = db_session.execute(text(
        "SELECT factor_sanitario_fs, variables_ambientales_snap ->> 'definicion_fs' "
        "FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico = :l"), {"l": area["lote"]}).one()
    assert (float(contagio[0]), contagio[1]) == (0.8154, "SCORE_POBLACIONAL")
    # Un reintento del worker no duplica.
    evaluar_anomalia_poblacional(db_session, area["obs"])
    assert db_session.execute(text("SELECT count(*) FROM modulo4.resultados_inferencia WHERE id_activo_biologico = :l"),
                              {"l": area["lote"]}).scalar() == 1
