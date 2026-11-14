// TC-M09-G24 V2 — verificacion final de solo lectura (GET).
const H = require('./helpers.cjs');
const { runId } = H.settings({ requiereCaso: false });

(async () => {
  const token = await H.login();
  const actor = await H.validarActor(token);
  const ev54 = H.load(runId, 'TC-M09-54-v2.json');
  const items = (await H.get(`/configuracion/umbrales?id_especie=${ev54.especie.id}`, token)).items;
  const combinacion = items.filter((u) => u.id_variable_ambiental === ev54.variable.id);
  const u = items.find((x) => x.id_umbral_ambiental === ev54.idCreado);
  const ord = u ? [...u.niveles].sort((a, b) => Number(a.limite_inferior) - Number(b.limite_inferior)) : [];
  const res = {
    especie: ev54.especie, variable: ev54.variable, totalEspecie: items.length, ids: items.map((x) => x.id_umbral_ambiental),
    registrosDeLaCombinacion: combinacion.length,
    negativosSinPersistencia: combinacion.every((x) => x.id_umbral_ambiental === ev54.idCreado),
    tc54: u ? { id: u.id_umbral_ambiental, es_activo: u.es_activo, valor_min: u.valor_min, valor_max: u.valor_max, niveles: u.niveles,
      identicoAlCreado: JSON.stringify(u.niveles) === JSON.stringify(ev54.persistencia.detalle[0].niveles) && u.valor_min === ev54.persistencia.detalle[0].valor_min && u.valor_max === ev54.persistencia.detalle[0].valor_max,
      continuidad: ord.length === 3 && ord[0].limite_inferior === u.valor_min && ord[0].limite_superior === ord[1].limite_inferior && ord[1].limite_superior === ord[2].limite_inferior && ord[2].limite_superior === u.valor_max } : null,
    previosConservados: ev54.precondiciones.umbralesPreviosEspecie.every((id) => items.some((x) => x.id_umbral_ambiental === id)),
  };
  H.save(runId, 'verificacion-final-readonly.json', { actor: actor.correo_electronico, rol: actor.nombre_rol, operaciones: 'solo GET', resultado: res });
  console.log(JSON.stringify(res, null, 1));
})().catch((e) => { console.log('ERROR:', H.clean(e.message)); process.exitCode = 1; });
