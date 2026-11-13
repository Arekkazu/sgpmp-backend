# | Fecha       | Nombre | Que se hizo |
# |-------------|--------|-------------|
# | 2026-11-10  | —      | TC-M06-G109: el modo QA no avisa fuera de la lista autorizada |
"""Protección de destinatarios del aviso de vencimiento. Sin base de datos ni usuarios reales."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.use_cases.precios import alertar_vencimiento_precios_use_case as alertas
from src.financial_valuation.domain.services.precios import Precio
from src.financial_valuation.infrastructure.adapters.notificacion_financiera_m01_adapter import (
    NotificacionFinancieraM01Adapter,
)
from src.financial_valuation.infrastructure.configuracion_alertas import resolver_envio_alertas
from src.financial_valuation.infrastructure.reclamo_aviso import BitacoraAvisos

HOY = date(2026, 11, 8)
AUTORIZADO = 901
OTRO_AUTORIZADO = 902
NO_AUTORIZADO = 903


class Notificador:
    def __init__(self) -> None:
        self.enviados: list[dict] = []
        self.generales: list[dict] = []
        self.autorizados: list[tuple[tuple[int, ...], dict]] = []

    def ya_notificado(self, tipo_evento, detalle) -> bool:
        return any(detalle.items() <= enviado.items() for enviado in self.enviados)

    def a_contadores(self, tipo_evento, mensaje, detalle, id_finca=None) -> None:
        self.generales.append(dict(detalle))
        self.enviados.append(dict(detalle))

    def a_usuarios_autorizados(self, id_usuarios, tipo_evento, mensaje, detalle) -> None:
        self.autorizados.append((tuple(id_usuarios), dict(detalle)))
        self.enviados.append(dict(detalle))


def _precio(id_precio: int, vence: date) -> Precio:
    return Precio(id_precio, 99001, "PESO_KG", D("8000"), "kg", "MERCADO_ACTIVO", date(2026, 1, 1), vence)


def _caso(precios, notificador=None):
    notificador = notificador or Notificador()
    repo = SimpleNamespace(
        por_vencer=lambda desde, hasta: [p for p in precios if desde <= p.fecha_vencimiento <= hasta],
        de_especie=lambda *args: list(precios),
    )
    config = SimpleNamespace(
        obtener=lambda: SimpleNamespace(dias_alerta_vencimiento_precio=30),
        listar_parametros_especie=lambda: [{"id_especie": 99001, "especie": "Especie ficticia"}],
    )
    return alertas.AlertarVencimientoPreciosUseCase(repo, config, notificador), notificador


def _apagado(monkeypatch) -> None:
    monkeypatch.delenv("M06_ALERTAS_QA_HABILITADAS", raising=False)
    monkeypatch.delenv("M06_ALERTAS_QA_DESTINATARIOS", raising=False)
    monkeypatch.delenv("M06_ALERTAS_QA_PRECIOS_PERMITIDOS", raising=False)


def _qa(monkeypatch, destinatarios: str | None, precios: str | None = "1") -> None:
    monkeypatch.setenv("SGPMP_ENTORNO", "TEST")
    monkeypatch.setenv("M06_ALERTAS_QA_HABILITADAS", "true")
    if destinatarios is None:
        monkeypatch.delenv("M06_ALERTAS_QA_DESTINATARIOS", raising=False)
    else:
        monkeypatch.setenv("M06_ALERTAS_QA_DESTINATARIOS", destinatarios)
    if precios is None:
        monkeypatch.delenv("M06_ALERTAS_QA_PRECIOS_PERMITIDOS", raising=False)
    else:
        monkeypatch.setenv("M06_ALERTAS_QA_PRECIOS_PERMITIDOS", precios)


def test_modo_qa_desactivado_no_usa_la_via_qa(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "PROD")
    _apagado(monkeypatch)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=30))])
    assert caso.execute() == 1
    assert notificador.autorizados == []
    assert notificador.generales == [{"id_precio_mercado": 1, "aviso": "30_DIAS"}]


@pytest.mark.parametrize("destinatarios", ["", "   ", None])
def test_lista_vacia_no_envia_ni_consulta_contadores(monkeypatch, destinatarios):
    _qa(monkeypatch, destinatarios)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY)])
    assert caso.execute() == 0
    assert notificador.autorizados == []
    assert notificador.generales == []


@pytest.mark.parametrize("destinatarios", ["abc", "0", "-1", "1.5", "901,0", "901,,902", "901,901", "true"])
def test_lista_invalida_no_produce_envio_general(monkeypatch, destinatarios, caplog):
    _qa(monkeypatch, destinatarios)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY - timedelta(days=1))])
    with caplog.at_level(logging.ERROR):
        assert caso.execute() == 0
    assert notificador.autorizados == []
    assert notificador.generales == []
    assert caplog.text.strip().endswith("Alertas de vencimiento M06 detenidas.")
    for parte in destinatarios.replace(",", " ").split():
        if parte.isdecimal() and int(parte) > 0:
            assert parte not in caplog.text


def test_interruptor_no_reconocido_no_habilita_el_envio_general(monkeypatch):
    monkeypatch.setenv("M06_ALERTAS_QA_HABILITADAS", "yes")
    monkeypatch.setenv("M06_ALERTAS_QA_DESTINATARIOS", str(AUTORIZADO))
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=7))])
    assert caso.execute() == 0
    assert notificador.autorizados == []
    assert notificador.generales == []


def test_error_al_leer_la_configuracion_no_envia(monkeypatch, caplog):
    def estallar():
        raise RuntimeError("destinatario-no-autorizado-903")

    monkeypatch.setattr(alertas, "resolver_envio_alertas", estallar)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY)])
    with caplog.at_level(logging.ERROR):
        assert caso.execute() == 0
    assert notificador.autorizados == []
    assert notificador.generales == []
    assert "903" not in caplog.text


def test_un_destinatario_autorizado_es_el_unico(monkeypatch):
    _qa(monkeypatch, str(AUTORIZADO))
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=15))])
    assert caso.execute() == 1
    assert notificador.generales == []
    assert notificador.autorizados == [((AUTORIZADO,), {"id_precio_mercado": 1, "aviso": "15_DIAS"})]


def test_varios_destinatarios_autorizados_no_incluyen_a_otro_contador(monkeypatch):
    _qa(monkeypatch, f"{AUTORIZADO}, {OTRO_AUTORIZADO}")
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=7))])
    caso.execute()
    assert notificador.generales == []
    assert notificador.autorizados == [((AUTORIZADO, OTRO_AUTORIZADO), {"id_precio_mercado": 1, "aviso": "7_DIAS"})]
    assert NO_AUTORIZADO not in notificador.autorizados[0][0]


def test_precio_vencido_no_sale_de_la_lista_qa(monkeypatch):
    _qa(monkeypatch, str(AUTORIZADO))
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY - timedelta(days=2))])
    caso.execute()
    assert notificador.generales == []
    assert [aviso for _, aviso in notificador.autorizados] == [{"id_precio_mercado": 1, "aviso": "VENCIDO"}]
    assert notificador.autorizados[0][0] == (AUTORIZADO,)


def test_segunda_ejecucion_y_otro_caso_de_uso_no_repiten_la_marca(monkeypatch):
    _qa(monkeypatch, str(AUTORIZADO))
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    precios = [_precio(1, HOY)]
    caso, notificador = _caso(precios)
    assert caso.execute() == 1
    assert caso.execute() == 0
    reinicio, _ = _caso(precios, notificador)
    assert reinicio.execute() == 0
    assert notificador.generales == []
    assert [aviso["aviso"] for _, aviso in notificador.autorizados] == ["0_DIAS"]


def test_adaptador_no_abre_sesion_si_la_lista_no_es_valida():
    def prohibido():
        raise AssertionError("no debe abrir una sesión")

    adaptador = NotificacionFinancieraM01Adapter(prohibido)
    for lista in ([], (), [0], [-1], [True], ["901"], None):
        adaptador.a_usuarios_autorizados(lista, "ALERTA_FINANCIERA_NIC41", "aviso", {"aviso": "0_DIAS"})


def test_adaptador_no_consulta_el_rol_contador(caplog):
    class Sesion:
        def __init__(self):
            self.textos: list[str] = []
            self.confirmada = False

        def execute(self, sentencia, params=None):
            texto = str(sentencia)
            self.textos.append(texto)
            if "Contador" in texto or "nombre_rol" in texto:
                raise AssertionError("consultó el rol Contador")

            class Resultado:
                def __iter__(self):
                    return iter([SimpleNamespace(id_usuario=NO_AUTORIZADO)])

                def scalar(self):
                    return 40

            return Resultado()

        def commit(self):
            self.confirmada = True

        def rollback(self):
            pass

        def close(self):
            pass

    sesion = Sesion()
    adaptador = NotificacionFinancieraM01Adapter(lambda: sesion)
    with caplog.at_level(logging.ERROR):
        adaptador.a_usuarios_autorizados((AUTORIZADO,), "ALERTA_FINANCIERA_NIC41", "aviso",
                                         {"id_precio_mercado": 1, "aviso": "VENCIDO"})
    assert sesion.textos
    assert sesion.confirmada is False
    assert all("Contador" not in texto and "nombre_rol" not in texto for texto in sesion.textos)
    assert str(AUTORIZADO) not in caplog.text
    assert str(NO_AUTORIZADO) not in caplog.text


def test_el_proceso_periodico_no_llama_al_notificador_directamente():
    fuente = open("main.py", encoding="utf-8").read()
    assert "a_contadores" not in fuente
    assert "a_usuarios_autorizados" not in fuente
    assert "AlertarVencimientoPreciosUseCase" in fuente


def test_entorno_ausente_no_autoriza_la_via_general(monkeypatch):
    monkeypatch.delenv("SGPMP_ENTORNO", raising=False)
    _apagado(monkeypatch)
    decision = resolver_envio_alertas()
    assert decision.modo == "bloqueado"
    assert decision.permite_envio is False


def _repo_que_no_debe_recorrer():
    def prohibido(*args, **kwargs):
        raise AssertionError("no debe recorrer precios")

    return SimpleNamespace(por_vencer=prohibido, de_especie=prohibido)


def test_qa_sin_lista_de_precios_no_procesa_ninguno(monkeypatch):
    _qa(monkeypatch, str(AUTORIZADO), precios=None)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([])
    caso.precios = _repo_que_no_debe_recorrer()
    assert caso.execute() == 0
    assert notificador.autorizados == []
    assert notificador.generales == []


@pytest.mark.parametrize("precios", ["", "abc", "0", "-4", "1,1", "1.5"])
def test_qa_con_lista_de_precios_invalida_no_envia(monkeypatch, precios):
    _qa(monkeypatch, str(AUTORIZADO), precios)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY)])
    caso.precios = _repo_que_no_debe_recorrer()
    assert caso.execute() == 0
    assert notificador.generales == []


def test_solo_el_precio_autorizado_genera_aviso(monkeypatch):
    _qa(monkeypatch, str(AUTORIZADO), "11")
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    consultas = []
    caso, notificador = _caso([_precio(11, HOY + timedelta(days=15)), _precio(12, HOY + timedelta(days=15))])
    original = caso.precios.de_especie

    def espiar(*args):
        consultas.append(args)
        return original(*args)

    caso.precios.de_especie = espiar
    caso.execute()
    assert notificador.generales == []
    assert [aviso["id_precio_mercado"] for _, aviso in notificador.autorizados] == [11]
    assert consultas == []


def test_precio_vencido_no_autorizado_no_genera_marca(monkeypatch):
    _qa(monkeypatch, str(AUTORIZADO), "11")
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    consultas = []
    caso, notificador = _caso([_precio(12, HOY - timedelta(days=3))])

    def espiar(*args):
        consultas.append(args)
        return []

    caso.precios.de_especie = espiar
    assert caso.execute() == 0
    assert notificador.autorizados == []
    assert notificador.generales == []
    assert consultas == []


def test_test_con_qa_desactivado_no_envia(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "TEST")
    _apagado(monkeypatch)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY)])
    caso.precios = _repo_que_no_debe_recorrer()
    assert caso.execute() == 0
    assert notificador.generales == []
    assert notificador.autorizados == []


def test_test_con_qa_y_listas_validas_solo_avisa_lo_autorizado(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "TEST")
    _qa(monkeypatch, f"{AUTORIZADO},{OTRO_AUTORIZADO}", "11")
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(11, HOY + timedelta(days=7)), _precio(12, HOY - timedelta(days=1))])
    caso.execute()
    assert notificador.generales == []
    assert notificador.autorizados == [((AUTORIZADO, OTRO_AUTORIZADO), {"id_precio_mercado": 11, "aviso": "7_DIAS"})]


def test_produccion_conserva_el_barrido_aunque_exista_una_lista_de_precios(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "PROD")
    _apagado(monkeypatch)
    monkeypatch.setenv("M06_ALERTAS_QA_PRECIOS_PERMITIDOS", "11")
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(11, HOY + timedelta(days=30)), _precio(12, HOY + timedelta(days=15))])
    assert caso.execute() == 2
    assert notificador.autorizados == []
    assert [aviso["id_precio_mercado"] for aviso in notificador.generales] == [11, 12]


def test_error_de_categoria_no_confirma_ni_registra_identificadores(caplog):
    class Sesion:
        def __init__(self):
            self.textos: list[str] = []
            self.confirmada = False

        def execute(self, sentencia, params=None):
            texto = str(sentencia)
            self.textos.append(texto)
            if "Contador" in texto or "nombre_rol" in texto or "pg_advisory" in texto:
                raise AssertionError(texto)

            class Resultado:
                def __iter__(self):
                    return iter([SimpleNamespace(id_usuario=AUTORIZADO)])

                def scalar(self):
                    return 99

            return Resultado()

        def commit(self):
            self.confirmada = True

        def rollback(self):
            pass

        def close(self):
            pass

    sesion = Sesion()
    adaptador = NotificacionFinancieraM01Adapter(lambda: sesion)
    with caplog.at_level(logging.ERROR):
        entregado = adaptador.a_usuarios_autorizados(
            (AUTORIZADO,), "ALERTA_FINANCIERA_NIC41", "aviso",
            {"id_precio_mercado": 11, "aviso": "VENCIDO"},
        )
    assert entregado is False
    assert sesion.confirmada is False
    assert "el código lo asocia" in caplog.text
    assert "ALERTA_FINANCIERA_NIC41" in caplog.text
    assert str(AUTORIZADO) not in caplog.text
    assert "11" not in caplog.text


def test_el_candado_se_consulta_antes_de_confirmar_un_aviso_repetido():
    class Sesion:
        def __init__(self):
            self.textos: list[str] = []
            self.confirmada = False

        def execute(self, sentencia, params=None):
            texto = str(sentencia)
            self.textos.append(texto)

            class Resultado:
                def __iter__(self):
                    return iter([SimpleNamespace(id_usuario=AUTORIZADO)])

                def scalar(self):
                    if "EXISTS" in texto:
                        return True
                    return 40

            return Resultado()

        def commit(self):
            self.confirmada = True

        def rollback(self):
            pass

        def close(self):
            pass

    sesion = Sesion()
    adaptador = NotificacionFinancieraM01Adapter(lambda: sesion)
    entregado = adaptador.a_usuarios_autorizados(
        (AUTORIZADO,), "ALERTA_FINANCIERA_NIC41", "aviso",
        {"id_precio_mercado": 11, "aviso": "15_DIAS"},
    )
    assert entregado is False
    assert sesion.confirmada is False
    candado = next(i for i, texto in enumerate(sesion.textos) if "pg_advisory_xact_lock" in texto)
    existe = next(i for i, texto in enumerate(sesion.textos) if "EXISTS" in texto)
    assert candado < existe
    assert all("Contador" not in texto for texto in sesion.textos)


def test_dos_reclamos_concurrentes_dejan_una_sola_marca():
    bitacora = BitacoraAvisos()
    marca = (11, "15_DIAS")
    assert bitacora.reservar(marca) is True
    assert bitacora.reservar(marca) is False
    bitacora.confirmar(marca)
    assert bitacora.reservar(marca) is False
    assert bitacora.confirmadas == {marca}


def test_un_fallo_antes_de_confirmar_permite_el_reintento():
    bitacora = BitacoraAvisos()
    marca = (11, "VENCIDO")
    assert bitacora.reservar(marca) is True
    bitacora.revertir(marca)
    assert bitacora.reservar(marca) is True
    bitacora.confirmar(marca)
    assert bitacora.reservar(marca) is False


def test_el_caso_de_uso_reintenta_si_la_persistencia_no_confirma(monkeypatch):
    _qa(monkeypatch, str(AUTORIZADO), "1")
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)

    class FallaLuegoEnvia(Notificador):
        def __init__(self):
            super().__init__()
            self.intentos = 0

        def a_usuarios_autorizados(self, id_usuarios, tipo_evento, mensaje, detalle):
            self.intentos += 1
            if self.intentos == 1:
                return False
            return super().a_usuarios_autorizados(id_usuarios, tipo_evento, mensaje, detalle)

    notificador = FallaLuegoEnvia()
    caso, _ = _caso([_precio(1, HOY)], notificador)
    assert caso.execute() == 0
    assert caso.execute() == 1
    assert [aviso["aviso"] for _, aviso in notificador.autorizados] == ["0_DIAS"]
    assert notificador.generales == []


def _bloquear_recorrido(caso):
    caso.precios = _repo_que_no_debe_recorrer()
    return caso


def _listas_qa(monkeypatch, destinatarios="901", precios="1"):
    monkeypatch.setenv("M06_ALERTAS_QA_HABILITADAS", "true")
    monkeypatch.setenv("M06_ALERTAS_QA_DESTINATARIOS", destinatarios)
    monkeypatch.setenv("M06_ALERTAS_QA_PRECIOS_PERMITIDOS", precios)


def test_prod_explicito_conserva_la_via_general(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "PROD")
    _apagado(monkeypatch)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=30))])
    assert caso.execute() == 1
    assert notificador.autorizados == []
    assert notificador.generales == [{"id_precio_mercado": 1, "aviso": "30_DIAS"}]


def test_test_con_qa_apagado_no_envia(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "TEST")
    _apagado(monkeypatch)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY)])
    _bloquear_recorrido(caso)
    assert caso.execute() == 0
    assert notificador.generales == []
    assert notificador.autorizados == []


def test_dev_no_usa_la_via_general(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "DEV")
    _apagado(monkeypatch)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=7))])
    _bloquear_recorrido(caso)
    assert caso.execute() == 0
    assert notificador.generales == []


def test_dev_con_listas_validas_solo_avisa_por_la_via_qa(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "DEV")
    _listas_qa(monkeypatch)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=15)), _precio(2, HOY - timedelta(days=1))])
    caso.execute()
    assert notificador.generales == []
    assert [aviso["id_precio_mercado"] for _, aviso in notificador.autorizados] == [1]


@pytest.mark.parametrize("entorno", [None, "", "   ", "STAGING", "PR OD", "producción"])
def test_entorno_no_explicito_no_envia_aunque_el_qa_este_completo(monkeypatch, entorno):
    if entorno is None:
        monkeypatch.delenv("SGPMP_ENTORNO", raising=False)
    else:
        monkeypatch.setenv("SGPMP_ENTORNO", entorno)
    _listas_qa(monkeypatch)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY), _precio(2, HOY - timedelta(days=1))])
    _bloquear_recorrido(caso)
    assert caso.execute() == 0
    assert notificador.generales == []
    assert notificador.autorizados == []


@pytest.mark.parametrize("entorno", ["prod", " PROD ", "Prod"])
def test_prod_con_mayusculas_o_espacios_conserva_la_via_general(monkeypatch, entorno):
    monkeypatch.setenv("SGPMP_ENTORNO", entorno)
    _apagado(monkeypatch)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=7))])
    assert caso.execute() == 1
    assert notificador.generales == [{"id_precio_mercado": 1, "aviso": "7_DIAS"}]
    assert notificador.autorizados == []


def test_test_con_espacios_o_minusculas_no_abre_la_via_general(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "  test ")
    _apagado(monkeypatch)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY)])
    _bloquear_recorrido(caso)
    assert caso.execute() == 0
    assert notificador.generales == []


def test_error_al_leer_el_entorno_no_envia(monkeypatch):
    import src.financial_valuation.infrastructure.configuracion_alertas as configuracion

    def estalla(*args, **kwargs):
        raise RuntimeError("lectura-imposible")

    monkeypatch.setattr(configuracion.os, "getenv", estalla)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY)])
    _bloquear_recorrido(caso)
    assert caso.execute() == 0
    assert notificador.generales == []
    assert notificador.autorizados == []


def test_prod_con_qa_incompleto_no_cae_en_la_via_general(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "PROD")
    _listas_qa(monkeypatch, precios="")
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY), _precio(2, HOY - timedelta(days=2))])
    _bloquear_recorrido(caso)
    assert caso.execute() == 0
    assert notificador.generales == []
    assert notificador.autorizados == []


def test_test_con_qa_sin_destinatarios_no_cae_en_la_via_general(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "TEST")
    _listas_qa(monkeypatch, destinatarios="")
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY - timedelta(days=1))])
    _bloquear_recorrido(caso)
    assert caso.execute() == 0
    assert notificador.generales == []
    assert notificador.autorizados == []
