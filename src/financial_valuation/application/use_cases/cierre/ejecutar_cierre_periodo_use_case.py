# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-87 v1.1: cierre del período contable con comprobante NIC 41 |
# | 2026-11-05 | Arekkazu | M06 RF-87: el bloqueo por cuentas faltantes nombra hecho, sentido y especie sin códigos |
# | 2026-11-08 | Arekkazu | RFC-024 RF-88 v2.0: el cierre avisa al Contador de los activos al costo que ya tienen precio |
# | 2026-11-08 | destroyerban | INC-M06-308-G12 RF-83: alerta al Contador de mediciones estimadas o pendientes |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-281-G68-07 RF-88: alerta persistente al llevar el valor en libros a cero |
# | 2026-11-10 | Arekkazu | INC-M06-345/350 RF-87: EN_CIERRE en espera de autorización, cancelación, matriz y titular |
"""Caso de uso RF-87: cierre del período contable de un titular (NIC 41 ¶12: todo activo se mide al
valor razonable menos costos de venta a la fecha de cierre).

Tres transacciones: (1) el período pasa a EN_CIERRE y queda visible para todos (los hechos nuevos se
encolan para el período siguiente); (2) los 9 pasos, atómicos — escriben con el período EN_CIERRE
declarando ``app.cierre_periodo``; (3) si (2) falla, el período vuelve a ABIERTO y el cierre queda
FALLIDO en RF-94. Si hay exclusiones por autorizar (FA-2/FA-3), el período se queda EN_CIERRE
esperando la decisión: la autorización continúa el mismo cierre y la cancelación lo devuelve a ABIERTO. El paso 3 mide contra el último valor registrado del activo, no contra el valor al
inicio del período (C-3), y el paso 7 no vuelve a registrar los costos de M05 como gasto (C-4)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.application.services.medidor import Medidor
from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados, ConstructorInformeRevelaciones
from src.financial_valuation.application.use_cases.trazabilidad.verificar_trazabilidad_use_case import VerificadorTrazabilidad
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento, Periodo
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.costo_repository import CostoRepository
from src.financial_valuation.domain.repositories.cotizacion_repository import CotizacionRepository
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02Port
from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.domain.repositories.periodo_repository import PeriodoRepository
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.services.consolidacion import LineaContable, consolidar_comprobantes
from src.financial_valuation.application.use_cases.valoracion_costo.registrar_deterioro_use_case import (
    evento_valor_libros_cero,
)
from src.financial_valuation.domain.entities.activo_financiero import DatosActivo
from src.financial_valuation.domain.services.nic41 import (
    hash_sha256,
    meses_transcurridos,
    periodo_siguiente,
    truncar2,
    valor_libros_calculado,
    valor_por_costo,
)
from src.financial_valuation.domain.value_objects.nic41 import (
    ETIQUETA_HECHO,
    ETIQUETA_SENTIDO,
    EstadoPeriodo,
    Sentido,
    Severidad,
    TipoEvidencia,
    TipoHecho,
)
from src.shared.errors import AppError, BusinessRuleError, ConflictError, InfrastructureError, NotFoundError
from src.shared.fechas import en_zona_usuario, hoy_usuario

logger = logging.getLogger(__name__)
_CIERRE_ABANDONADO = timedelta(minutes=30)
_VARIACIONES = [(t.value, s.value) for t in (TipoHecho.VARIACION_VR_TB, TipoHecho.VARIACION_VR_PM)
                for s in (Sentido.GANANCIA, Sentido.PERDIDA)]


@dataclass
class Prevalidacion:
    bloqueos: list[dict]
    activos_sin_precio: list[dict]
    lineas_sin_trazabilidad: list[dict]

    @property
    def puede_cerrar(self) -> bool:
        return not self.bloqueos

    def a_dict(self) -> dict:
        return {"bloqueos": self.bloqueos, "activos_sin_precio": self.activos_sin_precio,
                "lineas_sin_trazabilidad": self.lineas_sin_trazabilidad, "puede_cerrar": self.puede_cerrar,
                "requiere_autorizacion": bool(self.activos_sin_precio or self.lineas_sin_trazabilidad)}


class EjecutarCierrePeriodoUseCase:
    def __init__(self, db: Session, periodos: PeriodoRepository, activos: ActivoFinancieroPort,
                 valoraciones: ValoracionRepository, costos: CostoRepository, cotizaciones: CotizacionRepository,
                 eventos: EventoM02Port, medidor: Medidor, contabilizador: Contabilizador,
                 verificador: VerificadorTrazabilidad, estado_resultados: ConstructorEstadoResultados,
                 revelaciones: ConstructorInformeRevelaciones, notificador: NotificacionFinancieraPort,
                 procesador_eventos) -> None:
        self.db = db
        self.procesador_eventos = procesador_eventos  # ProcesarEventosM02UseCase
        self.periodos = periodos
        self.activos = activos
        self.valoraciones = valoraciones
        self.costos = costos
        self.cotizaciones = cotizaciones
        self.eventos = eventos
        self.medidor = medidor
        self.contabilizador = contabilizador
        self.verificador = verificador
        self.estado_resultados = estado_resultados
        self.revelaciones = revelaciones
        self.notificador = notificador

    # --- Prevalidación (RF-87 precondiciones y v1.1) ---------------------------------------------

    def prevalidar(self, periodo: Periodo) -> Prevalidacion:
        bloqueos: list[dict] = []
        anterior = self.periodos.abierto_anterior(periodo)
        if anterior is not None:
            bloqueos.append({"codigo": "PERIODO_ANTERIOR_ABIERTO",
                             "mensaje": f"Cierre antes el período {anterior.fecha_inicio:%Y-%m} del mismo titular."})
        pendientes_cuenta = self.contabilizador.asientos.pendientes_de_cuenta(periodo.id_periodo_contable)
        if pendientes_cuenta:
            especies = {e: (self.activos.especie(e) or {}).get("nombre", "especie inactiva")
                        for e in {ln.id_especie for ln in pendientes_cuenta if ln.id_especie}}
            combinaciones = sorted({
                f"{ETIQUETA_HECHO.get(ln.tipo_hecho_corregido or ln.tipo_hecho, 'Hecho contable')} "
                f"({ETIQUETA_SENTIDO.get(ln.sentido, ln.sentido.lower())}) de {especies.get(ln.id_especie, 'todas las especies')}"
                for ln in pendientes_cuenta})
            bloqueos.append({"codigo": "LINEAS_PENDIENTE_CUENTA", "mensaje": (
                f"{len(pendientes_cuenta)} líneas no tienen cuentas en la matriz contable: {'; '.join(combinaciones[:10])}. "
                "Asígnelas en Configuración contable.")})
        sin_clasificar = self.costos.pendientes_clasificacion(periodo.id_periodo_contable)
        if sin_clasificar:
            bloqueos.append({"codigo": "COSTOS_PENDIENTE_CLASIFICACION",
                             "mensaje": f"{len(sin_clasificar)} costos están pendientes de clasificación."})
        if self.costos.recepciones_pendientes_titular(periodo.numero_id_tributaria, periodo.fecha_fin):
            bloqueos.append({"codigo": "ENTREGAS_M05_PENDIENTES",
                             "mensaje": "Hay costos de Suministros por incorporar. Espere a que se procesen e intente de nuevo."})
        fincas = self.activos.fincas_sin_titular_del_periodo(periodo.id_periodo_contable, periodo.numero_id_tributaria)
        if fincas:  # RF-19 v1.1: sin titular no hay a quién atribuir los hechos del período
            bloqueos.append({"codigo": "FINCA_SIN_TITULAR", "mensaje": (
                f"Las fincas {', '.join(fincas)} tienen movimientos en este período pero ya no tienen su titular "
                "tributario. Complételo en Configuración → Fincas.")})
        dia = min(periodo.fecha_fin, hoy_usuario())
        reconocidos = self.activos.listar_reconocidos(periodo.numero_id_tributaria)
        sin_precio, faltantes = [], self._combinaciones_sin_cuenta(reconocidos)
        if faltantes:
            bloqueos.append({"codigo": "MATRIZ_CONTABLE_INCOMPLETA", "mensaje": (
                f"La matriz contable no cubre lo que registra el cierre: {'; '.join(faltantes[:10])}. "
                "Asígnelas en Configuración contable.")})
        for activo in reconocidos:
            if self.valoraciones.valoracion_costo_activa(activo.id_activo_biologico) is not None:
                continue
            precio, _ = self.medidor.valorador.precio_para(activo, dia, False)
            if precio is None:
                sin_precio.append({"id_activo_biologico": activo.id_activo_biologico, "identificador": activo.identificador,
                                   "especie": activo.especie})
        sin_trazabilidad = self.verificador.evaluar(self.contabilizador.asientos.del_periodo(periodo.id_periodo_contable))
        return Prevalidacion(bloqueos, sin_precio, sin_trazabilidad)

    def _combinaciones_sin_cuenta(self, reconocidos: list[DatosActivo]) -> list[str]:
        """RF-87 v1.1: la matriz debe cubrir los hechos que el cierre registra (variaciones de los activos a
        valor razonable y depreciación de los activos al costo), no solo los ya pendientes de cuenta."""
        requeridas: dict[tuple, DatosActivo] = {}
        for activo in reconocidos:
            if self.valoraciones.valoracion_costo_activa(activo.id_activo_biologico) is not None:
                combos = [(TipoHecho.DEPRECIACION_ACTIVO_COSTO.value, Sentido.UNICO.value)]
            else:
                combos = _VARIACIONES
            for tipo, sentido in combos:
                requeridas.setdefault((tipo, sentido, activo.id_especie), activo)
        return sorted(
            f"{ETIQUETA_HECHO.get(tipo, 'Hecho contable')} ({ETIQUETA_SENTIDO.get(sentido, sentido.lower())}) de {activo.especie}"
            for (tipo, sentido, especie), activo in requeridas.items()
            if self.contabilizador.config.resolver_cuenta(tipo, sentido, especie, None) is None)

    # --- Ejecución -------------------------------------------------------------------------------

    def execute(self, id_periodo_contable: int, id_usuario: int, *, autorizar_exclusiones: bool = False,
                incluir_activos_sin_precio: bool = False) -> dict:
        # Los eventos de M02 pendientes se miden antes (RF-83: el cierre va después de los eventos).
        self.eventos_pendientes_primero()
        id_cierre = self._iniciar(id_periodo_contable, id_usuario, autorizar_exclusiones, incluir_activos_sin_precio)
        self._paso = 1
        try:
            self.db.execute(text("SELECT set_config('app.cierre_periodo', :p, true)"), {"p": str(id_periodo_contable)})
            periodo = self.periodos.obtener(id_periodo_contable)
            resultado = self._pasos(periodo, id_cierre, id_usuario, autorizar_exclusiones, incluir_activos_sin_precio)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            self.medidor.tomar_alertas()  # lo revertido no se avisa
            if isinstance(exc, ConflictError) and exc.code == "EXCLUSION_REQUIERE_AUTORIZACION":  # FA-3 en el paso 3
                self._esperar(id_cierre, id_periodo_contable)
                raise
            paso = self._paso
            self._fallar(id_periodo_contable, id_cierre, paso, exc, id_usuario)
            if isinstance(exc, AppError):
                raise
            raise InfrastructureError(code="CIERRE_PERIODO_FALLIDO", message=(
                f"El proceso de cierre falló en el paso {paso}. Se revirtieron todos los cambios y el período permanece "
                "ABIERTO. Corrija el problema y reinicie el cierre.")) from exc
        self.notificador.a_contadores("CIERRE_PERIODO_CONTABLE", (
            f"Período {resultado['periodo']} cerrado: listo para transferir desde Agrofusión."),
            {"id_periodo_contable": id_periodo_contable, "id_cierre": id_cierre})
        if resultado["activos_al_costo_con_precio"]:  # RF-88 v2.0: ¶30 exige pasarlos a valor razonable
            self.notificador.a_contadores("ALERTA_FINANCIERA_NIC41", (
                f"Al cerrar el período {resultado['periodo']}, estos activos valorados por costo ya tienen precio de mercado "
                f"para su especie: {', '.join(resultado['activos_al_costo_con_precio'])}. La NIC 41 ¶30 exige pasarlos a "
                "valor razonable."), {"id_periodo_contable": id_periodo_contable, "id_cierre": id_cierre})
        for alerta in self.medidor.tomar_alertas():  # RF-83: mediciones estimadas o pendientes del cierre
            self.notificador.a_contadores("ALERTA_FINANCIERA_NIC41", alerta.mensaje, alerta.detalle, alerta.id_finca)
        return resultado

    def eventos_pendientes_primero(self) -> None:
        self.procesador_eventos.execute(2000)

    def _iniciar(self, id_periodo, id_usuario, autorizar, incluir_sin_precio) -> int:
        try:
            periodo = self.periodos.obtener(id_periodo, bloquear=True)
            if periodo is None:
                raise NotFoundError(code="PERIODO_NO_ENCONTRADO", message="El período contable no existe.")
            if periodo.estado == EstadoPeriodo.CERRADO.value:  # FA-5
                quien = (self.periodos.ultima_ejecucion(id_periodo) or {}).get("nombre_usuario_ejecutor")
                raise ConflictError(code="PERIODO_CERRADO", message=(
                    f"El período {periodo.fecha_inicio:%Y-%m} ya fue cerrado el {periodo.fecha_cierre:%Y-%m-%d}"
                    f"{f' por {quien}' if quien else ''}. Los períodos cerrados no se reabren: corrija con ajustes "
                    "en el período abierto."))
            en_espera = None
            if periodo.estado == EstadoPeriodo.EN_CIERRE.value:
                en_curso = self.periodos.ejecucion_en_proceso(id_periodo)
                vigente = en_curso and datetime.now(timezone.utc) - en_curso["fecha_inicio"] < _CIERRE_ABANDONADO
                if vigente and en_curso["esperando_autorizacion"] and (autorizar or incluir_sin_precio):
                    en_espera = en_curso  # el Contador decide sobre el cierre que espera (FA-2/FA-3)
                elif vigente:
                    raise ConflictError(code="CIERRE_EN_EJECUCION", message=self._mensaje_concurrencia(en_curso))
                elif en_curso:  # cierre abandonado (caída del servidor): se reinicia sin efectos (RNF Mantenibilidad)
                    self.periodos.finalizar_cierre(en_curso["id_cierre"], "FALLIDO", {"paso": 1, "error": "Cierre abandonado"})
            prevalidacion = self.prevalidar(periodo)
            if not prevalidacion.puede_cerrar:
                raise BusinessRuleError(code="CIERRE_BLOQUEADO",
                                        message=" ".join(b["mensaje"] for b in prevalidacion.bloqueos))
            pendiente = None
            if prevalidacion.lineas_sin_trazabilidad and not autorizar:  # FA-3
                pendiente = (f"{len(prevalidacion.lineas_sin_trazabilidad)} asientos tienen la cadena de trazabilidad "
                             "incompleta y no pueden entrar al cierre. Autorice su exclusión para continuar.")
            elif prevalidacion.activos_sin_precio and not (autorizar or incluir_sin_precio):  # FA-2
                pendiente = (f"{len(prevalidacion.activos_sin_precio)} activos no tienen precio de mercado vigente. "
                             "Autorice su exclusión o inclúyalos con el último precio conocido como estimación.")
            if en_espera is not None:
                id_cierre = en_espera["id_cierre"]
                if pendiente is None:
                    self.periodos.reanudar_cierre(id_cierre, incluir_sin_precio)
            else:
                id_cierre = self.periodos.iniciar_cierre(id_periodo, id_usuario, incluir_sin_precio)
                self.periodos.cambiar_estado(id_periodo, EstadoPeriodo.EN_CIERRE.value)
                self.contabilizador.auditar(EventoAuditoria(
                    tipo_evento="CIERRE_PERIODO_INICIADO", severidad=Severidad.INFO.value, id_usuario=id_usuario,
                    payload={"autorizar_exclusiones": autorizar, "incluir_activos_sin_precio": incluir_sin_precio,
                             "advertencias": prevalidacion.a_dict()},
                    id_periodo_contable=id_periodo, id_referencia=id_cierre,
                ))
                if pendiente is not None:
                    self.periodos.esperar_autorizacion(id_cierre)
            self.db.commit()
            if pendiente is not None:
                raise ConflictError(code="EXCLUSION_REQUIERE_AUTORIZACION", message=(
                    f"{pendiente} El período queda en cierre hasta que autorice o cancele el cierre."))
            return id_cierre
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _mensaje_concurrencia(en_curso: dict) -> str:
        quien = en_curso.get("nombre_usuario_ejecutor") or "otro usuario"
        cuando = f"{en_zona_usuario(en_curso['fecha_inicio']):%Y-%m-%d %H:%M}"
        if en_curso["esperando_autorizacion"]:
            return (f"El período tiene un cierre iniciado el {cuando} por {quien} que espera la autorización de las "
                    "exclusiones. Autorícelas para continuar ese cierre o cancélelo.")
        return (f"El período está siendo procesado por otro cierre iniciado el {cuando} por {quien}. Espere a que "
                "termine antes de intentar un nuevo cierre.")

    def _esperar(self, id_cierre: int, id_periodo: int) -> None:
        """La transacción de los pasos se revirtió, pero el período sigue EN_CIERRE (paso 1): queda esperando."""
        try:
            self.periodos.esperar_autorizacion(id_cierre)
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("RF-87 FA-3: no se pudo dejar el cierre del período %s en espera.", id_periodo)

    def cancelar(self, id_periodo_contable: int, id_usuario: int) -> dict:
        """FA-2/FA-3: el Contador no autoriza las exclusiones; el período vuelve a ABIERTO sin cambios."""
        try:
            periodo = self.periodos.obtener(id_periodo_contable, bloquear=True)
            if periodo is None:
                raise NotFoundError(code="PERIODO_NO_ENCONTRADO", message="El período contable no existe.")
            en_curso = self.periodos.ejecucion_en_proceso(id_periodo_contable)
            if periodo.estado != EstadoPeriodo.EN_CIERRE.value or not en_curso or not en_curso["esperando_autorizacion"]:
                raise ConflictError(code="CIERRE_NO_CANCELABLE", message=(
                    "Solo se puede cancelar un cierre que espera la autorización de exclusiones."))
            self.periodos.cambiar_estado(id_periodo_contable, EstadoPeriodo.ABIERTO.value)
            self.periodos.finalizar_cierre(en_curso["id_cierre"], "ROLLBACK",
                                           {"paso": 3, "error": "El Contador canceló el cierre sin autorizar las exclusiones."})
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="CIERRE_PERIODO_FALLIDO", severidad=Severidad.WARNING.value, id_usuario=id_usuario,
                payload={"cancelado": True, "motivo": "El Contador no autorizó las exclusiones."},
                id_periodo_contable=id_periodo_contable, id_referencia=en_curso["id_cierre"],
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_periodo_contable": id_periodo_contable, "id_cierre": en_curso["id_cierre"],
                "estado": EstadoPeriodo.ABIERTO.value}

    def _pasos(self, periodo: Periodo, id_cierre: int, id_usuario: int, autorizar: bool, incluir_sin_precio: bool):
        dia = min(periodo.fecha_fin, hoy_usuario())
        activos = self.activos.listar_reconocidos(periodo.numero_id_tributaria)
        # Paso 2: precios congelados al inicio del cierre (por especie).
        self._paso = 2
        congelados, excluidos = {}, []
        for activo in activos:
            if activo.id_especie not in congelados:
                precio, _ = self.medidor.valorador.precio_para(activo, dia, incluir_sin_precio)
                congelados[activo.id_especie] = precio
        # Pasos 3-5: revaluación masiva, variaciones y líneas (más depreciación de los activos al costo).
        self._paso = 3
        procesados, al_costo_con_precio = 0, []
        for activo in activos:
            costo = self.valoraciones.valoracion_costo_activa(activo.id_activo_biologico)
            if costo is not None:
                self._depreciar(activo, costo, periodo, dia, id_cierre, id_usuario, congelados[activo.id_especie])
                if congelados[activo.id_especie] is not None:
                    al_costo_con_precio.append(activo.identificador)
                procesados += 1
                continue
            precio = congelados[activo.id_especie]
            if precio is None:
                excluidos.append({"id_activo_biologico": activo.id_activo_biologico, "identificador": activo.identificador,
                                  "motivo": "PENDIENTE_PRECIO"})
                continue
            anterior = self.valoraciones.ultimo_calculo(activo.id_activo_biologico)
            magnitud, _ = activo.magnitud(precio.categoria)
            hubo_cambio_fisico = anterior is not None and magnitud is not None and magnitud != anterior.magnitud
            resultado = self.medidor.medir(
                activo, periodo, dia, origen="CIERRE_PERIODO", id_usuario=id_usuario, id_usuario_auditoria=id_usuario,
                id_cierre=id_cierre, hubo_evento=hubo_cambio_fisico, permitir_estimado=incluir_sin_precio,
                precio_congelado=precio, tipo_evidencia_tb=TipoEvidencia.CIERRE_PERIODO.value,
                tipo_evidencia_pm=TipoEvidencia.CIERRE_PERIODO.value)
            if resultado.estado == "PENDIENTE":
                excluidos.append({"id_activo_biologico": activo.id_activo_biologico, "identificador": activo.identificador,
                                  "motivo": resultado.motivo, "detalle": resultado.mensaje})
                continue
            procesados += 1
        # Paso 3 (RF-91): trazabilidad; lo incompleto se excluye con autorización y pasa al período siguiente.
        lineas = self.contabilizador.asientos.del_periodo(periodo.id_periodo_contable)
        verificacion = self.verificador.verificar(lineas, id_usuario)
        pendientes = verificacion["PENDIENTE_TRAZABILIDAD"]
        siguiente = self._abrir_siguiente(periodo, id_usuario)
        if pendientes:
            if not autorizar:
                raise ConflictError(code="EXCLUSION_REQUIERE_AUTORIZACION", message=(
                    f"{len(pendientes)} asientos quedaron con la trazabilidad incompleta. El período queda en cierre "
                    "hasta que autorice su exclusión o cancele el cierre."))
            self.contabilizador.asientos.mover_a_periodo([p["id_linea"] for p in pendientes], siguiente.id_periodo_contable)
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="EXCLUSION_CIERRE_AUTORIZADA", severidad=Severidad.WARNING.value, id_usuario=id_usuario,
                payload={"lineas": pendientes, "activos_sin_precio": excluidos,
                         "id_periodo_destino": siguiente.id_periodo_contable},
                id_periodo_contable=periodo.id_periodo_contable, id_referencia=id_cierre,
            ))
        sin_cuenta = self.contabilizador.asientos.pendientes_de_cuenta(periodo.id_periodo_contable)
        if sin_cuenta:  # RF-87 v1.1: la matriz debe cubrir todos los hechos del período, también los del cierre
            raise BusinessRuleError(code="CIERRE_BLOQUEADO", message=(
                f"La revaluación generó {len(sin_cuenta)} líneas sin cuentas en la matriz contable "
                f"({'; '.join(sorted({f'{ETIQUETA_HECHO.get(ln.tipo_hecho, ln.tipo_hecho)} ({ETIQUETA_SENTIDO.get(ln.sentido, ln.sentido)})' for ln in sin_cuenta}))}). "
                "Complétela en Configuración contable y reintente."))
        # Paso 6: comprobante NIC 41 por (titular, tipo de hecho, especie).
        self._paso = 6
        incluidas = [ln for ln in self.contabilizador.asientos.del_periodo(periodo.id_periodo_contable)
                     if ln.estado == "REGISTRADA"]
        comprobantes = consolidar_comprobantes(
            [LineaContable(ln.id_linea_asiento_nic41, ln.tipo_hecho, ln.sentido, ln.numero_id_tributaria, ln.id_especie,
                           ln.cuenta_debito, ln.cuenta_credito, ln.valor) for ln in incluidas], periodo.fecha_fin)
        codigos = []
        for comprobante in comprobantes:
            id_comprobante = self.periodos.guardar_comprobante(comprobante, periodo.id_periodo_contable, id_cierre)
            self.contabilizador.asientos.asignar_comprobante(comprobante.ids_lineas, id_comprobante)
            codigos.append({"codigo": comprobante.codigo, "hash": comprobante.hash_integridad,
                            "valor_total": str(comprobante.valor_total)})
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="COMPROBANTE_GENERADO", severidad=Severidad.INFO.value, id_usuario=id_usuario,
                payload={"codigo": comprobante.codigo, "lineas": len(comprobante.ids_lineas)},
                id_periodo_contable=periodo.id_periodo_contable, id_referencia=id_comprobante,
                monto_afectado=comprobante.valor_total,
            ))
        # Paso 7: los costos de mantenimiento ya están en RF-90/RF-86; solo se consolidan en RF-93 (C-4).
        self._paso = 7
        self.cotizaciones.fijar_estado_al_cierre(periodo.id_periodo_contable)
        # Paso 9 (antes del 8: RF-92/93 exigen el período cerrado; su fallo no revierte el cierre).
        self._paso = 9
        self.periodos.cambiar_estado(periodo.id_periodo_contable, EstadoPeriodo.CERRADO.value)
        hash_cierre = hash_sha256({"periodo": periodo.id_periodo_contable, "comprobantes": codigos, "excluidos": excluidos})
        reportes = self._reportes(periodo, id_usuario, excluidos)
        self.periodos.finalizar_cierre(id_cierre, "COMPLETADO", {
            "paso": 9, "procesados": procesados, "pendientes": len(excluidos), "excluidos": excluidos + pendientes,
            "precios": [{"id_especie": k, "id_precio_mercado": p.id_precio_mercado, "precio_unitario": str(p.precio_unitario),
                         "fuente": p.fuente, "fecha_vigencia": str(p.fecha_vigencia)} for k, p in congelados.items() if p],
            "hash": hash_cierre})
        self.contabilizador.auditar(EventoAuditoria(
            tipo_evento="CIERRE_PERIODO_COMPLETADO", severidad=Severidad.INFO.value, id_usuario=id_usuario,
            payload={"comprobantes": codigos, "activos_procesados": procesados, "excluidos": excluidos,
                     "hash_cierre": hash_cierre, "reportes": reportes},
            id_periodo_contable=periodo.id_periodo_contable, id_referencia=id_cierre,
        ))
        return ({"id_cierre": id_cierre, "id_periodo_contable": periodo.id_periodo_contable,
                 "periodo": f"{periodo.fecha_inicio:%Y-%m}", "estado": EstadoPeriodo.CERRADO.value,
                 "activos_procesados": procesados, "activos_excluidos": excluidos, "lineas_excluidas": pendientes,
                 "comprobantes": codigos, "hash_cierre": hash_cierre, "reportes": reportes,
                 "id_periodo_siguiente": siguiente.id_periodo_contable, "activos_al_costo_con_precio": al_costo_con_precio})

    def _depreciar(self, activo, costo, periodo, dia, id_cierre, id_usuario, precio_vigente) -> None:
        """RF-88 4.1: depreciación del período como gasto; ¶30 exige pasar a valor razonable si ya hay precio."""
        valor = valor_por_costo(costo.costos_adquisicion, costo.vida_util_meses or 1,
                                meses_transcurridos(costo.fecha_adquisicion, dia), costo.deterioro_acumulado)
        delta = truncar2(valor.depreciacion_acumulada - costo.depreciacion_acumulada)
        if delta > 0:
            calculado = valor_libros_calculado(costo.costos_adquisicion, valor.depreciacion_acumulada,
                                               costo.deterioro_acumulado)
            if calculado < 0 and costo.valor_contable_por_costo > 0:  # RF-88: el ajuste a cero ocurre en este cierre
                self.contabilizador.auditar(evento_valor_libros_cero(
                    costo, calculado, "DEPRECIACION", activo.id_activo_biologico, periodo.id_periodo_contable,
                    id_cierre, id_usuario))
            costo.depreciacion_acumulada = valor.depreciacion_acumulada
            costo.valor_contable_por_costo = valor.valor_contable
            self.valoraciones.actualizar_valoracion_costo(costo)
            self.contabilizador.asentar(LineaAsiento(
                tipo_hecho=TipoHecho.DEPRECIACION_ACTIVO_COSTO.value, sentido=Sentido.UNICO.value, valor=delta,
                fecha_hecho=dia, id_periodo_contable=periodo.id_periodo_contable,
                id_activo_biologico=activo.id_activo_biologico, id_especie=activo.id_especie, id_finca=activo.id_finca,
                numero_id_tributaria=activo.numero_id_tributaria, tabla_origen="valoraciones_por_costos",
                id_origen=costo.id_valoracion_por_costo, tipo_evidencia=TipoEvidencia.CIERRE_PERIODO.value,
                id_usuario=id_usuario,
            ), id_usuario)
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="DEPRECIACION_REGISTRADA", severidad=Severidad.INFO.value, id_usuario=id_usuario,
                payload={"depreciacion_periodo": str(delta), "depreciacion_acumulada": str(valor.depreciacion_acumulada),
                         "valor_contable": str(valor.valor_contable), "totalmente_depreciado": valor.totalmente_depreciado},
                id_activo_biologico=activo.id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
                id_referencia=id_cierre, monto_afectado=delta,
            ))
        if precio_vigente is not None:
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="MEDICION_PENDIENTE", severidad=Severidad.WARNING.value, id_usuario=id_usuario,
                payload={"mensaje": (f"El activo {activo.identificador} está valorado por costo y ya hay precio de mercado "
                                     "para su especie: la NIC 41 ¶30 exige pasarlo a valor razonable.")},
                id_activo_biologico=activo.id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
            ))

    def _abrir_siguiente(self, periodo: Periodo, id_usuario: int) -> Periodo:
        inicio, fin = periodo_siguiente(periodo.fecha_fin, self.contabilizador.config.obtener().tipo_cierre)
        existente = self.periodos.que_contiene(periodo.numero_id_tributaria, inicio)
        return existente or self.periodos.crear(periodo.numero_id_tributaria, self.contabilizador.config.obtener().tipo_cierre,
                                                inicio, fin, id_usuario)

    def _reportes(self, periodo: Periodo, id_usuario: int, excluidos: list) -> dict:
        """Paso 8: si RF-92 o RF-93 fallan, el cierre se completa y quedan PENDIENTE_GENERACION (CA-11)."""
        estado = {"estado_resultados": "PENDIENTE_GENERACION", "informe_revelaciones": "PENDIENTE_GENERACION"}
        try:
            with self.db.begin_nested():
                er = self.estado_resultados.guardar(periodo.id_periodo_contable, {}, id_usuario, excluidos)
            estado["estado_resultados"] = {"id_estado": er["id_estado"], "resultado_neto": str(er["resultado_neto"])}
        except Exception:
            logger.exception("RF-87 paso 8: no se pudo generar el estado de resultados del período %s.", periodo.id_periodo_contable)
        try:
            with self.db.begin_nested():
                informe = self.revelaciones.guardar(periodo.id_periodo_contable, {}, id_usuario)
            estado["informe_revelaciones"] = {"id_informe": informe["id_informe"], "version": informe["version_informe"]}
        except Exception:
            logger.exception("RF-87 paso 8: no se pudo generar el informe de revelaciones del período %s.", periodo.id_periodo_contable)
        return estado

    def _fallar(self, id_periodo, id_cierre, paso, exc, id_usuario) -> None:
        try:
            self.periodos.cambiar_estado(id_periodo, EstadoPeriodo.ABIERTO.value)
            self.periodos.finalizar_cierre(id_cierre, "FALLIDO", {"paso": paso, "error": str(exc)[:1000]})
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="CIERRE_PERIODO_FALLIDO", severidad=Severidad.CRITICAL.value, id_usuario=id_usuario,
                payload={"paso": paso, "error": str(exc)[:2000]}, id_periodo_contable=id_periodo, id_referencia=id_cierre,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("RF-87 FA-1: no se pudo reabrir el período %s tras el fallo del cierre.", id_periodo)
