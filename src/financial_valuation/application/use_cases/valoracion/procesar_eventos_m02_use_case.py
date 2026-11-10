# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-83/85/86: medición por evento, productos agrícolas y bajas desde M02 |
# | 2026-11-09 | destroyerban | INC-M06-320-G24 RF-85 FA-4: la cosecha del 100 % deja el activo en cero e inicia su baja |
"""Caso de uso de fondo: procesa los eventos biológicos de M02 de los activos ya reconocidos.

- Crecimiento (pesaje): medición posterior con efecto transformación y efecto precio (RF-83).
- Ingreso a un POBLACIONAL por nacimiento: las crías se reconocen (¶27). Por compra, donación o
  traslado, sin costo en el evento, solo se actualiza la base de valoración y se alerta al Contador.
- Producción (RF-43): reconocimiento del producto agrícola (RF-85, ¶13 y ¶28). Si la cosecha consume el 100 %
  del activo (FA-4), su valor queda en cero y, después del commit, se registra su baja en M02 (RF-45).
- Baja (RF-45): ``BAJA_ACTIVO`` por el valor en libros (RFC-018); no se registra el ingreso de la venta.
- Reproductivos, sanitarios y otros no cambian el valor razonable.
Un activo valorado por costo (¶30) no genera variaciones de valor razonable (RF-88 CA-4).

Cada evento va en su propia transacción: un fallo no detiene los demás (se reintenta hasta 3 veces)."""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import ID_SISTEMA, Contabilizador, PeriodoEnCierreError
from src.financial_valuation.application.services.medidor import Medidor
from src.financial_valuation.domain.entities.activo_financiero import DatosActivo
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento, Periodo
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.baja_activo_port import BajaActivoPort
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02, EventoM02Port
from src.financial_valuation.domain.repositories.precio_repository import PrecioRepository
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.services.nic41 import CERO, costos_venta, q4, truncar2, valor_neto
from src.financial_valuation.domain.services.precios import precio_vigente
from src.financial_valuation.domain.value_objects.nic41 import (
    CategoriaPrecio,
    Clasificacion,
    Sentido,
    Severidad,
    TipoEvidencia,
    TipoHecho,
)
from src.shared.errors import AppError
from src.shared.fechas import fecha_usuario

logger = logging.getLogger(__name__)

_BAJAS_DE_VENTA = ("venta", "sacrificio")
_UNIDADES_KG = ("kg", "kgs", "kilogramo", "kilogramos")


