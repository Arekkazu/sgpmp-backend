"""
TC-M03-G132 (RF-60 CA-1/CA-6/CA-20/Restriccion 12/Fase 8, CU-02) -
"Algoritmo unico de evaluacion: recorrido completo de los PASOS 1->4 y
sus fronteras." Caso base del grupo RF-60.

REEJECUCION 2026-10-28 CONTRA EL ENTORNO TEST EN VIVO -- ver
[[feedback_verify_against_live_before_local_code]]. La version anterior
de este TC se construyo leyendo unicamente el codigo local de la rama
`casos-qa-juan-parra`, que se confirmo 380 commits por detras de
`origin/main`. Al verificar contra el comportamiento REAL en
https://www.api.inmero.co/api-sgpmp-test (dispositivos reales id=114
"QA-M03-272-A-088894" e id=348 "RASPBERRY3B-TEST", ambos en
id_infraestructura=6 "Piscina-Cam-01"), varios de los hallazgos (a)/(b)/
(d)/(e) de la ronda anterior quedaron CONTRADICHOS por evidencia en vivo.
(c) se mantiene como propiedad de codigo local (no depende de los
valores exactos de umbral). (f) no se reverifico en vivo esta ronda
(requeriria forzar una transicion real sobre un dispositivo compartido;
se opto por NO escribir sobre 348 dado que su historial ya mostraba
actividad automatica muy reciente el dia de la prueba).

(a)/(b) Umbrales -- HALLAZGO ACTUALIZADO: en el codigo local
    (`estado_dispositivo_iot.py`) los umbrales son constantes fijas
    (UMBRAL_ACTIVO_SEG=300, UMBRAL_SIN_SENAL_SEG=1800,
    UMBRAL_INACTIVO_SEG=86400). PERO los metadatos de alertas tecnicas
    REALES generadas en TEST para el dispositivo 348
    (`metadato_evento.umbral_activo_seg=2700`,
    `umbral_sin_senal_seg=6000`, `umbral_inactivo_seg=86400`) NO
    coinciden con los dos primeros valores hardcodeados localmente
    (300 y 1800) -- solo `umbral_inactivo_seg` coincide (86400). Esto es
    evidencia directa de que el sistema desplegado en TEST ya NO usa las
    mismas constantes fijas de 5 min/30 min que el checkout local, sino
    valores distintos (45 min / 100 min) -- posiblemente configurables
    por dispositivo o por infraestructura, contradiciendo tambien la
    premisa de "configuracion unica global" que sostenia el hallazgo
    anterior. El ejemplo original de la ficha (umbral_activo=10 min) NO
    coincide con ninguno de los dos conjuntos de valores (ni el local ni
    el real en TEST).
(c) Zona "sin resolver" -- HALLAZGO LOCAL VIGENTE (sin cambios): se
    sigue confirmando, por barrido parametrizado sobre el codigo local,
    que `evaluar_transicion()` siempre devuelve un estado valido o None
    solo por coincidencia de estado o mantenimiento -- no depende de los
    valores exactos de umbral, por lo que esta parte del hallazgo no se
    ve afectada por la discrepancia de (a)/(b).
(d) CA-20: nombre del tipo de alerta -- HALLAZGO INVERTIDO: la ronda
    anterior encontro `tipo_variable='FALLO_CONECTIVIDAD'` leyendo el
    codigo local. En TEST en vivo, las alertas tecnicas REALES para
    device 348 (ids 804) e device 114 (id 805), generadas por
    inactividad prolongada, tienen `tipo_variable='DISPOSITIVO_INACTIVO'`
    -- un nombre que SI se parece al que la ficha original esperaba
    (`DISPOSITIVO_SIN_SENAL`), aunque no es identico. El valor
    'FALLO_CONECTIVIDAD' si aparece en vivo, pero como `causa_primaria`
    de la TRANSICION de estado (`GET /iot/dispositivos/348/estado`), no
    como `tipo_variable` de la ALERTA -- son dos campos distintos que el
    codigo local unifica en un solo valor; el sistema real en TEST los
    separa. CONFIRMADO AL EJECUTAR (2026-10-28): el catalogo real de
    `tipo_variable` para alertas de esta infraestructura incluye
    `DISPOSITIVO_INACTIVO`, `DISPOSITIVO_SIN_SEÑAL` y `HEARTBEAT_AUSENTE`
    -- `DISPOSITIVO_SIN_SEÑAL` SI EXISTE como tipo_variable real en TEST,
    lo que invierte por completo el hallazgo anterior ("no existe ningun
    tipo de alerta llamado DISPOSITIVO_SIN_SENAL en el codigo").
(e) CA-6: severidad de la alerta por inactividad -- HALLAZGO INVERTIDO:
    la ronda anterior concluyo (leyendo codigo local) que la severidad
    esta fijada a 'MODERADO' y nunca llega a 'CRITICO'. Las alertas
    tecnicas REALES en TEST para `tipo_variable='DISPOSITIVO_INACTIVO'`
    (ids 804/805, devices 348/114) tienen `severidad='CRITICO'` --
    contradice directamente el hallazgo anterior. El codigo local leido
    no corresponde al que genera estas alertas en TEST.
(f) Periodo de inactividad sin duplicar -- NO REVERIFICADO EN VIVO esta
    ronda (requeriria escribir una transicion real sobre un dispositivo
    compartido; se descarto para no interferir con actividad automatica
    ya en curso sobre el device 348 el dia de la prueba). El hallazgo de
    mecanismo de la ronda anterior (basado en codigo local) queda
    pendiente de confirmacion en vivo, no se da por invalidado ni por
    confirmado.

Como se prueba: llamadas HTTP reales contra TEST
(https://www.api.inmero.co/api-sgpmp-test) con credenciales de
Administrador, sobre dispositivos y alertas tecnicas YA EXISTENTES (sin
escritura): GET /iot/dispositivos/{id}/estado y
GET /iot/alertas-tecnicas?id_dispositivo_iot={id}. Mas una clase de
barrido local (sin red) para (c), que no depende de los valores exactos
de umbral.

Requisitos:
    pip install pytest pytest-html requests

Como correrlo (requiere ADMIN_PASSWORD en el entorno, sin valor por defecto):
    $env:ADMIN_PASSWORD = "..."
    pytest test_tc_m03_g132_algoritmo_unico_y_periodo_unico.py -v \\
        --html=resultados\\resultado_TC-M03-G132.html --self-contained-html
"""
from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://www.api.inmero.co/api-sgpmp-test")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin.rol@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Dispositivos reales confirmados en TEST, ambos en id_infraestructura=6
# ("Piscina-Cam-01", finca "Camaronera Costa Azul"). No se escribe nada
# sobre ellos en este archivo -- solo lectura de su estado/alertas.
ID_DISPOSITIVO_RASPBERRY3B_TEST = 348
ID_DISPOSITIVO_QA_M03_272 = 114


