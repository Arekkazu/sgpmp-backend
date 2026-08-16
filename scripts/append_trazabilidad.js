#!/usr/bin/env node
/**
 * Se ejecuta como parte del pipeline de release (ver .releaserc.json,
 * plugin @semantic-release/exec, hook "prepareCmd").
 *
 * Recorre los commits entre la versión anterior y la nueva, extrae los
 * IDs de RF/RNF/RFC/BUG referenciados (según la convención definida en
 * CONTRIBUTING.md) y agrega una fila a TRAZABILIDAD_CAMBIOS.md.
 *
 * Uso: node append_trazabilidad.js <nextVersion> <gitTag> <lastVersion>
 */
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const [, , nextVersion, gitTag, lastVersion] = process.argv;
const FILE = path.join(__dirname, "..", "docs", "trazabilidad", "TRAZABILIDAD_CAMBIOS.md");

function getCommitsSinceLastRelease() {
  const range = lastVersion && lastVersion !== "undefined"
    ? `v${lastVersion}..HEAD`
    : "HEAD";
  try {
    const log = execSync(`git log ${range} --pretty=format:"%s|||%H"`, { encoding: "utf8" });
    return log.split("\n").filter(Boolean).map(line => {
      const [subject, hash] = line.split("|||");
      return { subject, hash: hash.slice(0, 7) };
    });
  } catch (e) {
    return [];
  }
}

function extractIds(subject) {
  const rf = [...subject.matchAll(/\b(RF|RNF)-\d+\b/g)].map(m => m[0]);
  const rfc = [...subject.matchAll(/\bRFC-\d+\b/g)].map(m => m[0]);
  const bug = [...subject.matchAll(/\bBUG-\d+\b/g)].map(m => m[0]);
  return { rf, rfc, bug };
}

function buildRow() {
  const commits = getCommitsSinceLastRelease();
  const rfSet = new Set();
  const rfcSet = new Set();
  const bugSet = new Set();

  commits.forEach(({ subject }) => {
    const { rf, rfc, bug } = extractIds(subject);
    rf.forEach(id => rfSet.add(id));
    rfc.forEach(id => rfcSet.add(id));
    bug.forEach(id => bugSet.add(id));
  });

  const fecha = new Date().toISOString().slice(0, 10);
  const commitList = commits.length
    ? commits.map(c => `${c.hash} ${c.subject}`).join("<br>")
    : "(sin commits detectados en el rango)";

  return `| ${nextVersion} | ${gitTag || "v" + nextVersion} | ${fecha} | ${[...rfSet].join(", ") || "—"} | ${[...rfcSet].join(", ") || "—"} | ${[...bugSet].join(", ") || "—"} | ${commitList} |\n`;
}

function ensureFile() {
  if (!fs.existsSync(FILE)) {
    fs.mkdirSync(path.dirname(FILE), { recursive: true });
    const header = `# Trazabilidad de cambios a main\n\n` +
      `Este archivo se genera automáticamente en cada release (ver ` +
      `\`scripts/append_trazabilidad.js\` y \`.releaserc.json\`). No editar a mano.\n\n` +
      `| Versión | Tag | Fecha | RF/RNF | RFC | Bugs | Commits incluidos |\n` +
      `|---|---|---|---|---|---|---|\n`;
    fs.writeFileSync(FILE, header, "utf8");
  }
}

ensureFile();
fs.appendFileSync(FILE, buildRow(), "utf8");
console.log(`TRAZABILIDAD_CAMBIOS.md actualizado con la versión ${nextVersion}`);
