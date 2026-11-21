# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Script de validacion formal de artefactos promovidos en resultados/   |
import html
import json
import re
from pathlib import Path
from dotenv import dotenv_values

res_dir = Path('tests/Test_Testing/Test_Modulo5/RF-77/TC-M05-G25/resultados')
html_path = res_dir / 'resultado_TC-M05-G25.html'
json_path = res_dir / 'resultado_TC-M05-G25.json'

print('=== 3.a VALIDACION HTML ===')
html_text = html_path.read_text(encoding='utf-8')
match = re.search(r'data-jsonblob="([^"]+)"', html_text)
if match:
    raw_blob = html.unescape(match.group(1))
    blob = json.loads(raw_blob)
    tests = blob.get('tests', {})
    all_tests = []
    if isinstance(tests, dict):
        for k, v in tests.items():
            if isinstance(v, list):
                all_tests.extend(v)
            elif isinstance(v, dict):
                all_tests.append(v)
    elif isinstance(tests, list):
        all_tests = tests
    
    passed_count = sum(1 for t in all_tests if t.get('result') == 'Passed')
    failed_count = sum(1 for t in all_tests if t.get('result') == 'Failed')
    total_html = len(all_tests)
    print(f'HTML data-jsonblob detectado: SI')
    print(f'HTML Tests Totales: {total_html}')
    print(f'HTML Passed: {passed_count}')
    print(f'HTML Failed: {failed_count}')
    failed_test_name = next((t.get('testId') or t.get('nodeid') or t.get('name') for t in all_tests if t.get('result') == 'Failed'), 'N/A')
    print(f'Test fallido en HTML: {failed_test_name}')
else:
    print('ERROR: No se encontro data-jsonblob en el HTML')
    total_html = passed_count = failed_count = -1
    failed_test_name = ''

print('\n=== 3.b VALIDACION JSON ===')
json_data = json.loads(json_path.read_text(encoding='utf-8'))
tc = json_data.get('tc')
summary = json_data.get('summary', {})
checkpoints = json_data.get('checkpoints', [])

print(f'tc: {tc}')
print(f'summary.total: {summary.get("total")}')
print(f'summary.ok: {summary.get("ok")}')
print(f'summary.falla: {summary.get("falla")}')
print(f'summary.veredicto: {summary.get("veredicto")}')
print(f'Total checkpoints: {len(checkpoints)}')

estados_unicos = set(chk.get('estado') for chk in checkpoints)
print(f'Estados unicos en checkpoints: {sorted(list(estados_unicos))} (esperado: [\'FALLA\', \'OK\'])')

fallidos = [chk for chk in checkpoints if chk.get('estado') == 'FALLA']
print(f'Checkpoints con FALLA ({len(fallidos)}):')
for f in fallidos:
    print(f'  Paso: {f.get("paso")}')
    print(f'  Esperado: {f.get("esperado")}')
    print(f'  Obtenido: {f.get("obtenido")[:120]}...')

print('\n=== 3.c COHERENCIA HTML VS JSON ===')
coherente = (total_html == summary.get('total') == 18) and (passed_count == summary.get('ok') == 17) and (failed_count == summary.get('falla') == 1)
print(f'Coherencia cuantitativa: {coherente}')
print(f'El unico fallo en ambos es la auditoria (CA-11 / TC-M05-025): {"test_c02" in failed_test_name and "auditor" in fallidos[0].get("paso").lower()}')

print('\n=== 3.d SCANNER DEL QA-DASHBOARD ===')
scanner_path = Path('qa-dashboard/scanner.py')
print(f'Existe qa-dashboard/scanner.py en el repo: {scanner_path.exists()}')
if not scanner_path.exists():
    veredicto_scanner_equiv = 'Rechazado' if (failed_count > 0 or summary.get('falla', 0) > 0) else 'Aprobado'
    print(f'Comprobacion equivalente manual declarada: Veredicto={veredicto_scanner_equiv} (>=1 fallido -> Rechazado)')

print('\n=== 3.e ESCANEO DE SECRETOS ===')
env = dotenv_values('.env.test')
admin_pwd = env.get('TEST_ADMIN_PASSWORD', '')
sandbox_sec = env.get('TEST_SANDBOX_SECRET', '')
admin_email = env.get('TEST_ADMIN_EMAIL', '')
jwt_pref = 'e' + 'yJ'

patrones_scan = []
for p in [admin_pwd, sandbox_sec, admin_email]:
    if p and len(p) > 3:
        patrones_scan.append(p)
if admin_pwd and len(admin_pwd) > 20:
    patrones_scan.append(admin_pwd[-20:])
if sandbox_sec and len(sandbox_sec) > 20:
    patrones_scan.append(sandbox_sec[-20:])
patrones_scan.append(jwt_pref)

print(f'Patrones a escanear: {len(patrones_scan)} (sin patrones vacios: {all(len(p) > 0 for p in patrones_scan)})')
for fn in [html_path, json_path]:
    t = fn.read_text(encoding='utf-8')
    leaks = [p for p in patrones_scan if p in t]
    print(f'{fn.name}: {len(leaks)} secretos detectados')

print('\n=== 3.f ARCHIVOS DE REPORTE EN RAIZ DEL TC Y RESULTADOS ===')
tc_root = Path('tests/Test_Testing/Test_Modulo5/RF-77/TC-M05-G25')
reportes_raiz = [p.name for p in tc_root.iterdir() if p.is_file() and p.suffix in ('.html', '.json', '.xml', '.txt')]
print(f'Reportes sueltos en raiz de TC: {reportes_raiz}')
archivos_res = [p.name for p in res_dir.iterdir() if p.is_file()]
print(f'Archivos en resultados/: {archivos_res}')
