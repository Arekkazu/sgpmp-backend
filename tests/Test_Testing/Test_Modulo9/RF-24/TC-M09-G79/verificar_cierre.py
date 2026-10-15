"""Cierre de TC-M09-G79: verificacion read-only en TEST, auditoria de secretos y Git.

No escribe en TEST, no ejecuta SQL y no realiza ninguna operacion de escritura de Git.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import helpers_g79 as h

EVID = h.EVID
BACKEND = Path(__file__).resolve().parents[5]
FRONTEND = BACKEND.parent / 'SGPMP-FRONT-END-PWA'

VALORES = [
    (re.compile(r'eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.'), 'JWT'),
    (re.compile(r'Bearer\s+[A-Za-z0-9_.-]{12,}'), 'Authorization con token'),
    (re.compile(r'set-cookie', re.I), 'cabecera de cookie'),
    (re.compile(r'(?:access|refresh)_token"?\s*[:=]\s*"?[A-Za-z0-9_.-]{12,}', re.I), 'token en clave/valor'),
    # La URL del harness no lleva credencial real, pero se vigila el patron igualmente.
    (re.compile(r'postgres(?:ql)?(?:\+\w+)?://(?!harness:harness@127\.0\.0\.1)[^\s"\']+', re.I), 'cadena de conexion'),
]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True).stdout.strip()


def main() -> int:
    token = h.login()
    plan = json.loads((EVID / 'TC-M09-150-descubrimiento.json').read_text(encoding='utf-8'))['plan']
    historial = h.historial_test(token, plan['sensor']['id'])
    igual = (historial['total'] == plan['historialTest']['total']
             and historial['ids'] == [c['id_calibracion'] for c in plan['historialTest']['items']])

    secretos = [v for v in (os.environ.get('QA_PASSWORD'),) if v]
    revisados = []
    for ruta in sorted(EVID.rglob('*')):
        if not ruta.is_file() or ruta.suffix.lower() not in {'.log', '.xml', '.json', '.md'}:
            continue
        texto = ruta.read_text(encoding='utf-8', errors='replace')
        revisados.append({
            'archivo': str(ruta.relative_to(EVID)).replace('\\', '/'),
            'bytes': len(texto),
            'secretos': [n for p, n in VALORES if p.search(texto)],
            'credencialesEnClaro': sum(1 for s in secretos if s in texto),
        })
    sucios = [r for r in revisados if r['secretos'] or r['credencialesEnClaro']]

    h.guardar('verificacion-final-readonly.json', {
        'sensor': plan['sensor'], 'dispositivo': plan['dispositivo'],
        'historialTestAlInicio': plan['historialTest']['total'],
        'historialTestAlCierre': historial,
        'testSinEscrituras': igual,
        'soloLectura': True, 'sqlEjecutado': 'ninguno',
        'postgresqlDirectoUtilizado': False,
    })
    h.guardar('seguridad-evidencias.json', {
        'revisados': revisados, 'limpio': not sucios,
        'criterio': 'Se marcan solo valores de secreto. La URL del harness no contiene credenciales reales.',
    })
    h.guardar('git-final.json', {
        'backend': {'rama': _git(BACKEND, 'branch', '--show-current'),
                    'sha': _git(BACKEND, 'rev-parse', 'HEAD'),
                    'diffStat': _git(BACKEND, 'diff', '--stat') or '(vacio)',
                    'untrackedG79': len([x for x in _git(BACKEND, 'ls-files', '--others', '--exclude-standard').splitlines() if 'TC-M09-G79' in x]),
                    'untrackedFueraDeG79': len([x for x in _git(BACKEND, 'ls-files', '--others', '--exclude-standard').splitlines() if 'TC-M09-G79' not in x])},
        'frontend': {'rama': _git(FRONTEND, 'branch', '--show-current'),
                     'sha': _git(FRONTEND, 'rev-parse', 'HEAD'),
                     'diffStat': _git(FRONTEND, 'diff', '--stat') or '(vacio)',
                     'hallazgoFueraDeAlcance': 'testing/test_testing/Modulo9/RF-17/TC-M09-G22/.gitkeep sigue eliminado; observado desde G75. No se revirtio ni se restauro.'},
        'soloLectura': True, 'operacionesDeEscrituraGit': 'ninguna',
    })
    print('historial TEST al inicio:', plan['historialTest']['total'], '| al cierre:', historial['total'],
          '| sin escrituras:', igual)
    print('archivos revisados:', len(revisados), '| con valores de secreto:',
          [r['archivo'] for r in sucios] or 'ninguno')
    print('backend diff:', _git(BACKEND, 'diff', '--stat') or '(vacio)')
    return 0 if igual and not sucios else 1


if __name__ == '__main__':
    raise SystemExit(main())
