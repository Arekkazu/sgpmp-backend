"""Redacta secretos de un reporte HTML de Newman (htmlextra) para poder subirlo a Git.

Uso:  python limpiar_reporte.py ruta\\resultado_TC-M03-Gxx.html

Redacta: JWT, cabeceras Authorization/Bearer, X-Sandbox-Secret, y los valores JSON de
contrasena / password / token / access_token / refresh_token / secret. No deja copia del
original. Sale con codigo 0 solo si, tras limpiar, no queda ningun secreto reconocible.
"""
import re
import sys

Q = r'(?:"|&quot;|&#34;|\\")'          # comilla normal, escapada en HTML o escapada en JSON
RED = '[REDACTADO]'

PATRONES = [
    # JWT completos (tres segmentos base64url)
    (re.compile(r'eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}'), '[JWT-REDACTADO]'),
    # Authorization: Bearer xxxx  (incluye el token del broker, que no es JWT)
    (re.compile(r'(Bearer\s+)[^\s"\'<&\\]{6,}', re.I), r'\1' + RED),
    # X-Sandbox-Secret: valor
    (re.compile(r'(X-Sandbox-Secret["\'<>:\s&;a-z#0-9]{0,40}?)([A-Za-z0-9_\-\.=+/]{8,})', re.I), None),
    # "clave": "valor"  para claves sensibles (JSON normal o escapado en HTML)
    (re.compile(r'(' + Q + r'(?:contrasena|contraseña|password|nueva_contrasena|token|access_token|refresh_token|secret|sandbox_secret|broker_service_token|access_key)' + Q + r'\s*:\s*' + Q + r')([^"&\\]*)(' + Q + r')', re.I), r'\1' + RED + r'\3'),
]


def limpiar(texto):
    for rx, rep in PATRONES:
        if rep is None:
            texto = rx.sub(lambda m: m.group(1) + RED, texto)
        else:
            texto = rx.sub(rep, texto)
    return texto


def quedan_secretos(texto):
    """Comprobacion posterior: devuelve una lista de tipos de secreto que aun se reconocen."""
    restos = []
    if re.search(r'eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.', texto):
        restos.append('JWT')
    if re.search(r'Bearer\s+(?!\[REDACTADO\]|\[JWT-REDACTADO\])[A-Za-z0-9_\-\.]{8,}', texto):
        restos.append('Bearer')
    if re.search(Q + r'(?:contrasena|password|token|secret)' + Q + r'\s*:\s*' + Q + r'(?!\[REDACTADO\]|\[JWT-REDACTADO\]|' + Q + r')[^"&\\]+', texto, re.I):
        restos.append('valor sensible en JSON')
    return restos


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    ruta = sys.argv[1]
    with open(ruta, encoding='utf-8', errors='surrogateescape', newline='') as f:
        original = f.read()
    nuevo = limpiar(original)
    restos = quedan_secretos(nuevo)
    if restos:
        print('ATENCION: tras limpiar aun se reconocen secretos (' + ', '.join(restos) + '). No subas el reporte.')
        return 1
    if nuevo != original:
        with open(ruta, 'w', encoding='utf-8', errors='surrogateescape', newline='') as f:
            f.write(nuevo)
    print('Reporte limpiado: ' + ruta + (' (con cambios)' if nuevo != original else ' (sin cambios)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
