# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-01 RF-46: el historial del activo suma alertas IoT, cambios de riesgo, diagnósticos y contagio alto |
"""AJF-01: el historial del activo solo unía M02. Sesión falsa que responde por SQL."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.biological_assets.infrastructure.dto.consultar_historial_dto import ConsultarHistorialDTO
from src.biological_assets.infrastructure.repositories.transferencia_repository import (
    SqlAlchemyTransferenciaRepository,
)

T0 = datetime(2026, 11, 1, 8, tzinfo=timezone.utc)


class _Resultado:
    def __init__(self, filas):
        self._filas = filas

    def fetchall(self):
        return self._filas


class _Db:
    """Devuelve filas según la tabla que consulta cada SQL; lo de M02 viene vacío."""

    def __init__(self):
        self.consultas = []

    def execute(self, sql, params=None):
        texto = str(sql)
        self.consultas.append(texto)
        if 'modulo3.alertas' in texto:
            return _Resultado([
                SimpleNamespace(id_alerta=1, tipo_alerta='FIEBRE', severidad='MODERADO', estado_alerta='ACTIVA',
                                tipo_variable='TEMP_CORPORAL', valor=Decimal('39.8'), unidad='°C',
                                fecha_generacion=T0, es_del_animal=True, nombre_area='Corral 1'),
                SimpleNamespace(id_alerta=2, tipo_alerta='FALLO_AMBIENTAL', severidad='CRITICO', estado_alerta='RESUELTA',
                                tipo_variable='NH3', valor=None, unidad=None,
                                fecha_generacion=T0 + timedelta(hours=1), es_del_animal=False, nombre_area='Corral 1'),
            ])
        if 'resultados_inferencia' in texto:
            return _Resultado([SimpleNamespace(
                id_resultado_inferencia=uuid.uuid4(), fecha_inferencia=T0 + timedelta(hours=2), nivel_riesgo=2,
                nivel_anterior=0, tipo_modelo='MODELO_ESPECIES_GRANDES', confianza_global=Decimal('0.75'),
                tiene_alerta_generada=False, id_alerta_generada=None, modo_sombra=True, nombre_patologia='Mastitis')])
        if 'retroalimentaciones_clinicas' in texto:
            return _Resultado([SimpleNamespace(
                id_retroalimentacion=uuid.uuid4(), fecha_retroalimentacion=T0 + timedelta(hours=3),
                estado_retroalimentacion='CONFIRMADO', observaciones_clinicas='Ubre inflamada', fuente_diagnostico='CLINICO',
                id_resultado_inferencia=None, diagnosticos='Mastitis', usuario='Ana Vet')])
        if 'resultados_riesgo_contagio' in texto:
            return _Resultado([SimpleNamespace(id_resultado_contagio=9, fecha_calculo=T0 + timedelta(hours=4),
                                               probabilidad_contagio=Decimal('0.7200'), nivel_riesgo_contagio=2,
                                               id_alerta_generada=None)])
        return _Resultado([])


def test_historial_completo_trae_las_cuatro_categorias_en_orden():
    db = _Db()
    pagina = SqlAlchemyTransferenciaRepository(db).consultar_historial(4)
    cats = [r.categoria for r in pagina.registros]
    assert cats == ['ALERTA_IOT', 'ALERTA_IOT', 'PREDICCION', 'DIAGNOSTICO_CLINICO', 'CONTAGIO']
    prediccion = pagina.registros[2]
    assert prediccion.descripcion == 'Riesgo pasó de Normal a Moderado (de prueba, no generó alerta)'
    assert prediccion.detalle_especifico['modo_sombra'] is True
    ambiental = pagina.registros[1]
    assert ambiental.detalle_especifico['ambito'] == 'AREA'
    assert pagina.registros[4].descripcion == 'Riesgo de contagio alto (72 %)'


def test_las_predicciones_solo_entran_al_cambiar_de_nivel_o_con_alerta():
    db = _Db()
    SqlAlchemyTransferenciaRepository(db).consultar_historial(4, categoria='PREDICCION')
    sql = next(c for c in db.consultas if 'resultados_inferencia' in c)
    assert 'LAG(r.nivel_riesgo)' in sql and 'IS DISTINCT FROM' in sql and 'tiene_alerta_generada' in sql
    assert not any('modulo3.alertas' in c for c in db.consultas)


def test_alertas_ambientales_solo_criticas_y_nunca_tecnicas():
    db = _Db()
    SqlAlchemyTransferenciaRepository(db).consultar_historial(4, categoria='ALERTA_IOT')
    sql = next(c for c in db.consultas if 'modulo3.alertas' in c)
    assert "a.severidad = 'CRITICO'" in sql and "a.tipo_alerta <> 'TECNICA'" in sql


@pytest.mark.parametrize('categoria', ['alerta_iot', 'PREDICCION', 'Diagnostico_Clinico', 'CONTAGIO'])
def test_el_filtro_acepta_las_categorias_nuevas(categoria):
    assert ConsultarHistorialDTO(categoria_evento=categoria).categoria_evento == categoria.upper()
