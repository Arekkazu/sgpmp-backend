"""
TC-M02-G63 (parte Pytest) - Registro de evento productivo valido
(TC-M02-238) y rechazo por producto no habilitado para la fase activa
(TC-M02-240).

RF relacionado: RF-43, CU09 Gestionar eventos productivos y bajas
Categoria: Pruebas funcionales / Pruebas de validacion

NOTA: esta ficha (TC-M02-G63) es un duplicado literal de trabajo ya
cubierto en sesiones anteriores -- TC-M02-238 es el mismo escenario que
TC-M02-106 de TC-M02-G61 (test_tc_m02_106_evento_productivo_valido.py) y
TC-M02-240 es el mismo escenario que TC-M02-108 de TC-M02-G62
(test_tc_m02_108_111_validaciones_con_fase.py). Se rehace de todas
formas como artefacto propio de TC-M02-G63 a pedido explicito del
usuario (2026-09-09), con los mismos dobles de prueba y la misma
justificacion: ambos sub-casos exigen que el activo YA tenga una fase
productiva activa (E-02) antes de poder evaluarse -- y TC-M02-G61
confirmo en vivo, en dos activos/especies distintos, que POST
/activos-biologicos/{id}/fases (RF-37) responde 500 siempre
(cambiar_fase_use_case.py:72 llama cerrar_gestion_activa con 3 argumentos
en vez de 4, falta id_usuario). Ningun activo puede llegar a tener una
fase activa real hoy en TEST, asi que ambos sub-casos se verifican con
dobles de prueba, simulando la fase que RF-37 deberia poder crear. El
sub-caso 2 (TC-M02-239, catalogo) SI se prueba en vivo con Newman
(tc_m02_g63.postman_collection.json), porque ocurre antes del chequeo de
fase y no depende de este bug.

Datos usados: especie Cachama Blanca (id_especie=4), unica especie con
metrica de catalogo RF-16 seedeada en TEST (id_metrica_produccion=16,
tipo_medicion=PESO, unidad_medida=kg, aplica_a_tipo_activo=AMBOS).

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_238_240_camino_feliz_y_fase.py -v \
        --html=Resultados/reporte-TC-M02-238-240.html --self-contained-html
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_evento_productivo_use_case import (
    RegistrarEventoProductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoActivo,
    EventoProductivo,
    GestionFase,
)
from src.biological_assets.domain.repositories.parametros_especie_port import MetricaProductiva
from src.biological_assets.infrastructure.dto.registrar_evento_productivo_dto import (
    RegistrarEventoProductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError

ID_ACTIVO = 165  # Cachama INDIVIDUAL creado en la exploracion en vivo de esta sesion (TC-M02-G63)
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


def _use_case(ciclo_habilitado: bool, evento_guardado=None) -> RegistrarEventoProductivoUseCase:
    activo_repo = MagicMock()
    activo_repo.obtener_por_id.return_value = _activo()
    activo_repo.obtener_fase_activa.return_value = _fase_activa()

    parametros_port = MagicMock()
    parametros_port.obtener_metrica_productiva.return_value = _metrica()

    ciclo_port = MagicMock()
    ciclo_port.metrica_habilitada_en_ciclo.return_value = ciclo_habilitado

    evento_repo = MagicMock()
    evento_repo.existe_productivo_duplicado.return_value = False
    if evento_guardado is not None:
        evento_repo.guardar.return_value = evento_guardado

    return RegistrarEventoProductivoUseCase(
        db=MagicMock(),
        activo_repo=activo_repo,
        evento_repo=evento_repo,
        parametros_port=parametros_port,
        ciclo_port=ciclo_port,
        bitacora_repo=MagicMock(),
    )


class TestTCM02238EventoProductivoValido:

    def test_registrar_evento_productivo_camino_feliz(self):
        """
        RF-43: con un activo ACTIVO, catalogo RF-16 valido para su
        especie y una fase productiva activa que habilita esa metrica,
        registrar un evento productivo (tipo_producto=PESO, cantidad=20,
        unidad=kg) debe aceptarse y quedar disponible para RF-51/M06.
        """
        evento_guardado = EventoActivo(
            id_activo_biologico=ID_ACTIVO,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=902,
            productivo=EventoProductivo(
                cantidad=Decimal('20'),
                id_metrica_produccion=ID_METRICA_PESO,
                id_ciclo_productivo=ID_CICLO_PRODUCTIVO_CACHAMA,
                tipo_producto='PESO',
                unidad_medida='kg',
            ),
        )
        use_case = _use_case(ciclo_habilitado=True, evento_guardado=evento_guardado)
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
        dto = RegistrarEventoProductivoDTO(
            tipo_producto='peso',
            cantidad_producida=Decimal('20'),
            unidad_medida='kg',
            fecha_evento=date(2026, 9, 9),
        )

        resultado = use_case.execute(ID_ACTIVO, dto, usuario_actual)

        assert resultado is evento_guardado
        assert resultado.productivo.cantidad == Decimal('20')
        assert resultado.productivo.tipo_producto == 'PESO'
        assert resultado.productivo.unidad_medida == 'kg'


class TestTCM02240ProductoNoHabilitadoParaFase:

    def test_rechaza_tipo_producto_no_habilitado_para_el_ciclo_activo(self):
        """
        RF-43 (E-04): un tipo_producto que SI esta en el catalogo RF-16
        de la especie, pero que NO esta habilitado para el ciclo
        productivo de la fase activa, debe rechazarse con 422
        TIPO_PRODUCTO_NO_HABILITADO_FASE -- equivalente a la ficha
        "tipo_producto=LECHE en fase Levante".
        """
        use_case = _use_case(ciclo_habilitado=False)
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
