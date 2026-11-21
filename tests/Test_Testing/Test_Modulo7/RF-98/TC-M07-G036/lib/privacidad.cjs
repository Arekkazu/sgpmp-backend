function sanearError(valor, secretos=[]) {
  let texto=String(valor??'');
  for(const secreto of secretos.filter(x=>typeof x==='string'&&x.length>3))texto=texto.split(secreto).join('[RESERVADO]');
  return texto.replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+/g,'[JWT]')
    .replace(/[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'[CORREO]')
    .replace(/authorization\s*(?:[:=]|\\?"\s*:\s*\\?")\s*(?:Bearer\s+)?[^\s,}\\"]+/gi,'[CABECERA_RESERVADA]')
    .replace(/authorization/gi,'[CABECERA_RESERVADA]');
}
module.exports={sanearError};
