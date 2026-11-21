import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const group=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const front=path.resolve(group,'../../../../../..','SGPMP-FRONT-END-PWA/src');
const read=p=>fs.readFileSync(p,'utf8');
const spec=read(path.join(group,'g40.cy.js'));
const smoke=read(path.join(group,'pruebas/g40_cypress_smoke.mjs'));
const view=read(path.join(front,'financial_valuation/pages/ConfiguracionContableView.tsx'));
const alert=read(path.join(front,'shared/design-system/Alert.tsx'));
const locale=JSON.parse(read(path.join(front,'shared/i18n/locales/es-CO/finanzas.json')));

test('el localizador del panel coincide con el frontal real',()=>{
  assert.match(view,/<Alert variant="warning" title=\{t\('config\.pendientes_titulo'/);
  assert.ok(view.indexOf('<Alert variant="warning"')<view.indexOf('<General config={c}'));
  assert.match(view,/<section aria-labelledby="cfg-general"/);
  assert.match(view,/<h2 id="cfg-general"/);
  assert.match(alert,/role="alert"/);
  assert.match(alert,/className=\{\['ds-alert', `ds-alert--\$\{variant\}`/);
  assert.match(alert,/className="ds-alert__title"/);

  assert.match(spec,/const ALERT_SELECTOR='\.ds-alert\.ds-alert--warning\[role="alert"\]'/);
  assert.match(spec,/querySelectorAll\(ALERT_SELECTOR\)/);
  assert.match(spec,/querySelector\('\.ds-alert__title'\)/);
  assert.doesNotMatch(spec,/#cfg-general\s+\[role=/);
  for(const id of spec.matchAll(/#(cfg-[\w-]+)/g))
    assert.ok(view.includes(`id="${id[1]}"`),`id inexistente en el frontal: ${id[1]}`);

  const literal=spec.match(/const TITLE=(\/[^\n]+\/i);/)?.[1];
  assert.ok(literal,'falta la expresión del título en el spec');
  const title=Function(`return ${literal}`)();
  for(const [count,key] of [[1,'pendientes_titulo_one'],[2,'pendientes_titulo_other']]){
    const actual=locale.config[key].replace('{{count}}',String(count));
    assert.match(actual,title,`el título real para ${count} no coincide con el spec`);
  }
  assert.match(smoke,/const title=count\+' '\+\(count===1\?'línea':'líneas'\)\+' de asiento sin cuenta contable';/);
  assert.match(smoke,/<div id="alert-slot"><\/div><section aria-labelledby="cfg-general"><h2 id="cfg-general">/);
  assert.match(smoke,/class="ds-alert ds-alert--warning"/);
  assert.match(smoke,/class="ds-alert__title"/);
  assert.match(smoke,/name:'aviso_plural',notice:true,conteo:2/);
});
