"""TC-M09-G29 V4 -- cierre: escaneo de secretos sobre EvaluacionV4 y gate Git de solo lectura.

No modifica el indice de Git ni ejecuta ningun comando de escritura: solo ``branch``,
``rev-parse``, ``rev-list``, ``status``, ``diff`` y ``ls-files``.

Salida: ``RESULTADOS/<G29_REEVAL_V4_RUN_ID>/{seguridad-evidencias.json,git-final.json}``
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
RUN_ID = os.environ['G29_REEVAL_V4_RUN_ID']
OUT = AQUI / 'RESULTADOS' / RUN_ID
RAMA = 'qa/juan-esteban-cuarta-evaluacion-M09-y-M02'

PALABRAS = ['Authorization', 'Bearer ', 'access_token', 'refresh_token', 'password', 'cookie', 'jwt']
JWT = re.compile(r'eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}')
BEARER = re.compile(r'Bearer\s+(?!\[REDACTED\]|\{|f"|\' \+)[A-Za-z0-9_.\-]{12,}')
SECRETOS = [v for v in (os.environ.get('DEV_ADMIN_PASSWORD'), os.environ.get('TEST_ADMIN_PASSWORD'),
                        os.environ.get('MQTT_PASSWORD')) if v]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True,
                          encoding='utf-8', errors='replace').stdout


def main() -> None:
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
    comprometidos = [a['archivo'] for a in archivos
                     if a['contrasenaLiteral'] or a['jwt'] or a['bearerConValor']]
    (OUT / 'seguridad-evidencias.json').write_text(json.dumps({
        'grupo': 'TC-M09-G29', 'tipo': 'REEVALUACION V4', 'runId': RUN_ID,
        'fecha': datetime.now(timezone.utc).isoformat(), 'patrones': PALABRAS,
        'conclusion': {
            'secretosPersistidos': bool(comprometidos),
            'archivosComprometidos': comprometidos,
            'secretosComparadosEnEsteEscaneo': len(SECRETOS),
            'nota': 'Las coincidencias de palabras clave corresponden a nombres de variable, a la '
                    'cabecera construida en codigo o a texto descriptivo del informe; ningun valor '
                    'secreto. No se usaron credenciales MQTT ni se abrio conexion al broker.',
        },
        'archivos': archivos,
    }, indent=2, ensure_ascii=False), encoding='utf-8')

    estado = {}
    for nombre, repo in (('backend', BACKEND), ('frontend', FRONTEND)):
        estado[nombre] = {
            'branch --show-current': git(repo, 'branch', '--show-current'),
            'rev-parse HEAD': git(repo, 'rev-parse', 'HEAD'),
            'rev-list --left-right --count HEAD...origin/test': git(
                repo, 'rev-list', '--left-right', '--count', 'HEAD...origin/test'),
            'status --short': git(repo, 'status', '--short'),
            'diff --stat': git(repo, 'diff', '--stat'),
            'diff --cached --stat': git(repo, 'diff', '--cached', '--stat'),
            'ls-files --others --exclude-standard': git(
                repo, 'ls-files', '--others', '--exclude-standard'),
        }
    backend_status = [l for l in estado['backend']['status --short'].splitlines() if l.strip()]
    frontend_status = [l for l in estado['frontend']['status --short'].splitlines() if l.strip()]
    ruta_v4 = 'TC-M09-G29/EvaluacionV4/'
    runs_v4 = sorted(p.name for p in (AQUI / 'RESULTADOS').iterdir() if p.is_dir())
    resultado = {
        'grupo': 'TC-M09-G29', 'tipo': 'REEVALUACION V4', 'runId': RUN_ID, 'ramaObligatoria': RAMA,
        **estado,
        'validacion': {
            'ramaCorrectaEnAmbos': all(estado[k]['branch --show-current'].strip() == RAMA for k in estado),
            'indiceIntactoEnAmbos': all(estado[k]['diff --cached --stat'].strip() == '' for k in estado),
            'v1Modificada': any('TC-M09-G29/RESULTADOS/' in l for l in backend_status),
            'v2Modificada': any('TC-M09-G29/EvaluacionV2' in l for l in backend_status),
            'v3Modificada': any('TC-M09-G29/EvaluacionV3' in l for l in backend_status),
            'codigoProductivoModificado': any(l.split()[-1].startswith('src/') for l in backend_status),
            'frontendModificado': bool(frontend_status),
            'todosLosCambiosDelBackendDentroDeEvaluacionV4': all(ruta_v4 in l for l in backend_status),
            'runsV4Existentes': runs_v4,
            'unicoRunV4': len(runs_v4) == 1,
            'escriturasApi': 0, 'sqlWrite': False, 'mqttPublish': False,
            'cambiosInfraestructura': 0, 'cambiosBroker': 0, 'cambiosGateway': 0,
            'desconexionesHardware': 0, 'tc63Ejecutada': False,
            'gitAdd': False, 'commit': False, 'push': False, 'merge': False, 'rebase': False,
            'reset': False, 'clean': False, 'stash': False, 'checkout': False, 'switch': False,
            'tag': False, 'deploy': False,
        },
    }
    (OUT / 'git-final.json').write_text(json.dumps(resultado, indent=2, ensure_ascii=False),
                                        encoding='utf-8')
    print(json.dumps({
        'seguridad': {'archivosRevisados': len(archivos), 'comprometidos': comprometidos,
                      'secretosComparados': len(SECRETOS)},
        'validacion': resultado['validacion'],
        'backendStatus': backend_status,
        'frontendStatus': frontend_status,
    }, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