class ProcesarEventosM02UseCase:
    def __init__(self, db: Session, eventos: EventoM02Port, activos: ActivoFinancieroPort,
                 valoraciones: ValoracionRepository, precios: PrecioRepository, medidor: Medidor,
                 contabilizador: Contabilizador, id_usuario_servicio: int,
                 bajas: Optional[BajaActivoPort] = None) -> None:
        self.db = db
        self.eventos = eventos
        self.activos = activos
        self.valoraciones = valoraciones
        self.precios = precios
        self.medidor = medidor
        self.contabilizador = contabilizador
        self.id_servicio = id_usuario_servicio
        self.bajas = bajas
        self._bajas_pendientes: list[tuple] = []  # (activo, periodo, id_evento, dia): se ejecutan tras el commit

    def execute(self, limite: int = 200) -> dict:
        conteo: dict[str, int] = {}
        for evento in self.eventos.pendientes(limite):
            self._bajas_pendientes = []
            try:
                resultado, detalle = self._procesar(evento)
                self.eventos.registrar_procesamiento(evento.id_evento, resultado, detalle)
                self.db.commit()
                self._iniciar_bajas()
            except Exception as exc:  # un evento fallido no detiene la cola
                self.db.rollback()
                logger.exception("M06: no se pudo procesar el evento %s de M02.", evento.id_evento)
                resultado = "ERROR"
                try:
                    self.eventos.registrar_procesamiento(evento.id_evento, "ERROR", str(exc)[:500])
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            conteo[resultado] = conteo.get(resultado, 0) + 1
        return conteo

    def _procesar(self, evento: EventoM02) -> tuple[str, Optional[str]]:
        if evento.tipo not in ("CRECIMIENTO", "INGRESO", "BAJA", "PRODUCTIVO"):
            return "SIN_EFECTO", None
        activo = self.activos.obtener(evento.id_activo_biologico)
        if activo is None:
            return "SIN_EFECTO", "Activo no encontrado"
        dia = fecha_usuario(evento.fecha)
        try:
            periodo = self.contabilizador.periodo_para(activo.numero_id_tributaria, dia, self.id_servicio)
        except PeriodoEnCierreError as exc:
            return "ENCOLADO_CIERRE", exc.message
        except AppError as exc:
            return "MEDICION_PENDIENTE", exc.message
        if evento.tipo == "BAJA":
            return self._baja(evento, activo, periodo, dia)
        if self.valoraciones.valoracion_costo_activa(activo.id_activo_biologico) is not None:
            return "SIN_EFECTO", "Activo valorado por costo (NIC 41 ¶30)"
        if evento.tipo == "PRODUCTIVO":
            return self._producto(evento, activo, periodo, dia)
        if evento.tipo == "INGRESO" and (evento.datos.get("tipo_ingreso") or "") != "nacimiento":
            return self._nueva_base(evento, activo, periodo, dia)
        evidencia = TipoEvidencia.IOT_DIRECTO.value if activo.id_dispositivo_iot else TipoEvidencia.REGISTRO_MANUAL.value
        tipo_hecho = (TipoHecho.RECONOCIMIENTO_NACIMIENTO.value if evento.tipo == "INGRESO"
                      else TipoHecho.VARIACION_VR_TB.value)
        medicion = self.medidor.medir(activo, periodo, dia, origen="EVENTO", id_usuario=self.id_servicio,
                                      id_usuario_auditoria=None, id_evento=evento.id_evento,
                                      tipo_evidencia_tb=evidencia, tipo_hecho_tb=tipo_hecho)
        return {"MEDIDO": "PROCESADO", "SIN_VARIACION": "SIN_EFECTO"}.get(medicion.estado, "MEDICION_PENDIENTE"), medicion.mensaje

    # --- Ingreso sin costo en el evento ---------------------------------------------------------

    def _nueva_base(self, evento, activo, periodo, dia) -> tuple[str, Optional[str]]:
        resultado = self.medidor.valorador.valorar(activo, dia, periodo.id_periodo_contable, self.id_servicio,
                                                   permitir_estimado=True)
        if not resultado.es_valido:
            return "MEDICION_PENDIENTE", resultado.mensaje
        self.valoraciones.agregar_calculo(resultado.calculo)
        mensaje = (f"Ingreso de {evento.datos.get('cantidad_ingresada')} individuos por "
                   f"{evento.datos.get('tipo_ingreso')} al activo {activo.identificador}: se actualizó la base de "
                   "valoración. Registre su costo en Costos (factura de compra) si corresponde.")
        self._auditar("MEDICION_PENDIENTE", Severidad.WARNING, activo, periodo, evento.id_evento, {"mensaje": mensaje})
        return "PROCESADO", mensaje

    # --- Baja (RF-45 → RF-83 FA-3, RFC-018) ------------------------------------------------------

    def _baja(self, evento: EventoM02, activo: DatosActivo, periodo: Periodo, dia: date) -> tuple[str, Optional[str]]:
        cantidad = Decimal(evento.datos.get("cantidad_afectada") or 0)
        antes = (activo.cantidad_actual or 0) + int(cantidad)  # M02 ya descontó la baja de cantidad_actual
        proporcion = Decimal(1) if not activo.es_poblacional or antes <= 0 else min(Decimal(1), cantidad / antes)
        costo = self.valoraciones.valoracion_costo_activa(activo.id_activo_biologico)
        base = None if costo else self.valoraciones.ultimo_calculo(activo.id_activo_biologico)
        valor_libros = costo.valor_contable_por_costo if costo else (base.valor_neto if base else None)
        if not valor_libros or proporcion <= 0:
            return "SIN_EFECTO", "Sin valor en libros para dar de baja"
        valor = truncar2(valor_libros * proporcion)
        tipo_baja = (evento.datos.get("tipo_baja") or "").lower()
        sentido = Sentido.UNICO.value if tipo_baja in _BAJAS_DE_VENTA else Sentido.PERDIDA.value
        if valor > 0:
            self.contabilizador.asentar(LineaAsiento(
                tipo_hecho=TipoHecho.BAJA_ACTIVO.value, sentido=sentido, valor=valor, fecha_hecho=dia,
                id_periodo_contable=periodo.id_periodo_contable, id_activo_biologico=activo.id_activo_biologico,
                id_especie=activo.id_especie, id_finca=activo.id_finca, numero_id_tributaria=activo.numero_id_tributaria,
                tabla_origen="procesamientos_eventos_m02", id_origen=evento.id_evento,
                tipo_evidencia=TipoEvidencia.REGISTRO_MANUAL.value, justificacion=f"Baja por {tipo_baja}",
            ), None)
        restante = Decimal(1) - proporcion
        if costo is not None:
            costo.costos_adquisicion = q4(costo.costos_adquisicion * restante) if restante > 0 else costo.costos_adquisicion
            costo.depreciacion_acumulada = q4(costo.depreciacion_acumulada * restante) if restante > 0 else costo.depreciacion_acumulada
            costo.deterioro_acumulado = q4(costo.deterioro_acumulado * restante) if restante > 0 else costo.deterioro_acumulado
            costo.valor_contable_por_costo = max(CERO, costo.costos_adquisicion - costo.depreciacion_acumulada - costo.deterioro_acumulado)
            costo.es_activa = restante > 0
            self.valoraciones.actualizar_valoracion_costo(costo)
        elif restante > 0:
            self.valoraciones.agregar_calculo(base.escalado(restante, periodo.id_periodo_contable))
        self._auditar("BAJA_ACTIVO_REGISTRADA", Severidad.INFO, activo, periodo, evento.id_evento,
                      {"tipo_baja": tipo_baja, "cantidad": str(cantidad), "proporcion": str(proporcion),
                       "valor_libros": str(valor_libros), "valor_baja": str(valor)}, monto=valor)
        return "PROCESADO", None

    # --- Producto agrícola (RF-85) -------------------------------------------------------------

    def _producto(self, evento: EventoM02, activo: DatosActivo, periodo: Periodo, dia: date) -> tuple[str, Optional[str]]:
        cantidad = Decimal(evento.datos.get("cantidad_producida") or 0)
        metrica = self.activos.metrica_produccion(evento.datos["id_metrica_produccion"]) \
            if evento.datos.get("id_metrica_produccion") else None
        if cantidad <= 0 or metrica is None:  # CA-10: datos mínimos del evento
            return self._producto_pendiente(activo, periodo, evento, "El evento productivo no trae producto o cantidad.")
        reconocimiento = self.valoraciones.reconocimiento_confirmado(activo.id_activo_biologico)
        if reconocimiento.clasificacion == Clasificacion.CONSUMO.value:
            return self._cosecha_consumo(evento, activo, periodo, dia, cantidad, metrica)
        precio = precio_vigente(self.precios.de_especie(activo.id_especie, CategoriaPrecio.PRODUCTO.value,
                                                        metrica["id_metrica_produccion"]), dia)
        parametro = self.medidor.valorador.config.costos_venta_vigentes(activo.id_especie)
        if precio is None or parametro is None:
            falta = "precio de mercado" if precio is None else "costos de venta"
            return self._producto_pendiente(activo, periodo, evento, f"Falta {falta} para el producto {metrica['nombre']}.")
        costos = costos_venta(cantidad * precio.precio_unitario, parametro.pct_transporte, parametro.pct_comisiones,
                              parametro.pct_impuestos)
        vn = valor_neto(cantidad, precio.precio_unitario, costos)
        if vn.requiere_revision:
            return self._producto_pendiente(activo, periodo, evento, "Los costos de venta igualan o superan el valor del producto.")
        id_calculo = self.valoraciones.agregar_calculo(CalculoValor(
            id_activo_biologico=activo.id_activo_biologico, id_precio_mercado=precio.id_precio_mercado,
            id_periodo_contable=periodo.id_periodo_contable, magnitud=cantidad, unidad_magnitud=metrica["unidad_medida"],
            precio_unitario=precio.precio_unitario, valor_razonable_bruto=vn.bruto, costo_transporte=costos.transporte,
            costo_comisiones=costos.comisiones, costo_impuestos_transaccion=costos.impuestos,
            otros_costos_disposicion=costos.otros, valor_neto=vn.neto, metodo_costo=costos.metodo_global,
            json_metodo_costo={**costos.metodos, "es_producto": True, "producto": metrica["nombre"]},
            id_usuario=self.id_servicio, id_parametro_costo_venta=parametro.id_parametro_costo_venta,
            tiene_valor_estimado=precio.fuente == "ESTIMADA",
        ))
        return self._registrar_producto(evento, activo, periodo, dia, metrica, cantidad, precio.precio_unitario,
                                        q4(costos.total / cantidad), truncar2(vn.neto), None, None, id_calculo, None,
                                        "PRODUCTO_PERIODICO", Sentido.UNICO.value)

    def _cosecha_consumo(self, evento, activo, periodo, dia, cantidad, metrica) -> tuple[str, Optional[str]]:
        """Cosecha que consume el activo (peces, biomasa): se remide y se traslada a inventario por el
        mismo valor, así el asiento cuadra (contradicción C-2 de RF-85 paso 7)."""
        if self.medidor.valorador.categoria(activo.id_especie) != CategoriaPrecio.PESO_KG.value \
                or (metrica["unidad_medida"] or "").strip().lower() not in _UNIDADES_KG:
            return self._producto_pendiente(activo, periodo, evento, (
                f"No hay regla de conversión entre {metrica['unidad_medida']} y la magnitud del activo (kg)."))
        medicion = self.medidor.medir(activo, periodo, dia, origen="EVENTO", id_usuario=self.id_servicio,
                                      id_usuario_auditoria=None, id_evento=evento.id_evento)
        if medicion.estado == "PENDIENTE":
            return "MEDICION_PENDIENTE", medicion.mensaje
        base = self.valoraciones.ultimo_calculo(activo.id_activo_biologico)
        proporcion = min(Decimal(1), cantidad / base.magnitud)
        valor_reduccion = truncar2(base.valor_neto * proporcion)
        precio_unitario = q4(base.valor_razonable_bruto * proporcion / cantidad)
        costo_unitario = q4((base.valor_razonable_bruto - base.valor_neto) * proporcion / cantidad)
        resultado = self._registrar_producto(evento, activo, periodo, dia, metrica, cantidad, precio_unitario,
                                             costo_unitario, valor_reduccion, q4(proporcion), valor_reduccion,
                                             base.id_calculo_valor_razonable, medicion.id_medicion,
                                             "PRODUCTO_DE_CONSUMO", Sentido.TRASLADO.value)
        if proporcion < 1:
            self.valoraciones.agregar_calculo(base.escalado(Decimal(1) - proporcion, periodo.id_periodo_contable))
        else:  # FA-4: el producto enlaza este cálculo con proporción 1, que deja de ser valor vigente (queda en 0)
            self._auditar("MEDICION_POSTERIOR", Severidad.INFO, activo, periodo, evento.id_evento, {
                "estado_activo": "COSECHADO_COMPLETAMENTE", "valor_anterior": str(base.valor_neto),
                "valor_actual": "0", "valor_reduccion": str(valor_reduccion),
                "id_calculo_consumido": base.id_calculo_valor_razonable,
                "mensaje": (f"El activo {activo.identificador} quedó cosechado completamente: su valor pasó a "
                            "inventario y queda en cero. Se inicia su baja en Activos biológicos.")}, monto=valor_reduccion)
            self._bajas_pendientes.append((activo, periodo, evento.id_evento, dia))
        return resultado

    def _iniciar_bajas(self) -> None:
        """RF-85 FA-4 / postcondición 6: baja en M02 (RF-45) de los activos cosechados por completo.

        Va después del commit de M06: si M02 la rechaza, el reconocimiento ya quedó y se alerta al Contador."""
        pendientes, self._bajas_pendientes = self._bajas_pendientes, []
        for activo, periodo, id_evento, dia in pendientes:
            motivo = f"Cosechado completamente: la cosecha del {dia:%Y-%m-%d} consumió todo el activo."
            rechazo = (self.bajas.dar_de_baja_por_cosecha(activo.id_activo_biologico, dia, motivo) if self.bajas
                       else "La baja automática no está disponible.")
            if rechazo is None:
                continue
            try:
                self._auditar("MEDICION_PENDIENTE", Severidad.WARNING, activo, periodo, id_evento, {
                    "mensaje": (f"El activo {activo.identificador} quedó cosechado completamente, pero no se pudo "
                                f"registrar su baja: {rechazo} Regístrela en Activos biológicos.")})
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("M06: no se pudo alertar la baja pendiente del activo %s.", activo.id_activo_biologico)

    def _registrar_producto(self, evento, activo, periodo, dia, metrica, cantidad, precio_unitario, costo_unitario,
                            valor, proporcion, valor_reduccion, id_calculo, id_medicion, tipo, sentido):
        id_producto = self.valoraciones.agregar_producto({
            "id_evento_productivo": evento.id_evento, "id_activo_biologico": activo.id_activo_biologico,
            "producto_agricola": metrica["nombre"], "cantidad_cosechada": cantidad, "unidad_medida": metrica["unidad_medida"],
            "precio_mercado_producto": precio_unitario, "costo_venta_producto": costo_unitario, "valor_producto": valor,
            "proporcion_cosechada": proporcion, "valor_reduccion_activo": valor_reduccion,
            "id_calculo_valor_razonable": id_calculo, "id_periodo_contable": periodo.id_periodo_contable,
            "justificacion": None, "fecha_cosecha": dia, "id_usuario": self.id_servicio, "tipo": tipo,
            "id_medicion_posterior": id_medicion,
        })
        if valor > 0:
            self.contabilizador.asentar(LineaAsiento(
                tipo_hecho=TipoHecho.PRODUCTO_AGRICOLA.value, sentido=sentido, valor=valor, fecha_hecho=dia,
                id_periodo_contable=periodo.id_periodo_contable, id_activo_biologico=activo.id_activo_biologico,
                id_especie=activo.id_especie, id_finca=activo.id_finca, numero_id_tributaria=activo.numero_id_tributaria,
                tabla_origen="reconocimientos_productos_agricolas", id_origen=id_producto,
                tipo_evidencia=TipoEvidencia.REGISTRO_MANUAL.value,
            ), None)
        self._auditar("PRODUCTO_AGRICOLA_RECONOCIDO", Severidad.INFO, activo, periodo, id_producto,
                      {"producto": metrica["nombre"], "cantidad": str(cantidad), "valor_producto": str(valor), "tipo": tipo},
                      monto=valor)
        return "PROCESADO", None

    def _producto_pendiente(self, activo, periodo, evento, mensaje) -> tuple[str, str]:
        """RF-85 FA-1/FA-2: el reconocimiento queda pendiente y se alerta al Contador."""
        self._auditar("RECONOCIMIENTO_PRODUCTO_PENDIENTE", Severidad.WARNING, activo, periodo, evento.id_evento,
                      {"mensaje": mensaje})
        return "MEDICION_PENDIENTE", mensaje

    def _auditar(self, tipo, severidad, activo, periodo, id_referencia, payload, monto=None) -> None:
        self.contabilizador.auditar(EventoAuditoria(
            tipo_evento=tipo, severidad=severidad.value, payload=payload, id_sistema=ID_SISTEMA,
            id_activo_biologico=activo.id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
            id_referencia=id_referencia, monto_afectado=monto,
        ))
