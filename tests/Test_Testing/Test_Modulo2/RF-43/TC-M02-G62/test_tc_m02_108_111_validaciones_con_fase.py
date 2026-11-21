"""
TC-M02-G62 (parte Pytest) - Validaciones de RF-43 que requieren una fase
productiva activa real: TC-M02-108 (producto no habilitado para la fase,
E-04) y TC-M02-111 (evento productivo duplicado, E-08).

RF relacionado: RF-43, CU09 Gestionar eventos productivos y bajas
Categoria: Pruebas de validacion

Por que Pytest con dobles de prueba y no Newman contra el backend en
vivo: en registrar_evento_productivo_use_case.py el orden real de
validaciones es FA-01 -> E-01 -> E-03 (catalogo) -> E-07 (unidad) -> E-02
(fase activa) -> E-04 (metrica habilitada en el ciclo) -> E-05 (fechas)
-> E-08 (duplicado). Los sub-casos E-04 y E-08 solo se alcanzan si el
activo YA tiene una fase productiva activa -- y TC-M02-G61 confirmo en
vivo (dos activos/especies distintos) que POST /activos-biologicos/{id}/
fases (RF-37) responde 500 siempre (cambiar_fase_use_case.py:72 llama
cerrar_gestion_activa con 3 argumentos en vez de 4, falta id_usuario).
Ningun activo puede llegar a tener una fase activa real hoy en TEST, asi
que estos dos sub-casos se verifican con dobles de prueba, simulando la
fase que RF-37 deberia poder crear -- el resto de sub-casos de esta
ficha (E-03, E-06, E-07) SI se prueban en vivo con Newman
(tc_m02_g62.postman_collection.json), porque ocurren ANTES del chequeo
de fase y no dependen de ese bug.

Datos usados: especie Cachama Blanca (id_especie=4), unica especie con
metrica de catalogo RF-16 seedeada en TEST (id_metrica_produccion=16,
tipo_medicion=PESO, unidad_medida=kg, aplica_a_tipo_activo=AMBOS) -- ver
TC-M02-G61.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_108_111_validaciones_con_fase.py -v \
        --html=Resultados/reporte-TC-M02-108-111.html --self-contained-html
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_evento_productivo_use_case import (
    RegistrarEventoProductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, GestionFase
from src.biological_assets.domain.repositories.parametros_especie_port import MetricaProductiva
from src.biological_assets.infrastructure.dto.registrar_evento_productivo_dto import (
    RegistrarEventoProductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError

ID_ACTIVO = 161  # Cachama INDIVIDUAL, mismo id creado en la exploracion en vivo de esta sesion
ID_ESPECIE_CACHAMA = 4
ID_METRICA_PESO = 16
ID_CICLO_PRODUCTIVO_CACHAMA = 4


def _activo() -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=ID_ESPECIE_CACHAMA,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=6,
        id_estado=1,  # ACTIVO
        id_usuario=1,
        id_activo_biologico=ID_ACTIVO,
        fecha_inicio_ciclo=date(2026, 8, 1),
        fecha_creacion=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def _fase_activa() -> GestionFase:
    return GestionFase(
        id_gestion_fases=1,
        id_activo_biologico=ID_ACTIVO,
        id_ciclo_productiva=ID_CICLO_PRODUCTIVO_CACHAMA,
        nombre_ciclo='Ciclo completo cachama 2025-A',
        nombre_fase_actual='Fase juvenil cachama',
        paso_actual=1,
        total_pasos=2,
        fecha_inicio=datetime(2026, 8, 1, tzinfo=timezone.utc),
        fecha_finalizacion=None,
        es_activa=True,
        id_usuario=1,
    )


def _metrica() -> MetricaProductiva:
    return MetricaProductiva(
        id_metrica_produccion=ID_METRICA_PESO,
        tipo_producto='PESO',
        unidad_medida='kg',
        aplica_a_tipo_activo='AMBOS',
    )


def _use_case(ciclo_habilitado: bool, duplicado: bool) -> RegistrarEventoProductivoUseCase:
    activo_repo = MagicMock()
    activo_repo.obtener_por_id.return_value = _activo()
    activo_repo.obtener_fase_activa.return_value = _fase_activa()

    parametros_port = MagicMock()
    parametros_port.obtener_metrica_productiva.return_value = _metrica()

    ciclo_port = MagicMock()
    ciclo_port.metrica_habilitada_en_ciclo.return_value = ciclo_habilitado

    evento_repo = MagicMock()
    evento_repo.existe_productivo_duplicado.return_value = duplicado

    return RegistrarEventoProductivoUseCase(
        db=MagicMock(),
        activo_repo=activo_repo,
        evento_repo=evento_repo,
        parametros_port=parametros_port,
        ciclo_port=ciclo_port,
        bitacora_repo=MagicMock(),
    )


class TestTCM02108ProductoNoHabilitadoParaFase:

    def test_rechaza_tipo_producto_no_habilitado_para_el_ciclo_activo(self):
        """
        RF-43 (E-04): un tipo_producto que SI esta en el catalogo RF-16 de
        la especie, pero que NO esta habilitado para el ciclo productivo
        de la fase activa (metricas_ciclo_productivo), debe rechazarse
        con 422 TIPO_PRODUCTO_NO_HABILITADO_FASE -- equivalente a la
        ficha "tipo_producto=LECHE en fase Levante".
        """
        use_case = self._use_case_no_habilitado()
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
        dto = RegistrarEventoProductivoDTO(
            tipo_producto='peso',
            cantidad_producida=Decimal('20'),
            unidad_medida='kg',
            fecha_evento=date(2026, 9, 9),
        )

        with pytest.raises(BusinessRuleError) as exc_info:
            use_case.execute(ID_ACTIVO, dto, usuario_actual)

        assert exc_info.value.code == 'TIPO_PRODUCTO_NO_HABILITADO_FASE'

    @staticmethod
    def _use_case_no_habilitado() -> RegistrarEventoProductivoUseCase:
        return _use_case(ciclo_habilitado=False, duplicado=False)


class TestTCM02111EventoProductivoDuplicado:

    def test_rechaza_segundo_evento_del_mismo_tipo_producto_en_la_misma_fecha(self):
        """
        RF-43 (E-08): un segundo evento productivo del mismo
        tipo_producto para el mismo activo en la misma fecha debe
        rechazarse con 409 EVENTO_PRODUCTIVO_DUPLICADO.
        """
        use_case = self._use_case_duplicado()
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
        dto = RegistrarEventoProductivoDTO(
            tipo_producto='peso',
            cantidad_producida=Decimal('20'),
            unidad_medida='kg',
            fecha_evento=date(2026, 9, 1),
        )

        with pytest.raises(ConflictError) as exc_info:
            use_case.execute(ID_ACTIVO, dto, usuario_actual)

        assert exc_info.value.code == 'EVENTO_PRODUCTIVO_DUPLICADO'

    @staticmethod
    def _use_case_duplicado() -> RegistrarEventoProductivoUseCase:
        return _use_case(ciclo_habilitado=True, duplicado=True)
