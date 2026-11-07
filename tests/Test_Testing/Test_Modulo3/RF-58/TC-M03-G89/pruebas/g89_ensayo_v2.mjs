import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { evaluar } from '../g89.mjs';

const CASOS = ['TC-M03-173', 'TC-M03-174'];
const RUN = 'RUN-G89-V2-20261030-120000';

async function modo(nombre, opciones = {}) {
  const padre = fs.mkdtempSync(path.join(os.tmpdir(), 'g89-v2-ensayo-'));
  const dir = path.join(padre, RUN);
  const original = globalThis.fetch;
  let solicitudesNewman = 0;
  let telemetria = 100, alerta = 200, verde = false, color = 'VERDE', idActual = null;
  let ultimoValor = 25, ultimaMarca = null;
  let fallaAislada = false, fallasSeguidas = 0, cerrado = false;
  const alertas = new Map();
  const valores = {
    SIGAB_API_TEST_BASE: 'http://local.invalid', QA_SANDBOX_SECRET: 'SANDBOX_FALSO',
    QA_ADMIN_EMAIL: 'ADMIN_FALSO', QA_ADMIN_PASSWORD: 'CLAVE_ADMIN_FALSA',
    QA_PROD_EMAIL: 'PROD_FALSO', QA_PROD_PASSWORD: 'CLAVE_PROD_FALSA',
    BROKER_SERVICE_TOKEN: 'BROKER_FALSO', QA_G88_169_171_SERIAL: 'SERIAL_FALSO',
    QA_AUTORIZADO: 'SI'
  };
  const contrato = { runId: RUN, directorio: dir, operacion: 'reevaluar', version: 2,
    intento: 1, referencia: 'ENSAYO_LOCAL', contexto: { casos: CASOS,
      alcance_reevaluacion: { casos: CASOS, version_anterior: 1, motivo: 'Ensayo local',
        incumplimientos_previos: '174 rechazado', correcciones_informadas: 'PR #732',
        resultado_esperado: '173 y 174 aprobados' } } };
  const respuesta = (status, data, run = true) => ({ status,
    headers: { get: (k) => k.toLowerCase() === 'x-test-run-id' && run ? RUN.slice(4) : null },
    text: async () => JSON.stringify(data) });
  const dashboard = () => ({ sensores: verde ? [{ id_sensor: 552, ultimo_valor: String(ultimoValor),
    ultimo_timestamp_captura: ultimaMarca, estado_semaforo: color, id_alerta: idActual }] : [], total: verde ? 1 : 0,
    pagina: 1, por_pagina: 50 });
  const recalcular = () => {
    if ([...alertas.values()].some((a) => a.estado_alerta === 'ACTIVA' && a.severidad === 'CRITICO')) {
      color = opciones.regresion173 ? 'VERDE' : 'ROJO';
      idActual = [...alertas.values()].find((a) => a.estado_alerta === 'ACTIVA' && a.severidad === 'CRITICO').id_alerta;
    } else if ([...alertas.values()].some((a) => a.estado_alerta === 'ACTIVA')) {
      color = opciones.activa174 ? 'VERDE' : 'AMARILLO';
      idActual = [...alertas.values()].find((a) => a.estado_alerta === 'ACTIVA').id_alerta;
    } else { color = opciones.persiste174 && alerta >= 202 ? 'AMARILLO'
      : ultimoValor === 25 ? 'VERDE' : 'AMARILLO'; idActual = null; }
  };
  globalThis.fetch = async (url, solicitud) => {
    const ruta = new URL(url).pathname;
    const metodo = solicitud.method;
    const body = solicitud.body ? JSON.parse(solicitud.body) : {};
    const token = solicitud.headers.Authorization?.replace('Bearer ', '');
    if (opciones.sinRespuesta && ruta === '/usuarios/me') throw new Error('SIN_RESPUESTA_LOCAL');
    if (opciones.tres5xx && ruta === '/usuarios/me' && ++fallasSeguidas <= 3)
      return respuesta(503, { detail: 'fallo simulado' });
    if (opciones.un5xx && ruta === '/usuarios/me' && !fallaAislada) {
      fallaAislada = true; return respuesta(503, { detail: 'fallo aislado' });
    }
    if (ruta === '/sesiones/') return respuesta(200,
      { token: body.correo_electronico === valores.QA_ADMIN_EMAIL ? 'JWT_ADMIN_FALSO' : 'JWT_PROD_FALSO' }, false);
    if (ruta === '/usuarios/me') return respuesta(200, token === 'JWT_ADMIN_FALSO'
      ? { id_usuario: 10, nombre_rol: 'Administrador', fincas: [] }
      : { id_usuario: 20, nombre_rol: 'Productor', fincas: opciones.sinFinca ? [] : [{ id_finca: 184 }] });
    if (ruta === '/configuracion/dispositivos-iot/357') return respuesta(200,
      { id_infraestructura: 349, es_activo: true, serial: valores.QA_G88_169_171_SERIAL });
    if (ruta === '/configuracion/infraestructuras/349') return respuesta(200,
      { id_infraestructura: 349, id_finca: 184, especie_id: 126, es_activo: true });
    if (ruta === '/configuracion/dispositivos-iot/357/sensores') return respuesta(200,
      { items: [{ id_sensores: 552, categoria: 'TEMPERATURA', es_activo: true }] });
    if (ruta === '/configuracion/sensores/552/asociaciones') return respuesta(200,
      { items: [{ id_infraestructura: 349, tiene_estado: true, fecha_finalizacion: null }] });
    if (ruta === '/configuracion/sensores/552/calibraciones') return respuesta(200,
      { items: [{ id_dispositivo_iot: 357, fecha_calibracion: '2026-10-01', ganancia: 1, offset: 0 }] });
    if (ruta === '/configuracion/umbrales') return respuesta(200, { items: [{ es_activo: true,
      id_variable_ambiental: 1, niveles: [
        { nivel: 'normal', limite_inferior: 20, limite_superior: 30 },
        { nivel: 'precaucion' }, { nivel: 'critico' }] }] });
    if (ruta === '/iot/monitoreo/dashboard') return respuesta(200, dashboard(), !cerrado);
    if (ruta === '/iot/telemetria' && metodo === 'POST') {
      if (opciones.clave403) return respuesta(403, { detail: 'rechazada' });
      verde = true; ultimoValor = Number(body.valor); ultimaMarca = body.timestamp_captura;
      recalcular();
      if (ultimoValor === 25 && ![...alertas.values()].some((a) => a.estado_alerta === 'ACTIVA'))
        color = 'VERDE';
      return respuesta(201, { id_telemetria: ++telemetria });
    }
    if (ruta === '/iot/alertas' && metodo === 'POST') {
      if (opciones.alta422 && body.severidad_edge === 'CRITICO')
        return respuesta(422, { error_code: 'REGLA_COMPUESTA_NO_ACTIVADA',
          message: 'Condición mínima no cumplida',
          fields: [{ field: 'correlacion_variables', message: 'falta THI' }] });
      if (opciones.normalAlerta && body.severidad_edge === 'CRITICO')
        return respuesta(201, { id_alerta: null, es_duplicado: false, severidad: null,
          motivo_descarte: 'TEMPERATURA_AMBIENTAL=25 está en la banda NORMAL de RF-57: no genera alerta' });
      const id = ++alerta;
      const severidad = opciones.severidadDistinta && body.severidad_edge === 'CRITICO'
        ? 'MODERADO' : Number(body.valor) > 36 ? 'CRITICO' : Number(body.valor) > 33 ? 'MODERADO' : 'LEVE';
      alertas.set(id, { id_alerta: id, estado_alerta: 'ACTIVA', severidad,
        id_sensor: 552 }); recalcular();
      return respuesta(201, { id_alerta: id, es_duplicado: false, severidad });
    }
    if (ruta === '/iot/alertas' && metodo === 'GET') {
      const estado = new URL(url).searchParams.get('estado');
      return respuesta(200, { total: [...alertas.values()].filter((a) => a.estado_alerta === estado).length });
    }
    const idAlerta = Number(ruta.match(/^\/iot\/alertas\/(\d+)/)?.[1]);
    if (idAlerta && metodo === 'GET') return cerrado ? respuesta(404, { detail: 'ausente' }, false)
      : respuesta(200, alertas.get(idAlerta));
    if (idAlerta && metodo === 'PATCH') {
      alertas.get(idAlerta).estado_alerta = body.nuevo_estado;
      recalcular(); return respuesta(200, { estado_alerta: body.nuevo_estado });
    }
    if (ruta === `/test-control/runs/${RUN.slice(4)}` && metodo === 'DELETE') {
      cerrado = true; verde = false; color = 'VERDE'; idActual = null;
      return respuesta(200, { ok: true }, false);
    }
    if (ruta === '/iot/monitoreo/historial') return opciones.historial422
      ? respuesta(422, { detail: 'FECHA_FIN_FUTURA' }, false)
      : respuesta(200, { items: [], total: 0 }, false);
    throw new Error(`RUTA_NO_SIMULADA_${metodo}_${ruta}`);
  };
  const newman = ({ contrato: c }) => {
    solicitudesNewman++;
    const archivo = 'newman/newman-TC-M03-G89.json';
    fs.mkdirSync(path.join(c.directorio, 'newman'), { recursive: true });
    fs.writeFileSync(path.join(c.directorio, archivo), JSON.stringify({ run: { executions: [{
      item: { name: 'Dashboard G89' }, request: { method: 'GET' }, response: { code: 200 },
      assertions: [{ assertion: 'Semáforo esperado' }] }] } }));
    if (opciones.dosJson) fs.writeFileSync(path.join(c.directorio, 'newman', 'extra.json'), '{}');
    return { archivo, http: 200, cuerpo: dashboard(), fallos: [], eco: true,
      aserciones: 4, latencia_ms: 1, ejecuciones: 1, status_proceso: 0 };
  };
  try {
    let codigo = null, error = null;
    try { codigo = await evaluar(contrato, { valores, newman }); }
    catch (e) { error = e.message; }
    const r = fs.existsSync(path.join(dir, 'resultado.json'))
      ? JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8')) : null;
    const informePath = path.join(dir, 'TC-M03-G89_reevaluacion_V2.md');
    const informe = fs.existsSync(informePath) ? fs.readFileSync(informePath, 'utf8') : '';
    assert.ok(r, `${nombre}: falta resultado.json local`);
    assert.deepEqual(fs.readdirSync(dir).filter((x) => x.endsWith('.md')),
      ['TC-M03-G89_reevaluacion_V2.md']);
    assert.ok(r.evidencias.every((x) => x === 'resultado.json' || fs.existsSync(path.join(dir, x))));
    if (opciones.dosJson) assert.match(error ?? '', /NEWMAN_MULTIPLES_JSON/);
    else assert.equal(error, null, `${nombre}: ${error}`);
    const post = r.evidencias.filter((x) => x.startsWith('api/POST-ALERTA-'))
      .map((x) => JSON.parse(fs.readFileSync(path.join(dir, x), 'utf8')));
    const erroresGuardados = r.evidencias.filter((x) => x.startsWith('api/ERROR-'))
      .map((x) => ({ archivo: x, contenido: JSON.parse(fs.readFileSync(path.join(dir, x), 'utf8')) }));
    assert.doesNotMatch(JSON.stringify(post), /SANDBOX_FALSO|BROKER_FALSO|SERIAL_FALSO|JWT_ADMIN_FALSO/);
    return { codigo, r, solicitudesNewman, informe, post, erroresGuardados };
  } finally {
    globalThis.fetch = original;
    fs.rmSync(padre, { recursive: true, force: true });
  }
}

