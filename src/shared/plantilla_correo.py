# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Plantilla HTML común a todos los correos de SIGAB.

Una sola estructura para los avisos de cuenta (RF-14), los correos con enlace
(activación, recuperación) y los avisos de suministros (RF-76). Cada correo
lleva la constancia que RF-14 exige: tipo de evento, mensaje y fecha y hora.

Restricciones de los clientes de correo que explican el HTML:
- Maquetación con tablas y estilos en línea: Gmail y Outlook descartan casi
  todo el CSS de ``<style>`` y no soportan flex ni grid.
- Sin imágenes: con las imágenes bloqueadas, el correo se lee igual.
- El ``<style>`` solo agrega mejoras opcionales (móvil y modo oscuro) para
  los clientes que lo respetan (Apple Mail, iOS, Outlook.com).

Todo texto se escapa aquí: el nombre del usuario y los datos del dominio
nunca se interpretan como HTML.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import escape
from typing import Literal, Optional, Sequence

from src.shared.fechas import en_zona_usuario, etiqueta_zona

Tono = Literal["info", "atencion", "critico"]

_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# Tokens del design system del frontend (src/shared/design-system/tokens.css).
_TINTA = "#252820"
_TINTA_SUAVE = "#585e53"
_BORDE = "#e2e4de"
_PAGINA = "#f8f9f7"
_MARCA = "#226a28"
_MARCA_ISOTIPO = "#2e8634"
_TONOS: dict[str, tuple[str, str]] = {
    # tono: (barra y texto de énfasis, fondo de la constancia)
    "info": (_MARCA, "#f0f7ee"),
    "atencion": ("#986000", "#fff8e6"),
    "critico": ("#c0280a", "#fff0ed"),
}
_FUENTE = "'Plus Jakarta Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


@dataclass(frozen=True)
class Accion:
    """Botón principal del correo. ``url`` también se muestra como texto."""

    texto: str
    url: str


def formatear_fecha(momento: datetime) -> str:
    """``10 de octubre de 2026, 6:42 p. m. (UTC-05:00)``.

    En la zona de quien hizo la petición (``X-Zona-Horaria``) o en UTC si no la
    hay, como en las tareas de fondo. La etiqueta evita que el destinatario,
    que puede estar en otra zona, lea la hora como si fuera la suya.
    """
    local = en_zona_usuario(momento)
    hora = local.hour % 12 or 12
    sufijo = "a. m." if local.hour < 12 else "p. m."
    return f"{formatear_dia(local.date())}, {hora}:{local.minute:02d} {sufijo} ({etiqueta_zona(local)})"


def formatear_dia(dia: date) -> str:
    """``10 de octubre de 2026``."""
    return f"{dia.day} de {_MESES[dia.month - 1]} de {dia.year}"


def formatear_hora(momento: datetime) -> str:
    """``6:42 p. m. (UTC-05:00)``, ver ``formatear_fecha``."""
    return formatear_fecha(momento).split(", ", 1)[1]


