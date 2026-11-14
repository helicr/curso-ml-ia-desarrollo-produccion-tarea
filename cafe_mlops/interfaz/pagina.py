"""La pagina de la interfaz: un solo HTML, sin recursos externos (funciona sin internet y dentro de un contenedor)."""

HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Café CQI · probabilidad de especialidad</title>
<link rel="icon" href="data:,">
<style>
:root{--fondo:#f6f4f1;--panel:#fff;--texto:#231f1c;--suave:#645c55;--borde:#ded7cf;--acento:#6b3f1d;--acento-t:#fff;
--alta:#1f7a4d;--alta-f:#e3f4ea;--media:#8a5a00;--media-f:#fdf1d8;--baja:#b3261e;--baja-f:#fbe5e3;--aviso:#7a4b00;--aviso-f:#fff6e0;--barra:#e3dbd2}
@media (prefers-color-scheme:dark){:root{--fondo:#16130f;--panel:#201b16;--texto:#ece6df;--suave:#a89f95;--borde:#37302a;--acento:#d9a56f;--acento-t:#1a1208;
--alta:#6fd19c;--alta-f:#173226;--media:#f0c060;--media-f:#352a12;--baja:#ff8a80;--baja-f:#3a1d1b;--aviso:#f0c060;--aviso-f:#33270f;--barra:#3a322a}}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--texto);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header.cab{background:var(--panel);border-bottom:1px solid var(--borde)}
.cab div{max-width:1100px;margin:0 auto;padding:10px 16px;display:flex;flex-wrap:wrap;gap:6px 22px;align-items:center;font-size:.88rem}
.cab span{color:var(--suave)}.cab b{color:var(--texto)}
.punto{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;background:var(--suave)}
.punto.ok{background:var(--alta)}.punto.mal{background:var(--baja)}
main{max-width:1100px;margin:0 auto;padding:22px 16px 48px}
h1{font-size:1.45rem;margin:0 0 4px}h2{font-size:1.1rem;margin:0 0 10px}
.sub{color:var(--suave);margin:0 0 18px}
.panel{background:var(--panel);border:1px solid var(--borde);border-radius:10px;padding:16px;margin-bottom:16px}
.dos{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px}
@media (max-width:520px){.dos{grid-template-columns:1fr}}
.dos .panel{margin-bottom:0}
label{font-weight:600;display:block;margin-bottom:4px}
textarea,input[type=text],select{width:100%;font:inherit;padding:7px 8px;border:1px solid var(--borde);border-radius:6px;background:var(--fondo);color:var(--texto)}
textarea{min-height:84px;resize:vertical;font:14px ui-monospace,Consolas,monospace}
.fila{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin-top:10px}
.rejilla{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.ayuda{color:var(--suave);font-size:.84rem;margin-top:3px}
button{font:inherit;border-radius:6px;border:1px solid var(--borde);background:var(--panel);color:var(--texto);padding:7px 14px;cursor:pointer}
button.principal{background:var(--acento);color:var(--acento-t);border-color:var(--acento);font-weight:600}
button:disabled{opacity:.55;cursor:wait}
.estado{font-size:.86rem;color:var(--suave)}
.error{background:var(--baja-f);color:var(--baja);border:1px solid var(--baja);border-radius:8px;padding:10px 12px;margin-bottom:16px}
.error ul{margin:6px 0 0;padding-left:20px}
.banner{background:var(--aviso-f);color:var(--aviso);border:1px solid var(--aviso);border-radius:8px;padding:10px 12px;margin-bottom:16px}
.tarjetas{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:12px}
.tarjeta{border-radius:8px;padding:10px 12px;border:1px solid var(--borde)}
.tarjeta b{font-size:1.5rem;display:block}
.alta{background:var(--alta-f);color:var(--alta)}.media{background:var(--media-f);color:var(--media)}.baja{background:var(--baja-f);color:var(--baja)}
.tabla{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--borde);vertical-align:top}
th{color:var(--suave);font-weight:600;white-space:nowrap}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.chip{display:inline-block;border-radius:999px;padding:1px 9px;font-size:.82rem;font-weight:600}
.barra{display:inline-block;width:70px;height:7px;border-radius:4px;background:var(--barra);vertical-align:middle;margin-left:6px;overflow:hidden}
.barra i{display:block;height:100%;background:var(--acento)}
.avisos{margin:4px 0 0;padding:6px 10px;list-style:none;background:var(--aviso-f);color:var(--aviso);border-radius:6px;font-size:.84rem}
.avisos li+li{margin-top:3px}
details summary{cursor:pointer;color:var(--acento);font-size:.85rem}
dl{display:grid;grid-template-columns:auto auto;gap:2px 12px;margin:6px 0 0;font-size:.84rem}
dt{color:var(--suave)}dd{margin:0;font-variant-numeric:tabular-nums}
.pie{color:var(--suave);font-size:.84rem;margin-top:12px}
code{font-family:ui-monospace,Consolas,monospace;font-size:.9em}
[hidden]{display:none!important}
</style>
</head>
<body>
<header class="cab"><div>
  <span>Repositorio: <b id="c-repo">…</b></span>
  <span>Modelo: <b id="c-modelo">…</b></span>
  <span><i class="punto" id="c-punto"></i>API: <b id="c-api">comprobando…</b></span>
  <span>Lotes en la base: <b id="c-lotes">…</b></span>
</div></header>
<main>
<h1>¿Será café de especialidad?</h1>
<p class="sub">Consulta lotes que ya están en la base, o prueba un lote nuevo con sus datos de recepción (antes de catarlo). La probabilidad la calcula el modelo; el tramo y la recomendación son una regla de negocio provisional.</p>

<div id="banner" class="banner" hidden></div>
<div id="error" class="error" hidden role="alert"></div>

<div class="dos">
<section class="panel" aria-label="Lotes existentes">
  <h2>1 · Lotes que ya están en la base</h2>
  <label for="ids">Ids de lote</label>
  <textarea id="ids" placeholder="1&#10;25, 40 300&#10;(separados por comas, espacios o saltos de línea)"></textarea>
  <div class="fila">
    <button class="principal" id="consultar">Consultar</button>
    <button id="ejemplo-ids">Ejemplo</button>
    <button id="limpiar">Limpiar</button>
  </div>
  <div class="fila">
    <div>
      <label for="fichero">…o cargar un CSV de lotes</label>
      <input type="file" id="fichero" accept=".csv,.txt,text/csv,text/plain">
      <div class="ayuda">Con columna <code>lote_id</code> (o una lista de ids), consulta lotes de la base. Con las columnas <code>especie</code>, <code>pais</code>… predice lotes nuevos. El CSV que descargas sirve de modelo.</div>
    </div>
  </div>
</section>

<section class="panel" aria-label="Lote nuevo">
  <h2>2 · Un lote nuevo</h2>
  <form id="formulario" autocomplete="off" novalidate>
  <div class="rejilla">
    <div><label for="f-especie">Especie</label><select id="f-especie"></select></div>
    <div><label for="f-pais">País de origen</label><select id="f-pais"></select><input type="text" id="f-pais-otro" placeholder="Escribe el país" hidden></div>
    <div><label for="f-variedad">Variedad</label><select id="f-variedad"></select><input type="text" id="f-variedad-otro" placeholder="Escribe la variedad" hidden></div>
    <div><label for="f-metodo_proceso">Método de beneficio</label><select id="f-metodo_proceso"></select></div>
    <div><label for="f-color">Color del grano verde</label><select id="f-color"></select></div>
    <div><label for="f-altitud_media_m">Altitud media (m)</label><input type="text" inputmode="decimal" id="f-altitud_media_m"><div class="ayuda" id="a-altitud_media_m"></div></div>
    <div><label for="f-humedad">Humedad (fracción)</label><input type="text" inputmode="decimal" id="f-humedad"><div class="ayuda" id="a-humedad"></div></div>
    <div><label for="f-defectos_cat1">Defectos de categoría 1</label><input type="text" inputmode="decimal" id="f-defectos_cat1"><div class="ayuda" id="a-defectos_cat1"></div></div>
    <div><label for="f-defectos_cat2">Defectos de categoría 2</label><input type="text" inputmode="decimal" id="f-defectos_cat2"><div class="ayuda" id="a-defectos_cat2"></div></div>
    <div><label for="f-quakers">Granos «quaker»</label><input type="text" inputmode="decimal" id="f-quakers"><div class="ayuda" id="a-quakers"></div></div>
  </div>
  <p class="ayuda">Deja vacío lo que no conozcas: el modelo lo trata como «sin dato» y lo avisa. Un país o variedad que no esté en la lista se puede escribir con «Otro»: el modelo no lo conoce y lo avisará.</p>
  <div class="fila">
    <button type="submit" class="principal" id="predecir-nuevo">Predecir lote nuevo</button>
    <button type="button" id="ejemplo-nuevo">Rellenar con un ejemplo</button>
    <button type="button" id="limpiar-nuevo">Vaciar</button>
  </div>
  </form>
</section>
</div>

<section class="panel" id="resultado" hidden aria-live="polite" style="margin-top:16px">
  <h2>Resultado</h2>
  <div class="tarjetas" id="tarjetas"></div>
  <p class="estado" id="resumen"></p>
  <div class="tabla"><table>
    <thead><tr><th>Lote</th><th>Probabilidad de especialidad</th><th>Tramo</th><th>Recomendación y avisos</th><th>Variables</th></tr></thead>
    <tbody id="filas"></tbody>
  </table></div>
  <div id="faltan"></div>
  <p><button id="descargar">Descargar CSV</button></p>
  <p class="pie" id="pie"></p>
</section>
</main>

<script>
const $ = id => document.getElementById(id);
const VARS = ['especie','pais','variedad','metodo_proceso','color','altitud_media_m','humedad','defectos_cat1','defectos_cat2','quakers'];
const NUM = ['altitud_media_m','humedad','defectos_cat1','defectos_cat2','quakers'];
const NOMBRES = {especie:'Especie', pais:'País', variedad:'Variedad', metodo_proceso:'Beneficio', color:'Color', altitud_media_m:'Altitud (m)',
  humedad:'Humedad', defectos_cat1:'Defectos cat. 1', defectos_cat2:'Defectos cat. 2', quakers:'Quakers'};
let ESTADO = null, ULTIMO = null;
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = p => (100 * p).toLocaleString('es', {maximumFractionDigits: 1}) + ' %';

function mostrarError(texto, errores){
  const e = $('error');
  if (!texto){ e.hidden = true; e.textContent = ''; return; }
  let html = `<b>${esc(texto)}</b>`;
  if (errores && errores.length){
    html += '<ul>' + errores.slice(0, 20).map(x => `<li>${x.fila ? 'Fila ' + x.fila + ': ' : ''}${x.campo ? '<b>' + esc(NOMBRES[x.campo] || x.campo) + '</b>: ' : ''}${esc(x.mensaje)}</li>`).join('') +
      (errores.length > 20 ? `<li>…y ${errores.length - 20} más.</li>` : '') + '</ul>';
  }
  e.innerHTML = html; e.hidden = false;
}

async function pedir(url, cuerpo){
  let r;
  try { r = await fetch(url, cuerpo ? {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(cuerpo)} : {}); }
  catch (e) { const x = new Error('No se pudo contactar con la interfaz. ¿Sigue en marcha?'); x.errores = []; throw x; }
  const datos = await r.json().catch(() => ({}));
  if (!r.ok){
    const x = new Error(datos.detalle || (r.status === 503 ? 'Servicio no disponible.' : 'La petición no se pudo atender.'));
    x.errores = datos.errores || []; x.codigo = r.status; throw x;
  }
  return datos;
}

/* ---------------- cabecera y formulario ---------------- */
function llenar(sel, valores, opciones){
  const s = $(sel); s.innerHTML = '';
  const add = (v, t) => { const o = document.createElement('option'); o.value = v; o.textContent = t; s.appendChild(o); };
  if (opciones.vacio) add('', '(sin dato)');
  valores.forEach(v => add(v, v));
  if (opciones.otro) add('__otro__', 'Otro (escribir)…');
}

async function cargarEstado(){
  try { ESTADO = await pedir('estado'); }
  catch (e) { $('c-api').textContent = 'sin respuesta'; $('c-punto').className = 'punto mal'; mostrarError(e.message); return; }
  const E = ESTADO;
  $('c-repo').textContent = E.repositorio || 'sin identificar'; $('c-repo').title = E.repositorio ? '' : 'Define TALLER_REPOSITORIO (en un Codespace lo pone GITHUB_REPOSITORY)';
  const m = E.modelo;
  $('c-modelo').textContent = m ? `${m.modelo}${m.version_modelo ? ' v' + m.version_modelo : ''} · huella ${m.huella_datos}` : 'sin modelo';
  $('c-api').textContent = E.api.estado === 'lista' ? 'lista' : 'no disponible';
  $('c-punto').className = 'punto ' + (E.api.estado === 'lista' ? 'ok' : 'mal');
  $('c-lotes').textContent = E.datos.estado === 'ok' ? E.datos.lotes.toLocaleString('es') : 'sin base';
  const avisos = [];
  if (E.api.estado !== 'lista') avisos.push('La API del modelo no está disponible: ' + E.api.detalle);
  if (E.datos.estado !== 'ok') avisos.push('Sin base de datos: no se pueden consultar lotes por id (el formulario de lote nuevo sí funciona si la API responde). ' + E.datos.detalle);
  $('banner').innerHTML = avisos.map(esc).join('<br>'); $('banner').hidden = !avisos.length;
  const o = E.opciones;
  llenar('f-especie', o.especie, {}); llenar('f-pais', o.pais, {vacio: true, otro: true}); llenar('f-variedad', o.variedad, {vacio: true, otro: true});
  llenar('f-metodo_proceso', o.metodo_proceso, {vacio: true}); llenar('f-color', o.color, {vacio: true});
  $('f-pais').value = ''; $('f-variedad').value = ''; $('f-metodo_proceso').value = ''; $('f-color').value = '';
  for (const c of NUM){
    const l = E.limites[c];
    $('a-' + c).textContent = c === 'humedad' ? `Entre 0 y 1. Un 0 se trata como «no medido».` :
      (l.unidad === 'm' ? `Entre ${l.minimo} y ${l.maximo} m.` : `Entre 0 y ${l.maximo}.`);
  }
}
for (const c of ['pais', 'variedad']) $('f-' + c).addEventListener('change', e => { $('f-' + c + '-otro').hidden = e.target.value !== '__otro__'; });

function valorNumerico(t){
  t = t.trim(); if (!t) return null;
  const n = Number(t.replace(',', '.'));
  return Number.isFinite(n) ? n : t;   // si no es número se manda tal cual: la validación lo explica
}
function loteDelFormulario(){
  const l = {};
  for (const c of VARS){
    if (NUM.includes(c)) { l[c] = valorNumerico($('f-' + c).value); continue; }
    let v = $('f-' + c).value;
    if (v === '__otro__') v = $('f-' + c + '-otro').value.trim();
    l[c] = v === '' ? null : v;
  }
  return l;
}
function ponerEnFormulario(l){
  for (const c of VARS){
    const v = l[c] === null || l[c] === undefined ? '' : l[c];
    if (NUM.includes(c)) { $('f-' + c).value = String(v).replace('.', ','); continue; }
    const s = $('f-' + c); const hay = [...s.options].some(o => o.value === v);
    if (hay) { s.value = v; if ($('f-' + c + '-otro')) $('f-' + c + '-otro').hidden = true; }
    else if ($('f-' + c + '-otro')) { s.value = '__otro__'; $('f-' + c + '-otro').hidden = false; $('f-' + c + '-otro').value = v; }
  }
}

/* ---------------- consultas ---------------- */
async function ejecutar(boton, texto, accion){
  mostrarError('');
  boton.disabled = true; const t0 = boton.textContent; boton.textContent = texto;
  try { ULTIMO = await accion(); pintar(ULTIMO); }
  catch (e) { mostrarError(e.message, e.errores); $('resultado').hidden = true; }
  finally { boton.disabled = false; boton.textContent = t0; }
}
const idsDelTexto = t => [...new Set((t.match(/\d+/g) || []).map(Number))];

$('consultar').onclick = () => {
  const ids = idsDelTexto($('ids').value);
  if (!ids.length){ mostrarError('Escribe al menos un id de lote o carga un CSV.'); return; }
  const max = ESTADO ? ESTADO.maximo_lotes : 1000;
  if (ids.length > max){ mostrarError(`Como mucho ${max} lotes por consulta (hay ${ids.length}).`); return; }
  ejecutar($('consultar'), 'Consultando…', () => pedir('recomendar', {lote_ids: ids}));
};
$('formulario').addEventListener('submit', ev => {
  ev.preventDefault();
  ejecutar($('predecir-nuevo'), 'Calculando…', () => pedir('recomendar/nuevo', loteDelFormulario()));
});
$('ejemplo-ids').onclick = () => { if (ESTADO && ESTADO.ejemplos.length) $('ids').value = ESTADO.ejemplos.join(', ') + ', 99999'; else mostrarError('No hay lotes en la base para dar un ejemplo.'); };
$('limpiar').onclick = () => { $('ids').value = ''; $('fichero').value = ''; $('resultado').hidden = true; mostrarError(''); };
$('ejemplo-nuevo').onclick = () => { if (ESTADO) ponerEnFormulario(ESTADO.ejemplo_lote); };
$('limpiar-nuevo').onclick = () => { $('formulario').reset(); ['pais','variedad'].forEach(c => { $('f-' + c).value = ''; $('f-' + c + '-otro').hidden = true; }); };

/* ---------------- CSV ---------------- */
function parseCSV(texto){
  texto = texto.replace(/^﻿/, '');
  const primera = texto.split(/\r?\n/, 1)[0];
  const sep = primera.includes(';') && !primera.includes(',') ? ';' : (primera.includes('\t') && !primera.includes(',') ? '\t' : ',');
  const filas = []; let fila = [], campo = '', comillas = false;
  for (let i = 0; i < texto.length; i++){
    const c = texto[i];
    if (comillas){
      if (c === '"'){ if (texto[i+1] === '"'){ campo += '"'; i++; } else comillas = false; } else campo += c;
    } else if (c === '"') comillas = true;
    else if (c === sep){ fila.push(campo); campo = ''; }
    else if (c === '\n' || c === '\r'){ if (c === '\r' && texto[i+1] === '\n') i++; fila.push(campo); filas.push(fila); fila = []; campo = ''; }
    else campo += c;
  }
  if (campo !== '' || fila.length){ fila.push(campo); filas.push(fila); }
  return filas.filter(f => f.some(x => x.trim() !== ''));
}
$('fichero').onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  mostrarError('');
  const filas = parseCSV(await f.text());
  if (!filas.length){ mostrarError(`El archivo ${f.name} está vacío.`); return; }
  const cab = filas[0].map(c => c.trim().toLowerCase());
  if (cab.includes('especie')){
    const lotes = filas.slice(1).map(r => { const l = {}; for (const v of VARS){ const i = cab.indexOf(v); const t = i < 0 ? '' : (r[i] || '').trim();
      l[v] = NUM.includes(v) ? valorNumerico(t) : (t === '' ? null : t); } return l; });
    if (!lotes.length){ mostrarError(`El archivo ${f.name} no tiene filas de lotes.`); return; }
    ejecutar($('consultar'), 'Calculando…', () => pedir('recomendar/nuevos', {lotes}));
    return;
  }
  let col = cab.findIndex(c => ['lote_id', 'id_lote', 'lote', 'id'].includes(c));
  const conCabecera = col >= 0 || isNaN(Number(cab[0]));
  if (col < 0) col = 0;
  const ids = [...new Set(filas.slice(conCabecera ? 1 : 0).map(r => (r[col] || '').trim()).filter(v => /^\d+$/.test(v)).map(Number))];
  if (!ids.length){ mostrarError(`No encontré ids de lote ni columnas de variables en ${f.name}.`); return; }
  $('ids').value = ids.join('\n');
  ejecutar($('consultar'), 'Consultando…', () => pedir('recomendar', {lote_ids: ids}));
};
function descargar(){
  if (!ULTIMO) return;
  const cab = ['lote_id', 'probabilidad_especialidad', 'tramo', 'recomendacion', 'avisos', ...VARS];
  const q = v => { const s = v === null || v === undefined ? '' : String(v); return /[",;\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  const filas = ULTIMO.resultados.map(x => [x.lote_id, x.probabilidad, x.segmento, x.recomendacion, x.avisos.map(a => a.mensaje).join(' | '), ...VARS.map(k => x.variables[k])].map(q).join(','));
  const blob = new Blob(['﻿' + [cab.join(','), ...filas].join('\r\n')], {type: 'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'lotes_especialidad.csv'; a.click(); URL.revokeObjectURL(a.href);
}
$('descargar').onclick = descargar;

/* ---------------- resultado ---------------- */
function pintar(r){
  const segs = ESTADO ? ESTADO.segmentos : [];
  $('tarjetas').innerHTML = segs.map((s, i) => {
    const tramo = !i ? `≥ ${pct(s.desde)}` : (s.desde > 0 ? `${pct(s.desde)} – ${pct(segs[i-1].desde)}` : `< ${pct(segs[i-1].desde)}`);
    return `<div class="tarjeta ${esc(s.segmento)}"><b>${r.por_segmento[s.segmento] || 0}</b>Tramo ${esc(s.segmento)} (${tramo})</div>`;
  }).join('');
  $('resumen').textContent = r.origen === 'ids' ? `${r.encontrados} de ${r.pedidos} lotes con predicción.` : `${r.encontrados} lote(s) nuevo(s) con predicción.`;
  $('filas').innerHTML = r.resultados.map((x, n) => {
    const vars = VARS.map(k => { const v = x.variables[k];
      return `<dt>${esc(NOMBRES[k])}</dt><dd>${v === null || v === undefined ? '—' : esc(typeof v === 'number' ? v.toLocaleString('es') : v)}</dd>`; }).join('');
    const avisos = x.avisos.length ? `<ul class="avisos">${x.avisos.map(a => `<li>⚠ ${esc(a.mensaje)}</li>`).join('')}</ul>` : '';
    return `<tr><td class="num"><b>${x.lote_id === null ? 'nuevo ' + (n + 1) : x.lote_id}</b></td>
      <td class="num">${pct(x.probabilidad)}<span class="barra" aria-hidden="true"><i style="width:${(100*x.probabilidad).toFixed(1)}%"></i></span></td>
      <td><span class="chip ${esc(x.segmento)}">${esc(x.segmento)}</span></td><td>${esc(x.recomendacion)}${avisos}</td>
      <td><details><summary>Ver</summary><dl>${vars}</dl></details></td></tr>`;
  }).join('');
  $('faltan').innerHTML = r.no_encontrados.length ? `<p><b>Sin predicción (${r.no_encontrados.length}):</b></p><ul>` +
    r.no_encontrados.map(f => `<li><code>${f.lote_id}</code>: ${esc(f.motivo)}</li>`).join('') + '</ul>' : '';
  const m = r.modelo;
  $('pie').textContent = (m ? `Modelo ${m.modelo}${m.version_modelo ? ' v' + m.version_modelo : ''} · huella ${m.huella_datos}. ` : '') +
    'La probabilidad la calcula el modelo; el tramo y la recomendación son una regla de negocio provisional (config.SEGMENTOS).';
  $('resultado').hidden = false;
  $('resultado').scrollIntoView({block: 'nearest'});
}
cargarEstado();
</script>
</body>
</html>
"""
