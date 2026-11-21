import crypto from 'node:crypto';

const varint = n => { const out = []; do { let b = n & 127; n >>>= 7; if (n) b |= 128; out.push(b); } while (n); return out; };
const campo = (n, wire, bytes) => [n * 8 + wire, ...bytes];
const texto = (n, s) => { const b = Buffer.from(s); return campo(n, 2, [...varint(b.length), ...b]); };
const mensaje = (n, b) => campo(n, 2, [...varint(b.length), ...b]);
const entero = (n, x) => campo(n, 0, varint(x));

// ModelProto (onnx.proto): ir_version=1; GraphProto=7; OperatorSetIdProto=8.
export function onnxMinimo() {
  const forma = mensaje(1, entero(1, 1));
  const tensor = [...entero(1, 1), ...mensaje(2, forma)];
  const valor = nombre => [...texto(1, nombre), ...mensaje(2, mensaje(1, tensor))];
  const nodo = [...texto(1, 'x'), ...texto(2, 'y'), ...texto(4, 'Identity')];
  const grafo = [...mensaje(1, nodo), ...texto(2, 'g059_identity'),
    ...mensaje(11, valor('x')), ...mensaje(12, valor('y'))];
  return Buffer.from([...entero(1, 9), ...texto(2, 'qa-g059'),
    ...mensaje(7, grafo), ...mensaje(8, entero(2, 19))]);
}

// tensorflow/core/protobuf/saved_model.proto: schema_version=1 varint,
// meta_graphs=2. meta_graph.proto: meta_info_def=1, graph_def=2,
// signature_def=5. La firma sirve Placeholder FLOAT -> Identity FLOAT.
export function savedModelMinimo() {
  const attr = (k, value) => mensaje(5, [...texto(1, k), ...mensaje(2, entero(6, value))]);
  const placeholder = [...texto(1, 'x'), ...texto(2, 'Placeholder'), ...attr('dtype', 1)];
  const identity = [...texto(1, 'y'), ...texto(2, 'Identity'), ...texto(3, 'x'), ...attr('T', 1)];
  const graph = [...mensaje(1, placeholder), ...mensaje(1, identity)];
  const tensorInfo = name => [...texto(1, name), ...entero(2, 1), ...mensaje(3, [])];
  const entry = (key, value) => [...texto(1, key), ...mensaje(2, value)];
  const sig = [...mensaje(1, entry('x', tensorInfo('x:0'))),
    ...mensaje(2, entry('y', tensorInfo('y:0'))),
    ...texto(3, 'tensorflow/serving/predict')];
  const meta = [...mensaje(1, texto(4, 'serve')), ...mensaje(2, graph),
    ...mensaje(5, entry('serving_default', sig))];
  return Buffer.from([...entero(1, 1), ...mensaje(2, meta)]);
}

// Lector independiente de campos protobuf; comprueba estructura, no el primer byte.
export function camposProto(bytes) {
  const out = []; let i = 0;
  const leer = () => { let x = 0, shift = 0, b;
    do { if (i >= bytes.length || shift > 35) throw Error('PROTO_TRUNCADO');
      b = bytes[i++]; x += (b & 127) * 2 ** shift; shift += 7; } while (b & 128);
    return x;
  };
  while (i < bytes.length) {
    const tag = leer(), numero = tag >>> 3, wire = tag & 7;
    if (!numero || ![0, 2].includes(wire)) throw Error('PROTO_CAMPO_INVALIDO');
    const valor = wire === 0 ? leer() : (() => { const len = leer();
      if (i + len > bytes.length) throw Error('PROTO_TRUNCADO');
      const b = bytes.subarray(i, i + len); i += len; return b; })();
    out.push({ numero, wire, valor });
  }
  return out;
}
const unico = (campos, n, wire) => campos.find(x => x.numero === n && x.wire === wire)?.valor;
export function validarSavedModel(bytes) {
  const root = camposProto(bytes);
  if (unico(root, 1, 0) !== 1) return false;
  const metaBytes = unico(root, 2, 2); if (!metaBytes) return false;
  const meta = camposProto(metaBytes);
  const info = unico(meta, 1, 2), graph = unico(meta, 2, 2), sigEntry = unico(meta, 5, 2);
  if (!info || !graph || !sigEntry) return false;
  const tags = camposProto(info).filter(x => x.numero === 4 && x.wire === 2)
    .map(x => x.valor.toString());
  const nodes = camposProto(graph).filter(x => x.numero === 1 && x.wire === 2)
    .map(x => camposProto(x.valor));
  const ops = nodes.map(x => unico(x, 2, 2)?.toString());
  const entry = camposProto(sigEntry);
  const sig = unico(entry, 2, 2);
  if (unico(entry, 1, 2)?.toString() !== 'serving_default' || !sig) return false;
  const sf = camposProto(sig);
  return tags.includes('serve') && ops.includes('Placeholder') && ops.includes('Identity')
    && !!unico(sf, 1, 2) && !!unico(sf, 2, 2)
    && unico(sf, 3, 2)?.toString() === 'tensorflow/serving/predict';
}
export const sha256 = b => crypto.createHash('sha256').update(b).digest('hex');
