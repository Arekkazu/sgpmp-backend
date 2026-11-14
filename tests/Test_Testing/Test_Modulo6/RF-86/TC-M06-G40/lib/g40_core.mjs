import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const CASOS = ['TC-M06-018'];
export const IDS = ['G40-API-018-01'];
export const CONTRATO = JSON.parse(fs.readFileSync(path.join(DIR, 'pruebas', 'contrato_g40.json'), 'utf8'));
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 150, duracion_segundos: 1800,
  logins_fuera_run: 2, eventos_m02: 1, procesamientos: 1, cambios_matriz: 3 });

export function entrada(id) {
  const p = CONTRATO.peticiones.find(x => x.id === id);
  if (!p) throw Error(`PeticiÃ³n fuera del contrato: ${id}`);
  return p;
}
export function validarActor(id, actor) {
  const p = entrada(id), rol = CONTRATO.roles[actor];
  if (!rol || p.actor !== actor) throw Error(`Actor sin permiso para ${id}`);
  if (p.permiso === 'autenticado:0') return true;
  const [recurso, accion] = p.permiso.split(':');
  if (!rol.permisos[recurso]?.includes(Number(accion))) throw Error(`Permiso ausente para ${id}`);
  return true;
}
function validarCampos(plantilla, valor, ruta) {
  if (typeof plantilla === 'string') {
    const tipos = plantilla.split('|');
    const tipo = valor === null ? 'null' : Array.isArray(valor) ? 'array' : typeof valor;
    if (tipos.includes('decimal') && tipo === 'string' && /^-?\d+(\.\d+)?$/.test(valor)) return;
    if (tipos.includes('decimal') && tipo === 'number' && !Number.isFinite(valor))
      throw Error(`Tipo fuera del contrato: ${ruta}: esperado ${plantilla}, llegÃ³ nÃºmero no finito`);
    if (!tipos.includes(tipo)) throw Error(`Tipo fuera del contrato: ${ruta}: esperado ${plantilla}, llegÃ³ ${tipo}`);
    return;
  }
  if (Array.isArray(plantilla)) {
    if (!Array.isArray(valor)) throw Error(`Se esperaba lista: ${ruta}`);
    for (const item of valor) validarCampos(plantilla[0], item, `${ruta}[]`);
    return;
  }
  if (!valor || typeof valor !== 'object' || Array.isArray(valor)) throw Error(`Se esperaba objeto: ${ruta}`);
  for (const k of Object.keys(valor)) if (!(k in plantilla)) throw Error(`Campo no declarado: ${ruta}.${k}`);
  for (const [k, v] of Object.entries(plantilla)) {
    if (!(k in valor)) throw Error(`Campo ausente del mock: ${ruta}.${k}`);
    validarCampos(v, valor[k], `${ruta}.${k}`);
  }
}
export function validarMock(id, cuerpo) {
  const p = entrada(id);
  validarCampos(p.tipo === 'array' ? [p.campos] : p.campos, cuerpo, id);
  if (id === 'cadena' && cuerpo.eslabones !== null)
    validarCampos(p.subcampos_eslabones, cuerpo.eslabones, 'cadena.eslabones');
  return true;
}
export function validarDecimales(id, cuerpo) {
  const revisar = (t, v, ruta) => {
    if (typeof t === 'string') {
      if (t.split('|').includes('decimal') && v !== null &&
        !(typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v)) &&
        !(t.split('|').includes('number') && typeof v === 'number' && Number.isFinite(v)))
        throw Error(`Decimal invÃ¡lido: ${ruta}; esperado ${t}, llegÃ³ ${typeof v}`);
    } else if (Array.isArray(t)) {
      for (const x of v ?? []) revisar(t[0], x, `${ruta}[]`);
    } else if (t && typeof t === 'object' && v && typeof v === 'object') {
      for (const [k, x] of Object.entries(t)) revisar(x, v[k], `${ruta}.${k}`);
    }
  };
  const p = entrada(id);
  revisar(p.tipo === 'array' ? [p.campos] : p.campos, cuerpo, id);
  if (id === 'periodos') for (const periodo of cuerpo) {
    const precios = periodo.ultimo_cierre?.precios_congelados ?? [];
    for (const precio of precios) revisar(p.subcampos_ultimo_cierre.precios_congelados[0], precio,
      'periodos[].ultimo_cierre.precios_congelados[]');
  }
  return true;
}
export function mock(id) {
  const p = entrada(id);
  const crear = t => typeof t === 'string' ? ({ number: 1, decimal: '1.00', string: 'x', boolean: false, object: {} })[t.split('|')[0]] ?? null
    : Array.isArray(t) ? [crear(t[0])] : Object.fromEntries(Object.entries(t).map(([k, v]) => [k, crear(v)]));
  const cuerpo = p.tipo === 'array' ? [crear(p.campos)] : crear(p.campos);
  if (id === 'cadena') cuerpo.eslabones = crear(p.subcampos_eslabones);
  validarMock(id, cuerpo);
  return cuerpo;
}
export function leerCampo(id, cuerpo, ruta) {
  const partes = ruta.split('.');
  let t = entrada(id).tipo === 'array' ? [entrada(id).campos] : entrada(id).campos;
  let v = cuerpo;
  for (const parte of partes) {
    if (parte === '[]') { if (!Array.isArray(t)) throw Error(`Campo ausente del contrato: ${id}.${ruta}`);
      t = t[0]; v = v?.[0]; continue; }
    if (!t || typeof t !== 'object' || !(parte in t)) throw Error(`Campo ausente del contrato: ${id}.${ruta}`);
    t = t[parte]; v = v?.[parte];
  }
  return v;
}
// Mantener una escala decimal explÃ­cita; nunca sumar importes con Number.
export function monto(x) {
  const s = String(x);
  if (x == null || !/^-?\d+(\.\d+)?$/.test(s)) throw Error('Importe decimal invÃ¡lido');
  const [entero, fraccion = ''] = s.replace('-', '').split('.');
  return { n: BigInt(entero + fraccion) * (s.startsWith('-') ? -1n : 1n), escala: fraccion.length };
}
const escalar = (x, escala) => x.n * 10n ** BigInt(escala - x.escala);
export function igual(a, b) {
  try { const x = monto(a), y = monto(b), escala = Math.max(x.escala, y.escala);
    return escalar(x, escala) === escalar(y, escala);
  } catch { return false; }
}
export const idsNuevos = (antes, despues, campo) => {
  const base = new Set(antes.map(x => String(x[campo])));
  return despues.filter(x => !base.has(String(x[campo])));
};
export function vigente(precios, especie, hoy) {
  const lista = precios.filter(p => Number(p.id_especie) === Number(especie) && p.categoria === 'PESO_KG' &&
    Number(p.precio_unitario)>0 && p.fecha_vigencia <= hoy && (!p.fecha_vencimiento || p.fecha_vencimiento >= hoy));
  for (const fuente of ['MERCADO_ACTIVO', 'UPRA', 'ESTIMADA']) {
    const p = lista.filter(x => x.fuente === fuente).sort((a, b) =>
      String(b.fecha_vigencia).localeCompare(String(a.fecha_vigencia)) || b.id_precio_mercado - a.id_precio_mercado)[0];
    if (p) return p;
  }
  return null;
}
export function periodoDestino(periodos, nit, hoy) {
  const propios = periodos.filter(p => String(p.numero_id_tributaria) === String(nit));
  const actual = propios.find(p => p.fecha_inicio <= hoy && p.fecha_fin >= hoy);
  return actual?.estado === 'ABIERTO' ? actual : null;
}
export function seleccionarCandidatos(candidatos, cantidad = 4, precondicion = null) {
  const motivos = [], elegibles = [];
  for (const c of candidatos) {
    const faltan = [];
    if (!/bovin/i.test(c.especie ?? '')) faltan.push('no es bovino');
    if (c.tipo !== 'INDIVIDUAL') faltan.push('no es activo individual');
    if (c.estado !== 'ACTIVO') faltan.push('estado distinto de ACTIVO para pesaje');
    if (c.valorado_por_costo) faltan.push('valorado por costo');
    if (!c.periodo || c.periodo.estado !== 'ABIERTO') faltan.push('sin perÃ­odo destino ABIERTO');
    if (!c.precio) faltan.push('sin precio vigente');
    if (!c.calculo || c.calculo.estado !== 'CALCULADO') faltan.push('sin cÃ¡lculo previo');
    if (!(Number(c.peso) > 0)) faltan.push('sin peso actual positivo');
    motivos.push({ activo: c.id_activo_biologico, descartado: faltan.length > 0, motivos: faltan });
    if (!faltan.length) elegibles.push(c);
  }
  elegibles.sort((a, b) => Number(b.calculo.id_precio_mercado === b.precio.id_precio_mercado) -
    Number(a.calculo.id_precio_mercado === a.precio.id_precio_mercado) || a.id_activo_biologico - b.id_activo_biologico);
  const porPeriodo = new Map();
  for (const c of elegibles) {
    const p = c.periodo.id_periodo_contable;
    if (!porPeriodo.has(p)) porPeriodo.set(p, []);
    porPeriodo.get(p).push(c);
  }
  const grupos = [...porPeriodo.values()].filter(xs => xs.length >= cantidad);
  grupos.sort((a, b) => b.filter(x => x.calculo.id_precio_mercado === x.precio.id_precio_mercado).length -
    a.filter(x => x.calculo.id_precio_mercado === x.precio.id_precio_mercado).length ||
    Number(a[0].periodo.id_periodo_contable) - Number(b[0].periodo.id_periodo_contable));
  const grupo = (precondicion && grupos.find(xs => xs.some(x =>
    Number(x.id_activo_biologico) === precondicion.id_activo_biologico &&
    Number(x.dispositivo) === precondicion.id_dispositivo_iot))) ?? grupos[0] ?? [];
  const conDispositivo = (precondicion && grupo.find(x =>
    Number(x.id_activo_biologico) === precondicion.id_activo_biologico &&
    Number(x.dispositivo) === precondicion.id_dispositivo_iot)) ?? grupo.find(x => x.dispositivo);
  const elegido = conDispositivo ? [conDispositivo, ...grupo.filter(x => x !== conDispositivo)].slice(0, cantidad) :
    grupo.slice(0, cantidad);
  if (!grupo.length) for (const m of motivos) if (!m.descartado)
    m.motivos.push('menos de cuatro elegibles en el mismo perÃ­odo');
  return { elegido, motivos };
}
// Decimal fijo de cuatro posiciones: reproduce q4(ROUND_HALF_UP) de nic41.py.
export function q4(x) {
  const d = monto(x), shift = d.escala - 4;
  if (shift <= 0) return d.n * 10n ** BigInt(-shift);
  const divisor = 10n ** BigInt(shift), positivo = d.n >= 0n;
  const absoluto = positivo ? d.n : -d.n;
  const n = absoluto / divisor + (absoluto % divisor * 2n >= divisor ? 1n : 0n);
  return positivo ? n : -n;
}
export function decimal4(n) {
  const signo = n < 0n ? '-' : '';
  const x = (n < 0n ? -n : n).toString().padStart(5, '0');
  return `${signo}${x.slice(0, -4)}.${x.slice(-4)}`;
}
// Predictor puro: los cinco insumos son explÃ­citos y el resultado no depende de API ni reloj.
export function predecirComponentes({magnitud_anterior, magnitud_actual, precio_unitario,
  pct_transporte, pct_comisiones, pct_impuestos, otros='0', valor_neto_anterior, hubo_evento=true}) {
  const redondear = (n, d) => n >= 0n ? (n + d / 2n) / d : -((-n + d / 2n) / d);
  const bruto = redondear(q4(precio_unitario) * q4(magnitud_actual), 10000n);
  const [transporte,comisiones,impuestos] = [pct_transporte, pct_comisiones, pct_impuestos]
    .map(p=>redondear(bruto * q4(p ?? '0'), 10000n));
  const neto = bruto - transporte - comisiones - impuestos - q4(otros);
  const previo = q4(valor_neto_anterior);
  const ajustado = hubo_evento ? redondear(neto * q4(magnitud_anterior), q4(magnitud_actual)) : neto;
  return {bruto:decimal4(bruto),transporte:decimal4(transporte),comisiones:decimal4(comisiones),
    impuestos:decimal4(impuestos),neto: decimal4(neto),
    tb: decimal4(neto - ajustado), pm: decimal4(ajustado - previo)};
}
export function truncar2(x) {
  const n = q4(x), absoluto = n < 0n ? -n : n;
  return `${absoluto / 10000n}.${String(absoluto % 10000n / 100n).padStart(2, '0')}`;
}
export function redondear2(x) {
  const n = q4(x), absoluto = n < 0n ? -n : n;
  const centavos = (absoluto + 50n) / 100n;
  return `${centavos / 100n}.${String(centavos % 100n).padStart(2, '0')}`;
}
export function resolverMatriz(matriz, tipo, sentido, especie, subtipo = null) {
  return matriz.filter(x => x.tipo_hecho === tipo && x.sentido === sentido &&
    (Number(x.id_especie) === Number(especie) || x.id_especie === null) &&
    (x.subtipo_costo === subtipo || x.subtipo_costo === null))
    .sort((a, b) => Number(a.id_especie === null) - Number(b.id_especie === null) ||
      Number(a.subtipo_costo === null) - Number(b.subtipo_costo === null))[0] ?? null;
}
export function estructuraLineas(antes, despues, nuevas) {
  const errores = [], vistos = new Set();
  const previa = new Map(antes.map(x => [String(x.id_linea_asiento_nic41), x]));
  for (const l of despues) {
    const ident = l.id_linea_asiento_nic41, clave = String(ident);
    if (ident == null || clave === '' || vistos.has(clave)) errores.push(`id_linea duplicado o ausente: ${clave}`);
    vistos.add(clave);
    for (const campo of ['tipo_hecho', 'fecha_hecho', 'numero_id_tributaria'])
      if (typeof l[campo] !== 'string' || !l[campo]) errores.push(`${clave}: ${campo}`);
    for (const campo of ['id_periodo_contable', 'id_activo_biologico', 'id_especie', 'id_finca', 'id_origen'])
      if (!Number.isInteger(l[campo]) || l[campo] <= 0) errores.push(`${clave}: ${campo}`);
    if (typeof l.es_estimacion !== 'boolean') errores.push(`${clave}: es_estimacion`);
    try { if (q4(l.valor) <= 0n || q4(l.valor) % 100n !== 0n) errores.push(`${clave}: valor`); }
    catch { errores.push(`${clave}: valor`); }
    if (nuevas.includes(l) && l.estado === 'REGISTRADA' &&
      (!l.cuenta_debito || !l.cuenta_credito || l.cuenta_debito === l.cuenta_credito)) errores.push(`${clave}: cuentas`);
    const p = previa.get(clave);
    if (p && (p.id_origen !== l.id_origen || p.tipo_hecho !== l.tipo_hecho || p.valor !== l.valor))
      errores.push(`${clave}: identidad cambiada`);
  }
  for (const clave of previa.keys()) if (!vistos.has(clave)) errores.push(`${clave}: id_linea cambiÃ³ o desapareciÃ³`);
  return errores;
}

