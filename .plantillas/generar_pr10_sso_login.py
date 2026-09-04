#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comunicación de cambios — PR #10 "Feature/sso-login" (feature/sso-login -> dev).

Genera la página 1 de la plantilla de comunicación de cambios, ya rellenada
con los datos de ese PR, reutilizando los helpers de dibujo de
generar_plantillas.py.

Uso:
    python3 generar_pr10_sso_login.py
    python3 generar_pr10_sso_login.py --outdir ./plantillas
"""

import argparse
import textwrap
from pathlib import Path

from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from generar_plantillas import (
    W, H, MARGIN, NAVY, GRAY, LINEGRAY,
    section_header, label, checkbox,
)


def value_line(c, x, y, width, text_label, value, size=8.3):
    """Etiqueta en negrita + valor en texto normal a continuación (campo ya lleno)."""
    label(c, x, y, text_label, size=size, bold=True)
    lw = stringWidth(text_label, "Helvetica-Bold", size)
    c.setFont("Helvetica", size)
    c.setFillColor(black)
    c.drawString(x + lw + 6, y, value)


def checked_box(c, x, y, text_label, checked, size=8.0):
    c.setStrokeColor(GRAY)
    c.setLineWidth(0.8)
    c.rect(x, y - 0.5, 7.5, 7.5, stroke=1, fill=0)
    if checked:
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(black)
        c.drawString(x + 1.4, y - 0.3, "X")
    c.setFont("Helvetica", size)
    c.setFillColor(black)
    c.drawString(x + 11, y, text_label)
    return x + 11 + stringWidth(text_label, "Helvetica", size)


def wrapped_text(c, x, y_top, width, text, size=8.6, line_gap=12, font="Helvetica"):
    """Envuelve texto en varias líneas dentro de `width` puntos. Devuelve la y final."""
    # ancho aproximado en caracteres a partir del ancho real en puntos
    avg_char_w = stringWidth("n", font, size) or 1
    wrap_chars = max(10, int(width / avg_char_w))
    lines = []
    for parrafo in text.split("\n"):
        lines.extend(textwrap.wrap(parrafo, wrap_chars) or [""])
    c.setFont(font, size)
    c.setFillColor(black)
    yy = y_top
    for ln in lines:
        c.drawString(x, yy, ln)
        yy -= line_gap
    return yy + line_gap


def generar(output_path: Path) -> None:
    c = canvas.Canvas(str(output_path), pagesize=A4)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(W / 2, H - 46, "Comunicación de cambios — rama de desarrollo")
    c.setFont("Helvetica-Oblique", 9.5)
    c.setFillColor(GRAY)
    c.drawCentredString(W / 2, H - 62, "PR #10 — Feature/sso-login")
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.2)
    c.line(MARGIN, H - 72, W - MARGIN, H - 72)

    y = H - 92
    colw = (W - 2 * MARGIN - 20) / 2

    # --- 1. Datos generales ---
    y = section_header(c, y, "1. Datos generales")
    y -= 22
    value_line(c, MARGIN, y, colw, "Proyecto:", "sgpmp-backend")
    value_line(c, MARGIN + colw + 20, y, colw, "Fecha:", "12/08/2026")
    y -= 22
    value_line(c, MARGIN, y, colw, "Responsable / Autor:", "Arekkazu")
    value_line(c, MARGIN + colw + 20, y, colw, "Pull Request (N.° / enlace):",
               "#10 — github.com/Arekkazu/sgpmp-backend/pull/10")
    y -= 22
    value_line(c, MARGIN, y, W - 2 * MARGIN, "Nombre de la rama:", "feature/sso-login")
    y -= 22
    value_line(c, MARGIN, y, W - 2 * MARGIN, "Tarea de Taiga:", "#85 Feature/sso login")
    y -= 22
    value_line(c, MARGIN, y, colw, "Módulo:", "M01 (identity_access)")
    value_line(c, MARGIN + colw + 20, y, colw, "Requerimiento:",
               "Pendiente de asignar RF (funcionalidad nueva)")
    y -= 20
    label(c, MARGIN, y, "Tipo de rama:", bold=True)
    xb = MARGIN + 70
    for opt in ["feature/*", "fix/*", "release/*", "hotfix/*"]:
        xb = checked_box(c, xb, y, opt, checked=(opt == "feature/*")) + 16
    y -= 26

    # --- 2. Descripción del cambio ---
    y = section_header(c, y, "2. Descripción del cambio")
    y -= 22
    label(c, MARGIN, y, "Tipo de cambio:", bold=True)
    xb = MARGIN + 78
    for opt in ["Nueva funcionalidad", "Corrección de bug", "Cambio de requerimiento", "Ajuste de estándar"]:
        xb = checked_box(c, xb, y, opt, checked=(opt == "Nueva funcionalidad")) + 14
    y -= 20
    label(c, MARGIN, y, "Descripción (qué se hizo / qué se va a hacer):", bold=True)
    y -= 13
    descripcion = (
        "Se documentó y finalizó la implementación de la integración de SSO con AgroFusion, "
        "cubriendo el inicio de sesión interactivo (Mecanismo A) y la sincronización servidor-a-servidor "
        "(Mecanismo B). Es un requerimiento nuevo, no contemplado en el alcance original: desarrollo "
        "adelantó la construcción del mecanismo antes de contar con un RF formal, por lo que corresponde "
        "a analisis redactar el requerimiento y a diseño construir el DFD correspondiente con base en lo "
        "ya implementado. Incluye guia para el equipo de frontend (UI, flujos de API, manejo de errores, "
        "onboarding de perfiles incompletos), checklist de tareas de backend para ambos mecanismos "
        "(migraciones de BD, cambios de dominio e infraestructura, configuracion), comandos curl de "
        "ejemplo para los endpoints nuevos, y actualizacion de .env.example (se eliminaron variables "
        "OAuth de Google/Microsoft heredadas y se agregaron las variables de SSO/AgroFusion)."
    )
    y = wrapped_text(c, MARGIN, y, W - 2 * MARGIN, descripcion)
    y -= 14

    # --- 3. Impacto y notificaciones ---
    y = section_header(c, y, "3. Impacto y notificaciones")
    y -= 22
    label(c, MARGIN, y, "¿Requiere ajuste de BD, roles o permisos?", bold=True)
    checked_box(c, MARGIN + 220, y, "Sí", checked=True)
    checked_box(c, MARGIN + 260, y, "No", checked=False)
    y -= 16
    y = wrapped_text(
        c, MARGIN, y, W - 2 * MARGIN,
        "Detalle: nuevo rol \"Externo AgroFusion\" (id_rol=9) sin permisos por defecto; "
        "nuevo estado de cuenta PENDIENTE_DATOS.",
        size=8.3,
    )
    y -= 14
    label(c, MARGIN, y, "¿Afecta el contrato de mensajería con AIOT (broker)?", bold=True)
    checked_box(c, MARGIN + 275, y, "Sí", checked=False)
    checked_box(c, MARGIN + 315, y, "No", checked=True)
    y -= 16
    value_line(c, MARGIN, y, W - 2 * MARGIN, "Detalle:", "No aplica.")
    y -= 20
    label(c, MARGIN, y, "¿Afecta otros módulos o componentes?", bold=True)
    checked_box(c, MARGIN + 210, y, "Sí", checked=True)
    checked_box(c, MARGIN + 250, y, "No", checked=False)
    y -= 16
    y = wrapped_text(
        c, MARGIN, y, W - 2 * MARGIN,
        "Detalle: modulo1 (identity_access) y sgpmp-frontend (3 pantallas nuevas: login, "
        "callback y completar perfil).",
        size=8.3,
    )
    y -= 16

    # --- 4. Pruebas realizadas ---
    y = section_header(c, y, "4. Pruebas realizadas")
    y -= 22
    xb = MARGIN
    for opt in ["Unitarias", "Integración", "Contract tests"]:
        xb = checked_box(c, xb, y, opt, checked=(opt == "Integración")) + 22
    y -= 18
    label(c, MARGIN, y, "Observaciones de pruebas:", bold=True)
    y -= 13
    y = wrapped_text(
        c, MARGIN, y, W - 2 * MARGIN,
        "Verificacion de endpoints y flujos documentada mediante checklist de backend y ejemplos "
        "de llamadas a la API para ambos mecanismos.",
        size=8.3,
    )
    y -= 16

    # --- 5. Estado del cambio ---
    y = section_header(c, y, "5. Estado del cambio")
    y -= 22
    row1 = ["En desarrollo", "En revisión (PR)", "En pruebas QA", "Rechazado - en corrección"]
    row2 = ["Aprobado - fusionado a develop", "En release", "Liberado a producción", "Hotfix aplicado"]
    xb = MARGIN
    for opt in row1:
        xb = checked_box(c, xb, y, opt, checked=False) + 14
    y -= 16
    xb = MARGIN
    for opt in row2:
        xb = checked_box(c, xb, y, opt, checked=(opt == "Aprobado - fusionado a develop")) + 14
    y -= 26

    # --- 6. Retroalimentación / lo necesario para que la integración funcione ---
    y = section_header(c, y, "6. Retroalimentación de QA / Observaciones")
    y -= 20
    pendientes = (
        "Para que la integracion quede completamente operativa falta, del lado de AgroFusion:\n"
        "1. La URL real de login de AgroFusion para configurar VITE_AGROFUSION_LOGIN_URL en el "
        "frontend de sgpmp (Mecanismo A). El mecanismo ya esta listo del lado de sgpmp; mientras "
        "no se reciba el valor, el boton \"Continuar con AgroFusion\" permanece deshabilitado.\n"
        "2. La implementacion de las llamadas salientes en el backendint (Hub) de AgroFusion hacia "
        "los endpoints CREATE_USER, GET_ROLES, GET_USER y CHANGE_USER_STATUS (Mecanismo B). Del "
        "lado de sgpmp esos endpoints ya estan implementados y no requieren desarrollo adicional."
    )
    y = wrapped_text(c, MARGIN, y, W - 2 * MARGIN, pendientes, size=8.3, line_gap=12)
    y -= 18

    c.setFont("Helvetica-Oblique", 7.6)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, y, "Este formulario se sube al Drive del proyecto para dejar trazabilidad del cambio.")

    c.showPage()
    c.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera la comunicación de cambios del PR #10 (SSO login).")
    parser.add_argument("--outdir", default=".", help="Carpeta de salida (por defecto la carpeta actual).")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    ruta = outdir / "PR-10_feature-sso-login.pdf"
    generar(ruta)
    print(f"Generado: {ruta}")


if __name__ == "__main__":
    main()
