"""
TC-M04-G005 (sub-caso 1, parte BD) - Integracion del catalogo de patologias con las variables I3P-1.

RF relacionado: RF-64 (CU01), CA-13. Caso: TC-M04-012.

Criterio de la ficha: toda variable asociada a una patologia corresponde a un ID valido del catalogo I3P-1
(RF-16); al dar de baja una variable en I3P-1, el sistema lo refleja de forma consistente.

Que verifica este archivo, en la BD de TEST (solo lectura, usuario QA; las tablas no tienen RLS):
- ninguna asociacion de modulo4.patologias_variables_sensoricas apunta a una variable inexistente en
  modulo9.variables_ambientales. Importa revisarlo en la BD porque las FK fk_pvs_variable y fk_pvs_patologia
  estan creadas como NOT VALID: PostgreSQL no valido los datos que ya existian al crearlas;
- ninguna asociacion apunta a una patologia inexistente en modulo9.patologias;
- ninguna patologia ACTIVA referencia una variable dada de baja (es_activo = false) en I3P-1: eso es lo que
  el sistema deberia reflejar de forma consistente tras una baja.

"Repetir tras dar de baja una variable" no se ejecuta: el catalogo I3P-1 no tiene endpoint de baja (solo
GET /configuracion/variables-ambientales) y hacerlo por BD modificaria el catalogo compartido de TEST. El test
correspondiente queda en SKIP con la razon. La comprobacion por API (todas las patologias contra el catalogo
vigente) esta en TC-M04-G005.postman_collection.json.

Requisitos: acceso de red a Postgres de TEST (5448).
Variables opcionales: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo4/RF-64/TC-M04-G005 -v \
        --html=reporte-TC-M04-G005.html --self-contained-html
"""
from __future__ import annotations

import os

import psycopg2
import pytest

DB = dict(
    host=os.getenv("DB_HOST", "158.69.200.27"), port=os.getenv("DB_PORT", "5448"),
    user=os.getenv("DB_USER", "member_qa"), password=os.getenv("DB_PASSWORD", "qaSGP2026"),
    dbname=os.getenv("DB_NAME", "sgpmp_test"),
)


@pytest.fixture(scope="module")
def cur():
    con = psycopg2.connect(**DB)
    con.set_session(readonly=True, autocommit=True)
    try:
        with con.cursor() as c:
            yield c
    finally:
        con.close()


def test_tc_m04_012_ninguna_asociacion_apunta_a_una_variable_inexistente(cur):
    cur.execute(
        """
        SELECT pvs.id_patologia, pvs.id_variable_ambiental
        FROM modulo4.patologias_variables_sensoricas pvs
        LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = pvs.id_variable_ambiental
        WHERE va.id_variable_ambiental IS NULL
        """
    )
    huerfanas = cur.fetchall()
    assert not huerfanas, f"(id_patologia, id_variable) sin variable en I3P-1 (FK NOT VALID): {huerfanas}"


def test_tc_m04_012_ninguna_asociacion_apunta_a_una_patologia_inexistente(cur):
    cur.execute(
        """
        SELECT pvs.id_patologia_variable, pvs.id_patologia
        FROM modulo4.patologias_variables_sensoricas pvs
        LEFT JOIN modulo9.patologias p ON p.id_patologia = pvs.id_patologia
        WHERE p.id_patologia IS NULL
        """
    )
    huerfanas = cur.fetchall()
    assert not huerfanas, f"Asociaciones sin patologia (FK NOT VALID): {huerfanas}"


def test_tc_m04_012_ninguna_patologia_activa_usa_una_variable_dada_de_baja(cur):
    cur.execute(
        """
        SELECT p.id_patologia, p.nombre, va.id_variable_ambiental, va.nombre
        FROM modulo4.patologias_variables_sensoricas pvs
        JOIN modulo9.patologias p ON p.id_patologia = pvs.id_patologia
        JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = pvs.id_variable_ambiental
        WHERE p.es_activo = true AND va.es_activo = false
        """
    )
    inconsistentes = cur.fetchall()
    assert not inconsistentes, f"Patologias activas que dependen de variables inactivas en I3P-1: {inconsistentes}"


def test_tc_m04_012_reflejo_de_la_baja_de_una_variable():
    pytest.skip(
        "No hay endpoint para dar de baja una variable de I3P-1 (solo GET /configuracion/variables-ambientales) y "
        "hacerlo por BD modificaria el catalogo compartido de TEST. Coordinar con Desarrollo un entorno aislado o una "
        "variable de prueba dedicada; mientras tanto, el test anterior detecta cualquier patologia activa que dependa "
        "de una variable ya dada de baja."
    )
