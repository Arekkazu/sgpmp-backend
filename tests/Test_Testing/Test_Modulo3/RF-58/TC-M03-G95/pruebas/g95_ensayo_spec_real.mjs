import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { evaluarResultadoCypress, LIMITE_LECTURAS_DASHBOARD } from '../lib/g95_escenario.mjs';

const DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const cypressPkg = require.resolve('cypress/package.json', { paths: [DIR] });
const cli = path.join(path.dirname(cypressPkg), 'bin', 'cypress');
const json = (res, status, body, extra = {}) => {
  res.writeHead(status, { 'Content-Type': 'application/json', ...extra });
  res.end(JSON.stringify(body));
};

function pagina(modo, tipo) {
  const aviso = modo === 'sin_aviso' ? '' : ['ok', 'sin_recarga'].includes(modo)
    ? 'Sesión cerrada. Se inició sesión con tu cuenta en otro dispositivo o navegador. Ingresa de nuevo y volverás a la pantalla donde estabas.'
    : 'Sesión cerrada. Ingresa de nuevo y volverás a la pantalla donde estabas.';
  if (tipo === 'login') return `<!doctype html><meta charset="utf-8"><main><h1>Iniciar sesión</h1><div class="auth-alert" role="alert"></div><form><label>Correo electrónico<input type="email"></label><label>Contraseña<input type="password"></label><button type="submit">Ingresar</button></form></main><script>
    const base='/api-sgpmp-test';
    document.querySelector('.auth-alert').textContent=sessionStorage.getItem('aviso')||'';
    document.querySelector('form').onsubmit=async e=>{e.preventDefault();const r=await fetch(base+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({correo_electronico:document.querySelector('input[type=email]').value,contrasena:document.querySelector('input[type=password]').value})});if(r.ok){const j=await r.json();sessionStorage.setItem('token',j.token);sessionStorage.removeItem('aviso');const p=${JSON.stringify(modo !== 'texto')}?sessionStorage.getItem('returnPath'):null;sessionStorage.removeItem('returnPath');location.href=p||'/sigab-test/dashboard';}};
    </script>`;
  if (tipo === 'dashboard') return '<!doctype html><meta charset="utf-8"><h1>Inicio</h1>';
  return `<!doctype html><meta charset="utf-8"><h1>Monitoreo en tiempo real</h1><div class="ds-field"><label for="monitoreo-area">Área</label><div><input id="monitoreo-area" role="combobox" aria-controls="monitoreo-area-lista" aria-expanded="false" aria-autocomplete="list" placeholder="Busca por nombre o escribe el ID"><button type="button" aria-label="Mostrar opciones de Área">⌄</button><ul id="monitoreo-area-lista" role="listbox" aria-label="Área"></ul></div></div><button id="auto">Auto ON</button><button aria-label="Refrescar ahora">Refrescar</button><section id="datos"></section><script>
    const base='/api-sgpmp-test';const input=document.querySelector('[role=combobox]');const auto=document.querySelector('#auto');const lista=document.querySelector('[role=listbox]');let timer=null, areas=[];
    function idArea(){const v=input.value.trim();return /\\(#(\\d+)\\)$/.exec(v)?.[1]||/^#?(\\d+)$/.exec(v)?.[1]||null}
    async function cargar(areasSolo=false){const q=new URLSearchParams({pagina:'1',por_pagina:areasSolo?'1':'50'});if(!areasSolo&&idArea())q.set('id_infraestructura',idArea());const r=await fetch(base+'/iot/monitoreo/dashboard?'+q,{headers:{Authorization:'Bearer '+sessionStorage.getItem('token')}});if(r.status===401){const refresh=await fetch(base+'/sesiones/refresh',{method:'POST',credentials:'include'});if(refresh.status===401||refresh.status===410){sessionStorage.setItem('aviso',${JSON.stringify(aviso)});sessionStorage.setItem('returnPath','/sigab-test/telemetria/monitoreo');location.href='/sigab-test/login';}return;}if(r.ok){const j=await r.json();if(areasSolo){areas=j.resumen_unidades||[];return;}document.querySelector('#datos').textContent=j.resumen_unidades.length?'Unidad sintética':'';}}
    function opciones(){lista.innerHTML='';input.setAttribute('aria-expanded','true');for(const a of areas){const li=document.createElement('li');li.setAttribute('role','option');li.textContent=a.nombre_infraestructura+' (#'+a.id_infraestructura+')';const detalle=document.createElement('span');detalle.textContent=a.nombre_finca;li.appendChild(detalle);li.onclick=()=>{input.value=a.nombre_infraestructura+' (#'+a.id_infraestructura+')';lista.innerHTML='';input.setAttribute('aria-expanded','false');cargar()};lista.appendChild(li)}}
    input.oninput=()=>{opciones();cargar()};document.querySelector('button[aria-label="Mostrar opciones de Área"]').onclick=opciones;
    document.querySelector('button[aria-label="Refrescar ahora"]').onclick=()=>cargar();
    auto.onclick=()=>{const encendido=auto.textContent==='Auto ON';auto.textContent=encendido?'Auto OFF':'Auto ON';if(timer)clearInterval(timer);timer=encendido?null:setInterval(()=>cargar(),3000)};
    cargar();cargar(true);timer=setInterval(()=>cargar(),3000);window.addEventListener('beforeunload',()=>{if(timer)clearInterval(timer)});
    </script>`;
}

