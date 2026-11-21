# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-18 | TEX053 | TC-M07 RF-95/RF-101: colecciones Newman y redaccion de secretos |
"""Redacta secretos de un reporte HTML de Newman (htmlextra) de M07 antes de subirlo a Git.

Uso:  python redactar_m07.py ruta\\resultado_TC-M07-Gxxx.html

1. Reemplaza, de forma literal, el valor de toda variable de entorno QA_* cuyo nombre contenga
   SECRET o CONTRASENA (son las que correr_m07.ps1 deja en la terminal).
2. Redacta los valores JSON de client_secret (incluidos los que genera el sistema al registrar o
   rotar un cliente) y de secretos provistos en las pruebas de borde.
3. Aplica limpiar_reporte.py (JWT, Bearer, X-Sandbox-Secret, contrasena, token...).
Sale con codigo distinto de 0 si tras limpiar aun queda alguno de los valores literales.
"""
import os
import re
import subprocess
import sys

RED = '[REDACTADO]'
Q = r'(?:"|&quot;|&#34;|\\")'


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    ruta = sys.argv[1]
    with open(ruta, encoding='utf-8', errors='surrogateescape', newline='') as f:
        texto = f.read()

    valores = [v for k, v in os.environ.items()
               if k.startswith('QA_') and ('SECRET' in k or 'CONTRASENA' in k) and len(v) >= 6]
    for v in sorted(set(valores), key=len, reverse=True):
        texto = texto.replace(v, RED)

    texto = re.sub(r'(' + Q + r'(?:client_secret|secret_[a-z]+)' + Q + r'\s*:\s*' + Q + r')[^"&\\]+', r'\1' + RED, texto, flags=re.I)

    with open(ruta, 'w', encoding='utf-8', errors='surrogateescape', newline='') as f:
        f.write(texto)

    limpiador = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'limpiar_reporte.py')
    if os.path.exists(limpiador):
        rc = subprocess.call([sys.executable, limpiador, ruta])
        if rc != 0:
            return rc

    with open(ruta, encoding='utf-8', errors='surrogateescape') as f:
        final = f.read()
    restos = [v for v in valores if v in final]
    if restos:
        print('ATENCION: quedan %d valores secretos literales en el reporte.' % len(restos))
        return 1
    print('Reporte limpio de secretos.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
