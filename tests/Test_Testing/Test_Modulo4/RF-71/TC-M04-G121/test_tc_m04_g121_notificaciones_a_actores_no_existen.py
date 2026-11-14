"""
TC-M04-G121 (RF-71 v2.0 CA-6/Fase 7/Salida 6/RFC-009, CU-17) -
"Notificaciones a los actores." La v2.0 añade (f): notificación por
vencimiento de calibración y por auditorías de RF-24 incompletas.

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE. HALLAZGO PRINCIPAL
INVERTIDO: la ronda anterior buscó únicamente la palabra literal
"notificacion" -- el mecanismo real no usa esa palabra, usa "aviso". El
merge del 2026-10-29 (DEV-48, autoría destroyerban/Arekkazu, nunca
revisado hasta ahora para RF-71) trajo un sistema de avisos por correo
REAL y CONECTADO: `AvisoVersionModeloPort`
(`src/prediction/domain/repositories/aviso_version_modelo_port.py`) con
dos métodos -- `avisar_carga_externa()` (RF-69 E1b, al Administrador) y
`avisar_version_rechazada()` (RF-69 E3, al Veterinario) -- implementados
por `AvisoVersionModeloEmailAdapter`
(`src/prediction/infrastructure/adapters/aviso_version_modelo_email_adapter.py`,
reusa el canal de correo de RF-14). `RegistrarVersionModeloUseCase`
recibe este puerto por constructor (`aviso_port`) y SÍ lo invoca: al
rechazar una versión (`self._aviso_port.avisar_version_rechazada(entidad)`)
y al detectar una carga externa sin clave interna válida
(`self._avisar_carga_externa(id_proceso)` → `avisar_carga_externa(...)`).

Código bajo prueba:
    src/prediction/domain/repositories/aviso_version_modelo_port.py
    src/prediction/infrastructure/adapters/aviso_version_modelo_email_adapter.py
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py

(a)-(e) -- HALLAZGO INVERTIDO PARA AL MENOS 2 DE LOS ESCENARIOS: de los
    "7 subescenarios" que la ronda anterior invalidaba en bloque, al
    menos el de "versión RECHAZADA avisa al Veterinario" (E3) y el de
    "carga externa avisa al Administrador" (E1b) SÍ tienen una
    notificación real por correo. No se verificó aquí, en detalle,
    cuántos de los (a)-(e) específicos de la ficha mapean 1:1 contra
    estos 2 avisos reales -- queda como trabajo pendiente de una ronda
    que compare la ficha completa contra estos 2 escenarios.
(f) RFC-009, notificación por vencimiento de calibración / auditorías de
    RF-24 incompletas -- HALLAZGO VIGENTE, SIN CAMBIOS: el RF-24 real
    sigue sin tener ningún concepto de "vencimiento" ni "auditoría"
    (`src/configuration/domain/entities/calibracion.py` no tocado por
    este pull) -- este subescenario específico de la ficha sigue sin ser
    evaluable, aunque el sistema de avisos en general ya no esté vacío.
(g) Deduplicación -- MATIZADO: `AvisoVersionModeloPort` es explícitamente
    "best-effort" (nunca propaga fallos de entrega) pero NO tiene
    deduplicación propia visible en el adapter -- distinto del aviso de
    carga externa (E1b), que SÍ reusa una ventana anti-spam de 5 min
    (`_VENTANA_AVISO_CARGA_EXTERNA`, igual criterio que RF-14).

Cómo se prueba: inspección directa de `AvisoVersionModeloPort`,
`AvisoVersionModeloEmailAdapter` y de las llamadas reales a
`self._aviso_port.avisar_*()` dentro de `registrar_version_modelo_use_case.py`.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g121_notificaciones_a_actores_no_existen.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G121.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestHallazgoInvertidoSiExisteUnSistemaDeAvisosRealYConectado:
    def test_aviso_version_modelo_port_existe_con_dos_metodos_reales(self):
        import inspect

        from src.prediction.domain.repositories.aviso_version_modelo_port import AvisoVersionModeloPort
        metodos = {n for n, _ in inspect.getmembers(AvisoVersionModeloPort, predicate=inspect.isfunction)}
        pytest.fail(
            f"HALLAZGO INVERTIDO: AvisoVersionModeloPort SI existe, con metodos reales "
            f"{sorted(metodos)!r} -- la busqueda literal de 'notificacion' de la ronda anterior "
            f"no encontro esto porque el mecanismo real se llama 'aviso', no 'notificacion'."
        ) if {'avisar_carga_externa', 'avisar_version_rechazada'} <= metodos else None

    def test_registrar_version_si_invoca_avisar_version_rechazada(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO (E3): registrar_version_modelo_use_case.py SI llama a "
            "self._aviso_port.avisar_version_rechazada(entidad) cuando una version queda "
            "RECHAZADO -- notifica al Veterinario, contradiciendo 'RegistrarVersionModeloUseCase "
            "nunca notifica a nadie'."
        ) if 'self._aviso_port.avisar_version_rechazada(' in texto else None

    def test_registrar_version_si_invoca_avisar_carga_externa(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO (E1b): registrar_version_modelo_use_case.py SI invoca "
            "_avisar_carga_externa()/avisar_carga_externa() ante un intento de carga externa -- "
            "notifica al Administrador."
        ) if 'avisar_carga_externa(' in texto else None

    def test_el_adapter_de_correo_real_implementa_el_puerto_y_reusa_el_canal_de_rf14(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/adapters/aviso_version_modelo_email_adapter.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO INVERTIDO: AvisoVersionModeloEmailAdapter SI implementa el puerto con "
            "envio real por correo (send_email), best-effort (nunca propaga fallos) -- no es un "
            "stub ni un placeholder."
        ) if 'send_email' in texto and 'AvisoVersionModeloPort' in texto else None


class TestSubCasoFVencimientoDeCalibracionNoExisteComoConcepto:
    def test_calibracion_real_no_tiene_concepto_de_vencimiento_ni_auditoria(self):
        archivo = REPO_ROOT / 'src/configuration/domain/entities/calibracion.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (f): el RF-24 real (Calibracion) no tiene ningun campo de vencimiento ni "
            "de auditoria -- es un registro puntual de ganancia/offset de sensor, sin fecha de "
            "expiracion ni estado de auditoria que pudiera disparar una notificacion."
        ) if 'vencimiento' not in texto.lower() and 'auditoria' not in texto.lower() else None
