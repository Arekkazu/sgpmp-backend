import http from 'node:http';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// Solo loopback y datos sintéticos. La página dispara las mismas clases de peticiones.
export async function iniciarLocal(modo = 'ok', puerto = 0) {
  const servidor = http.createServer((req, res) => {
    const ruta = new URL(req.url, 'http://127.0.0.1').pathname;
    const run = req.headers['x-test-run-id'];
    const sesion = ['/api-sgpmp-test/sesiones/refresh', '/api-sgpmp-test/usuarios/me',
      '/api-sgpmp-test/sesiones/me/permisos'].includes(ruta);
    const dashboard = ruta === '/api-sgpmp-test/iot/monitoreo/dashboard';
    const contexto = ruta === '/api-sgpmp-test/configuracion/interfaz/contexto';
    if (run && !(modo === 'sin_eco_dashboard' && dashboard)) res.setHeader('X-Test-Run-Id', run);
    if (ruta === '/sigab-test/login') {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end('<!doctype html><html><body><main>Login sintético local</main></body></html>');
      return;
    }
    if (ruta === '/sigab-test/telemetria/monitoreo') {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end(`<!doctype html><html><body><main id="panel"></main><script>
        (async()=>{
          const base='/api-sgpmp-test';
          await fetch(base+'/sesiones/refresh',{method:'POST'});
          const info=await fetch(base+'/usuarios/me');
          const permisos=await fetch(base+'/sesiones/me/permisos');
          if(!info.ok||!permisos.ok||${modo === 'lento'})return;
          await fetch(base+'/configuracion/interfaz/contexto');
          await fetch(base+'/iot/monitoreo/dashboard');
          document.getElementById('panel').innerHTML=${JSON.stringify(modo === 'texto'
    ? '<p>No hay sensores para mostrar con los filtros actuales.</p>'
    : '<p>No tiene unidades productivas asignadas</p><p>Contacte al administrador.</p>')};
        })();
      </script></body></html>`);
      return;
    }
    if (ruta.startsWith('/api-sgpmp-test/')) {
      res.setHeader('Content-Type', 'application/json');
      if (sesion && (run || modo === 'sesion500')) {
        res.statusCode = 500; res.end('{}'); return;
      }
      if ((dashboard || contexto) && !run) {
        res.statusCode = 400; res.end('{}'); return;
      }
      res.end(dashboard ? '{"total":0,"resumen_unidades":[],"sensores":[]}'
        : ruta === '/api-sgpmp-test/usuarios/me' ? '{"fincas":[{},{}]}' : '{}');
      return;
    }
    res.statusCode = 404; res.end('');
  });
  await new Promise(resolve => servidor.listen(puerto, '127.0.0.1', resolve));
  return { servidor, base: `http://127.0.0.1:${servidor.address().port}` };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  iniciarLocal(process.argv[2] ?? 'ok', Number(process.argv[3] ?? 42871))
    .then(({ base }) => console.log(`SERVIDOR_LOCAL ${base}`));
}