def renderizar_correo(
    *,
    titulo: str,
    parrafos: Sequence[str],
    evento: str,
    fecha: Optional[datetime] = None,
    nombre: Optional[str] = None,
    tono: Tono = "info",
    detalles: Sequence[tuple[str, str]] = (),
    accion: Optional[Accion] = None,
    nota: Optional[str] = None,
) -> str:
    """Arma el HTML completo de un correo.

    Args:
        titulo: Lo que pasó, en una frase. También es la vista previa.
        parrafos: Texto plano; cada elemento es un párrafo.
        evento: Nombre legible del tipo de evento (constancia RF-14).
        fecha: Momento del evento; por defecto, ahora.
        nombre: Nombre del destinatario para el saludo, si se conoce.
        tono: ``info``, ``atencion`` (revisar) o ``critico`` (acción urgente).
        detalles: Filas extra de la constancia, como ``("Medicamento", "X")``.
        accion: Botón principal, si el correo pide hacer algo.
        nota: Indicación final, como qué hacer si no fue el usuario.
    """
    color, fondo = _TONOS[tono]
    filas = [("Evento", evento), ("Fecha y hora", formatear_fecha(fecha or datetime.now(timezone.utc)))]
    filas.extend(detalles)

    saludo = (
        f'<p style="margin:0 0 8px;font-size:16px;line-height:24px;color:{_TINTA_SUAVE};">'
        f"Hola, {escape(nombre)}</p>"
        if nombre
        else ""
    )
    cuerpo = "".join(
        f'<p style="margin:0 0 16px;font-size:16px;line-height:26px;color:{_TINTA};">{escape(p)}</p>'
        for p in parrafos
    )
    constancia = "".join(
        f'<tr><td class="c-etiqueta" style="padding:4px 16px 4px 0;font-size:13px;line-height:20px;'
        f'font-weight:600;color:{_TINTA_SUAVE};white-space:nowrap;vertical-align:top;">{escape(etiqueta)}</td>'
        f'<td class="c-valor" style="padding:4px 0;font-size:14px;line-height:20px;color:{_TINTA};'
        f'vertical-align:top;">{escape(valor)}</td></tr>'
        for etiqueta, valor in filas
    )
    boton = ""
    if accion:
        url = escape(accion.url, quote=True)
        boton = f"""
          <table role="presentation" class="boton" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 12px;">
            <tr><td bgcolor="{_MARCA}" style="border-radius:8px;">
              <a href="{url}" style="display:inline-block;padding:14px 24px;font-family:{_FUENTE};font-size:16px;line-height:20px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;">{escape(accion.texto)}</a>
            </td></tr>
          </table>
          <p style="margin:0 0 20px;font-size:13px;line-height:20px;color:{_TINTA_SUAVE};">
            Si el botón no funciona, copia este enlace en tu navegador:<br>
            <a href="{url}" class="enlace" style="color:{_MARCA};word-break:break-all;">{url}</a>
          </p>"""
    nota_html = (
        f'<p class="nota" style="margin:20px 0 0;padding-top:16px;border-top:1px solid {_BORDE};font-size:14px;'
        f'line-height:22px;color:{_TINTA_SUAVE};">{escape(nota)}</p>'
        if nota
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="es" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{escape(titulo)}</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  body {{ margin:0; padding:0; width:100% !important; -webkit-text-size-adjust:100%; }}
  @media (max-width: 600px) {{
    .contenedor {{ padding:16px 12px !important; }}
    .tarjeta {{ padding:24px 20px !important; }}
    .titulo {{ font-size:22px !important; line-height:28px !important; }}
    .boton, .boton td, .boton a {{ width:100% !important; text-align:center !important; box-sizing:border-box; }}
    .c-etiqueta, .c-valor {{ display:block !important; padding:0 !important; }}
    .c-valor {{ padding-bottom:8px !important; }}
  }}
  @media (prefers-color-scheme: dark) {{
    .pagina, .contenedor {{ background:#141610 !important; }}
    .tarjeta {{ background:#252820 !important; border-color:#3c4138 !important; }}
    .tarjeta p, .tarjeta td, .titulo {{ color:#f0f2ee !important; }}
    .tarjeta .c-etiqueta, .pie p {{ color:#c8d0c4 !important; }}
    .constancia {{ background:#1e211b !important; }}
    .tarjeta a.enlace, .marca {{ color:#7eba82 !important; }}
    .tarjeta p.nota {{ border-top-color:#3c4138 !important; }}
  }}
</style>
</head>
<body class="pagina" style="margin:0;padding:0;background:{_PAGINA};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(titulo)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{_PAGINA}" class="pagina">
  <tr><td align="center" class="contenedor" style="padding:32px 16px;font-family:{_FUENTE};">
    <!--[if mso]><table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;">
      <tr><td style="padding:0 4px 16px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td bgcolor="{_MARCA_ISOTIPO}" width="28" height="28" style="width:28px;height:28px;border-radius:7px;"></td>
          <td class="marca" style="padding-left:10px;font-family:{_FUENTE};font-size:18px;line-height:28px;font-weight:800;letter-spacing:0.5px;color:{_MARCA};">SIGAB</td>
        </tr></table>
      </td></tr>
      <tr><td class="tarjeta" bgcolor="#ffffff" style="padding:32px;border:1px solid {_BORDE};border-radius:12px;font-family:{_FUENTE};">
        {saludo}
        <h1 class="titulo" style="margin:0 0 16px;font-size:24px;line-height:30px;font-weight:700;color:{_TINTA};">{escape(titulo)}</h1>
        {cuerpo}
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 24px;">
          <tr>
            <td width="4" bgcolor="{color}" style="width:4px;border-radius:2px;"></td>
            <td class="constancia" bgcolor="{fondo}" style="padding:14px 16px;border-radius:0 8px 8px 0;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">{constancia}</table>
            </td>
          </tr>
        </table>
        {boton}
        {nota_html}
      </td></tr>
      <tr><td class="pie" style="padding:20px 4px 0;font-family:{_FUENTE};">
        <p style="margin:0;font-size:13px;line-height:20px;color:{_TINTA_SUAVE};">
          Recibes este correo porque tienes una cuenta en SIGAB, el sistema de gestión pecuaria multiespecie. Es un aviso automático.
        </p>
      </td></tr>
    </table>
    <!--[if mso]></td></tr></table><![endif]-->
  </td></tr>
</table>
</body>
</html>"""
