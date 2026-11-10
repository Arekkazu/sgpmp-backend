// Servidor local y espía para LOCAL_SMOKE; recibe datos y paneles desde un escenario del grupo.
import http from 'node:http';

export async function simuladorBase(escenario){
  const peticiones=[];
  const paneles=escenario.paneles;
  const opciones=Object.keys(paneles).map(id=>`<option value="${id}">${id}</option>`).join('');
  const html=`<!doctype html><html><body>
    <form id="login"><input type="email"><input type="password"><button type="submit">Entrar</button></form>
    <select id="fin-periodo">${opciones}</select>
    <input type="radio" name="sin-precio" value="no"><input type="radio" name="sin-precio" value="si">
    <section aria-labelledby="cierre-pre"></section>
    <script>
      const paneles=${JSON.stringify(paneles)};
      document.querySelector('#login').onsubmit=async e=>{e.preventDefault();await fetch('/sesiones/',{method:'POST'});};
      document.querySelector('#fin-periodo').onchange=async e=>{
        const id=e.target.value;
        await fetch('/finanzas/periodos/'+id+'/prevalidacion');
        document.querySelector('section').innerHTML=paneles[id].html;
      };
      window.addEventListener('popstate',()=>document.querySelector('#fin-periodo').dispatchEvent(new Event('change')));
    </script></body></html>`;
  const server=http.createServer((req,res)=>{
    peticiones.push({metodo:req.method,ruta:req.url});
    const eco=req.headers['x-test-run-id']?{'x-test-run-id':req.headers['x-test-run-id']}:{};
    if(req.url==='/login'||req.url==='/'){
      res.writeHead(200,{'content-type':'text/html',...eco});res.end(html);return;
    }
    const match=req.url.match(/^\/finanzas\/periodos\/(\d+)\/prevalidacion$/);
    if(match&&paneles[match[1]]){
      res.writeHead(200,{'content-type':'application/json',...eco});
      res.end(JSON.stringify(paneles[match[1]].prevalidacion));return;
    }
    res.writeHead(404,eco);res.end();
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return{url:`http://127.0.0.1:${server.address().port}/`,peticiones,cerrar:()=>new Promise(resolve=>server.close(resolve))};
}
