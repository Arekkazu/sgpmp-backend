"""
TC-M02-G65 (parte Pytest) - Verificar rollback ante fallo transaccional
al registrar un evento productivo (TC-M02-246).

RF relacionado: RF-43, CU09 Gestionar eventos productivos y bajas
Categoria: Pruebas de validacion / Pruebas funcionales

Criterio de aceptacion (segun la ficha, sub-caso 3):
    Precondicion: "Fallo transaccional simulado en el repositorio de
    eventos productivos." Paso: "Simular un fallo interno durante la
    persistencia del evento productivo (ej. caida de conexion a BD a
    mitad de transaccion)." Resultado esperado: "HTTP 500 (E-09) ...
    El historial del activo permanece sin cambios y el fallo queda
    registrado en auditoria."

Por que Pytest y no Newman: no hay forma de forzar una caida de conexion
a BD a mitad de transaccion desde un cliente HTTP de caja negra contra el
backend real de TEST. Se simula el fallo con un doble de prueba que hace
fallar evento_repo.guardar() (el punto exacto de persistencia del
evento), igual que el patron ya usado en TC-M09-G60/TC-M09-115 para
simular fallos de auditoria.

Se verifica directamente en el codigo de
registrar_evento_productivo_use_case.py (bloque try/except del
metodo execute, lineas ~198-216) que el use case:
  1. Llama self.db.rollback() ante la excepcion (revierte cualquier
     escritura parcial, sin registros a medias).
  2. Registra el intento fallido en la bitacora de auditoria (RF-52)
     con rf_origen='RF43', tipo_evento='EVENTO_PRODUCTIVO_FALLIDO',
     resultado='FALLIDO', antes de relanzar la excepcion.
  3. Relanza la excepcion original -- el router no la captura
     especificamente, asi que llega al handler global de FastAPI
     (error_no_controlado_handler en error_handlers.py) y se traduce a
     HTTP 500 ERROR_INTERNO con un mensaje generico (NO el mensaje
     literal "El evento productivo no pudo ser registrado por un error
     interno del sistema..." que cita la ficha -- ese texto exacto no
     existe en el codigo; el mensaje real es "Ocurrio un error interno.
     Intenta de nuevo; si el problema persiste, contacta al equipo de
     soporte.", igual para cualquier excepcion no controlada del sistema).

Datos usados: especie Cachama Blanca (id_especie=4), unica especie con
metrica de catalogo RF-16 seedeada en TEST.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_246_rollback_fallo_transaccional.py -v \
        --html=Resultados/reporte-TC-M02-246.html --self-contained-html
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

ID_ACTIVO = 167  # Cachama INDIVIDUAL, mismo patron usado en TC-M02-G61/G62/G63/G64
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


class TestTCM02246RollbackFalloTransaccional:

    def test_rollback_y_auditoria_ante_fallo_de_persistencia(self):
        """
        RF-43 (E-09): si evento_repo.guardar() falla (simulando una caida
        de conexion a BD a mitad de la transaccion), el use case debe
        revertir (db.rollback()), registrar el intento fallido en la
        bitacora de auditoria (RF-52) y relanzar la excepcion original
        -- sin dejar registros parciales.
        """
        activo_repo = MagicMock()
        activo_repo.obtener_por_id.return_value = _activo()
        activo_repo.obtener_fase_activa.return_value = _fase_activa()

        parametros_port = MagicMock()
        parametros_port.obtener_metrica_productiva.return_value = _metrica()

        ciclo_port = MagicMock()
        ciclo_port.metrica_habilitada_en_ciclo.return_value = True

        evento_repo = MagicMock()
        evento_repo.existe_productivo_duplicado.return_value = False
        fallo_bd = ConnectionError('simulated: conexion a BD perdida a mitad de la transaccion')
        evento_repo.guardar.side_effect = fallo_bd

        db = MagicMock()
        bitacora_repo = MagicMock()

        use_case = RegistrarEventoProductivoUseCase(
            db=db,
            activo_repo=activo_repo,
            evento_repo=evento_repo,
            parametros_port=parametros_port,
            ciclo_port=ciclo_port,
            bitacora_repo=bitacora_repo,
        )
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
        dto = RegistrarEventoProductivoDTO(
            tipo_producto='peso',
            cantidad_producida=Decimal('20'),
            unidad_medida='kg',
            fecha_evento=date(2026, 9, 9),
        )

        with pytest.raises(ConnectionError):
            use_case.execute(ID_ACTIVO, dto, usuario_actual)

        db.rollback.assert_called_once()

        assert bitacora_repo.registrar.call_count >= 1, (
            'RF-43/RF-52 exige que un fallo de persistencia del evento '
            'productivo quede registrado en la bitacora de auditoria '
            '(tipo_evento=EVENTO_PRODUCTIVO_FALLIDO, resultado=FALLIDO).'
        )
        evento_auditoria = bitacora_repo.registrar.call_args_list[0].args[0]
        assert evento_auditoria.rf_origen == 'RF43'
        assert evento_auditoria.tipo_evento == 'EVENTO_PRODUCTIVO_FALLIDO'
        assert evento_auditoria.resultado == 'FALLIDO'
        assert evento_auditoria.id_activo_biologico == ID_ACTIVO
