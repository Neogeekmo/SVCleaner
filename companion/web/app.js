'use strict';
const $ = (selector) => document.querySelector(selector);
let state, csrf, page = 'overview', selected = null, currentPath = [], treeOffset = 0;
let filters = {query: '', account: '', scope: '', backups: false}, charQuery = '';
let pins = {left: null, right: null}, busy = false;
const fileSelection = new Set();
let deletingFiles = new Set();
const titles = {
  overview: ['Votre compte, au propre.', 'Comprenez ce que vos addons sauvegardent. Gardez ce qui compte.', 'Vue d’ensemble'],
  files: ['Vos SavedVariables.', 'Explorez les clés, éditez les valeurs et préparez les modifications.', 'SavedVariables'],
  orphans: ['Un peu de place à retrouver.', 'Fichiers sans addon installé correspondant. Vérifiez-les avant de les retirer.', 'À nettoyer'],
  characters: ['Chaque personnage, à sa place.', 'Dossiers locaux et personnages observés : des indices, jamais une preuve de suppression.', 'Personnages'],
  diff: ['Deux personnages. Une vue claire.', 'Comparez les valeurs et transférez les changements en conservant les identifiants.', 'Comparaison'],
  cache: ['Un entretien ciblé.', 'Distinguez les caches temporaires, les réglages et les actions de dépannage.', 'Caches & dépannage'],
  history: ['Vos changements sont sauvegardés.', 'Les fichiers originaux restent disponibles. Restaurez tant que les données actives n’ont pas changé.', 'Sauvegardes']
};
function h(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'class') element.className = value;
    else if (key === 'style') Object.assign(element.style, value);
    else if (key.startsWith('on')) element.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'disabled' || key === 'checked') element[key] = value;
    else element.setAttribute(key, value);
  }
  children.flat().forEach(child => {
    if (child !== null && child !== undefined) element.append(child instanceof Node ? child : document.createTextNode(String(child)));
  });
  return element;
}
function bytes(value) {
  const size = Math.abs(value);
  return (value < 0 ? '−' : '') + (size >= 1048576 ? (size / 1048576).toLocaleString(I18n.tag, {maximumFractionDigits: 2}) + ' ' + t('Mio') : size >= 1024 ? (size / 1024).toLocaleString(I18n.tag, {maximumFractionDigits: 1}) + ' ' + t('Kio') : size.toLocaleString(I18n.tag) + ' ' + t('octets'));
}
function date(value) { return new Date(value * 1000).toLocaleString(I18n.tag); }
function pathText(path) { return path.map(key => String(key.value)).join(' / '); }
function valueText(value) { return value === null ? t('— absent —') : String(value); }
function toast(message) { $('#toast').textContent = message; $('#toast').classList.remove('hidden'); clearTimeout(toast.timer); toast.timer = setTimeout(() => $('#toast').classList.add('hidden'), 7000); }
function button(label, action, style = '', disabled = false) { return h('button', {class: 'button ' + style, onClick: action, disabled}, label); }
function badge(label, style = '') { return h('span', {class: 'badge ' + style}, label); }
function empty(title, text) { return h('div', {class: 'empty'}, h('strong', {}, title), text); }
function panel(title, body, note = '') { return h('section', {class: 'panel'}, h('div', {class: 'panel-head'}, h('h2', {}, title), h('small', {}, note)), body); }
function table(headers, rows, cls = '') { return h('div', {class: 'table-wrap'}, h('table', {class: cls}, h('thead', {}, h('tr', {}, headers.map(v => h('th', {}, v)))), h('tbody', {}, rows))); }
async function get(path) {
  const response = await fetch(path, {headers: {'X-SVC-Language': I18n.language}});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || t("Erreur locale"));
  return result;
}
async function post(path, payload = {}) {
  const response = await fetch('/api/' + path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-SVC-Token': csrf, 'X-SVC-Language': I18n.language}, body: JSON.stringify(payload)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || t("Erreur locale"));
  return result;
}
async function action(fn) {
  if (busy) return;
  busy = true;
  try { await fn(); } catch (error) { toast(error.message); }
  finally { busy = false; }
}
function update(next) {
  if(state?.root!==next.root){fileSelection.clear();pins={left:null,right:null};diffFiles={left:null,right:null};}
  state={...next,versions:next.versions||state?.versions||[],currentVersion:next.currentVersion||state?.currentVersion};
  deletingFiles=new Set(state.pending.filter(change=>change.operation==='delete').map(change=>change.id));
  for(const side of ['left','right'])if(pins[side]&&(!state.records.some(r=>r.id===pins[side].id)||deletingFiles.has(pins[side].id)))pins[side]=null;
  comparisonOptions.clear();renderChrome();
}
function renderChrome() {
  $('#nav-files').textContent = state.stats.files;
  $('#nav-orphans').textContent = state.records.filter(r => r.status === 'orphan' && !r.backup).length;
  $('#location').textContent = '↳ ' + state.root;
  const versionSelect = $('#wow-version');
  versionSelect.replaceChildren(...state.versions.map(version => h('option', {value: version.id, disabled: !version.available, title: version.reason || version.root}, version.label + (version.available ? '' : t(' · indisponible')))));
  versionSelect.value = state.currentVersion?.id || '';
  $('#active-version').textContent = state.currentVersion?.label || 'WoW';
  $('#scan-time').textContent = t("Dernière analyse · ") + date(state.scanned);
  document.querySelectorAll('nav button').forEach(node => node.classList.toggle('active', node.dataset.page === page));
  const [title, subtitle, crumb] = titles[page].map(key => t(key));
  $('#page-title').textContent = title; $('#page-subtitle').textContent = subtitle; $('#crumb').textContent = crumb;
  const basket = $('#basket'); basket.replaceChildren(); basket.classList.toggle('hidden', !state.pending.length);
  if (state.pending.length) basket.append(
    h('div', {}, h('strong', {}, t("{p0} fichier(s) dans le panier", {p0: (state.pending.length)})), h('small', {}, t("Application hors jeu · sauvegarde des originaux · aucune modification avant validation"))),
    h('div', {class: 'actions'}, button(t("Voir les changements"), showBasket, 'small'), button(t("Abandonner"), () => action(async () => { update(await post('discard')); await render(); }), 'small'), button(t("Appliquer le panier"), applyBasket, 'primary'))
  );
}
async function navigate(next) { page = next; await render(); }
async function render() {
  document.body.dataset.page=page;
  renderChrome();
  const content = $('#content'); content.replaceChildren();
  try {
    if (page === 'overview') overview(content);
    else if (page === 'files' || page === 'orphans') await filesPage(content);
    else if (page === 'characters') charactersPage(content);
    else if (page === 'diff') await diffPage(content);
    else if (page === 'cache') await cachePage(content);
    else historyPage(content);
  } catch (error) { content.append(h('div', {class: 'error-box'}, error.message)); }
}
function metrics() {
  return h('div', {class: 'metrics'}, [
    [t("SavedVariables actives"), bytes(state.stats.bytes), t("{p0} fichiers · {p1} addons", {p0: (state.stats.files), p1: (state.stats.addons)}), '▤'],
    [t("Sans addon correspondant"), bytes(state.stats.orphanBytes), t("Candidats à examiner manuellement"), '◇'],
    [t("Retiré des fichiers actifs"), bytes(state.stats.savedBytes), t("Sauvegardes conservées sur disque"), '↙'],
    [t("Personnages locaux"), state.stats.characters, t("Existence en jeu non vérifiée"), '♙']
  ].map(([label, number, note, icon]) => h('div', {class: 'metric'}, h('div', {class: 'label'}, label, h('span', {class: 'symbol'}, icon)), h('div', {class: 'number'}, number), h('div', {class: 'note'}, note))));
}
function overview(content) {
  content.append(metrics());
  const maximum = state.groups[0]?.bytes || 1;
  const bars = h('div', {class: 'panel-body bars'}, state.groups.slice(0, 6).map((entry, i) => h('div', {class: 'bar-row'}, h('div', {class: 'bar-name'}, entry.addon), h('div', {class: 'bar-track'}, h('div', {class: 'bar-fill', style: {width: `${entry.bytes / maximum * 100}%`, opacity: String(1 - i * .1)}})), h('div', {class: 'bar-value'}, bytes(entry.bytes)))));
  const orphan = state.stats.orphanBytes, total = state.stats.bytes, installed = Math.max(0, total - orphan);
  const ratio = total ? orphan / total * 100 : 0;
  const donut = h('div', {class: 'panel-body'}, h('div', {class: 'donut-area'}, h('div', {class: 'donut', style: {background: `conic-gradient(var(--gold) 0 ${100 - ratio}%, var(--red) ${100 - ratio}% 100%)`}}, h('div', {class: 'donut-center'}, `${Math.round(100 - ratio)}%`, h('small', {}, t("LIÉS À UN ADDON")))), h('div', {class: 'legend'}, h('div', {}, h('div', {class: 'legend-line'}, h('i'), t("Installés / liés")), h('strong', {}, bytes(installed))), h('div', {}, h('div', {class: 'legend-line'}, h('i', {style: {background: 'var(--red)'}}), t("Sans correspondance")), h('strong', {}, bytes(orphan))))), h('p', {class: 'inline-note'}, t("{p0} de fichiers .bak en supplément. Mesures réelles sur disque ; les fichiers système Blizzard sont exclus.", {p0: (bytes(state.stats.backupBytes))})));
  content.append(h('div', {class: 'panels'}, panel(t("Les addons les plus volumineux"), bars, t("TAILLE DES FICHIERS .LUA")), panel(t("Ce que votre compte conserve"), donut, t("RÉPARTITION"))));
  content.append(h('div', {class: 'callout'}, h('span', {class: 'callout-icon'}, '◇'), h('div', {}, h('h3', {}, t("{p0} fichier(s) à examiner", {p0: (state.records.filter(r => r.status === 'orphan' && !r.backup).length)})), h('p', {}, t("Un addon désinstallé peut laisser ses réglages. Vous pouvez les garder ou les mettre en quarantaine."))), button(t("Examiner les candidats →"), () => navigate('orphans'), 'small')));
  const rows = state.groups.slice(0, 7).map(entry => {
    const related = state.records.filter(r => r.addon === entry.addon && !r.backup);
    return h('tr', {}, h('td', {}, h('strong', {}, entry.addon), h('small', {}, related[0]?.title || '')), h('td', {}, t('{count} fichier(s)', {count: related.length})), h('td', {class: 'mono'}, bytes(entry.bytes)), h('td', {}, statusBadge(related[0])), h('td', {}, button(t("Explorer ↗"), () => openFile(related[0].id), 'small')));
  });
  content.append(panel(t("Vos données, addon par addon"), table([t("ADDON"), t("FICHIERS"), t("VOLUME"), t("CORRESPONDANCE"), ''], rows), t("COMPTE + PERSONNAGES")));
}
function statusBadge(record) {
  if (!record) return badge(t("Inconnu"), 'muted');
  if (record.backup) return badge(t("Sauvegarde .bak"), 'muted');
  if (record.addon === 'SVCleaner') return badge(t("Gestionnaire · protégé"), 'muted');
  if (record.status === 'orphan') return badge(t("À vérifier"), 'warning');
  if (record.status === 'linked') return badge(t("Lié : ") + record.links.join(', '), 'warning');
  if (record.status === 'system') return badge(t("Blizzard · protégé"), 'muted');
  if (record.uncertain) return badge(t("TOC à vérifier"), 'warning');
  return badge(t("Addon installé"));
}
function charactersPage(content) {
  const cards = h('div', {class: 'character-grid'});
  const search = h('input', {placeholder: t('Rechercher'), 'aria-label': t('Rechercher'), value: charQuery, onInput: event => { charQuery = event.target.value; draw(); }});
  content.append(h('div', {class: 'filters'}, search), cards);
  function draw() {
    const visible = state.characters.filter(character => `${character.label} ${character.account}`.toLocaleLowerCase(I18n.tag).includes(charQuery.toLocaleLowerCase(I18n.tag)));
    cards.replaceChildren(...visible.map(character => h('section', {class: 'character-card'},
      h('div', {class: 'avatar'}, character.name.slice(0, 1)), h('h3', {}, character.name),
      h('p', {}, character.realm + ' · ' + character.account), badge(character.status, 'muted'),
      button(t('Fichiers'), () => { filters = {query: character.name, account: character.account, scope: 'character', backups: false}; selected = null; charQuery = ''; return action(() => navigate('files')); }, 'small')
    )));
    if (!visible.length) cards.append(empty(t('Aucun personnage local'), t('Aucun dossier de personnage trouvé pour cette version.')));
  }
  draw();
}
function filteredRecords() {
  return state.records.filter(r => (!filters.account || r.account === filters.account) && (!filters.scope || r.scope === filters.scope) && (filters.backups || !r.backup) && (page !== 'orphans' || r.status === 'orphan') && `${r.addon} ${r.title} ${r.character || ''} ${r.roots.join(' ')}`.toLowerCase().includes(filters.query.toLowerCase()));
}
function filterControls() {
  const query = h('input', {placeholder: t("Rechercher un addon, une variable, un personnage…"), 'aria-label': t("Rechercher"), value: filters.query, onInput: event => { filters.query = event.target.value; clearTimeout(filterControls.timer); filterControls.timer = setTimeout(refreshFileList, 180); }});
  const account = h('select', {'aria-label': t("Filtrer le compte"), onChange: event => { filters.account = event.target.value; refreshFileList(); }}, h('option', {value: ''}, t("Tous les comptes")), [...new Set(state.records.map(r => r.account))].map(name => h('option', {value: name}, name))); account.value = filters.account;
  const scope = h('select', {'aria-label': t("Filtrer la portée"), onChange: event => { filters.scope = event.target.value; refreshFileList(); }}, [['', t("Toutes les portées")], ['account', t("Compte")], ['character', t("Personnage")], ['machine', t("Installation")], ['system', t("Système Blizzard")]].map(([value, label]) => h('option', {value}, label))); scope.value = filters.scope;
  return h('div', {class: 'filters'}, query, account, scope, h('label', {class: 'checkbox'}, h('input', {type: 'checkbox', checked: filters.backups, onChange: event => { filters.backups = event.target.checked; refreshFileList(); }}), t("Inclure les .bak")));
}
async function filesPage(content) {
  content.append(filterControls());
  content.append(h('div', {id: 'bulk-actions', class: 'bulk-toolbar'}));
  if (page === 'orphans') content.append(h('p', {class: 'inline-note'}, t("Une absence de correspondance ne garantit pas que ces données sont inutiles : addon renommé, installation incomplète ou projet temporairement retiré. Les .bak se retirent séparément.")));
  const fileList = h('div', {id: 'file-list', class: 'file-list'});
  const tree = h('section', {id: 'tree', class: 'panel tree'});
  content.append(h('div', {class: 'explorer'}, panel(t("Fichiers"), fileList, ''), tree));
  refreshFileList();
  await browseTree();
}
function refreshFileList() {
  const container = $('#file-list'); if (!container) return;
  const records = filteredRecords();
  const allowed = new Set(records.filter(canSelectFile).map(record => record.id));
  for (const id of fileSelection) if (!allowed.has(id)) fileSelection.delete(id);
  container.replaceChildren(...records.map(r => h('div', {class: 'file-choice' + (fileSelection.has(r.id) ? ' checked' : '')},
    h('input', {type: 'checkbox', checked: fileSelection.has(r.id), disabled: !canSelectFile(r), 'aria-label': t("Sélectionner ") + r.path, onChange: event => { if (event.target.checked) fileSelection.add(r.id); else fileSelection.delete(r.id); refreshBulkActions(); event.target.parentElement.classList.toggle('checked', event.target.checked); }}),
    h('button', {class: 'file-mini' + (selected === r.id ? ' selected' : ''), onClick: () => action(async () => { selected = r.id; currentPath = []; treeOffset = 0; charQuery = ''; refreshFileList(); await browseTree(); })}, r.addon, h('small', {}, `${r.character || r.account} · ${r.backup ? '.bak · ' : ''}${bytes(r.bytes)}`), h('small', {}, !canSelectFile(r) ? (r.scope === 'system' || r.addon === 'SVCleaner' ? t("Fichier protégé") : t("Suppression déjà dans le panier")) : r.status === 'orphan' ? t("Sans addon correspondant") : t('{count} variable(s)', {count: r.roots.length})))
  )));
  if (!records.length) container.append(empty(t("Aucun fichier"), t("Essayez un autre filtre.")));
  refreshBulkActions();
}
function canSelectFile(record) {
  return record.scope !== 'system' && record.addon !== 'SVCleaner' && !deletingFiles.has(record.id);
}
function refreshBulkActions() {
  const toolbar = $('#bulk-actions'); if (!toolbar) return;
  const eligible = filteredRecords().filter(canSelectFile);
  const chosen = eligible.filter(record => fileSelection.has(record.id));
  const volume = chosen.reduce((total, record) => total + record.bytes, 0);
  toolbar.replaceChildren(
    h('div', {}, h('strong', {}, t("{p0} / {p1} fichier(s) sélectionné(s)", {p0: (chosen.length), p1: (eligible.length)})), h('small', {}, t("{p0} · version {p1} · résultats des filtres actuels · fichiers protégés exclus", {p0: (bytes(volume)), p1: (state.currentVersion?.label || 'WoW')}))),
    h('div', {class: 'actions'},
      button(t("Tout sélectionner"), () => { eligible.forEach(record => fileSelection.add(record.id)); refreshFileList(); }, 'small', !eligible.length),
      button(t("Tout désélectionner"), () => { fileSelection.clear(); refreshFileList(); }, 'small', !chosen.length),
      button(t("Supprimer la sélection"), () => action(async () => {
        const ids = filteredRecords().filter(record => canSelectFile(record) && fileSelection.has(record.id)).map(record => record.id);
        const result = await post('delete-files', {ids});
        fileSelection.clear(); update(result.state); selected = null; currentPath = []; treeOffset = 0;
        await render(); toast(t("{p0} fichier(s) ajouté(s) au panier de suppression. Appliquez le panier pour les retirer avec sauvegarde.", {p0: (result.staged)}));
      }), 'small danger', !chosen.length)
    )
  );
}
async function openFile(id) { selected = id; currentPath = []; treeOffset = 0; charQuery = ''; page = 'files'; await render(); }
async function browseTree() {
  const container = $('#tree'); if (!container) return;
  container.replaceChildren();
  const record = state.records.find(r => r.id === selected);
  if (!record) { container.append(empty(t("Ouvrez une SavedVariable"), t("Choisissez un fichier dans la liste pour parcourir ses données."))); return; }
  container.append(h('div', {class: 'panel-head'}, h('div', {}, h('h2', {}, record.addon), h('p', {}, record.character || record.account)), statusBadge(record)));
  const crumbs = h('div', {class: 'tree-path'}, button(t("Racine"), () => action(async () => { currentPath = []; treeOffset = 0; await browseTree(); }), 'small'));
  currentPath.forEach((key, i) => crumbs.append(' / ', h('button', {onClick: () => action(async () => { currentPath = currentPath.slice(0, i + 1); treeOffset = 0; await browseTree(); })}, key.value)));
  container.append(crumbs);
  if (!record.readOnly) container.append(button(t("Créer une clé / variable"), () => createValue(), 'small'));
  const filter = h('input', {placeholder: t("Filtrer les clés / personnages de ce bloc…"), 'aria-label': t("Filtrer les clés du bloc"), value: charQuery, onInput: event => { charQuery = event.target.value; drawTreeItems(); }});
  container.append(h('div', {class: 'panel-body', style: {padding: '12px 16px'}}, h('div', {class: 'filters', style: {marginBottom: '0'}}, filter)));
  try {
    const data = await get('/api/browse?id=' + encodeURIComponent(selected) + '&path=' + encodeURIComponent(JSON.stringify(currentPath)) + '&offset=' + treeOffset);
    const rowsContainer = h('div'); container.append(rowsContainer);
    function draw(items) {
      const rows = items.map(item => h('tr', {},
        h('td', {}, h('button', {class: 'key-btn', onClick: () => item.type === 'table' ? action(async () => { currentPath = item.path; treeOffset = 0; charQuery = ''; await browseTree(); }) : editValue(item)}, (item.type === 'table' ? '▸ ' : '  ') + (item.label || String(item.key.value))), item.characterStatus ? h('small', {}, item.characterStatus) : null),
        h('td', {}, h('span', {class: 'value', title: String(item.value).slice(0, 800)}, valueText(item.value))),
        h('td', {}, item.protected ? badge(t("ID protégé"), 'warning') : badge(t(item.type), 'muted')),
        h('td', {}, h('div', {class: 'actions'}, item.type === 'table' ? button(t("À gauche"), () => pin('left', record.id, item.path), 'small') : button(t("Éditer"), () => editValue(item), 'small', record.readOnly || item.protected || item.tooLarge), item.type === 'table' ? button(t("À droite"), () => pin('right', record.id, item.path), 'small') : null, button('×', () => deleteValue(item), 'small danger', record.readOnly || item.protected)))
      ));
      rowsContainer.replaceChildren(table([t("CLÉ"), t("VALEUR"), t("TYPE"), t("ACTIONS")], rows));
      if (!rows.length) rowsContainer.append(empty(t("Aucune clé affichée"), t("Ce bloc est vide ou le filtre ne correspond à aucune clé de cette page.")));
    }
    drawTreeItems.current = () => draw(data.items.filter(item => String(item.key.value).toLowerCase().includes(charQuery.toLowerCase())));
    drawTreeItems();
    container.append(h('div', {class: 'pagination'}, h('small', {}, t("{p0} clés · {p1}–{p2}", {p0: (data.total), p1: (data.offset + 1), p2: (Math.min(data.offset + 200, data.total))})), button('←', () => action(async () => { treeOffset = Math.max(0, treeOffset - 200); await browseTree(); }), 'small', treeOffset === 0), button('→', () => action(async () => { treeOffset += 200; await browseTree(); }), 'small', data.offset + 200 >= data.total)));
  } catch (error) { container.append(h('div', {class: 'error-box'}, error.message)); }
  container.append(h('div', {class: 'tree-meta'}, h('span', {}, t(record.scope) + ' · ' + bytes(record.bytes)), h('div', {class: 'actions'}, currentPath.length ? button(t("Comparer à gauche"), () => pin('left', record.id, currentPath), 'small') : null, currentPath.length ? button(t("Comparer à droite"), () => pin('right', record.id, currentPath), 'small') : null, button(t("Quarantaine du fichier"), () => deleteFile(record), 'small danger', record.scope === 'system' || record.addon === 'SVCleaner'))));
}
function drawTreeItems() { if (drawTreeItems.current) drawTreeItems.current(); }
function modal(title, description, elements, actions) {
  const dialog = $('#modal'); $('#modal-content').replaceChildren(h('h2', {}, title), h('p', {}, description), ...elements, h('div', {class: 'actions'}, button(t("Annuler"), () => dialog.close()), ...actions)); dialog.showModal();
}
function editValue(item) {
  const record = state.records.find(r => r.id === selected);
  if (record.readOnly || item.protected || item.tooLarge || item.type === 'table') { toast(t("Valeur protégée, bloc ou chaîne trop longue : choisissez une valeur éditable.")); return; }
  const input = item.type === 'boolean' ? h('select', {}, h('option', {value: 'true'}, 'true'), h('option', {value: 'false'}, 'false')) : h('textarea', {'aria-label': t("Nouvelle valeur")});
  input.value = String(item.value);
  const targetId = selected;
  modal(t("Éditer une valeur"), pathText(item.path) + t(" · Le type et la clé sont conservés."), [input], [button(t("Ajouter au panier"), () => action(async () => {
    let value = input.value;
    if (item.type === 'number') { if (!value.trim()) throw new Error(t("Saisissez un nombre.")); value = Number(value); if (!Number.isFinite(value)) throw new Error(t("Nombre invalide.")); }
    if (item.type === 'boolean') value = value === 'true';
    update(await post('stage', {id: targetId, path: item.path, operation: 'edit', value})); $('#modal').close(); await browseTree(); toast(t("Modification préparée dans le panier."));
  }), 'primary')]);
}
function createValue() {
  const targetId = selected, parentPath = structuredClone(currentPath);
  const key = h('input', {placeholder: parentPath.length ? t("Nouvelle clé") : t("Nom de la variable Lua"), 'aria-label': t("Nouvelle clé")});
  const keyType = h('select', {'aria-label': t("Type de la clé")}, ['string', 'number', 'boolean'].map(type => h('option', {value: type}, t(type))));
  keyType.disabled = !parentPath.length;
  const valueType = h('select', {'aria-label': t("Type de la valeur")}, ['string', 'number', 'boolean', 'table'].map(type => h('option', {value: type}, t(type))));
  const input = h('textarea', {placeholder: t("Nouvelle valeur (vide pour une table)"), 'aria-label': t("Nouvelle valeur")});
  const typed = (text, type) => {
    if (type === 'number') { if (!text.trim() || !Number.isFinite(Number(text))) throw new Error(t("Nombre invalide.")); return Number(text); }
    if (type === 'boolean') { if (!['true', 'false'].includes(text)) throw new Error(t("Saisissez true ou false.")); return text === 'true'; }
    return text;
  };
  modal(t("Préparer une création"), t("La clé doit être absente. Choisissez texte, nombre, booléen ou table vide ; vous pourrez ensuite remplir cette table."), [key, keyType, input, valueType], [button(t("Ajouter au panier"), () => action(async () => {
    const type = valueType.value;
    update(await post('stage', {id: targetId, path: [...parentPath, {type: keyType.value, value: typed(key.value, keyType.value)}], operation: 'create', valueType: type, value: type === 'table' ? null : typed(input.value, type)}));
    $('#modal').close(); await browseTree(); toast(t("Création préparée dans le panier."));
  }), 'primary')]);
}
function deleteValue(item) {
  const targetId = selected;
  modal(t("Préparer la suppression"), pathText(item.path) + t(" sera retiré du fichier actif. Une sauvegarde du fichier sera créée lors de l’application."), [], [button(t("Ajouter au panier"), () => action(async () => { update(await post('stage', {id: targetId, path: item.path, operation: 'delete-value'})); $('#modal').close(); await browseTree(); }), 'danger')]);
}
function deleteFile(record) {
  modal(t("Mettre ce fichier en quarantaine"), record.path + t(" · Ses réglages ne seront plus chargés. L’original sera conservé dans les sauvegardes. Un éventuel .bak doit être sélectionné séparément."), [], [button(t("Ajouter au panier"), () => action(async () => { update(await post('stage', {id: record.id, operation: 'delete-file'})); $('#modal').close(); await browseTree(); }), 'danger')]);
}

function pin(side,id,path){pins[side]={id,path:structuredClone(path)};toast((side==='left'?t("Données de gauche"):t("Données de droite"))+t(" sélectionnées : ")+pathText(path));}
function compareRequest(){return {leftId:pins.left.id,rightId:pins.right.id,leftPath:pins.left.path,rightPath:pins.right.path};}
const comparisonOptions=new Map();
let diffQuery='',diffStatus='all';
let diffFiles={left:null,right:null};
function slotKey(slot){return JSON.stringify([slot.id,slot.path]);}
function subject(slot){
 const record=slot&&state.records.find(r=>r.id===slot.id);if(!record)return t("Choisir des données");
 for(const key of slot.path){const match=String(key.value).match(/^(.*?)-Player-\d+-[a-fA-F0-9]+$/);if(match)return match[1];}
 return record.character||String(slot.path.at(-1)?.value||record.addon);
}
async function optionsFor(record){
 const key=state.root+'/'+record.id;if(!comparisonOptions.has(key))comparisonOptions.set(key,await get('/api/compare-options?id='+encodeURIComponent(record.id)));
 return comparisonOptions.get(key);
}
function sameSlot(a,b){return !!a&&!!b&&slotKey(a)===slotKey(b);}
function sameRoot(a,b){return a?.path[0]?.type===b?.path[0]?.type&&a?.path[0]?.value===b?.path[0]?.value;}
function beneath(path,prefix){return prefix.every((key,i)=>path[i]&&JSON.stringify(path[i])===JSON.stringify(key));}
async function diffPage(content){
 const records=state.records.filter(r=>!r.backup&&r.scope!=='system'&&r.addon!=='SVCleaner'&&!deletingFiles.has(r.id));
 const contexts=[...new Map(records.map(r=>[JSON.stringify([r.account,r.addon]),{account:r.account,addon:r.addon}])).entries()].sort((a,b)=>a[1].addon.localeCompare(b[1].addon));
 if(!contexts.length){content.append(empty(t("Aucune donnée à comparer"),t("Choisissez une version contenant des SavedVariables.")));return;}
 const pinnedRecord=state.records.find(r=>r.id===pins.left?.id||r.id===pins.right?.id);
 const initial=pinnedRecord?JSON.stringify([pinnedRecord.account,pinnedRecord.addon]):contexts.find(([,c])=>c.addon==='APR')?.[0]||contexts[0][0];
 const context=contexts.find(([id])=>id===initial)?.[1]||contexts[0][1];
 const contextRecords=records.filter(r=>r.addon===context.addon&&r.account===context.account);
 const contextSelect=h('select',{'aria-label':t("Addon et compte à comparer"),onChange:event=>action(async()=>{
  const [account,addon]=JSON.parse(event.target.value);const first=records.find(r=>r.account===account&&r.addon===addon);const options=await optionsFor(first);
  pins={left:options.options[0]||{id:first.id,path:[]},right:null};diffFiles={left:null,right:null};diffQuery='';await render();
 })},contexts.map(([id,c])=>h('option',{value:id},c.addon+' · '+c.account)));
 contextSelect.value=initial;
 content.append(h('div',{class:'comparison-context'},h('div',{},h('strong',{},t("1 · Choisir les données")),h('p',{},t("Même addon, même compte et même variable. Les noms sont affichés ; leurs clés restent intactes."))),contextSelect));
 const leftRecord=contextRecords.find(r=>r.id===pins.left?.id)||contextRecords.find(r=>r.scope==='account')||contextRecords[0];
 const leftOptions=await optionsFor(leftRecord);
 if(!pins.left||!pins.left.path.length)pins.left=leftOptions.options.find(o=>o.path.some(k=>String(k.value).includes('-Player-')))||leftOptions.options[0]||null;
 const rightRecord=contextRecords.find(r=>r.id===pins.right?.id)||contextRecords.find(r=>r.id===diffFiles.right)||leftRecord;
 const rightOptions=await optionsFor(rightRecord);const compatible=rightOptions.options.filter(o=>sameRoot(o,pins.left));
 if(!pins.right||!sameRoot(pins.left,pins.right))pins.right=compatible.find(o=>!sameSlot(o,pins.left)&&o.path.length===pins.left?.path.length)||compatible.find(o=>!sameSlot(o,pins.left))||compatible[0]||null;
 function picker(side,record,data){
  const fileSelect=h('select',{'aria-label':side==='left'?t("Fichier à gauche"):t("Fichier à droite"),onChange:event=>action(async()=>{
   const chosen=state.records.find(r=>r.id===event.target.value);const opts=await optionsFor(chosen);
   diffFiles[side]=chosen.id; pins[side]=opts.options.find(o=>side==='left'||sameRoot(o,pins.left))||null;await render();
  })},contextRecords.map(r=>h('option',{value:r.id},r.character||t("Compte · ")+r.account)));
  fileSelect.value=record.id;
  const choices=side==='right'&&pins.left?data.options.filter(o=>sameRoot(o,pins.left)):[...data.options];
  if(pins[side]&&!choices.some(o=>sameSlot(o,pins[side])))choices.push({...pins[side],label:subject(pins[side])});
  const slotSelect=h('select',{'aria-label':side==='left'?t("Personnage ou profil à gauche"):t("Personnage ou profil à droite"),onChange:event=>action(async()=>{
   pins[side]=choices.find(o=>slotKey(o)===event.target.value)||null;await render();
  })},choices.map(o=>h('option',{value:slotKey(o)},o.label+' · '+pathText(o.path))));
  if(pins[side])slotSelect.value=slotKey(pins[side]);
  return h('section',{class:'comparison-subject '+side},h('span',{class:'side-label'},side==='left'?t("GAUCHE"):t("DROITE")),h('h2',{},subject(pins[side])),
   h('label',{},t("Fichier"),fileSelect),h('label',{},t('Personnage, profil ou sous-table'),slotSelect),h('code',{},pins[side]?pathText(pins[side].path):t("Aucun bloc compatible")),
   data.truncated?h('p',{},t("Liste limitée. Ouvrez un sous-bloc dans SavedVariables pour le sélectionner.")):null,record.readOnly?badge(t("Destination en lecture seule"),'warning'):null);
 }
 content.append(h('div',{class:'comparison-subjects'},picker('left',leftRecord,leftOptions),button('⇄',()=>action(async()=>{pins={left:pins.right,right:pins.left};await render();}),'swap-sides',!pins.left||!pins.right),picker('right',rightRecord,rightOptions)));
 if(!pins.left||!pins.right){content.append(empty(t("Choisissez deux blocs compatibles"),t("Vous pouvez aussi sélectionner un sous-bloc depuis l’explorateur.")));return;}
 const result=await post('compare',compareRequest());const editable=result.rows.filter(row=>row.toLeft||row.toRight).length;
 content.append(h('div',{class:'comparison-summary'},h('div',{},h('strong',{},t("2 · Comparer et préparer les copies")),h('p',{},t("{p0} différence(s) · {p1} transférable(s) · {p2} protégée(s) ou incompatible(s)", {p0: (result.rows.length), p1: (editable), p2: (result.rows.length-editable)}))),
  h('div',{class:'actions'},button(t('Tout copier → {target}', {target: subject(pins.right)}),()=>reviewTransfer('right',[]),'small',!result.rows.some(r=>r.toRight)),button(t('← Tout copier vers {target}', {target: subject(pins.left)}),()=>reviewTransfer('left',[]),'small',!result.rows.some(r=>r.toLeft)))));
 content.append(h('p',{class:'inline-note'},t("Les valeurs affichées incluent les changements déjà préparés. Chaque copie affiche un aperçu ; aucun fichier n’est écrit avant « Sauvegarder et appliquer ».")));
 const body=h('div',{class:'comparison-groups'});
 const search=h('input',{'aria-label':t("Rechercher dans les différences"),placeholder:t("Rechercher une clé ou une valeur…"),value:diffQuery,onInput:event=>{diffQuery=event.target.value;draw();}});
 const status=h('select',{'aria-label':t("Filtrer les différences"),onChange:event=>{diffStatus=event.target.value;draw();}},[['all',t("Toutes les différences")],['editable',t("Transférables")],['blocked',t("Protégées / incompatibles")]].map(([v,label])=>h('option',{value:v},label)));
 status.value=diffStatus;content.append(h('div',{class:'filters comparison-filters'},search,status),body);
 function draw(){
  body.replaceChildren();const visible=result.rows.filter(row=>(pathText(row.path)+' '+valueText(row.left)+' '+valueText(row.right)).toLowerCase().includes(diffQuery.toLowerCase())&&(diffStatus==='all'||diffStatus==='editable'&&(row.toLeft||row.toRight)||diffStatus==='blocked'&&!row.toLeft&&!row.toRight));
  const groups=new Map();for(const row of visible){const prefix=row.path.length>1?row.path.slice(0,1):[];const key=prefix.length?JSON.stringify(prefix):'root';if(!groups.has(key))groups.set(key,{prefix,rows:[]});groups.get(key).rows.push(row);}
  for(const {prefix,rows} of groups.values()){
   const allGroup=result.rows.filter(row=>beneath(row.path,prefix));const title=prefix.length?pathText(prefix):t("Champs principaux");
   const header=h('div',{class:'comparison-group-head'},h('div',{},h('h3',{},title),h('small',{},rows.length+t(" différence(s) visible(s)"))),
    prefix.length?h('div',{class:'actions'},button(t('Groupe → {target}', {target: subject(pins.right)}),()=>reviewTransfer('right',prefix),'small',!allGroup.some(r=>r.toRight)),button(t('← Groupe vers {target}', {target: subject(pins.left)}),()=>reviewTransfer('left',prefix),'small',!allGroup.some(r=>r.toLeft))):badge(t("Copie par valeur"),'muted'));
   const columns=h('div',{class:'comparison-row comparison-columns'},h('span',{},t("CLÉ / CHAMP")),h('span',{},subject(pins.left)),h('span',{},t("COPIER")),h('span',{},subject(pins.right)));
   const rowNodes=rows.map(row=>{
    const reason={identity:t("Identité protégée"),missing:t("Clé absente · aucune création"),type:t("Types différents"),value:t("Valeur différente")}[row.reason]||t("Valeur différente");
    const value=side=>h('div',{class:'comparison-value '+side},h('small',{},t(row[side+'Type'])),h('pre',{},valueText(row[side]).slice(0,400)),String(row[side]).length>400?h('details',{},h('summary',{},t("Voir la valeur complète")),h('pre',{},valueText(row[side]))):null);
    const arrows=h('div',{class:'comparison-copy'},h('button',{class:'button',title:t('Copier vers {target}', {target: subject(pins.right)}),'aria-label':t('Copier {path} vers {target}', {path: pathText(row.path), target: subject(pins.right)}),disabled:!row.toRight,onClick:()=>reviewTransfer('right',row.path)},'→'),
     h('button',{class:'button',title:t('Copier vers {target}', {target: subject(pins.left)}),'aria-label':t('Copier {path} vers {target}', {path: pathText(row.path), target: subject(pins.left)}),disabled:!row.toLeft,onClick:()=>reviewTransfer('left',row.path)},'←'));
    return h('div',{class:'comparison-row '+(row.copyable?'editable':'blocked')},h('div',{},h('code',{},pathText(row.path)),h('small',{},reason)),value('left'),arrows,value('right'));
   });body.append(h('section',{class:'comparison-group'},header,columns,...rowNodes));
  }
  if(!visible.length)body.append(empty(result.rows.length?t("Aucune différence ne correspond aux filtres"):t("Les valeurs sont identiques"),result.rows.length?t("Modifiez la recherche ou le filtre."):t("Les blocs sélectionnés contiennent les mêmes valeurs.")));
 }
 draw();
}
function reviewTransfer(direction,relativePath){
 return action(async()=>{
  const request=structuredClone(compareRequest());const result=await post('compare',request);
  const target=direction==='right'?subject(pins.right):subject(pins.left),source=direction==='right'?subject(pins.left):subject(pins.right);
  const rows=result.rows.filter(row=>beneath(row.path,relativePath)&&row[direction==='right'?'toRight':'toLeft']);
  if(!rows.length){toast(t("Aucune valeur transférable dans cette sélection."));return;}
  const before=direction==='right'?'right':'left',after=direction==='right'?'left':'right';
  const details=rows.map(row=>h('div',{class:'copy-preview-row'},h('code',{},pathText(row.path)),h('div',{},h('small',{},target+' · '+t('AVANT')),h('pre',{},valueText(row[before]))),h('div',{},h('small',{},target+' · '+t('APRÈS')),h('pre',{},valueText(row[after])))));
  modal(t('Copier de {source} vers {target}', {source, target}),t("{p0} valeur(s) seront remplacée(s) dans {p1}. Les ID, clés, types et champs absents restent inchangés. Cette opération prépare le panier ; elle n’écrit pas dans WoW.", {p0: (rows.length), p1: (target)}),[h('div',{class:'copy-preview'},...details)],[button(t('Préparer {count} copie(s) vers {target}', {count: rows.length, target}),()=>action(async()=>{
   const transferred=await post('transfer',{...request,direction,relativePath,expectedSignature:result.signature});
   update(transferred.state);comparisonOptions.clear();$('#modal').close();await render();toast(t('{count} valeur(s) préparée(s) dans {target}.', {count: transferred.changed, target}));
  }),'primary')]);
 });
}
async function cachePage(content) {
  const info = await get('/api/cache');
  for (const cache of info.locations || [info]) {
    content.append(h('div', {class: 'callout'}, h('span', {class: 'callout-icon'}, '↻'), h('div', {}, h('h3', {}, t("{p0} WoW · {p1} · {p2} fichiers", {p0: (cache.path), p1: (bytes(cache.bytes)), p2: (cache.files)})), h('p', {}, t("Le dossier est renommé et conservé. WoW le reconstruira. Cette action ne libère pas d’espace physique tant que la sauvegarde reste sur disque."))), button(t("Mettre {p0} en quarantaine", {p0: (cache.path)}), () => {
      modal(t("Réinitialiser le cache disque"), t("Dossier {p0} : {p1}. Fermez tous les clients WoW. Le dossier actuel sera renommé, les prochains chargements pourront être plus lents.", {p0: (cache.path), p1: (bytes(cache.bytes))}), [], [button(t("Renommer et sauvegarder {p0}", {p0: (cache.path)}), () => action(async () => { update(await post('cache-reset', {location: cache.path})); $('#modal').close(); await render(); toast(t("{p0} mis en quarantaine.", {p0: (cache.path)})); }), 'primary')]);
    }, 'small', !cache.exists)));
  }
  const cards = [
    [t("Interface Lua"), t("En jeu · manuel"), '/reload', t("Recharge l’interface et sauvegarde les SavedVariables. Peut corriger un état d’interface dégradé. Aucun cache disque n’est effacé."), 'https://github.com/Gethe/wow-ui-source/blob/live/Interface/AddOns/Blizzard_APIDocumentationGenerated/AddOnsDocumentation.lua'],
    [t("Moteur graphique"), t("En jeu · diagnostic"), '/console GxRestart', t("Redémarre le moteur graphique. Une pause est possible. Ce n’est pas une suppression du cache shaders ; les témoignages de FPS restent des cas particuliers."), 'https://eu.forums.blizzard.com/en/wow/t/game-gradually-gets-choppier-fps-drops/590202'],
    [t("Objets Lua inaccessibles"), t("En jeu · ponctuel"), '/run collectgarbage("collect")', t("Force le ramasse-miettes Lua et peut provoquer une pause. Les tables encore référencées par les addons restent en mémoire. Ne pas automatiser périodiquement."), 'https://www.lua.org/manual/5.1/manual.html#pdf-collectgarbage'],
    [t("Caches du client"), t("WoW fermé · disque"), t('Cache / GPUCache → sauvegarde renommée'), t("Cache contient notamment WDB, ADB et les images téléchargées selon la version. GPUCache peut être un dossier séparé du client. Ils se reconstruisent ; aucun cache du pilote GPU n’est touché."), 'https://us.forums.blizzard.com/en/wow/t/need-help-with-this/2315977'],
    [t("Réglages persistants"), t("Réinitialisation · perte de réglages"), '/console cvar_default', t("Remet des CVars à leurs valeurs par défaut. À réserver au dépannage volontaire des réglages, pas au nettoyage. Certaines options sont synchronisées côté serveur."), 'https://us.forums.blizzard.com/en/wow/t/full-reset-on-settings/1405703'],
    [t("Fichiers « cache » dans WTF"), t("Données personnelles · protégées"), 'layout-cache / bindings-cache / macros-cache', t("Peuvent contenir disposition, raccourcis et macros. Ils ne sont pas proposés comme déchets. Même précaution pour les fichiers de chat et Config.wtf."), 'https://us.support.blizzard.com/en/help/article/7549'],
    [t("Cache shaders du pilote"), t("Windows / GPU · hors addon"), t("Outils du pilote ou de Windows"), t("Dépend du pilote et du backend graphique. Un addon ne peut pas le vider. Le reconstruire peut augmenter les saccades temporaires : action seulement pour un problème identifié."), 'https://eu.forums.blizzard.com/en/wow/t/crazy-fps-drops-when-panning-camera-since-prepatch/396350'],
    [t("Anciennes astuces Reddit"), t("Contexte historique · non automatisé"), 'GxAllowCachelessShaderMode 0 (2022)', t("Conseil lié à un incident du prépatch Dragonflight. Ce réglage n’est pas une commande de purge et son utilité dépend de la version. SpellQueueWindow et processPriority sont également des réglages."), 'https://www.reddit.com/r/wow/comments/ye282w/']
  ];
  content.append(h('div', {class: 'guide-grid'}, cards.map(([title, label, command, description, url]) => h('section', {class: 'guide-card'}, badge(label, 'muted'), h('h3', {}, title), h('code', {}, command), h('p', {}, description), h('a', {href: url, target: '_blank', rel: 'noopener noreferrer'}, t("Lire la source ↗"))))));
  content.append(h('p', {class: 'inline-note'}, t("Le cache Battle.net et les données d’installation ne sont pas touchés. La latence réseau, une boucle coûteuse d’addon et une compilation de shaders ne se corrigent pas par le même nettoyage. Voir docs/cache-research.md pour la recherche et les limites.")));
}
function historyPage(content) {
  const history = state.history;
  content.append(metrics());
  content.append(h('div', {class: 'history-list'}, history.map(tx => h('section', {class: 'history-item'}, h('div', {class: 'actions'}, h('div', {}, h('h3', {}, tx.type === 'cache' ? t("Cache mis en quarantaine") : t("{p0} fichier(s) · {p1} de différence sur les fichiers actifs", {p0: (tx.files.length), p1: (bytes(tx.savedBytes))})), h('small', {}, date(tx.timestamp) + ' · ' + tx.id)), h('div', {class: 'actions'}, badge(tx.status === 'applied' ? t("Sauvegarde disponible") : tx.status === 'restored' ? t("Restauré") : t(tx.status), tx.status === 'applied' ? '' : 'muted'), button(t("Restaurer"), () => {
    modal(t("Restaurer les fichiers originaux"), t("WoW doit être fermé. Si un fichier a changé depuis ce nettoyage, la restauration automatique sera refusée pour préserver les nouvelles données."), [], [button(t("Restaurer la sauvegarde"), () => action(async () => { update(await post('restore', {id: tx.id})); $('#modal').close(); await render(); toast(t("Sauvegarde restaurée.")); }), 'primary')]);
  }, 'small', !['applied', 'prepared', 'failed'].includes(tx.status)))), h('ul', {}, tx.type === 'cache' ? h('li', {}, tx.backupPath + ' · ' + bytes(tx.cacheBytes)) : tx.files.map(entry => h('li', {}, entry.path + ' · ' + t(entry.operation)))), h('p', {}, t("Les originaux conservés occupent encore de l’espace disque."))))));
  if (!history.length) content.append(empty(t("Aucun nettoyage appliqué"), t("Les sauvegardes apparaîtront ici après votre première application.")));
}
function showBasket() {
  modal(t("Votre panier de modifications"), t("Relisez les fichiers concernés. Les changements sont encore en mémoire dans le compagnon."), [basketDetails()], [button(t("Fermer"), () => $('#modal').close())]);
}
function basketDetails() {
  return h('div', {class: 'details-lines'}, state.pending.map(item => h('div', {}, h('strong', {}, item.path + ' · ' + item.summary), (item.details || []).map(detail => h('div', {}, pathText(detail.path) + ' : ' + detail.before + ' → ' + detail.after)))));
}
function applyBasket() {
  modal(t("Appliquer les changements"), t("{p0} fichier(s) seront modifiés ou retirés des fichiers actifs. Fermez tous les clients WoW. Chaque original sera sauvegardé avant la première modification.", {p0: (state.pending.length)}), [basketDetails()], [button(t("Sauvegarder et appliquer"), () => action(async () => { const result = await post('apply'); update(result.state); $('#modal').close(); selected = null; await render(); toast(t("Modifications appliquées. Sauvegarde disponible dans l’historique.")); }), 'primary')]);
}
document.querySelectorAll('nav button').forEach(node => node.addEventListener('click', () => action(() => navigate(node.dataset.page))));
$('#theme').addEventListener('click', () => { const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = next; localStorage.setItem('svcleaner-theme', next); });
$('#wow-version').addEventListener('change', event => {
  const selectedId = event.target.value;
  action(async () => {
    event.target.disabled = true;
    try {
      const next = await post('version', {id: selectedId});
      selected = null; currentPath = []; treeOffset = 0; charQuery = '';
      pins = {left: null, right: null}; filters = {query: '', account: '', scope: '', backups: false};
      update(next); localStorage.setItem('svcleaner-wow-version', next.root);
      await render(); toast(t("Version sélectionnée : ") + next.currentVersion.label);
    } finally { event.target.disabled = false; renderChrome(); }
  });
});
$('#scan').addEventListener('click', () => action(async () => { update(await post('scan')); selected = null; fileSelection.clear(); await render(); toast(t("Inventaire actualisé.")); }));
$('#import').addEventListener('click', () => action(async () => { const result = await post('import'); update(result.state); await render(); modal(t("Demandes préparées en jeu"), t("{p0} demande(s) importée(s) dans le panier. {p1} déjà appliquée(s). {p2} demande(s) nécessitent une vérification manuelle. Déconnectez-vous et actualisez le scan pour lire les dernières demandes.", {p0: (result.imported), p1: (result.alreadyApplied), p2: (result.skipped.length)}), [h('div', {class: 'details-lines'}, result.skipped.map(message => h('div', {}, message)))], [button(t("Fermer"), () => $('#modal').close())]); }));
window.addEventListener('beforeunload', event => { if (state?.pending?.length) { event.preventDefault(); event.returnValue = ''; } });
$('#manifest').addEventListener('click', () => action(async () => { const result = await post('manifest'); toast(t("{p0} addons indexés. Manifest.lua généré dans le projet ; synchronisez l’addon puis redémarrez WoW.", {p0: (result.addons)})); }));
const savedTheme = localStorage.getItem('svcleaner-theme'); if (savedTheme === 'light' || savedTheme === 'dark') document.documentElement.dataset.theme = savedTheme;
$('#language').addEventListener('change', event => {
 if (busy) { event.target.value = I18n.language; return; }
 return action(async () => {
  const previous = I18n.language;
  try {
    await post('language', {language: event.target.value});
    I18n.select(event.target.value); I18n.apply();
    $('#modal').close();
    update(await get('/api/state')); await render();
  } catch (error) { I18n.select(previous); I18n.apply(); throw error; }
  finally { event.target.value = I18n.language; }
 });
});
async function start() {
  I18n.select(navigator.language);
  const [catalogs, preference] = await Promise.all([get('/locales.json'), get('/api/language')]);
  I18n.load(catalogs); I18n.select(preference.language || navigator.language); I18n.apply();
  $('#language').replaceChildren(...Object.entries(I18n.names).map(([code, name]) => h('option', {value: code, lang: I18n.tags[code]}, name)));
  $('#language').value = I18n.language;
  const result = await get('/api/state');
  csrf = result.csrf; update(result);
  const remembered = localStorage.getItem('svcleaner-wow-version');
  const preferred = result.versions.find(version => version.root === remembered && version.available);
  if (preferred && preferred.root !== result.root) update(await post('version', {id: preferred.id}));
  await render();
}
start().catch(error => { $('#content').append(h('div', {class: 'error-box'}, error.message)); });