async function servidorLocal(modo) {
  let logins = 0;
  const servidor = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    if (req.method === 'POST' && url.pathname === '/api-sgpmp-test/sesiones/') {
      logins++;
      if (modo === 'sesion500' && logins === 2) { json(res, 500, { error_code: 'ERROR_INTERNO' }); return; }
      json(res, 200, { token: `tok-${logins}`, expira_en: 28800 },
        { 'Set-Cookie': `refresh_token=ref-${logins}; Path=/; HttpOnly; SameSite=Lax` });
      return;
    }
    if (req.method === 'POST' && url.pathname === '/api-sgpmp-test/sesiones/refresh') {
      json(res, 401, { error_code: 'SESION_INVALIDA' }); return;
    }
    if (req.method === 'GET' && url.pathname === '/api-sgpmp-test/iot/monitoreo/dashboard') {
      if (modo === 'sin_recarga' && logins >= 3) {
        json(res, 404, { error_code: 'MONITOREO_NO_DISPONIBLE' }); return;
      }
      if (modo !== 'lento' && req.headers.authorization !== `Bearer tok-${logins}`) {
        json(res, 401, { error_code: 'TOKEN_REVOCADO' }); return;
      }
      const unidades = [
        { id_infraestructura: 7, nombre_infraestructura: 'Unidad sintética', nombre_finca: 'Finca sintética', total_sensores: 1 },
        { id_infraestructura: 8, nombre_infraestructura: 'Unidad extensa', nombre_finca: 'Finca sintética', total_sensores: 69 },
      ];
      const sensores = [
        { id_infraestructura: 7, estado_semaforo: 'VERDE', dato_desactualizado: false },
        { id_infraestructura: 8, estado_semaforo: 'GRIS', dato_desactualizado: false },
      ];
      const filtrada = url.searchParams.get('id_infraestructura') === '7';
      json(res, 200, { resumen_unidades: filtrada ? unidades.slice(0, 1) : unidades,
        sensores: filtrada ? sensores.slice(0, 1) : sensores,
        total: filtrada ? 1 : 70, pagina: 1, por_pagina: 50 });
      return;
    }
    if (url.pathname === '/sigab-test/login') { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(pagina(modo, 'login')); return; }
    if (url.pathname === '/sigab-test/dashboard') { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(pagina(modo, 'dashboard')); return; }
    if (url.pathname === '/sigab-test/telemetria/monitoreo') { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(pagina(modo, 'monitoreo')); return; }
    res.writeHead(404); res.end();
  });
  await new Promise(resolve => servidor.listen(0, '127.0.0.1', resolve));
  return { servidor, base: `http://127.0.0.1:${servidor.address().port}` };
}