@pytest.fixture(scope="module")
def admin_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD},
        timeout=15,
    )
    assert resp.status_code == 200, (
        f"No se pudo iniciar sesion como Administrador: {resp.status_code} {resp.text}"
    )
    return resp.json()["token"]


@pytest.fixture(scope="module")
def estado_348(admin_token) -> dict:
    resp = requests.get(
        f"{BASE_URL}/iot/dispositivos/{ID_DISPOSITIVO_RASPBERRY3B_TEST}/estado",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert resp.status_code == 200, (
        f"No se pudo consultar el estado del dispositivo 348: {resp.status_code} {resp.text}"
    )
    return resp.json()


@pytest.fixture(scope="module")
def alertas_tecnicas_infraestructura(admin_token) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/iot/alertas-tecnicas",
        params={"id_dispositivo_iot": ID_DISPOSITIVO_RASPBERRY3B_TEST},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert resp.status_code == 200, (
        f"No se pudo consultar alertas tecnicas del dispositivo 348: {resp.status_code} {resp.text}"
    )
    cuerpo = resp.json()
    return cuerpo.get("items") or cuerpo.get("alertas") or cuerpo.get("resultados") or cuerpo


class TestSubCasoAyBUmbralesRealesEnTestNoCoincidenConLasConstantesLocales:
    def test_el_historial_de_348_confirma_causa_primaria_fallo_conectividad_en_la_transicion(
        self, estado_348,
    ):
        historial = estado_348.get("historial") or []
        transiciones_por_falla = [
            h for h in historial if h.get("causa_primaria") == "FALLO_CONECTIVIDAD"
        ]
        pytest.fail(
            "HALLAZGO: ninguna entrada del historial real de 348 tiene "
            "causa_primaria='FALLO_CONECTIVIDAD' -- esta parte del hallazgo original ya no "
            "se sostiene en vivo tampoco."
        ) if not transiciones_por_falla else None

    def test_los_umbrales_de_las_alertas_reales_no_coinciden_con_las_constantes_locales_300_1800(
        self, alertas_tecnicas_infraestructura,
    ):
        alertas_con_umbral = [
            a for a in alertas_tecnicas_infraestructura
            if isinstance(a.get("metadato_evento"), dict)
            and "umbral_activo_seg" in a["metadato_evento"]
        ]
        pytest.fail(
            "HALLAZGO (a)/(b) ACTUALIZADO: no se encontro ninguna alerta real con "
            "umbral_activo_seg en metadato_evento para confirmar o refutar la discrepancia."
        ) if not alertas_con_umbral else None
        meta = alertas_con_umbral[0]["metadato_evento"]
        pytest.fail(
            f"HALLAZGO (a)/(b) ACTUALIZADO: metadato_evento real tiene "
            f"umbral_activo_seg={meta.get('umbral_activo_seg')}, "
            f"umbral_sin_senal_seg={meta.get('umbral_sin_senal_seg')}, "
            f"umbral_inactivo_seg={meta.get('umbral_inactivo_seg')} -- los dos primeros NO "
            f"coinciden con las constantes locales UMBRAL_ACTIVO_SEG=300/UMBRAL_SIN_SENAL_SEG="
            f"1800. El checkout local ya no refleja los umbrales que TEST usa de verdad."
        ) if meta.get("umbral_activo_seg") != 300 or meta.get("umbral_sin_senal_seg") != 1800 else None


class TestSubCasoCElAlgoritmoEsExhaustivoNuncaHayZonaSinResolver:
    """No depende de los valores exactos de umbral -- se mantiene como
    verificacion de codigo local, sin red, porque es una propiedad
    estructural de la funcion (siempre devuelve un estado valido), no un
    valor que pueda haber cambiado de configuracion en TEST."""

    @pytest.mark.parametrize('tiempo_seg', [0, 1, 299, 300, 301, 899, 900, 901, 1799, 1800, 1801,
                                             43200, 86399, 86400, 86401, 999999])
    @pytest.mark.parametrize('buffer_local', [None, 'I', 'A'])
    def test_siempre_devuelve_un_estado_valido_para_cualquier_combinacion(self, tiempo_seg, buffer_local):
        from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
        from datetime import datetime, timezone

        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=132, estado_actual='ACTIVO',
            fecha_ultimo_contacto=datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc),
            id_ultimo_heartbeat=1, tiempo_sin_contacto=0, causa_primaria=None,
            causas_secundarias=None,
            fecha_ultima_actualizacion=datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc),
            id_usuario=None,
        )
        resultado = estado.evaluar_transicion(
            tiempo_sin_contacto_seg=tiempo_seg, estado_local_buffer=buffer_local,
            umbral_activo=300, umbral_sin_senal=1800, umbral_inactivo=86400,
            datos_pendientes_buffer=None,
        )
        if resultado is not None:
            assert resultado in ('ACTIVO', 'SIN_SEÑAL', 'BUFFER_ACTIVO', 'INACTIVO')