let modos = 0;
const comprobar = async (nombre, opciones, revisar) => {
  const dato = await modo(nombre, opciones); revisar(dato); modos++;
};
await comprobar('todo corregido', {}, ({ r, codigo, solicitudesNewman, informe, post }) => {
  assert.equal(codigo, 0); assert.equal(r.oficial, true); assert.equal(solicitudesNewman, 1);
  assert.deepEqual(CASOS.map((id) => r.casos[id].estado), ['APROBADO', 'APROBADO']);
  assert.equal(r.cierre.rollback.verificado, true);
  assert.equal(r.newman.length, 1); assert.equal(r.cypress.total_pruebas, 0);
  assert.deepEqual(post.map((x) => [x.severidad_esperada, x.severidad, x.http]),
    [['CRITICO', 'CRITICO', 201], ['LEVE', 'LEVE', 201], ['MODERADO', 'MODERADO', 201]]);
  assert.ok(r.casos['TC-M03-173'].comprobaciones.every((x) => x.lectura_en_rango && x.lectura_vigente));
  assert.match(informe, /## Altas RF-57 y respuestas POST/);
  assert.match(informe, /^# TC-M03-G89 — APROBADO/m);
  assert.match(informe, /INC-G89-174-01: CORREGIDA/);
  assert.match(informe, /## Detalle por caso/);
  assert.match(informe, /V1 → V2/);
});
await comprobar('alta descartada por banda NORMAL', { normalAlerta: true },
  ({ r, post, informe }) => {
    assert.equal(r.casos['TC-M03-173'].estado, 'NO_CONCLUYENTE');
    assert.match(r.casos['TC-M03-173'].prerequisitos.join(' '), /banda NORMAL de RF-57/);
    assert.equal(post[0].id_alerta, null);
    assert.match(post[0].motivo_descarte, /banda NORMAL/);
    assert.match(informe, /banda NORMAL de RF-57/);
  });
await comprobar('alta 422 conserva cuerpo y motivo', { alta422: true },
  ({ r, post, informe, erroresGuardados }) => {
    assert.equal(r.casos['TC-M03-173'].estado, 'NO_CONCLUYENTE');
    assert.equal(post[0].error_code, 'REGLA_COMPUESTA_NO_ACTIVADA');
    assert.match(post[0].message, /Condición mínima/);
    assert.equal(post[0].fields[0].field, 'correlacion_variables');
    assert.match(r.casos['TC-M03-173'].prerequisitos.join(' '), /REGLA_COMPUESTA_NO_ACTIVADA/);
    const error = erroresGuardados.find((x) => x.archivo.includes('iot-alertas'));
    assert.ok(error);
    assert.equal(error.contenido.cuerpo.error_code, 'REGLA_COMPUESTA_NO_ACTIVADA');
    assert.match(informe, /REGLA_COMPUESTA_NO_ACTIVADA/);
  });
await comprobar('severidad recalculada distinta', { severidadDistinta: true },
  ({ r, post }) => {
    assert.equal(r.casos['TC-M03-173'].estado, 'ERROR_QA');
    assert.match(r.casos['TC-M03-173'].prerequisitos.join(' '), /ERROR_QA_SEVERIDAD_POST/);
    assert.equal(post[0].severidad, 'MODERADO');
    assert.equal(r.casos['TC-M03-174'].estado, 'APROBADO');
  });
await comprobar('174 persiste', { persiste174: true }, ({ r, informe }) => {
  assert.equal(r.oficial, true); assert.equal(r.casos['TC-M03-174'].estado, 'RECHAZADO');
  assert.equal(r.incidencias.length, 1); assert.equal(r.incidencias[0].id, 'INC-G89-174-01');
  assert.match(informe, /INC-G89-174-01: PERSISTENTE/);
});
await comprobar('174 activa falla con cierre corregido', { activa174: true }, ({ r, informe }) => {
  assert.equal(r.oficial, true); assert.equal(r.casos['TC-M03-174'].estado, 'RECHAZADO');
  assert.deepEqual(r.incidencias.map((i) => i.id), ['INC-G89-174-V2-02']);
  assert.match(informe, /INC-G89-174-01: CORREGIDA/);
});
await comprobar('173 regresa', { regresion173: true }, ({ r }) => {
  assert.equal(r.oficial, true); assert.equal(r.casos['TC-M03-173'].estado, 'RECHAZADO');
  assert.equal(r.casos['TC-M03-174'].estado, 'APROBADO');
});
await comprobar('Productor sin finca 184', { sinFinca: true }, ({ r }) => {
  assert.equal(r.oficial, false); assert.equal(r.casos['TC-M03-173'].estado, 'ERROR_QA');
});
await comprobar('5xx aislado', { un5xx: true }, ({ r }) => assert.equal(r.oficial, true));
await comprobar('tres 5xx', { tres5xx: true }, ({ r }) => assert.equal(r.oficial, false));
await comprobar('403 de clave', { clave403: true }, ({ r, erroresGuardados, informe }) => {
  assert.equal(r.oficial, false); assert.equal(r.casos['TC-M03-173'].estado, 'ERROR_QA');
  assert.ok(erroresGuardados.some((x) => x.archivo.includes('iot-telemetria')
    && x.contenido.http === 403 && x.contenido.cuerpo.detail === 'rechazada'));
  assert.match(informe, /rechazada/);
});
await comprobar('sin respuesta', { sinRespuesta: true }, ({ r }) => assert.equal(r.oficial, false));
await comprobar('historial 422', { historial422: true }, ({ r }) => {
  assert.equal(r.oficial, false); assert.equal(r.cierre.rollback.verificado, false);
});
await comprobar('dos JSON Newman', { dosJson: true }, ({ r }) => assert.equal(r.oficial, false));
console.log(`OK G89: ${modos}/${modos} modos; V2, Newman único, cierre y errores técnicos; registro QA fiel`);
