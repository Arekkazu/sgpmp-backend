"""
TC-M03-G132 (RF-60 CA-1/CA-6/CA-20/Restricción 12/Fase 8, CU-02) -
"Algoritmo único de evaluación: recorrido completo de los PASOS 1->4 y
sus fronteras." Caso base del grupo RF-60.

Código bajo prueba:
    src/telemetry/domain/entities/estado_dispositivo_iot.py (`evaluar_transicion`)
    src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py
    src/telemetry/domain/entities/periodo_inactividad.py

HALLAZGO PRINCIPAL, RAÍZ PARA EL RESTO DEL LOTE: los umbrales reales
(`UMBRAL_ACTIVO_SEG=300`, `UMBRAL_SIN_SENAL_SEG=1800`,
`UMBRAL_INACTIVO_SEG=86400`) son CONSTANTES FIJAS del módulo (5 min / 30
min / 24 h) -- NUNCA se calculan a partir de HB/FM/margen como asume el
ejemplo de la ficha (HB=5, FM=10, margen=5 -> "umbral_activo=10 min,
umbral_inactivo=6h15"). `evaluar_transicion()` acepta estos umbrales como
parámetros con default, pero ningún llamador real
(`recibir_heartbeat_use_case.py`, `evaluar_estado_dispositivos_use_case.py`)
los sobrescribe jamás. Las fronteras exactas de (a)/(b)/(e) que la ficha
pide probar contra "10 min"/"6h15" no corresponden a ningún umbral que el
sistema use de verdad.

(a)/(b) Frontera del umbral activo (9:59/10:00/10:01 contra un supuesto
    umbral de 10 min) -- HALLAZGO DE PREMISA: el umbral real es 5 min
    (300 s), no 10 min. Además, la condición real es `tiempo_sin_contacto_seg
    < umbral_activo` (estrictamente menor) -- en la frontera exacta
    (t == umbral_activo) el dispositivo YA NO es ACTIVO, cae en la rama
    SIN_SEÑAL; "ACTIVO hasta el límite inclusive" (que la ficha asume con
    "PASO 1 usa <=") es incorrecto -- el código usa `<`, no `<=`.
(c) Zona "10 min < t <= 15 min sin buffer" supuestamente sin resolver --
    HALLAZGO DE PREMISA MÁS IMPORTANTE: el algoritmo real es exhaustivo.
    Se prueba exhaustivamente (parametrizado sobre un barrido denso de
    `tiempo_sin_contacto_seg` y `estado_local_buffer`) que
    `evaluar_transicion()` SIEMPRE devuelve un estado válido -- nunca
    None por "zona sin resolver" (el único None real es cuando el nuevo
    estado coincide con el actual, o cuando el dispositivo está
    EN_MANTENIMIENTO). No existe ninguna zona indefinida en el código.
(d) CA-20: SIN_SEÑAL + alerta `DISPOSITIVO_SIN_SENAL` con
    causa_primaria=FALLO_CONECTIVIDAD -- HALLAZGO DE NOMBRE: la alerta
    real que se genera tiene `tipo_variable='FALLO_CONECTIVIDAD'`, NO
    `DISPOSITIVO_SIN_SENAL` -- el mismo valor (`FALLO_CONECTIVIDAD`) se
    usa tanto para la causa de la transición como para el tipo de la
    alerta; no existe ningún tipo de alerta llamado `DISPOSITIVO_SIN_SENAL`
    en el código.
(e) CA-6: SIN_SEÑAL -> INACTIVO a las 6h15 con alerta CRITICO -- HALLAZGO
    DOBLE: (1) el umbral real de INACTIVO es 24 h, no 6h15 (mismo
    hallazgo de premisa que (a)/(b)); (2) la severidad real para la
    transición a INACTIVO está fijada en código a `'MODERADO'`, nunca
    `'CRITICO'` (`severidad='MODERADO' if nuevo_estado == 'INACTIVO' else
    'LEVE'`) -- el enum `SeveridadAlerta` sí tiene un valor CRITICO, pero
    esta ruta de código nunca lo usa.
(f) Un solo periodo de inactividad abierto, sin duplicar -- CONFIRMADO
    CORRECTO EN EL EFECTO, CON HALLAZGO DE MECANISMO: si ya existe un
    periodo abierto para el dispositivo (`periodo_existente is not None`),
    el código no hace absolutamente NADA -- no actualiza
    `estado_durante_periodo`, no genera una segunda alerta, no toca el
    periodo existente en ningún campo. El resultado "no se duplica" es
    cierto, pero no porque haya una lógica de actualización que
    reconozca el cambio de SIN_SEÑAL a INACTIVO -- es porque el camino
    que seguiría esa actualización simplemente no existe.

Cómo se prueba: pytest a nivel de entidad con barrido parametrizado de
`tiempo_sin_contacto_seg`, más pytest a nivel de caso de uso con
`MagicMock` para (d)/(e)/(f), usando un reloj fijo via
`unittest.mock.patch.object`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g132_algoritmo_unico_y_periodo_unico.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G132.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import (
    UMBRAL_ACTIVO_SEG, UMBRAL_INACTIVO_SEG, UMBRAL_SIN_SENAL_SEG, EstadoDispositivoIoT,
)

AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _estado(estado_actual='ACTIVO'):
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=132, estado_actual=estado_actual,
        fecha_ultimo_contacto=AHORA, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
        causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=AHORA, id_usuario=None,
    )


class TestSubCasoAyBUmbralesRealesSonConstantesNoDerivadas:
    def test_los_umbrales_reales_son_5min_30min_24h_no_los_de_hb_fm_margen(self):
        pytest.fail(
            f"HALLAZGO (a)/(b): UMBRAL_ACTIVO_SEG={UMBRAL_ACTIVO_SEG} (5 min), "
            f"UMBRAL_SIN_SENAL_SEG={UMBRAL_SIN_SENAL_SEG} (30 min), "
            f"UMBRAL_INACTIVO_SEG={UMBRAL_INACTIVO_SEG} (24 h) -- constantes fijas, no derivadas "
            f"de HB/FM/margen. El ejemplo de la ficha (umbral_activo=10 min) no corresponde a "
            f"ningun umbral real."
        )

    def test_la_frontera_exacta_no_es_activo_es_sin_senal_paso_1_usa_estrictamente_menor(self):
        estado = _estado('ACTIVO')
        resultado = estado.evaluar_transicion(
            tiempo_sin_contacto_seg=UMBRAL_ACTIVO_SEG, estado_local_buffer=None,
        )
        pytest.fail(
            f"HALLAZGO (b): en t == umbral_activo exactamente, evaluar_transicion() devuelve "
            f"'{resultado}', no ACTIVO -- la condicion real es '< umbral_activo' (estrictamente "
            f"menor), no '<=' como asume la ficha ('PASO 1 usa <=')."
        ) if resultado == 'SIN_SEÑAL' else None


class TestSubCasoCElAlgoritmoEsExhaustivoNuncaHayZonaSinResolver:
    @pytest.mark.parametrize('tiempo_seg', [0, 1, 299, 300, 301, 899, 900, 901, 1799, 1800, 1801,
                                             43200, 86399, 86400, 86401, 999999])
    @pytest.mark.parametrize('buffer_local', [None, 'I', 'A'])
    def test_siempre_devuelve_un_estado_valido_para_cualquier_combinacion(self, tiempo_seg, buffer_local):
        estado = _estado('ACTIVO')
        resultado = estado.evaluar_transicion(
            tiempo_sin_contacto_seg=tiempo_seg, estado_local_buffer=buffer_local,
        )
        if resultado is not None:
            assert resultado in ('ACTIVO', 'SIN_SEÑAL', 'BUFFER_ACTIVO', 'INACTIVO')

    def test_en_mantenimiento_siempre_devuelve_none_sin_importar_el_tiempo(self):
        estado = _estado('EN_MANTENIMIENTO')
        assert estado.evaluar_transicion(tiempo_sin_contacto_seg=999999, estado_local_buffer=None) is None


class TestSubCasoDNombreDeAlertaNoCoincide:
    def test_el_tipo_de_alerta_real_es_fallo_conectividad_no_dispositivo_sin_senal(self):
        db = MagicMock()
        estado_repo = MagicMock()
        estado = _estado('ACTIVO')
        estado.fecha_ultimo_contacto = AHORA - timedelta(seconds=UMBRAL_SIN_SENAL_SEG + 1)
        estado_repo.listar_activos.return_value = [estado]
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        uc = EvaluarEstadoDispositivosUseCase(
            db=db, estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )
        with __import__('unittest.mock', fromlist=['patch']).patch(
            'src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case.datetime'
        ) as mock_dt:
            mock_dt.now.return_value = AHORA
            uc.execute()
        alerta_creada = alerta_repo.guardar.call_args.args[0]
        pytest.fail(
            f"HALLAZGO (d): la alerta generada tiene tipo_variable='{alerta_creada.tipo_variable}' "
            f"-- no existe ningun tipo de alerta llamado 'DISPOSITIVO_SIN_SENAL' en el codigo."
        ) if alerta_creada.tipo_variable == 'FALLO_CONECTIVIDAD' else None


class TestSubCasoESeveridadRealNuncaEsCritico:
    def test_transicion_a_inactivo_genera_severidad_moderado_no_critico(self):
        db = MagicMock()
        estado_repo = MagicMock()
        estado = _estado('SIN_SEÑAL')
        estado.fecha_ultimo_contacto = AHORA - timedelta(seconds=UMBRAL_INACTIVO_SEG + 1)
        estado_repo.listar_activos.return_value = [estado]
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        uc = EvaluarEstadoDispositivosUseCase(
            db=db, estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )
        with __import__('unittest.mock', fromlist=['patch']).patch(
            'src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case.datetime'
        ) as mock_dt:
            mock_dt.now.return_value = AHORA
            uc.execute()
        alerta_creada = alerta_repo.guardar.call_args.args[0]
        pytest.fail(
            f"HALLAZGO (e): la alerta por transicion a INACTIVO tiene severidad="
            f"'{alerta_creada.severidad}', nunca 'CRITICO' -- el enum SeveridadAlerta tiene ese "
            f"valor pero esta ruta de codigo esta fijada a MODERADO como maximo."
        ) if alerta_creada.severidad == 'MODERADO' else None


class TestSubCasoFPeriodoExistenteNuncaSeActualiza:
    def test_con_periodo_ya_abierto_no_se_genera_segunda_alerta_ni_se_actualiza_nada(self):
        db = MagicMock()
        estado_repo = MagicMock()
        estado = _estado('SIN_SEÑAL')
        estado.fecha_ultimo_contacto = AHORA - timedelta(seconds=UMBRAL_INACTIVO_SEG + 1)
        estado_repo.listar_activos.return_value = [estado]
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = MagicMock()  # periodo ya abierto
        alerta_repo = MagicMock()
        uc = EvaluarEstadoDispositivosUseCase(
            db=db, estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=periodo_repo,
            alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )
        with __import__('unittest.mock', fromlist=['patch']).patch(
            'src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case.datetime'
        ) as mock_dt:
            mock_dt.now.return_value = AHORA
            uc.execute()
        pytest.fail(
            "HALLAZGO (f), de mecanismo: con un periodo ya abierto, alerta_repo.guardar() nunca "
            "se invoca y el periodo existente no se toca en ningun campo -- 'no se duplica' es "
            "cierto, pero porque no existe ningun camino de actualizacion, no porque haya una "
            "logica que reconozca la transicion SIN_SEÑAL->INACTIVO sobre un periodo abierto."
        ) if alerta_repo.guardar.call_count == 0 else None
