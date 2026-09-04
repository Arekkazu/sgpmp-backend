#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de plantillas PDF para el flujo de trabajo de desarrollo.

Genera dos documentos, listos para imprimir o llenar en un editor de PDF:

  1. plantilla_registro_cambios.pdf
     - Página 1: formulario "Comunicación de cambios" (uno por cada PR/cambio)
     - Página 2: "Registro de cambios" (bitácora acumulativa en tabla)

  2. plantilla_evidencia_pruebas.pdf
     - Evidencia de pruebas unitarias e integración que acompaña cada PR

Requisitos:
    pip install reportlab

Uso:
    python3 generar_plantillas.py
    python3 generar_plantillas.py --outdir ./plantillas

Para ajustar contenido (campos, checkboxes, textos), edita las funciones
generar_plantilla_cambios() y generar_plantilla_pruebas() más abajo: cada
sección está separada con un comentario "# ---" para ubicarla fácil.
"""

import argparse
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

# =============================================================================
# Estilo compartido
# =============================================================================
W, H = A4
MARGIN = 40

NAVY = HexColor("#1F3864")
ACCENT = HexColor("#2E5A87")
GRAY = HexColor("#495057")
LINEGRAY = HexColor("#B7BEC7")
CODEBG = HexColor("#F2F2F2")
CODEBORDER = HexColor("#C9CFD6")
GREEN = HexColor("#2E7D5B")


# =============================================================================
# Helpers de dibujo (compartidos entre las dos plantillas)
# =============================================================================
def section_header(c: canvas.Canvas, y: float, text: str, color=NAVY) -> float:
    """Barra de color con título de sección. Devuelve la nueva posición y."""
    c.setFillColor(color)
    c.rect(MARGIN, y - 16, W - 2 * MARGIN, 16, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(MARGIN + 6, y - 11.5, text)
    c.setFillColor(black)
    return y - 16


def label(c: canvas.Canvas, x: float, y: float, text: str, size=8.3, bold=False, color=GRAY) -> None:
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.setFillColor(color)
    c.drawString(x, y, text)
    c.setFillColor(black)


def field_line(c: canvas.Canvas, x: float, y: float, width: float, text_label: str) -> None:
    """Etiqueta seguida de una línea en blanco para escribir encima."""
    label(c, x, y + 3, text_label)
    lw = stringWidth(text_label, "Helvetica", 8.3)
    c.setStrokeColor(LINEGRAY)
    c.setLineWidth(0.7)
    c.line(x + lw + 4, y, x + width, y)


def checkbox(c: canvas.Canvas, x: float, y: float, text_label: str, size=8.0) -> float:
    """Dibuja un checkbox + texto. Devuelve la x donde termina (para encadenar)."""
    c.setStrokeColor(GRAY)
    c.setLineWidth(0.8)
    c.rect(x, y - 0.5, 7.5, 7.5, stroke=1, fill=0)
    c.setFont("Helvetica", size)
    c.setFillColor(black)
    c.drawString(x + 11, y, text_label)
    return x + 11 + stringWidth(text_label, "Helvetica", size)


def multiline_box(c: canvas.Canvas, x: float, y_top: float, width: float, n_lines: int, line_gap=15) -> float:
    """Varias líneas en blanco seguidas, para texto libre. Devuelve la y final."""
    c.setStrokeColor(LINEGRAY)
    c.setLineWidth(0.6)
    for i in range(n_lines):
        yy = y_top - i * line_gap
        c.line(x, yy, x + width, yy)
    return y_top - (n_lines - 1) * line_gap


def code_box(c: canvas.Canvas, x: float, y_top: float, width: float, height: float, placeholder: str) -> float:
    """Caja gris estilo 'bloque de código' con un texto de ejemplo dentro."""
    c.setFillColor(CODEBG)
    c.setStrokeColor(CODEBORDER)
    c.setLineWidth(0.8)
    c.rect(x, y_top - height, width, height, stroke=1, fill=1)
    c.setFont("Courier", 8.6)
    c.setFillColor(GRAY)
    c.drawString(x + 8, y_top - height / 2 - 3, placeholder)
    c.setFillColor(black)
    return y_top - height


def numbered_lines(c: canvas.Canvas, x: float, y_top: float, width: float, n: int, line_gap=17) -> float:
    """Lista numerada (1., 2., 3. ...) con línea en blanco para completar cada punto."""
    c.setFont("Helvetica", 8.3)
    yy = y_top
    for i in range(n):
        c.setFillColor(GRAY)
        c.drawString(x, yy, f"{i + 1}.")
        c.setStrokeColor(LINEGRAY)
        c.setLineWidth(0.6)
        c.line(x + 16, yy - 2, x + width, yy - 2)
        yy -= line_gap
    c.setFillColor(black)
    return yy + line_gap


# =============================================================================
# PLANTILLA 1: Comunicación de cambios + Registro (bitácora)
# =============================================================================
def generar_plantilla_cambios(output_path: Path) -> None:
    c = canvas.Canvas(str(output_path), pagesize=A4)

    # ---------------- Página 1: Comunicación de un cambio ----------------
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(W / 2, H - 46, "Comunicación de cambios — rama de desarrollo")
    c.setFont("Helvetica-Oblique", 9.5)
    c.setFillColor(GRAY)
    c.drawCentredString(W / 2, H - 62, "Plantilla universal para documentar y comunicar cambios entre Desarrollo, QA, DBA y AIOT")
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.2)
    c.line(MARGIN, H - 72, W - MARGIN, H - 72)

    y = H - 92
    colw = (W - 2 * MARGIN - 20) / 2

    # --- 1. Datos generales ---
    y = section_header(c, y, "1. Datos generales")
    y -= 22
    field_line(c, MARGIN, y, colw, "Proyecto:")
    field_line(c, MARGIN + colw + 20, y, colw, "Fecha:")
    y -= 22
    field_line(c, MARGIN, y, colw, "Responsable / Autor:")
    field_line(c, MARGIN + colw + 20, y, colw, "Pull Request (N.° / enlace):")
    y -= 22
    field_line(c, MARGIN, y, W - 2 * MARGIN, "Nombre de la rama (ej. feature/nombre-funcionalidad):")
    y -= 22
    field_line(c, MARGIN, y, W - 2 * MARGIN, "Tarea de Taiga (título del PR, ej. #81 [Frontend] Descripción (RF-21)):")
    y -= 22
    field_line(c, MARGIN, y, colw, "Módulo (ej. M09):")
    field_line(c, MARGIN + colw + 20, y, colw, "Requerimiento (ej. RF-21):")
    y -= 20
    label(c, MARGIN, y, "Tipo de rama:", bold=True)
    xb = MARGIN + 70
    for opt in ["feature/*", "fix/*", "release/*", "hotfix/*"]:
        xb = checkbox(c, xb, y, opt) + 16
    y -= 26

    # --- 2. Descripción del cambio ---
    y = section_header(c, y, "2. Descripción del cambio")
    y -= 22
    label(c, MARGIN, y, "Tipo de cambio:", bold=True)
    xb = MARGIN + 78
    for opt in ["Nueva funcionalidad", "Corrección de bug", "Cambio de requerimiento", "Ajuste de estándar"]:
        xb = checkbox(c, xb, y, opt) + 14
    y -= 16
    field_line(c, MARGIN, y, W - 2 * MARGIN, "Otro (especifique):")
    y -= 18
    label(c, MARGIN, y, "Descripción (qué se hizo / qué se va a hacer):", bold=True)
    y -= 12
    y = multiline_box(c, MARGIN, y, W - 2 * MARGIN, 3)
    y -= 20

    # --- 3. Impacto y notificaciones ---
    y = section_header(c, y, "3. Impacto y notificaciones")
    y -= 22
    label(c, MARGIN, y, "¿Requiere ajuste de BD, roles o permisos?", bold=True)
    checkbox(c, MARGIN + 220, y, "Sí")
    checkbox(c, MARGIN + 260, y, "No")
    y -= 16
    field_line(c, MARGIN, y, W - 2 * MARGIN, "Detalle / DBA notificado por:")
    y -= 20
    label(c, MARGIN, y, "¿Afecta el contrato de mensajería con AIOT (broker)?", bold=True)
    checkbox(c, MARGIN + 275, y, "Sí")
    checkbox(c, MARGIN + 315, y, "No")
    y -= 16
    field_line(c, MARGIN, y, W - 2 * MARGIN, "Detalle / contract test actualizado:")
    y -= 20
    label(c, MARGIN, y, "¿Afecta otros módulos o componentes?", bold=True)
    checkbox(c, MARGIN + 210, y, "Sí")
    checkbox(c, MARGIN + 250, y, "No")
    y -= 16
    field_line(c, MARGIN, y, W - 2 * MARGIN, "Detalle / módulos afectados:")
    y -= 24

    # --- 4. Pruebas realizadas ---
    y = section_header(c, y, "4. Pruebas realizadas")
    y -= 22
    xb = MARGIN
    for opt in ["Unitarias", "Integración", "Contract tests"]:
        xb = checkbox(c, xb, y, opt) + 22
    y -= 18
    field_line(c, MARGIN, y, W - 2 * MARGIN, "Observaciones de pruebas:")
    y -= 15
    c.setFont("Helvetica-Oblique", 7.6)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, y, "Evidencia detallada: ver plantilla de evidencia de pruebas unitarias e integración (documento aparte).")
    c.setFillColor(black)
    y -= 22

    # --- 5. Estado del cambio ---
    y = section_header(c, y, "5. Estado del cambio")
    y -= 22
    row1 = ["En desarrollo", "En revisión (PR)", "En pruebas QA", "Rechazado - en corrección"]
    row2 = ["Aprobado - fusionado a develop", "En release", "Liberado a producción", "Hotfix aplicado"]
    xb = MARGIN
    for opt in row1:
        xb = checkbox(c, xb, y, opt) + 14
    y -= 16
    xb = MARGIN
    for opt in row2:
        xb = checkbox(c, xb, y, opt) + 14
    y -= 24

    # --- 6. Retroalimentación ---
    y = section_header(c, y, "6. Retroalimentación de QA / Observaciones")
    y -= 20
    y = multiline_box(c, MARGIN, y, W - 2 * MARGIN, 4)
    y -= 18

    c.setFont("Helvetica-Oblique", 7.6)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, y, "Este formulario se sube al Drive del proyecto para dejar trazabilidad del cambio, conforme al flujo de comunicación entre equipos.")

    c.showPage()

    # ---------------- Página 2: Registro (log) de cambios ----------------
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(W / 2, H - 46, "Registro de cambios en desarrollo")
    c.setFont("Helvetica-Oblique", 9.5)
    c.setFillColor(GRAY)
    c.drawCentredString(W / 2, H - 62, "Bitácora acumulativa de cambios en la rama develop — usar junto con la plantilla de comunicación")
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.2)
    c.line(MARGIN, H - 72, W - MARGIN, H - 72)

    cols = [("Fecha", 52), ("Rama", 62), ("Responsable", 72), ("Tipo", 56),
            ("Módulo", 66), ("Descripción breve", 112), ("Estado", 95)]
    table_w = sum(w for _, w in cols)
    x0 = MARGIN
    y0 = H - 92
    row_h = 24
    n_rows = 20

    c.setFillColor(NAVY)
    c.rect(x0, y0 - row_h, table_w, row_h, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8.3)
    xc = x0
    for name, w in cols:
        c.drawString(xc + 5, y0 - row_h + 8, name)
        xc += w

    c.setStrokeColor(LINEGRAY)
    c.setLineWidth(0.6)
    yy = y0 - row_h
    for _ in range(n_rows):
        yy -= row_h
        c.line(x0, yy, x0 + table_w, yy)
    xc = x0
    for _, w in cols:
        c.line(xc, y0 - row_h, xc, y0 - row_h - n_rows * row_h)
        xc += w
    c.line(x0 + table_w, y0 - row_h, x0 + table_w, y0 - row_h - n_rows * row_h)
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.1)
    c.rect(x0, y0 - row_h - n_rows * row_h, table_w, row_h * (n_rows + 1), stroke=1, fill=0)

    c.setFont("Helvetica-Oblique", 7.6)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, y0 - row_h - n_rows * row_h - 16,
                 "Cada fila resume un cambio ya comunicado en una plantilla de la página 1. "
                 "Estado sugerido: PR abierto / en QA / fusionado / liberado / hotfix.")

    c.showPage()
    c.save()


# =============================================================================
# PLANTILLA 2: Evidencia de pruebas unitarias e integración
# =============================================================================
def _test_block(c: canvas.Canvas, y: float, title: str, file_placeholder: str,
                 intro_text: str, n_items: int, color) -> float:
    """Dibuja un bloque completo (unitaria o integración): archivo + lista + resultado."""
    y = section_header(c, y, title, color=color)
    y -= 20
    label(c, MARGIN, y, "Archivo:", bold=True)
    y -= 4
    y = code_box(c, MARGIN, y, W - 2 * MARGIN, 18, file_placeholder)
    y -= 16
    label(c, MARGIN, y, intro_text, bold=True)
    y -= 14
    y = numbered_lines(c, MARGIN + 4, y, W - 2 * MARGIN - 4, n_items)
    y -= 8
    label(c, MARGIN, y, "Resultado:", bold=True)
    xb = checkbox(c, MARGIN + 62, y, "Pasó") + 12
    xb = checkbox(c, xb, y, "Falló") + 12
    checkbox(c, xb, y, "Pendiente")
    y -= 22
    return y


def generar_plantilla_pruebas(output_path: Path) -> None:
    c = canvas.Canvas(str(output_path), pagesize=A4)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(W / 2, H - 46, "Evidencia de pruebas unitarias e integración")
    c.setFont("Helvetica-Oblique", 9.5)
    c.setFillColor(GRAY)
    c.drawCentredString(W / 2, H - 62, "Plantilla universal — se adjunta a cada Pull Request antes de pasar a QA")
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.2)
    c.line(MARGIN, H - 72, W - MARGIN, H - 72)

    y = H - 92

    # --- Identificación ---
    y = section_header(c, y, "Identificación")
    y -= 22
    colw = (W - 2 * MARGIN - 20) / 2
    field_line(c, MARGIN, y, colw, "Tarea de Taiga:")
    field_line(c, MARGIN + colw + 20, y, colw, "Módulo:")
    y -= 20
    field_line(c, MARGIN, y, colw, "Pull Request (N.° / enlace):")
    field_line(c, MARGIN + colw + 20, y, colw, "Requerimiento (RF-XX):")
    y -= 26

    # --- Prueba unitaria ---
    y = _test_block(c, y, "Prueba unitaria", "tests/shared/test_ejemplo.py",
                     "La prueba unitaria valida que:", 5, GREEN)

    # --- Prueba de integración ---
    y = _test_block(c, y, "Prueba de integración", "tests/integration/test_ejemplo.py",
                     "La prueba de integración valida que:", 6, ACCENT)

    # --- Consolidación ---
    y = section_header(c, y, "Consolidación")
    y -= 22
    checkbox(c, MARGIN, y, "Las pruebas unitarias e integración quedaron consolidadas y pasando antes de enviar el PR a QA.")
    y -= 22

    c.setFont("Helvetica-Oblique", 7.6)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, y, "Este formulario acompaña la plantilla de comunicación de cambios y se sube al Drive junto con el PR.")

    c.showPage()
    c.save()


# =============================================================================
# Main
# =============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="Genera las plantillas PDF del flujo de trabajo de desarrollo.")
    parser.add_argument("--outdir", default=".", help="Carpeta de salida (por defecto la carpeta actual).")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    ruta_cambios = outdir / "plantilla_registro_cambios.pdf"
    ruta_pruebas = outdir / "plantilla_evidencia_pruebas.pdf"

    generar_plantilla_cambios(ruta_cambios)
    generar_plantilla_pruebas(ruta_pruebas)

    print(f"Generado: {ruta_cambios}")
    print(f"Generado: {ruta_pruebas}")


if __name__ == "__main__":
    main()
