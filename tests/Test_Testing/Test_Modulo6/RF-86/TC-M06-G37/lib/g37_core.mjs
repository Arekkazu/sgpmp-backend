import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const CASOS = ['TC-M06-011', 'TC-M06-013'];
export const IDS = ['G37-API-011-01', 'G37-API-013-01'];
export const CONTRATO = JSON.parse(fs.readFileSync(path.join(DIR, 'pruebas', 'contrato_g37.json'), 'utf8'));
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 150, duracion_segundos: 1800,
  logins_fuera_run: 2, eventos_m02: 5, precios: 2, procesamientos: 5, cambios_estado: 1,
  acumulados: 4, verificaciones_rf91: 1 });

export function entrada(id) {
  const p = CONTRATO.peticiones.find(x => x.id === id);
  if (!p) throw Error(`Petición fuera del contrato: ${id}`);
  return p;
}
export function validarActor(id, actor) {
  const p = entrada(id), rol = CONTRATO.roles[actor];
  if (!rol || p.actor !== actor) throw Error(`Actor sin permiso para ${id}`);
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
      throw Error(`Tipo fuera del contrato: ${ruta}: esperado ${plantilla}, llegó número no finito`);
    if (!tipos.includes(tipo)) throw Error(`Tipo fuera del contrato: ${ruta}: esperado ${plantilla}, llegó ${tipo}`);
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
        throw Error(`Decimal inválido: ${ruta}; esperado ${t}, llegó ${typeof v}`);
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
  if (id === 'periodos') cuerpo[0].ultimo_cierre = null;
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
// Mantener una escala decimal explícita; nunca sumar importes con Number.
export function monto(x) {
  const s = String(x);
  if (x == null || !/^-?\d+(\.\d+)?$/.test(s)) throw Error('Importe decimal inválido');
  const [entero, fraccion = ''] = s.replace('-', '').split('.');
  return { n: BigInt(entero + fraccion) * (s.startsWith('-') ? -1n : 1n), escala: fraccion.length };
}
const escalar = (x, escala) => x.n * 10n ** BigInt(escala - x.escala);
export function igual(a, b) {
  try { const x = monto(a), y = monto(b), escala = Math.max(x.escala, y.escala);
    return escalar(x, escala) === escalar(y, escala);
  } catch { return false; }
}
const sumar = valores => {
  const xs = valores.map(x => typeof x === 'object' && x !== null && typeof x.n === 'bigint' ? x : monto(x));
  const escala = Math.max(0, ...xs.map(x => x.escala));
  return { n: xs.reduce((n, x) => n + escalar(x, escala), 0n), escala };
};
const diferenciaIgual = (despues, antes, sumandos) => {
  try { const a = monto(antes), b = monto(despues), s = sumar(sumandos);
    const escala = Math.max(a.escala, b.escala, s.escala);
    return escalar(b, escala) - escalar(a, escala) === escalar(s, escala);
  } catch { return false; }
};
export const idsNuevos = (antes, despues, campo) => {
  const base = new Set(antes.map(x => String(x[campo])));
  return despues.filter(x => !base.has(String(x[campo])));
};
export function vigente(precios, especie, hoy) {
  const lista = precios.filter(p => Number(p.id_especie) === Number(especie) && p.categoria === 'PESO_KG' &&
    p.fecha_vigencia <= hoy && (!p.fecha_vencimiento || p.fecha_vencimiento >= hoy));
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
  if (actual?.estado === 'ABIERTO') return actual;
  return null;
}
export function seleccionarCandidatos(candidatos, cantidad = 4, precondicion = null) {
  const motivos = [], elegibles = [];
  for (const c of candidatos) {
    const faltan = [];
    if (!/bovin/i.test(c.especie ?? '')) faltan.push('no es bovino');
    if (c.tipo !== 'INDIVIDUAL') faltan.push('no es activo individual');
    if (c.estado !== 'ACTIVO') faltan.push('estado distinto de ACTIVO para pesaje');
    if (c.valorado_por_costo) faltan.push('valorado por costo');
    if (!c.periodo || c.periodo.estado !== 'ABIERTO') faltan.push('sin período destino ABIERTO');
    if (!c.precio) faltan.push('sin precio vigente');
    if (!c.calculo || c.calculo.estado !== 'CALCULADO') faltan.push('sin cálculo previo');
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
    m.motivos.push('menos de cuatro elegibles en el mismo período');
  return { elegido, motivos };
}
export function oraculo011({ antes, despues, variaciones, otroAntes, otroDespues }) {
  if (!antes || !despues || !otroAntes || !otroDespues)
    return { estado: 'RECHAZADO', severidad: 'ALTA', motivo: 'No responde el acumulado público comparable.' };
  const campos = { GANANCIA_TRANSFORMACION_BIOLOGICA: 'ganancia_transformacion_biologica',
    PERDIDA_TRANSFORMACION_BIOLOGICA: 'perdida_transformacion_biologica',
    GANANCIA_PRECIO_MERCADO: 'ganancia_precio_mercado',
    PERDIDA_PRECIO_MERCADO: 'perdida_precio_mercado' };
  const fallos = [];
  for (const [tipo, campo] of Object.entries(campos)) {
    const xs = variaciones.filter(v => v.tipo === tipo).map(v => {
      const x = monto(v.monto_variacion); return { n: x.n < 0n ? -x.n : x.n, escala: x.escala };
    });
    if (!diferenciaIgual(despues.componentes?.[campo], antes.componentes?.[campo], xs)) fallos.push(campo);
  }
  const ganancias = variaciones.filter(v => v.tipo.startsWith('GANANCIA_')).map(v => v.monto_variacion);
  const perdidas = variaciones.filter(v => v.tipo.startsWith('PERDIDA_')).map(v => {
    const x = monto(v.monto_variacion); return { n: x.n < 0n ? -x.n : x.n, escala: x.escala };
  });
  for (const [campo, xs] of [['total_ingresos', ganancias], ['total_gastos', perdidas]])
    if (!diferenciaIgual(despues[campo], antes[campo], xs)) fallos.push(campo);
  if (JSON.stringify(otroAntes) !== JSON.stringify(otroDespues)) fallos.push('otro período');
  return { estado: fallos.length ? 'RECHAZADO' : 'APROBADO',
    severidad: fallos.length >= 6 ? 'ALTA' : fallos.length ? 'MEDIA' : null,
    motivo: fallos.length ? `Acumulado discordante: ${fallos.join(', ')}.` :
      'Los componentes y totales cambian exactamente; otro período sin cambios.' };
}
export function oraculo012(variaciones, auditorias) {
  const tipos = new Set(variaciones.map(v => v.tipo));
  const ids = new Set(variaciones.map(v => Number(v.id_variacion_valor_razonable)));
  const eventos = auditorias.filter(a => a.tipo_evento === 'VARIACION_REGISTRADA' && ids.has(Number(a.id_referencia)));
  const hallazgos = [];
  if (eventos.length !== variaciones.length) hallazgos.push(`Número de entradas ${eventos.length}, variaciones ${variaciones.length}.`);
  for (const v of variaciones) {
    const xs = eventos.filter(a => Number(a.id_referencia) === Number(v.id_variacion_valor_razonable));
    if (xs.length !== 1) { hallazgos.push(`Variación ${v.id_variacion_valor_razonable}: ${xs.length} entradas.`); continue; }
    const a = xs[0];
    if (Number(a.id_activo_biologico) !== Number(v.id_activo_biologico) || Number(a.id_periodo_contable) !== Number(v._periodo) || a.payload_evento?.tipo !== v.tipo ||
      !igual(a.monto_afectado, v.monto_variacion) || !igual(a.payload_evento?.monto, v.monto_variacion))
      hallazgos.push(`Variación ${v.id_variacion_valor_razonable}: datos de auditoría discordantes.`);
  }
  if (hallazgos.length) return { estado: 'RECHAZADO', motivo: hallazgos.join(' ') };
  if (!['GANANCIA_TRANSFORMACION_BIOLOGICA', 'PERDIDA_TRANSFORMACION_BIOLOGICA',
    'GANANCIA_PRECIO_MERCADO', 'PERDIDA_PRECIO_MERCADO'].every(t => tipos.has(t)))
    return { estado: 'NO_CONCLUYENTE', motivo: 'Las entradas RF-94 observadas coinciden, pero faltan tipos de variación exigidos.' };
  return { estado: 'APROBADO', motivo: 'Cada variación tiene una entrada RF-94 con identificador, activo, tipo, monto y período.' };
}
export function oraculo013({ inicial, cadenaInicial, final, cadena, evento, lecturaApta, verificadas = 1 }) {
  const ids = cadena?.eslabones?.ids;
  const ok = Number(verificadas) >= 1 && inicial?.estado_trazabilidad === 'VERIFICACION_PENDIENTE' &&
    cadenaInicial?.estado_trazabilidad === 'VERIFICACION_PENDIENTE' &&
    final?.estado_trazabilidad === 'VERIFICADO' && cadena?.estado_verificacion === 'VERIFICADO' &&
    cadena?.nivel_fallo == null && cadena?.eslabones?.nivel_fallo == null &&
    Number(ids?.id_evento) === Number(evento) && Array.isArray(ids?.ids_lectura_iot) &&
    ids.ids_lectura_iot.some(x => Number(x) === Number(lecturaApta));
  return { estado: ok ? 'APROBADO' : 'RECHAZADO',
    motivo: ok ? 'VERIFICACION_PENDIENTE inicial, VERIFICADO final y navegación a M02 y M03.' :
      `Cadena incompleta: nivel_fallo ${cadena?.nivel_fallo ?? cadena?.eslabones?.nivel_fallo ?? 'sin dato'}; evento M02 ${ids?.id_evento ?? 'faltante'}; lectura M03 ${ids?.ids_lectura_iot?.some(x => Number(x) === Number(lecturaApta)) ? 'presente' : 'faltante'}.` };
}
export function decidirVerificacion(http, codigo = '', causaG32Confirmada = false) {
  if (http === 422 && codigo === 'PERIODO_NO_ABIERTO') return { estado: 'NO_CONCLUYENTE',
    motivo: 'RF-91 devolvió PERIODO_NO_ABIERTO aunque el período 241 fue seleccionado ABIERTO; contraste técnico de período pendiente.' };
  if (http === 500) return { estado: 'RECHAZADO',
    motivo: `POST RF-91 HTTP 500 (${codigo || 'sin código'}); origen no navegable. Síntoma similar a INC-M06-G32-01; causa no demostrada en este RUN.`,
    incidencia: causaG32Confirmada ? 'INC-M06-G32-01' : null };
  if (http !== 200) return { estado: 'NO_CONCLUYENTE', motivo: `RF-91 HTTP ${http ?? 'sin respuesta'}; no se acreditó el resultado.` };
  return null;
}
