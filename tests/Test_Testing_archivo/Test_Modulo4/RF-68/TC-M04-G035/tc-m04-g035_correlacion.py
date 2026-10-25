#!/usr/bin/env python3
"""TC-M04-G035 - Subcaso 2 (TC-M04-24): correlacion >= 0.75 entre las estimaciones retrospectivas del modelo de contagio
y los eventos sanitarios reales (RF-68 RNF-01).

  python tc-m04-g035_correlacion.py --estimaciones estimaciones.csv --eventos eventos.csv [--umbral 0.75] [--freq D]

estimaciones.csv : fecha,id_lote,probabilidad_contagio
eventos.csv      : fecha,id_lote,evento   (evento = 1 si hubo brote/evento sanitario confirmado, o el numero de casos)
Se agrega por lote y periodo (--freq, por defecto dia), se cruzan ambas series y se calcula Pearson (criterio) y Spearman (informativo).
Falla (codigo 1) si Pearson < umbral. SCRIPT SIN EJECUTAR: el ambiente de pruebas aun no esta listo.
"""
import argparse
import sys

import pandas as pd
from scipy import stats


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--estimaciones', required=True); p.add_argument('--eventos', required=True)
    p.add_argument('--umbral', type=float, default=0.75); p.add_argument('--freq', default='D')
    a = p.parse_args()
    est = pd.read_csv(a.estimaciones, parse_dates=['fecha'], encoding='utf-8-sig')
    ev = pd.read_csv(a.eventos, parse_dates=['fecha'], encoding='utf-8-sig')
    est['periodo'] = est['fecha'].dt.to_period(a.freq)
    ev['periodo'] = ev['fecha'].dt.to_period(a.freq)
    e = est.groupby(['id_lote', 'periodo'], as_index=False)['probabilidad_contagio'].max()
    v = ev.groupby(['id_lote', 'periodo'], as_index=False)['evento'].max()
    m = e.merge(v, on=['id_lote', 'periodo'], how='left').fillna({'evento': 0})
    if len(m) < 3 or m['evento'].nunique() < 2:
        print('Datos insuficientes para correlacionar (n=%d, valores distintos de evento=%d)' % (len(m), m['evento'].nunique())); return 2
    pear, p_p = stats.pearsonr(m['probabilidad_contagio'], m['evento'])
    spear, p_s = stats.spearmanr(m['probabilidad_contagio'], m['evento'])
    print('n = %d pares lote-periodo' % len(m))
    print('Pearson  r = %.4f (p=%.4g)  umbral %.2f' % (pear, p_p, a.umbral))
    print('Spearman r = %.4f (p=%.4g)  (informativo)' % (spear, p_s))
    ok = pear >= a.umbral
    print('VEREDICTO:', 'APROBADO' if ok else 'FALLIDO - correlacion por debajo de %.2f' % a.umbral)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
