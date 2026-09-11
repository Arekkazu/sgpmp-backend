"""
TC-M02-G64 (parte Pytest) - Rechazo de evento productivo duplicado
(TC-M02-243).

RF relacionado: RF-43, CU09 Gestionar eventos productivos y bajas
Categoria: Pruebas de validacion

NOTA: ficha duplicada de TC-M02-111 (TC-M02-G62, mismo escenario de
duplicado). Se rehace de todas formas como artefacto propio de
TC-M02-G64 a pedido explicito del usuario, con los mismos dobles de
prueba y la misma justificacion: E-08 (duplicado) solo se evalua DESPUES
de E-02 (fase activa) en registrar_evento_productivo_use_case.py, y
TC-M02-G61 confirmo en vivo que POST /activos-biologicos/{id}/fases
(RF-37) responde 500 siempre (cambiar_fase_use_case.py:72, falta el
argumento usuario_id en cerrar_gestion_activa) -- ningun activo puede
llegar a tener una fase activa real hoy en TEST. Los sub-casos 1 y 2 de
esta ficha (cantidad invalida, unidad incompatible) SI se prueban en vivo
con Newman (tc_m02_g64.postman_collection.json), porque ocurren antes
del chequeo de fase.

Datos usados: especie Cachama Blanca (id_especie=4), unica especie con
metrica de catalogo RF-16 seedeada en TEST (id_metrica_produccion=16,
tipo_medicion=PESO, unidad_medida=kg, aplica_a_tipo_activo=AMBOS).

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_243_evento_duplicado.py -v \
        --html=Resultados/reporte-TC-M02-243.html --self-contained-html
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
from src.shared.errors import ConflictError

ID_ACTIVO = 166  # Cachama INDIVIDUAL, mismo patron usado en TC-M02-G61/G62/G63
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


class TestTCM02243EventoProductivoDuplicado:

    def test_rechaza_segundo_evento_del_mismo_tipo_producto_en_la_misma_fecha(self):
        """
        RF-43 (E-08): un segundo evento productivo del mismo
        tipo_producto para el mismo activo en la misma fecha debe
        rechazarse con 409 EVENTO_PRODUCTIVO_DUPLICADO -- equivalente a
        la ficha "ya existe un evento LECHE para el activo con fecha
        2026-09-01".
        """
        activo_repo = MagicMock()
        activo_repo.obtener_por_id.return_value = _activo()
        activo_repo.obtener_fase_activa.return_value = _fase_activa()

        parametros_port = MagicMock()
        parametros_port.obtener_metrica_productiva.return_value = _metrica()

        ciclo_port = MagicMock()
        ciclo_port.metrica_habilitada_en_ciclo.return_value = True

        evento_repo = MagicMock()
        evento_repo.existe_productivo_duplicado.return_value = True

        use_case = RegistrarEventoProductivoUseCase(
            db=MagicMock(),
            activo_repo=activo_repo,
            evento_repo=evento_repo,
            parametros_port=parametros_port,
            ciclo_port=ciclo_port,
            bitacora_repo=MagicMock(),
        )
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
        evento_repo.existe_productivo_duplicado.assert_called_once_with(
            ID_ACTIVO, ID_METRICA_PESO, date(2026, 9, 1)
        )
