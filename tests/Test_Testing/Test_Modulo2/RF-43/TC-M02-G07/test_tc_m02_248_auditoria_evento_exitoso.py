"""
TC-M02-G07 (parte Pytest) - Verificar registro en auditoria al crear un
evento productivo con exito (TC-M02-248).

RF relacionado: RF-43/RF-52, CU09 Gestionar eventos productivos y bajas
Categoria: Pruebas funcionales

Criterio de aceptacion (segun la ficha, sub-caso 1):
    "Registrar un evento productivo (ej. LECHE) y consultar
    inmediatamente la bitacora de auditoria." Resultado esperado: "El
    evento productivo queda reflejado en la bitacora de auditoria
    (RF-52) con rf_origen=RF-43, usuario responsable, fecha/hora, activo,
    tipo de producto y cantidad."

Por que Pytest y no Newman: registrar un evento productivo con EXITO
exige una fase productiva activa (E-02) -- TC-M02-G61 confirmo en vivo
que POST /activos-biologicos/{id}/fases (RF-37) responde 500 siempre, asi
que ningun activo puede llegar a tener fase activa hoy en TEST, y por lo
tanto nunca se puede alcanzar un evento productivo EXITOSO contra el
backend real. Se simula con dobles de prueba el estado que RF-37 deberia
poder crear, igual que en TC-M02-106/238 (TC-M02-G61/G63).

Este test va un paso mas alla que los anteriores: en vez de solo
verificar el resultado de la operacion, inspecciona los argumentos EXACTOS
con los que se llama a bitacora_repo.registrar() para confirmar que
contienen todos los campos que la ficha exige (usuario responsable,
activo, tipo de producto, cantidad, rf_origen=RF43).

Datos usados: especie Cachama Blanca (id_especie=4), unica especie con
metrica de catalogo RF-16 seedeada en TEST (id_metrica_produccion=16,
tipo_medicion=PESO, unidad_medida=kg).

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_248_auditoria_evento_exitoso.py -v \
        --html=Resultados/reporte-TC-M02-248.html --self-contained-html
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

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

ID_ACTIVO = 168  # Cachama INDIVIDUAL, mismo patron usado en TC-M02-G61/G62/G63/G64/G65
ID_ESPECIE_CACHAMA = 4
ID_METRICA_PESO = 16
ID_CICLO_PRODUCTIVO_CACHAMA = 4
ID_USUARIO_RESPONSABLE = 1


class TestTCM02248AuditoriaEventoProductivoExitoso:

    def test_registro_exitoso_queda_reflejado_en_bitacora_con_los_campos_exigidos(self):
        activo = ActivoBiologico(
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
        fase_activa = GestionFase(
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
        metrica = MetricaProductiva(
            id_metrica_produccion=ID_METRICA_PESO,
            tipo_producto='PESO',
            unidad_medida='kg',
            aplica_a_tipo_activo='AMBOS',
        )

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.return_value = activo
        activo_repo.obtener_fase_activa.return_value = fase_activa

        parametros_port = MagicMock()
        parametros_port.obtener_metrica_productiva.return_value = metrica

        ciclo_port = MagicMock()
        ciclo_port.metrica_habilitada_en_ciclo.return_value = True

        evento_repo = MagicMock()
        evento_repo.existe_productivo_duplicado.return_value = False
        evento_guardado = EventoActivo(
            id_activo_biologico=ID_ACTIVO,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=ID_USUARIO_RESPONSABLE,
            id_eventos=903,
            productivo=EventoProductivo(
                cantidad=Decimal('20'),
                id_metrica_produccion=ID_METRICA_PESO,
                id_ciclo_productivo=ID_CICLO_PRODUCTIVO_CACHAMA,
                tipo_producto='PESO',
                unidad_medida='kg',
            ),
        )
        evento_repo.guardar.return_value = evento_guardado

        bitacora_repo = MagicMock()
        use_case = RegistrarEventoProductivoUseCase(
            db=MagicMock(),
            activo_repo=activo_repo,
            evento_repo=evento_repo,
            parametros_port=parametros_port,
            ciclo_port=ciclo_port,
            bitacora_repo=bitacora_repo,
        )
        usuario_actual = UsuarioActual(
            id_usuario=ID_USUARIO_RESPONSABLE, id_token=1, id_rol=1, id_estado_cuenta=2
        )
        dto = RegistrarEventoProductivoDTO(
            tipo_producto='peso',
            cantidad_producida=Decimal('20'),
            unidad_medida='kg',
            fecha_evento=date(2026, 9, 9),
        )

        use_case.execute(ID_ACTIVO, dto, usuario_actual)

        assert bitacora_repo.registrar.call_count >= 1, (
            'RF-52 exige que todo evento productivo exitoso quede '
            'reflejado en la bitacora de auditoria.'
        )
        evento_auditoria = bitacora_repo.registrar.call_args_list[0].args[0]

        assert evento_auditoria.rf_origen == 'RF43'
        assert evento_auditoria.resultado == 'EXITOSO'
        assert evento_auditoria.id_usuario_responsable == ID_USUARIO_RESPONSABLE, (
            'La ficha exige que el usuario responsable quede en la bitacora.'
        )
        assert evento_auditoria.id_activo_biologico == ID_ACTIVO, (
            'La ficha exige que el activo quede en la bitacora.'
        )
        assert evento_auditoria.timestamp_evento is not None, (
            'La ficha exige que la fecha/hora del evento quede en la bitacora.'
        )
        detalle = evento_auditoria.detalle_tecnico or {}
        assert detalle.get('tipo_producto') == 'PESO', (
            'La ficha exige que el tipo de producto quede en la bitacora.'
        )
        assert 'cantidad' in detalle, (
            'La ficha exige que la cantidad producida quede en la bitacora.'
        )
