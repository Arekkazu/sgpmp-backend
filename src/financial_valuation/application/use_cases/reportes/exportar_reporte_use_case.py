# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-87/92/93: descarga del comprobante, del estado de resultados y del informe |
# | 2026-11-05 | Arekkazu | M06 RF-87: el comprobante descargado nombra el hecho contable, no su código |
# | 2026-11-10 | Arekkazu | INC-M06-344-G42 RF-93: el estado descargado desglosa el mantenimiento por tipo |
# | 2026-11-10 | Arekkazu | TC-DIS-246/259/264 RF-87/92/93: descargas con montos, fechas, signo y Ganancia/Pérdida en palabras |
# | 2026-11-12 | Arekkazu | Lote M05/M06 11-12 RF-93: cada activo excluido con su causa en palabras y el resultado que quedó fuera |
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G67 RF-92: los títulos de las secciones salen del constructor y el estado por sección no se imprime |
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G70 RF-92: el informe de revelaciones se descarga en PDF/A-1b |
"""Caso de uso: arma el documento descargable (CSV, Excel o PDF) de un reporte de M06.

- Comprobante NIC 41 (RF-87 v1.1): CSV y PDF, para registrarlo en SIGCON como comprobante manual.
- Estado de resultados (RF-93): solo APROBADO.
- Informe de revelaciones (RF-92): solo APROBADO o ARCHIVADO (CA-6); Excel o PDF.
Reutiliza el generador de archivos de M05 (mismo formato institucional)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from src.financial_valuation.application.services.reportes import SECCIONES_INFORME
from src.financial_valuation.domain.repositories.periodo_repository import PeriodoRepository
from src.financial_valuation.domain.repositories.reporte_repository import ReporteRepository
from src.financial_valuation.domain.value_objects.nic41 import ETIQUETA_HECHO, ETIQUETA_SUBTIPO
from src.shared.errors import BusinessRuleError, NotFoundError
from src.supplies.application.use_cases.exportacion.generador_archivos import (
    Documento,
    fecha,
    generar_csv,
    generar_excel,
    generar_pdf,
    moneda,
)

ETIQUETAS_COMPONENTES = {
    "ganancia_transformacion_biologica": "Ganancia por transformación biológica",
    "ganancia_precio_mercado": "Ganancia por variación de precio de mercado",
    "ganancia_reconocimiento_inicial": "Ganancia en el reconocimiento inicial",
    "ingresos_productos_agricolas": "Ingresos por productos agrícolas",
    "ganancia_ajustes_periodos_anteriores": "Ajustes de períodos anteriores (ganancia)",
    "perdida_transformacion_biologica": "Pérdida por transformación biológica",
    "perdida_precio_mercado": "Pérdida por variación de precio de mercado",
    "perdida_reconocimiento_inicial": "Pérdida en el reconocimiento inicial",
    "costos_mantenimiento": "Costos de mantenimiento",
    "inversiones_llevadas_a_gasto": "Inversiones llevadas a gasto",
    "bajas_activos": "Bajas de activos (valor en libros)",
    "depreciacion_activos_costo": "Depreciación de activos al costo",
    "deterioro_activos_costo": "Deterioro de activos al costo",
    "perdida_ajustes_periodos_anteriores": "Ajustes de períodos anteriores (pérdida)",
}
_GASTOS = {"perdida_transformacion_biologica", "perdida_precio_mercado", "perdida_reconocimiento_inicial", "costos_mantenimiento",
           "inversiones_llevadas_a_gasto", "bajas_activos", "depreciacion_activos_costo", "deterioro_activos_costo",
           "perdida_ajustes_periodos_anteriores"}
# Secciones del informe de revelaciones en el orden de la norma (¶40-56 y NIIF 13 ¶93).
_OCULTOS_INFORME = {"id_activo_biologico", "id_precio_mercado", "json_metodo_costo"}
_CAMPOS_INFORME = {
    "especie": "Especie",
    "cantidad_activos": "Activos",
    "valor_cierre": "Valor al cierre",
    "clasificacion": "Clasificación",
    "reconocimiento_inicial": "Reconocimiento inicial",
    "transformacion_biologica": "Transformación biológica",
    "precio_mercado": "Precio de mercado",
    "total": "Total",
    "identificador": "Activo",
    "valor_inicio": "Valor al inicio",
    "compras": "Compras",
    "nacimientos_y_otros_ingresos": "Nacimientos y otros ingresos",
    "cosechas": "Cosechas",
    "bajas": "Bajas",
    "depreciacion_y_deterioro": "Depreciación y deterioro",
    "magnitud": "Magnitud",
    "unidad_magnitud": "Unidad",
    "precio_unitario": "Precio unitario",
    "valor_razonable_bruto": "Valor bruto",
    "valor_neto": "Valor neto",
    "metodo_costo": "Costos de venta",
    "tiene_valor_estimado": "Estimado",
    "fuente": "Fuente",
    "categoria": "Categoría",
    "unidad_medida": "Unidad",
    "fecha_vigencia": "Vigente desde",
    "evidencia": "Evidencia",
    "justificacion": "Justificación",
    "razon": "Razón",
    "metodo_depreciacion": "Método de depreciación",
    "vida_util_meses": "Vida útil (meses)",
    "costo": "Costo",
    "depreciacion_acumulada": "Depreciación acumulada",
    "deterioro_acumulado": "Deterioro acumulado",
    "valor_contable": "Valor en libros",
    "rango_valor_razonable": "Rango del valor razonable",
    "compromisos": "Compromisos",
    "activos_pignorados": "Activos dados en garantía",
    "declaracion_sin_novedad": "Declaración sin novedad",
    "descripcion": "Descripción",
    "contraparte": "Contraparte",
    "monto_estimado": "Monto estimado",
    "fecha_estimada": "Fecha estimada",
    "entidad_acreedora": "Entidad acreedora",
    "monto_garantia": "Monto de la garantía",
    "fecha_vencimiento": "Vencimiento",
    "tipo_evento": "Evento",
    "fecha": "Fecha",
    "impacto_economico_cop": "Impacto económico",
    "motivo": "Motivo",
}
_CATALOGO_INFORME = {
    "DATOS_INSUFICIENTES": "Datos insuficientes para esta sección", "PRODUCCION": "Producción", "CONSUMO": "Consumo",
    "MERCADO_ACTIVO": "Mercado activo", "UPRA": "UPRA", "ESTIMADA": "Estimada", "PARAMETRIZADO": "Parametrizado", "MANUAL": "Manual",
    "PESO_KG": "Por kilo", "POR_CABEZA": "Por cabeza", "PRODUCTO": "Producto",
}
_ESTADO_DOC = {"APROBADO": "Aprobado", "ARCHIVADO": "Archivado", "BORRADOR": "Borrador", "RECHAZADO": "Rechazado", "GENERADO": "Generado"}


def _nit(nit) -> str:
    return f"NIT {nit}" if nit else "Sin NIT asignado"


def _rotulo(clave: str) -> str:
    return _CAMPOS_INFORME.get(clave) or str(clave).replace("_", " ").strip().capitalize()


def _valor_informe(clave: str, valor) -> str:
    """Valor del contenido del informe en palabras: montos con moneda, sí/no, listas y objetos anidados."""
    if valor is None or valor == "":
        return "Sin dato"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, dict):
        return "; ".join(f"{_rotulo(k)}: {_valor_informe(k, v)}" for k, v in valor.items() if k not in _OCULTOS_INFORME)
    if isinstance(valor, list):
        return ", ".join(_valor_informe(clave, v) for v in valor) or "Sin datos"
    if isinstance(valor, str) and valor in _CATALOGO_INFORME:
        return _CATALOGO_INFORME[valor]
    if isinstance(valor, str) and re.fullmatch(r"[A-Z]{3,}(_[A-Z0-9]+)+", valor):  # enum crudo, no un identificador
        return _rotulo(valor)
    if any(p in clave for p in ("valor", "monto", "costo", "precio", "compras", "bajas", "cosechas", "total", "depreciacion",
                                "deterioro", "transformacion", "reconocimiento", "nacimientos", "impacto")):
        try:
            return moneda(valor)
        except Exception:  # noqa: BLE001 - un valor no numérico se muestra tal cual
            return str(valor)
    if "fecha" in clave:
        return fecha(valor)
    return str(valor)


def _con_signo(valor, gasto: bool) -> str:
    texto = moneda(valor)
    if not texto:
        return "$ 0"
    return texto if not gasto or texto.startswith("−") or texto == "$ 0" else f"−{texto}"


def _resultado(neto) -> str:
    n = float(neto or 0)
    etiqueta = "Ganancia" if n > 0 else "Pérdida" if n < 0 else "Sin resultado"
    return f"{'+' if n > 0 else ''}{moneda(neto) or '$ 0'} ({etiqueta})"


def _excluido(x: dict) -> str:
    """RF-93: el activo excluido del cierre, por qué (el motivo viaja como código) y el resultado que quedó fuera."""
    causa = (x.get("detalle") or "Sin precio de mercado vigente").rstrip(".")
    neto = (x.get("montos_excluidos") or {}).get("resultado_neto")
    return (f"Excluido del cierre: {x.get('identificador') or 'activo sin identificador'}. {causa}."
            + (f" Resultado no incluido: {_resultado(neto)}." if neto is not None else ""))


def _alcance(filtros) -> str:
    activos = [n for k, n in (("id_especie", "especie"), ("id_finca", "finca"), ("id_activo_biologico", "activo"),
                              ("id_infraestructura", "infraestructura")) if (filtros or {}).get(k)]
    return "consolidado (sin filtros)" if not activos else "filtrado por " + ", ".join(activos)


_TIPOS = {"csv": ("text/csv", "csv"), "excel": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
          "pdf": ("application/pdf", "pdf")}


def _archivo(doc: Documento, formato: str, pdfa: bool = False) -> tuple[bytes, str, str]:
    if formato not in _TIPOS:
        raise BusinessRuleError(code="FORMATO_NO_SOPORTADO", message="Formato no soportado: use csv, excel o pdf.")
    pdf = (lambda d: generar_pdf(d, datetime.now(timezone.utc), pdfa=True)) if pdfa else (
        lambda d: generar_pdf(d, datetime.now(timezone.utc)))
    contenido = {"csv": generar_csv, "excel": generar_excel}.get(formato, pdf)(doc)
    tipo, extension = _TIPOS[formato]
    return contenido, tipo, extension


class ExportarReporteUseCase:
    def __init__(self, periodos: PeriodoRepository, reportes: ReporteRepository) -> None:
        self.periodos = periodos
        self.reportes = reportes

    def comprobantes(self, id_periodo_contable: int, formato: str) -> tuple[bytes, str, str]:
        periodo = self.periodos.obtener(id_periodo_contable)
        if periodo is None or periodo.estado != "CERRADO":
            raise BusinessRuleError(code="PERIODO_NO_CERRADO", message="El comprobante existe solo para períodos cerrados.")
        legible = formato != "csv"  # el CSV conserva números y fechas ISO para cargarlo en la contabilidad externa
        filas = []
        for c in self.periodos.comprobantes(id_periodo_contable):
            for linea in c["lineas"]:
                filas.append([c["codigo"], fecha(c["fecha_comprobante"]) if legible else c["fecha_comprobante"],
                              ETIQUETA_HECHO.get(c["tipo_hecho"], "Hecho contable"), c["especie"], linea["cuenta_debito"],
                              linea["cuenta_credito"], moneda(linea["valor"]) if legible else linea["valor"], c["hash_integridad"]])
        doc = Documento(titulo=f"Comprobante NIC 41 {periodo.fecha_inicio:%m/%Y}",
                        columnas=["Comprobante", "Fecha", "Hecho contable", "Especie", "Cuenta débito", "Cuenta crédito", "Valor",
                                  "Huella de integridad"],
                        filas=filas, encabezado=[f"Titular: {_nit(periodo.numero_id_tributaria)}",
                                                 f"Período: {periodo.fecha_inicio:%d/%m/%Y} a {periodo.fecha_fin:%d/%m/%Y}"])
        return (*_archivo(doc, formato), f"comprobante_nic41_{periodo.numero_id_tributaria}_{periodo.fecha_fin:%Y%m}")

    def estado_resultados(self, id_estado: int, formato: str) -> tuple[bytes, str, str]:
        estado = self.reportes.obtener_estado(id_estado)
        if estado is None:
            raise NotFoundError(code="ESTADO_RESULTADOS_NO_ENCONTRADO", message="El estado de resultados no existe.")
        if estado["estado"] != "APROBADO":
            raise BusinessRuleError(code="ESTADO_RESULTADOS_NO_APROBADO", message="Solo se descarga el estado aprobado.")
        componentes = estado["componentes"] or {}
        filas = []
        for clave, etiqueta in ETIQUETAS_COMPONENTES.items():
            gasto = clave in _GASTOS
            valor = componentes.get(clave, "0")
            # Signo y tipo en texto (TC-DIS-264): el gasto lleva «−» y la columna «Tipo» lo nombra.
            filas.append([etiqueta, "Gasto" if gasto else "Ingreso",
                          _con_signo(valor, gasto) if float(valor or 0) else "Sin actividad en el período"])
            if clave == "costos_mantenimiento":  # RF-87 paso 7: por tipo
                filas += [[f"   {ETIQUETA_SUBTIPO.get(t, t).capitalize()}", "Gasto", _con_signo(v, True)]
                          for t, v in (componentes.get("desglose_costos_mantenimiento") or {}).items()]
        excluidos = componentes.get("activos_excluidos_cierre") or []
        aprobado = (f"Aprobado el {fecha(estado['fecha_aprobacion'])}" + (f" por {estado['nombre_aprobador']}" if estado.get("nombre_aprobador") else "")
                    if estado.get("fecha_aprobacion") else "Aprobado")
        doc = Documento(titulo="Estado de resultados del período agropecuario", columnas=["Componente", "Tipo", "Valor"],
                        filas=filas, encabezado=[f"Versión {estado['version']} · {aprobado}", f"Alcance: {_alcance(estado['filtros'])}"],
                        pie=[f"Total ingresos: {moneda(estado['total_ingresos']) or '$ 0'}",
                             f"Total gastos: {_con_signo(estado['total_gastos'], True)}",
                             f"Resultado neto: {_resultado(estado['resultado_neto'])}",
                             *[_excluido(x) for x in excluidos]])
        return (*_archivo(doc, formato), f"estado_resultados_v{estado['version']}")

    def informe(self, id_informe: int, formato: str) -> tuple[bytes, str, str]:
        informe = self.reportes.obtener_informe(id_informe)
        if informe is None:
            raise NotFoundError(code="INFORME_NO_ENCONTRADO", message="El informe no existe.")
        if informe["estado"] not in ("APROBADO", "ARCHIVADO"):  # R2 / CA-6
            raise BusinessRuleError(code="INFORME_NO_APROBADO", message="Solo se descargan informes aprobados.")
        contenido = informe["contenido"] or {}
        # El estado por sección (RF-92 R6) es control de la aprobación, no una revelación: no se imprime.
        orden = [k for k in SECCIONES_INFORME if k in contenido] + [k for k in contenido
                                                                     if k not in SECCIONES_INFORME and k != "estado_secciones"]
        filas = []
        for seccion in orden:
            titulo, valor = SECCIONES_INFORME.get(seccion, _rotulo(seccion)), contenido[seccion]
            if isinstance(valor, list):
                for elemento in valor or ["Sin datos en el período"]:
                    filas.append([titulo, _valor_informe(seccion, elemento)])
            else:
                filas.append([titulo, _valor_informe(seccion, valor)])
        aprobado = (f" el {fecha(informe['fecha_aprobacion'])}" if informe.get("fecha_aprobacion") else "") + (
            f" por {informe['nombre_aprobador']}" if informe.get("nombre_aprobador") else "")
        doc = Documento(titulo=f"Informe de revelaciones NIC 41 {informe['version_informe']}", columnas=["Sección", "Detalle"],
                        filas=filas, encabezado=[f"Estado: {_ESTADO_DOC.get(informe['estado'], _rotulo(informe['estado']))}{aprobado}",
                                                 f"Huella de integridad: {informe['hash_informe']}"])
        # RNF-92-02 / RNF-92-03: el informe se conserva 10 años; el PDF va en PDF/A-1b (TC-M06-G70).
        return (*_archivo(doc, formato, pdfa=True), f"revelaciones_nic41_{informe['version_informe']}")