async function ensayo(modo) {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), `g95-ensayo-${modo}-`));
  const { servidor, base } = await servidorLocal(modo);
  try {
    const env = { ...process.env, CYPRESS_AUTORIZADO_RUN: 'SI', CYPRESS_ENSAYO_LOCAL: 'SI',
      CYPRESS_API_BASE: `${base}/api-sgpmp-test`, CYPRESS_API_BASE_CONTROL: `${base}/api-sgpmp-test`,
      CYPRESS_FRONT_BASE: `${base}/sigab-test`, CYPRESS_RUN_ID: 'ENSAYO-G95-20261026-120000-local',
      CYPRESS_ARTIFACTS_DIR: temporal, CYPRESS_HANDOFF: path.join(temporal, 'auth.json'),
      CYPRESS_PROD_EMAIL: 'productor@example.test', CYPRESS_PROD_PASSWORD: 'sintetico',
      CYPRESS_CRASH_REPORTS: '0', CYPRESS_TELEMETRY: '0' };
    delete env.ELECTRON_RUN_AS_NODE;
    const args = [cli, 'run', '--project', DIR, '--spec', path.join(DIR, 'g95.cy.js'),
      '--config-file', path.join(DIR, 'g95.cypress.config.cjs'),
      '--config', `screenshotsFolder=${temporal},videosFolder=${temporal},downloadsFolder=${temporal}`,
      '--browser', 'chrome', '--headless'];
    const { codigo, salida } = await new Promise((resolve, reject) => {
      const p = spawn(process.execPath, args, { cwd: DIR, env, shell: false, stdio: ['ignore', 'pipe', 'pipe'] });
      let log = '';
      for (const flujo of [p.stdout, p.stderr]) flujo.on('data', x => { log = (log + x.toString()).slice(-3000); });
      p.once('error', reject); p.once('close', code => resolve({ codigo: code, salida: log }));
    });
    const actaPath = path.join(temporal, 'UI-186-01.json');
    assert.ok(fs.existsSync(actaPath), `Acta ausente ${modo}; Cypress ${codigo}: ${salida}`);
    const acta = JSON.parse(fs.readFileSync(actaPath, 'utf8'));
    const resumen = JSON.parse(fs.readFileSync(path.join(temporal, 'UI-186-01-cypress.json'), 'utf8'));
    const capturas = fs.readdirSync(temporal, { recursive: true }).filter(x => /\.png$/i.test(String(x)));
    assert.ok(capturas.length, `Captura ausente ${modo}; ${salida}`);
    const estados = evaluarResultadoCypress({ acta, resumen, capturas, error: null });
    const esperado = {
      ok: ['APROBADO', 'APROBADO'], texto: ['APROBADO', 'APROBADO'],
      sin_aviso: ['RECHAZADO', 'APROBADO'],
      sin_recarga: ['APROBADO', 'RECHAZADO'], sesion500: ['BLOQUEADO', 'BLOQUEADO'],
      lento: ['NO_CONCLUYENTE', 'NO_CONCLUYENTE'],
    }[modo];
    assert.deepEqual([estados['UI-186-01'].estado, estados['UI-186-02'].estado], esperado,
      `${modo}: ${JSON.stringify(acta)}; Cypress ${codigo}: ${salida}`);
    assert.equal(resumen.totalTests, 1);
    assert.equal(resumen.totalPending, 0);
    assert.equal(resumen.totalSkipped, 0);
    assert.ok(acta.peticiones.every(p => p.fuera_sandbox === true));
    assert.ok(acta.auto_on && acta.periodica_200 && acta.filtro_fijado);
    assert.ok(acta.lecturas_dashboard <= LIMITE_LECTURAS_DASHBOARD, `${modo}: lecturas ${acta.lecturas_dashboard}`);
    assert.equal(acta.filtro_id, 7);
    if (modo === 'texto') assert.match(acta.aviso_texto, /Sesión cerrada/);
    if (modo === 'texto') {
      assert.equal(acta.ruta_aterrizaje, '/dashboard');
      assert.equal(acta.navegacion_manual, true);
      assert.equal(acta.recarga_200_posterior, true);
      assert.equal(acta.filtro_conservado, false);
      assert.equal(acta.auto_conservado, true);
      assert.equal(estados['UI-186-02'].observaciones.length, 2);
    }
    if (modo === 'sin_recarga') assert.equal(acta.recarga_200_posterior, false);
    if (modo === 'sin_aviso') {
      assert.equal(acta.aviso_texto, '');
      assert.equal(acta.aviso_sesion_terminada, false);
    }
    if (modo === 'ok') {
      assert.equal(acta.e7_riesgo, false);
      assert.equal(acta.bloqueo_datos, null);
      assert.equal(acta.ruta_aterrizaje, '/telemetria/monitoreo');
      assert.equal(acta.retorno_automatico, true);
      assert.equal(acta.filtro_conservado, false);
      assert.equal(acta.auto_conservado, true);
    }
    console.log(`ENSAYO ${modo}: UI-186-01 ${esperado[0]}; UI-186-02 ${esperado[1]}`);
  } finally {
    await new Promise(resolve => servidor.close(resolve));
    assert.ok(path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(temporal, { recursive: true, force: true });
  }
}

if (process.argv[2] === '--servidor') {
  const modo = process.argv[3];
  assert.ok(['ok', 'texto', 'sin_aviso', 'sin_recarga', 'sesion500', 'lento'].includes(modo), 'Modo local inválido');
  const { base } = await servidorLocal(modo);
  console.log(`SERVIDOR_G95 ${modo} ${base}`);
  await new Promise(() => {});
} else {
  for (const modo of ['ok', 'texto', 'sin_aviso', 'sin_recarga', 'sesion500', 'lento']) await ensayo(modo);
}
