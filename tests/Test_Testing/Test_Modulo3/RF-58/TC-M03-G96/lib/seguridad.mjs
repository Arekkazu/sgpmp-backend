// Saneamiento de artefactos Newman antes de conservarlos en el RUN.
export function sanearArtefacto(texto, secretos) {
  const valores = [...new Set(secretos.filter((x) => typeof x === 'string' && x.length >= 4))]
    .sort((a, b) => b.length - a.length);
  const redactar = (entrada) => {
    let s = String(entrada);
    for (const valor of valores) s = s.split(valor).join('[REDACTADO]');
    return s.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g, '[JWT_REDACTADO]')
      .replace(/((?:refresh_token|x-sandbox-secret|password|contrasena)\s*[:=]\s*)[^\s;,"']+/gi, '$1[REDACTADO]')
      .replace(/(Authorization\s*:\s*Bearer\s+)\S+/gi, '$1[REDACTADO]')
      .replace(/(\\?"(?:serial|correo_electronico|email|nombre(?:_[a-z_]+)?|apellidos|telefono|direccion|identificador|numero_identificacion|fecha_nacimiento|contrasena|password|token|usuario|username|id_usuario)\\?"\s*:\s*\\?")[^"\\]*(\\?")/gi, '$1[REDACTADO]$2')
      .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[CORREO_REDACTADO]');
  };
  let json;
  try { json = JSON.parse(texto); } catch { return redactar(texto); }
  const visitar = (valor) => {
    if (typeof valor === 'string') return redactar(valor);
    if (Array.isArray(valor)) return valor.map(visitar);
    if (!valor || typeof valor !== 'object') return valor;
    const cabecera = /^(authorization|x-sandbox-secret|broker_service_token|sandbox_secret|tok_prod|tok_eng)$/i.test(String(valor.key ?? ''));
    const resultado = {};
    for (const [k, v] of Object.entries(valor)) {
      if (/^(authorization|x-sandbox-secret|broker_service_token|sandbox_secret|tok_prod|tok_eng|serial|correo_electronico|email|nombre(?:_[a-z_]+)?|apellidos|telefono|direccion|identificador|numero_identificacion|fecha_nacimiento|contrasena|password|token|usuario|username|id_usuario)$/i.test(k)
        || (cabecera && k === 'value')) resultado[k] = '[REDACTADO]';
      else if (k === 'data' && Array.isArray(v) && v.every((n) => Number.isInteger(n) && n >= 0 && n <= 255)) {
        const bytes = Buffer.from(v);
        const limpio = redactar(bytes.toString('utf8'));
        resultado[k] = limpio === bytes.toString('utf8') ? v : [...Buffer.from(limpio)];
      } else resultado[k] = visitar(v);
    }
    return resultado;
  };
  return redactar(JSON.stringify(visitar(json), null, 2));
}
