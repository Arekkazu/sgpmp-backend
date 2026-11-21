#!/usr/bin/env python3
"""TC-M04-G024 - Calidad y disponibilidad del modelo desplegado (RF-66 RNF-02 / RNF-03).

Subcaso 1 (TC-M04-21): F1-score y recall de la clase Riesgo Alto con scikit-learn.
    python tc-m04-g024_calidad_modelo.py f1 --dataset validacion.csv
    El CSV debe tener las columnas y_true,y_pred con las 4 clases de nivel_riesgo (0..3). Falla si F1 < 0.80 o recall(Alto) < 0.85.
Subcaso 2 (TC-M04-22): disponibilidad del nodo Edge >= 99.0 % sin dependencia de red.
    python tc-m04-g024_calidad_modelo.py disponibilidad --url http://<nodo-edge>/<ruta> --minutos 60 --intervalo 5
SCRIPT SIN EJECUTAR: el ambiente de pruebas aun no esta listo.
"""
import argparse
import csv
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone


def cmd_f1(a):
    from sklearn.metrics import classification_report, f1_score, recall_score
    y_true, y_pred = [], []
    with open(a.dataset, newline='', encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            y_true.append(int(row['y_true']))
            y_pred.append(int(row['y_pred']))
    if not y_true:
        print('Dataset vacio'); return 2
    clases = sorted(set(y_true))
    if len(clases) < 4:
        print('ADVERTENCIA: el dataset no contiene las 4 clases de nivel_riesgo (%s)' % clases)
    f1 = f1_score(y_true, y_pred, average=a.promedio, zero_division=0)
    rec_alto = recall_score(y_true, y_pred, labels=[a.clase_alto], average=None, zero_division=0)[0]
    print(classification_report(y_true, y_pred, zero_division=0))
    print('F1 (%s) = %.4f  (umbral %.2f)' % (a.promedio, f1, a.umbral_f1))
    print('Recall clase Alto (%d) = %.4f  (umbral %.2f)' % (a.clase_alto, rec_alto, a.umbral_recall))
    fallos = []
    if f1 < a.umbral_f1: fallos.append('F1 por debajo del umbral')
    if rec_alto < a.umbral_recall: fallos.append('recall de la clase Alto por debajo del umbral')
    print('VEREDICTO:', 'FALLIDO - ' + '; '.join(fallos) if fallos else 'APROBADO')
    return 1 if fallos else 0


def cmd_disp(a):
    ok = total = 0
    fin = time.time() + a.minutos * 60
    log = []
    while time.time() < fin:
        total += 1
        t0 = time.time()
        try:
            req = urllib.request.Request(a.url, data=(a.cuerpo.encode('utf-8') if a.cuerpo else None),
                                         headers={'Content-Type': 'application/json'}, method='POST' if a.cuerpo else 'GET')
            with urllib.request.urlopen(req, timeout=a.timeout) as r:
                exito = 200 <= r.status < 300
        except Exception as e:  # noqa: BLE001 - cualquier fallo cuenta como operacion no exitosa
            exito = False
        ok += 1 if exito else 0
        log.append({'t': datetime.now(timezone.utc).isoformat(), 'ok': exito, 'ms': round((time.time() - t0) * 1000)})
        time.sleep(max(0, a.intervalo - (time.time() - t0)))
    disp = 100.0 * ok / total if total else 0.0
    print('Operaciones exitosas: %d / %d  -> disponibilidad = %.3f %% (umbral %.1f %%)' % (ok, total, disp, a.umbral))
    with open('tc-m04-g024_disponibilidad.json', 'w', encoding='utf-8') as fh:
        json.dump({'ok': ok, 'total': total, 'disponibilidad_pct': disp, 'detalle': log}, fh, ensure_ascii=False, indent=1)
    print('VEREDICTO:', 'APROBADO' if disp >= a.umbral else 'FALLIDO')
    return 0 if disp >= a.umbral else 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd', required=True)
    f = sp.add_parser('f1'); f.set_defaults(fn=cmd_f1)
    f.add_argument('--dataset', required=True); f.add_argument('--umbral-f1', type=float, default=0.80)
    f.add_argument('--umbral-recall', type=float, default=0.85); f.add_argument('--clase-alto', type=int, default=2)
    f.add_argument('--promedio', default='macro', choices=['macro', 'weighted', 'micro'])
    d = sp.add_parser('disponibilidad'); d.set_defaults(fn=cmd_disp)
    d.add_argument('--url', required=True); d.add_argument('--minutos', type=float, default=60); d.add_argument('--intervalo', type=float, default=5)
    d.add_argument('--timeout', type=float, default=3); d.add_argument('--umbral', type=float, default=99.0)
    d.add_argument('--cuerpo', help='JSON del paquete (si se indica, se hace POST)')
    a = p.parse_args()
    sys.exit(a.fn(a))


if __name__ == '__main__':
    main()
