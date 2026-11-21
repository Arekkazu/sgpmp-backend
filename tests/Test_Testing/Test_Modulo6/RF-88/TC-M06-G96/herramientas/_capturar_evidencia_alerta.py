"""Captura evidencia de alerta G96 en BD temporal; siempre hace rollback."""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal as D
from pathlib import Path

import bcrypt
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.financial_valuation.infrastructure.factories.m06_factory import M06
from tests.integration.test_m06_flujo_nic41_integration import (
    _activo,
    _configurar,
    _finca,
    _id,
    _pesaje,
)


def main() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    parsed = make_url(url)
    assert parsed.host in ("127.0.0.1", "localhost")
    assert parsed.port == 55496
    assert (parsed.database or "").lower() == "g96_ab_test"

    out_path = Path(__file__).with_name("evidencia_alerta.json")
    engine = create_engine(url, pool_pre_ping=True, use_insertmanyvalues=False)
    conn = engine.connect()
    outer = conn.begin()
    db = Session(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
    try:
        password_hash = bcrypt.hashpw(b"Integracion123*", bcrypt.gensalt()).decode("utf-8")
        numero = str(uuid.uuid4().int % 10**15).zfill(15)
        correo = f"it-{uuid.uuid4().hex}@example.com"
        fecha = datetime.now(timezone.utc).replace(tzinfo=None)
        fila = db.execute(
            text(
                """
                INSERT INTO modulo1.usuarios (
                    tipo_identificacion, numero_identificacion, nombre, apellidos,
                    fecha_nacimiento, genero, correo_electronico,
                    contrasena_cifrada, telefono, direccion, id_rol, fecha_registro
                ) VALUES (
                    'CC', :numero, 'Integracion', 'Prueba', :fecha_nacimiento,
                    CAST('M' AS modulo1.enum_usuario_genero), :correo,
                    :contrasena, '3001234567', 'Direccion Integracion', 5, :fecha
                )
                RETURNING id_usuario
                """
            ),
            {
                "numero": numero,
                "fecha_nacimiento": date(1990, 1, 1),
                "correo": correo,
                "contrasena": password_hash,
                "fecha": fecha,
            },
        ).mappings().one()
        uid = int(fila["id_usuario"])

        db.execute(
            text(
                "INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre) VALUES "
                "(1,'ACTIVO'),(2,'INACTIVO'),(3,'EN_TRATAMIENTO'),(4,'AISLADO'),(5,'CERRADO'),(6,'BAJA') "
                "ON CONFLICT (id_estado_activo_biologico) DO NOTHING"
            )
        )

        class _Notif:
            def __init__(self) -> None:
                self.avisos: list = []

            def a_contadores(self, tipo_evento, mensaje, detalle, id_finca=None) -> None:
                self.avisos.append({"mensaje": mensaje, "detalle": detalle, "tipo": tipo_evento})

            def ya_notificado(self, tipo_evento, detalle) -> bool:
                return False

        notif = _Notif()
        m06 = M06(db)
        # El Contabilizador captura el notificador al construirse.
        m06.__dict__["notificador"] = notif
        if hasattr(m06, "contabilizador"):
            m06.contabilizador.notificador = notif
        # Forzar notificador en use case de deterioro si ya esta cacheado
        deterioro_uc = m06.registrar_deterioro()
        if hasattr(deterioro_uc, "notificador"):
            deterioro_uc.notificador = notif
        if hasattr(deterioro_uc, "contabilizador") and hasattr(deterioro_uc.contabilizador, "notificador"):
            deterioro_uc.contabilizador.notificador = notif

        especie = 3
        finca = _finca(db, uid)
        _configurar(m06, uid, especie, vida=24)
        activo = _activo(db, finca, uid, especie=especie, origen="compra", costo=D("10000000"))
        _pesaje(db, activo, "30")
        assert m06.confirmar_reconocimiento().execute(activo, uid)["indicador_valoracion"] == "VALORACION_POR_COSTO"
        db.execute(
            text(
                """
                UPDATE modulo6.valoraciones_por_costos
                SET depreciacion_acumulada = 7000000, valor_contable_por_costo = 3000000
                WHERE id_activo_biologico = :a AND es_activa
                """
            ),
            {"a": activo},
        )

        id_evento = _id()
        db.execute(text("SET LOCAL session_replication_role = replica"))
        db.execute(
            text(
                "INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha) "
                "VALUES (:e, :a, now())"
            ),
            {"e": id_evento, "a": activo},
        )
        db.execute(
            text(
                "INSERT INTO modulo2.eventos_sanitarios (id_evento, tipo, diagnostico) "
                "VALUES (:e, 'DIAGNOSTICO', 'Brucelosis')"
            ),
            {"e": id_evento},
        )
        db.execute(text("SET LOCAL session_replication_role = origin"))

        resultado = m06.registrar_deterioro().execute(
            activo,
            id_evento,
            D("5000000"),
            "Brucelosis confirmada: perdida de capacidad productiva del animal",
            uid,
        )
        eventos = m06.consultar_auditoria().execute(
            {"id_activo_biologico": activo, "tipo_evento": ["VALOR_LIBROS_AJUSTADO_A_CERO"]},
            1,
            100,
            True,
        )
        raw = db.execute(
            text(
                """
                SELECT tipo_evento::text AS tipo_evento, severidad::text AS severidad,
                       datos_nuevos::text AS payload, id_activo_biologico
                FROM modulo6.auditorias_financieras
                WHERE id_activo_biologico = :a
                  AND tipo_evento = 'VALOR_LIBROS_AJUSTADO_A_CERO'
                """
            ),
            {"a": activo},
        ).mappings().all()

        out = {
            "grupo": "TC-M06-G96",
            "tipo_evento": "VALOR_LIBROS_AJUSTADO_A_CERO",
            "estado": "COMPROBADA_EN_BD_TEMPORAL_AISLADA",
            "entorno": {
                "host": "127.0.0.1",
                "port": 55496,
                "database": "g96_ab_test",
                "container": "g96-ab-postgres-tmp",
                "persistido_en_TEST_compartido": False,
            },
            "resultado_deterioro": {
                "valor_contable": str(resultado.get("valor_contable")),
                "valor_libros_calculado": str(resultado.get("valor_libros_calculado")),
                "aviso_presente": resultado.get("aviso") is not None,
            },
            "consulta_use_case": {
                "total_registros": eventos.get("total_registros"),
                "eventos": eventos.get("eventos"),
            },
            "consulta_sql_en_transaccion": [dict(r) for r in raw],
            "notificacion": {
                "cantidad_avisos": len(notif.avisos),
                "avisos": notif.avisos,
            },
            "id_activo_sintetico": activo,
            "nota_rollback": (
                "Evidencia capturada dentro de la transaccion de prueba; "
                "al finalizar se hace rollback y no queda residuo."
            ),
        }
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(
            "EVIDENCIA_OK",
            "total=",
            eventos.get("total_registros"),
            "calc=",
            resultado.get("valor_libros_calculado"),
        )
    finally:
        db.close()
        if outer.is_active:
            outer.rollback()
        conn.close()
        engine.dispose()


if __name__ == "__main__":
    main()
