# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-87: períodos por titular, ejecuciones de cierre y comprobantes |
# | 2026-11-10 | Arekkazu | INC-M06-345/350 RF-87: cierre en espera de autorización y nombre de quien cerró |
# | 2026-11-11 | Arekkazu | USAB-M06 M6-03 RF-82/87: razón social del período y listas filtradas por el titular del período |
# | 2026-11-11 | Arekkazu | USAB-M06 RF-87/93: titulares con período, filtro sin titular y último cierre de todos los períodos en una consulta |
"""Implementación SQL de :class:`PeriodoRepository`."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.financial_valuation.domain.repositories.periodo_repository import PeriodoRepository
from src.financial_valuation.domain.services.consolidacion import Comprobante
from src.financial_valuation.infrastructure.repositories.sql import a_json, escribir, fila, filas
from src.shared.errors import ConflictError

_COLUMNAS = """id_periodo_contable, numero_id_tributaria, tipo_cierre::text AS tipo_cierre, fecha_inicio, fecha_fin,
               estado::text AS estado, fecha_cierre"""


# Un cierre EN_PROCESO en el paso 3 espera que el Contador autorice las exclusiones (RF-87 FA-2/FA-3);
# mientras corre, la ejecución queda en el paso 1 hasta que termina.
_PASO_ESPERA = 3
_JOIN_EJECUTOR = "LEFT JOIN modulo1.usuarios u ON u.id_usuario = e.id_usuario_ejecutor"
_NOMBRE_EJECUTOR = "NULLIF(trim(coalesce(u.nombre, '') || ' ' || coalesce(u.apellidos, '')), '') AS nombre_usuario_ejecutor"
_COLUMNAS_EJECUCION = f"""e.id_cierre, e.estado::text AS estado, e.paso_actual, e.activos_procesados, e.activos_pendientes,
                   e.activos_excluidos, e.json_precios_congelados AS precios_congelados, e.error_detalle, e.fecha_inicio,
                   e.fecha_fin, e.tiempo_ejecucion_ms, e.hash_saga AS hash_cierre, e.id_usuario_ejecutor, {_NOMBRE_EJECUTOR}"""


class SqlAlchemyPeriodoRepository(PeriodoRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self, id_periodo_contable: int, bloquear: bool = False) -> Optional[Periodo]:
        sql = f"SELECT {_COLUMNAS} FROM modulo6.periodos_contables WHERE id_periodo_contable = :id"
        try:
            f = fila(self.db, sql + (" FOR UPDATE NOWAIT" if bloquear else ""), {"id": id_periodo_contable})
        except OperationalError as exc:  # lock_not_available: otro cierre tiene el período (RF-87 FA-5)
            raise ConflictError(code="CIERRE_EN_EJECUCION",
                                message="El período está siendo procesado por otro cierre. Espere a que termine.") from exc
        return Periodo(**f) if f else None

    def que_contiene(self, numero_id_tributaria: str, dia: date) -> Optional[Periodo]:
        f = fila(self.db, f"""SELECT {_COLUMNAS} FROM modulo6.periodos_contables
                              WHERE numero_id_tributaria = :n AND :d BETWEEN fecha_inicio AND fecha_fin""",
                 {"n": numero_id_tributaria, "d": dia})
        return Periodo(**f) if f else None

    def primero_abierto_desde(self, numero_id_tributaria: str, dia: date) -> Optional[Periodo]:
        f = fila(self.db, f"""SELECT {_COLUMNAS} FROM modulo6.periodos_contables
                              WHERE numero_id_tributaria = :n AND estado = 'ABIERTO' AND fecha_fin >= :d
                              ORDER BY fecha_inicio LIMIT 1""", {"n": numero_id_tributaria, "d": dia})
        return Periodo(**f) if f else None

    def hay_posteriores(self, numero_id_tributaria: str, dia: date) -> bool:
        return fila(self.db, """SELECT 1 AS ok FROM modulo6.periodos_contables
                                WHERE numero_id_tributaria = :n AND fecha_inicio > :d LIMIT 1""",
                    {"n": numero_id_tributaria, "d": dia}) is not None

    def crear(self, numero_id_tributaria: str, tipo_cierre: str, inicio: date, fin: date, id_usuario: int) -> Periodo:
        escribir(self.db, """
            INSERT INTO modulo6.periodos_contables (tipo_cierre, fecha_inicio, fecha_fin, estado, id_usuario,
                                                    fecha_creacion, numero_id_tributaria)
            VALUES (CAST(:t AS modulo6.enum_periodos_contables_tipo_cierre), :i, :f, 'ABIERTO', :u, now(), :n)
            ON CONFLICT (numero_id_tributaria, fecha_inicio) DO NOTHING
        """, {"t": tipo_cierre, "i": inicio, "f": fin, "u": id_usuario, "n": numero_id_tributaria})
        return self.que_contiene(numero_id_tributaria, inicio)

    def cambiar_estado(self, id_periodo_contable: int, estado: str) -> None:
        escribir(self.db, """UPDATE modulo6.periodos_contables
                             SET estado = CAST(:e AS modulo6.enum_periodo_contables_estado),
                                 fecha_cierre = CASE WHEN :e = 'CERRADO' THEN now() ELSE fecha_cierre END
                             WHERE id_periodo_contable = :id""", {"id": id_periodo_contable, "e": estado})

    def listar(self, numero_id_tributaria: Optional[str], sin_titular: bool = False) -> list[Periodo]:
        return [Periodo(**f) for f in filas(self.db, f"""
            SELECT {_COLUMNAS},
                   (SELECT max(f.razon_social) FROM modulo9.fincas f
                     WHERE f.numero_id_tributaria = pc.numero_id_tributaria) AS razon_social
            FROM modulo6.periodos_contables pc
            WHERE CASE WHEN :sin THEN numero_id_tributaria IS NULL
                       ELSE CAST(:n AS varchar) IS NULL OR numero_id_tributaria = :n END
            ORDER BY numero_id_tributaria, fecha_inicio DESC""", {"n": numero_id_tributaria, "sin": sin_titular})]

    def titulares(self) -> list[dict]:
        return filas(self.db, """
            SELECT pc.numero_id_tributaria, max(f.razon_social) AS razon_social
            FROM modulo6.periodos_contables pc
            LEFT JOIN modulo9.fincas f ON f.numero_id_tributaria = pc.numero_id_tributaria
            GROUP BY pc.numero_id_tributaria
            ORDER BY pc.numero_id_tributaria IS NULL, max(f.razon_social) NULLS LAST, pc.numero_id_tributaria""")

    def abierto_anterior(self, periodo: Periodo) -> Optional[Periodo]:
        f = fila(self.db, f"""SELECT {_COLUMNAS} FROM modulo6.periodos_contables
                              WHERE numero_id_tributaria = :n AND estado <> 'CERRADO' AND fecha_inicio < :i
                              ORDER BY fecha_inicio LIMIT 1""",
                 {"n": periodo.numero_id_tributaria, "i": periodo.fecha_inicio})
        return Periodo(**f) if f else None

    def iniciar_cierre(self, id_periodo_contable: int, id_usuario: int, incluir_sin_precio: bool) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.ejecuciones_cierre_periodo (id_periodo_contable, id_usuario_ejecutor, estado, paso_actual,
                                                            fecha_inicio, es_incluir_activos_sin_precio, intento_reintento)
            VALUES (:p, :u, 'EN_PROCESO', 1, now(), :i, 0) RETURNING id_cierre
        """, {"p": id_periodo_contable, "u": id_usuario, "i": incluir_sin_precio})

    def ejecucion_en_proceso(self, id_periodo_contable: int) -> Optional[dict]:
        return fila(self.db, f"""SELECT e.id_cierre, e.id_usuario_ejecutor, e.fecha_inicio,
                                        e.paso_actual = {_PASO_ESPERA} AS esperando_autorizacion, {_NOMBRE_EJECUTOR}
                                 FROM modulo6.ejecuciones_cierre_periodo e {_JOIN_EJECUTOR}
                                 WHERE e.id_periodo_contable = :p AND e.estado = 'EN_PROCESO'""", {"p": id_periodo_contable})

    def esperar_autorizacion(self, id_cierre: int) -> None:
        escribir(self.db, f"UPDATE modulo6.ejecuciones_cierre_periodo SET paso_actual = {_PASO_ESPERA} WHERE id_cierre = :id",
                 {"id": id_cierre})

    def reanudar_cierre(self, id_cierre: int, incluir_sin_precio: bool) -> None:
        escribir(self.db, """UPDATE modulo6.ejecuciones_cierre_periodo SET paso_actual = 1, es_incluir_activos_sin_precio = :i
                             WHERE id_cierre = :id""", {"id": id_cierre, "i": incluir_sin_precio})

    def finalizar_cierre(self, id_cierre: int, estado: str, datos: dict) -> None:
        escribir(self.db, """
            UPDATE modulo6.ejecuciones_cierre_periodo
            SET estado = CAST(:e AS modulo6.enum_estado_cierre), paso_actual = :paso, activos_procesados = :proc,
                activos_pendientes = :pend, activos_excluidos = CAST(:excl AS jsonb),
                json_precios_congelados = CAST(:precios AS jsonb), error_detalle = :error, hash_saga = :hash,
                fecha_fin = now(), tiempo_ejecucion_ms = (extract(epoch FROM now() - fecha_inicio) * 1000)::integer
            WHERE id_cierre = :id
        """, {"id": id_cierre, "e": estado, "paso": datos.get("paso", 9), "proc": datos.get("procesados", 0),
              "pend": datos.get("pendientes", 0), "excl": a_json(datos.get("excluidos", [])),
              "precios": a_json(datos.get("precios", [])), "error": datos.get("error"), "hash": datos.get("hash")})

    def guardar_comprobante(self, comprobante: Comprobante, id_periodo_contable: int, id_cierre: int) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.comprobantes_nic41 (codigo, id_periodo_contable, id_cierre, numero_id_tributaria,
                tipo_hecho, id_especie, fecha_comprobante, json_lineas, valor_total, hash_integridad)
            VALUES (:codigo, :p, :c, :n, CAST(:t AS modulo6.enum_linea_asiento_nic41_tipo_hecho), :e, :f,
                    CAST(:lineas AS jsonb), :v, :h)
            RETURNING id_comprobante_nic41
        """, {"codigo": comprobante.codigo, "p": id_periodo_contable, "c": id_cierre,
              "n": comprobante.numero_id_tributaria, "t": comprobante.tipo_hecho, "e": comprobante.id_especie,
              "f": comprobante.fecha_comprobante, "lineas": a_json(comprobante.lineas), "v": comprobante.valor_total,
              "h": comprobante.hash_integridad})

    def comprobantes(self, id_periodo_contable: int) -> list[dict]:
        return filas(self.db, """
            SELECT c.id_comprobante_nic41, c.codigo, c.numero_id_tributaria, c.tipo_hecho::text AS tipo_hecho,
                   c.id_especie, e.nombre AS especie, c.fecha_comprobante, c.json_lineas AS lineas, c.valor_total,
                   c.hash_integridad, c.fecha_creacion
            FROM modulo6.comprobantes_nic41 c JOIN modulo9.especies e ON e.id_especie = c.id_especie
            WHERE c.id_periodo_contable = :p ORDER BY c.codigo""", {"p": id_periodo_contable})

    def ultima_ejecucion(self, id_periodo_contable: int) -> Optional[dict]:
        return fila(self.db, f"""
            SELECT {_COLUMNAS_EJECUCION}
            FROM modulo6.ejecuciones_cierre_periodo e {_JOIN_EJECUTOR} WHERE e.id_periodo_contable = :p
            ORDER BY e.id_cierre DESC LIMIT 1""", {"p": id_periodo_contable})

    def ultimas_ejecuciones(self, ids_periodos: list[int]) -> dict[int, dict]:
        # Una consulta para todo el listado: antes era una por período (N+1).
        if not ids_periodos:
            return {}
        return {f.pop("id_periodo_contable"): f for f in filas(self.db, f"""
            SELECT DISTINCT ON (e.id_periodo_contable) e.id_periodo_contable, {_COLUMNAS_EJECUCION}
            FROM modulo6.ejecuciones_cierre_periodo e {_JOIN_EJECUTOR} WHERE e.id_periodo_contable = ANY(:ids)
            ORDER BY e.id_periodo_contable, e.id_cierre DESC""", {"ids": list(ids_periodos)})}
