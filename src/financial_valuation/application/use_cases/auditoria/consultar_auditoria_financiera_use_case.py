# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-94 Fase 7: consulta técnica y legible de la auditoría financiera |
# | 2026-11-05 | Arekkazu | M06 RF-94: resumen por severidad, orden y activo por su identificador |
# | 2026-11-08 | destroyerban | INC-M06-306-G07 RF-82: descripción del intento de acceso sin permiso |
# | 2026-11-08 | destroyerban | INC-M06-313-G14 RF-83: excluye y registra los activos no elegibles |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-281-G68-07 RF-88: alerta persistente al llevar el valor en libros a cero |
"""Caso de uso RF-94 Fase 7: consulta paginada (máx. 500), en orden cronológico, con al menos un
filtro obligatorio. ``formato=LEGIBLE`` traduce el tipo de evento a lenguaje natural (CA-13)."""
from __future__ import annotations

from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.shared.errors import ValidationError

DESCRIPCIONES = {
    "RECONOCIMIENTO_INICIAL": "Registro inicial del activo en el sistema financiero",
    "RECONOCIMIENTO_REVERTIDO": "Reversión del reconocimiento inicial",
    "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR": "Reconocimiento bloqueado: sin precio ni costo",
    "REVERSION_BLOQUEADA": "Reversión bloqueada por registros dependientes",
    "CALCULO_VALOR_RAZONABLE": "Cálculo del valor razonable menos costos de venta",
    "AJUSTE_MANUAL_COSTOS_VENTA": "Ajuste manual de los costos de venta",
    "MEDICION_POSTERIOR": "Medición posterior del valor razonable",
    "MEDICION_CON_ESTIMACION": "Medición con precio estimado",
    "MEDICION_SIN_VARIACION": "Medición sin variación de valor",
    "MEDICION_PENDIENTE": "Medición pendiente de revisión",
    "MEDICION_EXCLUIDA": "Evento sin medición: activo no elegible",
    "VARIACION_REGISTRADA": "Variación de valor razonable registrada",
    "LINEA_ASIENTO_PENDIENTE_CUENTA": "Línea de asiento sin cuenta contable configurada",
    "LINEA_ASIENTO_REGISTRADA": "Línea de asiento registrada",
    "PRODUCTO_AGRICOLA_RECONOCIDO": "Producto agrícola reconocido",
    "RECONOCIMIENTO_PRODUCTO_PENDIENTE": "Reconocimiento de producto pendiente",
    "BAJA_ACTIVO_REGISTRADA": "Baja del activo registrada",
    "COSTO_REGISTRADO": "Costo registrado", "COSTO_CLASIFICADO": "Costo clasificado",
    "PRECIO_REGISTRADO": "Precio de mercado registrado", "PRECIO_MARCADO_REEMPLAZADO": "Precio de mercado reemplazado",
    "PRECIO_REFERENCIA_VENCIDO": "Precio de referencia vencido",
    "PARAMETRO_COSTOS_VENTA_ACTUALIZADO": "Costos de venta actualizados",
    "MATRIZ_CONTABLE_ACTUALIZADA": "Matriz contable actualizada",
    "CONFIGURACION_CONTABLE_ACTUALIZADA": "Configuración contable actualizada",
    "ACTIVO_MARCADO_SIN_MERCADO": "Activo sin precio de mercado: método de costo",
    "METODO_VALORACION_CAMBIADO": "Cambio de método de valoración",
    "DEPRECIACION_REGISTRADA": "Depreciación del período registrada", "DETERIORO_REGISTRADO": "Deterioro registrado",
    "VALOR_LIBROS_AJUSTADO_A_CERO": "Valor en libros negativo ajustado a cero",
    "COTIZACION_REGISTRADA": "Cotización registrada", "COTIZACION_MODIFICADA": "Cotización modificada",
    "COTIZACION_ANULADA": "Cotización anulada", "COTIZACION_VENCIDA": "Cotización vencida",
    "CIERRE_PERIODO_INICIADO": "Cierre del período contable iniciado",
    "CIERRE_PERIODO_COMPLETADO": "Cierre del período contable completado",
    "CIERRE_PERIODO_FALLIDO": "Cierre del período contable fallido",
    "EXCLUSION_CIERRE_AUTORIZADA": "Exclusión autorizada en el cierre", "COMPROBANTE_GENERADO": "Comprobante NIC 41 generado",
    "CADENA_TRAZABILIDAD_VERIFICADA": "Cadena de trazabilidad verificada",
    "INFORME_REVELACIONES_GENERADO": "Informe de revelaciones generado",
    "INFORME_REVELACIONES_APROBADO": "Informe de revelaciones aprobado",
    "INFORME_REVELACIONES_RECHAZADO": "Informe de revelaciones rechazado",
    "ERROR_CONSISTENCIA": "Inconsistencia entre fuentes", "ESTADO_RESULTADOS_GENERADO": "Estado de resultados generado",
    "ESTADO_RESULTADOS_APROBADO": "Estado de resultados aprobado", "ERROR_CONCILIACION": "Error de conciliación",
    "ERROR_TECNICO": "Error técnico",
    "ACCESO_NO_AUTORIZADO": "Intento de operación sin permiso del rol",
}


class ConsultarAuditoriaFinancieraUseCase:
    def __init__(self, auditoria: AuditoriaFinancieraRepository) -> None:
        self.auditoria = auditoria

    def execute(self, filtros: dict, pagina: int, tamano: int, legible: bool, descendente: bool = False) -> dict:
        if not any(filtros.get(k) for k in ("tipo_evento", "id_periodo_contable", "id_activo_biologico")):
            raise ValidationError(code="FILTRO_OBLIGATORIO", message=(
                "Indique al menos un filtro: tipo de evento, período contable o activo."))
        desconocidos = [t for t in filtros.get("tipo_evento") or [] if t not in DESCRIPCIONES]
        if desconocidos:
            raise ValidationError(code="TIPO_EVENTO_INVALIDO", field="tipo_evento",
                                  message="El tipo de evento elegido no existe en la auditoría financiera.")
        tamano = min(max(tamano, 1), 500)
        total, eventos = self.auditoria.consultar(filtros, max(pagina, 1), tamano, descendente)
        resumen = self.auditoria.conteo_por_severidad(filtros)
        if legible:
            eventos = [{
                "id_evento": e["id_evento"], "descripcion_evento": DESCRIPCIONES.get(e["tipo_evento"], e["tipo_evento"]),
                "tipo_evento": e["tipo_evento"], "fecha_hora": e["timestamp_evento"],
                "actor": e["nombre_usuario"] or ("Sistema automático" if e["tipo_actor"] == "SISTEMA" else "Usuario sin nombre registrado"),
                "activo": e["identificador_activo"],
                "id_periodo_contable": e["id_periodo_contable"], "resumen_payload": e["payload_evento"],
                "monto_afectado": e["monto_afectado"], "severidad": e["severidad_evento"],
                "integridad_verificable": bool(e["hash_integridad"]), "hash_integridad": e["hash_integridad"],
                "informacion_adicional_truncada": e["payload_truncado"],
                "origen": "Repositorio central" if e["origen_registro"] == "REPOSITORIO" else "Sincronizado desde respaldo",
            } for e in eventos]
        return {"total_registros": total, "pagina_actual": max(pagina, 1), "registros_por_pagina": tamano,
                "resumen_severidad": resumen, "eventos": eventos}
