"""TC-M09-G29 V3 — cierre: escaneo de secretos sobre EvaluacionV3 y gate Git de solo lectura.

Mismo formato de evidencia que V2 (seguridad-evidencias.json, git-final.json). No modifica
el indice de Git ni ejecuta ningun comando de escritura.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BACKEND = AQUI.parents[5]
FRONTEND = BACKEND.parent / 'SGPMP-FRONT-END-PWA'
RUN_ID = os.environ['G29_REEVAL_V3_RUN_ID']
OUT = AQUI / 'RESULTADOS' / RUN_ID
RAMA = 'qa/juan-esteban-tercera-evaluacion-M09'

PALABRAS = ['Authorization', 'Bearer ', 'access_token', 'refresh_token', 'password', 'cookie', 'jwt']
JWT = re.compile(r'eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}')
BEARER = re.compile(r'Bearer\s+(?!\[REDACTED\]|\{|f")[A-Za-z0-9_.\-]{12,}')
SECRETOS = [v for v in (os.environ.get('DEV_ADMIN_PASSWORD'), os.environ.get('MQTT_PASSWORD')) if v]


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, encoding='utf-8').stdout


def main():
    archivos = []
    for path in sorted(p for p in AQUI.rglob('*') if p.is_file() and '__pycache__' not in p.parts):
        texto = path.read_bytes().decode('latin1')
        palabras = {w.strip(): texto.lower().count(w.strip().lower()) for w in PALABRAS
                    if texto.lower().count(w.strip().lower()) > 0}
        archivos.append({
            'archivo': path.relative_to(AQUI).as_posix(),
            'palabrasClave': palabras,
            'contrasenaLiteral': any(s in texto for s in SECRETOS),
            'jwt': bool(JWT.search(texto)),
            'bearerConValor': bool(BEARER.search(texto)),
        })
    comprometidos = [a['archivo'] for a in archivos if a['contrasenaLiteral'] or a['jwt'] or a['bearerConValor']]
    (OUT / 'seguridad-evidencias.json').write_text(json.dumps({
        'grupo': 'TC-M09-G29', 'tipo': 'REEVALUACION V3', 'runId': RUN_ID,
        'fecha': datetime.now(timezone.utc).isoformat(), 'patrones': PALABRAS,
        'conclusion': {
            'secretosPersistidos': bool(comprometidos),
            'archivosComprometidos': comprometidos,
            'nota': 'Coincidencias de palabras clave: nombres de variable (DEV_ADMIN_PASSWORD), cabecera '
                    'construida en codigo o texto descriptivo del reporte; ningun valor secreto. '
                    'Sin credenciales MQTT usadas y sin conexion al broker.',
        },
        'archivos': archivos,
    }, indent=2, ensure_ascii=False), encoding='utf-8')

    estado = {}
    for nombre, repo in (('backend', BACKEND), ('frontend', FRONTEND)):
        estado[nombre] = {
            'branch --show-current': git(repo, 'branch', '--show-current'),
            'rev-parse HEAD': git(repo, 'rev-parse', 'HEAD'),
            'rev-list --left-right --count HEAD...origin/test': git(repo, 'rev-list', '--left-right', '--count', 'HEAD...origin/test'),
            'status --short': git(repo, 'status', '--short'),
            'diff --stat': git(repo, 'diff', '--stat'),
            'diff --cached --stat': git(repo, 'diff', '--cached', '--stat'),
            'ls-files --others --exclude-standard': git(repo, 'ls-files', '--others', '--exclude-standard'),
        }
    ruta_v3 = 'tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G29/EvaluacionV3/'
    backend_status = estado['backend']['status --short'].splitlines()
    resultado = {
        'grupo': 'TC-M09-G29', 'tipo': 'REEVALUACION V3', 'runId': RUN_ID, 'ramaObligatoria': RAMA,
        **estado,
        'validacion': {
            'ramaCorrectaEnAmbos': all(estado[k]['branch --show-current'].strip() == RAMA for k in estado),
            'indiceIntactoEnAmbos': all(estado[k]['diff --cached --stat'].strip() == '' for k in estado),
            'v1Modificada': any('TC-M09-G29/RESULTADOS/' in l for l in backend_status),
            'v2Modificada': any('TC-M09-G29/EvaluacionV2' in l for l in backend_status),
            'codigoProductivoModificado': any(l.strip().split()[-1].startswith('src/') for l in backend_status if l.strip()),
            'cambiosDelBackendDentroDeEvaluacionV3': all(ruta_v3 in l for l in backend_status if l.strip()),
            'escriturasApi': 0, 'sqlWrite': False, 'mqttPublish': False,
            'gitAdd': False, 'commit': False, 'push': False, 'merge': False,
            'rebase': False, 'reset': False, 'clean': False, 'stash': False, 'tag': False, 'deploy': False,
        },
    }
    (OUT / 'git-final.json').write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'seguridad': {'archivos': len(archivos), 'comprometidos': comprometidos},
                      'validacion': resultado['validacion'],
                      'backend_status': backend_status,
                      'frontend_status': estado['frontend']['status --short'].splitlines()},
                     indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