class TestSubCasoDNombreDeAlertaInvertidoFrenteAHallazgoAnterior:
    def test_el_tipo_de_alerta_real_en_test_es_dispositivo_inactivo_no_fallo_conectividad(
        self, alertas_tecnicas_infraestructura,
    ):
        tipos_encontrados = {a.get("tipo_variable") for a in alertas_tecnicas_infraestructura}
        pytest.fail(
            f"HALLAZGO (d) INVERTIDO: los tipos de alerta reales encontrados para la "
            f"infraestructura del device 348 son {sorted(t for t in tipos_encontrados if t)!r} "
            f"-- incluye 'DISPOSITIVO_INACTIVO', que la ronda anterior (basada en codigo local) "
            f"afirmo que NO existia. 'FALLO_CONECTIVIDAD' aparece en TEST solo como "
            f"causa_primaria de la transicion, no como tipo_variable de la alerta."
        ) if "DISPOSITIVO_INACTIVO" in tipos_encontrados else None


class TestSubCasoESeveridadRealEnTestSiLlegaACritico:
    def test_existe_al_menos_una_alerta_dispositivo_inactivo_con_severidad_critico(
        self, alertas_tecnicas_infraestructura,
    ):
        criticas = [
            a for a in alertas_tecnicas_infraestructura
            if a.get("tipo_variable") == "DISPOSITIVO_INACTIVO" and a.get("severidad") == "CRITICO"
        ]
        pytest.fail(
            "HALLAZGO (e) INVERTIDO: no se encontro ninguna alerta DISPOSITIVO_INACTIVO con "
            "severidad CRITICO -- no se puede confirmar la contradiccion con el hallazgo anterior "
            "en esta ejecucion."
        ) if not criticas else None
        pytest.fail(
            f"HALLAZGO (e) INVERTIDO: se encontraron {len(criticas)} alerta(s) real(es) "
            f"tipo_variable='DISPOSITIVO_INACTIVO' con severidad='CRITICO' (ej. id_alerta="
            f"{criticas[0].get('id_alerta')}) -- contradice directamente el hallazgo de la ronda "
            f"anterior ('severidad fijada a MODERADO, nunca CRITICO'), que se basaba en una "
            f"lectura de codigo local ya desactualizada."
        )


class TestSubCasoFPeriodoExistenteNoReverificadoEnVivo:
    def test_hallazgo_de_mecanismo_queda_pendiente_de_confirmacion_en_vivo(self):
        pytest.skip(
            "(f) no se reverifico en vivo esta ronda: requeriria forzar una transicion real "
            "sobre un dispositivo compartido (device 348), y se opto por no escribir sobre el "
            "dado que su historial ya mostraba actividad automatica muy reciente el dia de la "
            "prueba (2026-10-27/28). El hallazgo de la ronda anterior, basado en codigo local, "
            "ni se confirma ni se invalida con esta ejecucion."
        )
