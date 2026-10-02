/* Exercise template draft recovery with the real editor and DraftStore. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const DraftStore = require('../roleweaver/static/drafts.js');
const storageMap = new Map();
const storage = {getItem: k => storageMap.get(k), setItem: (k, v) => storageMap.set(k, v), removeItem: k => storageMap.delete(k)};
function element() {
  return {value: '', disabled: false, textContent: '', children: [], nodes: {},
    replaceChildren() { this.children = []; }, append(...nodes) { this.children.push(...nodes); },
    querySelector(id) { return this.nodes[id] ??= element(); }};
}
const context = vm.createContext({DraftStore, localStorage: storage,
  document: {createElement: element, createTextNode: s => s}, window: {addEventListener() {}},
  location: {hash: ''}, setInterval() {}, confirm: () => true});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../roleweaver/static/companion-templates.js'), 'utf8'), context);
const Editor = vm.runInContext('CompanionTemplateEditor', context);
const profile = Object.fromEntries(['role', 'personality', 'voice', 'lore', 'boundaries', 'guidance'].map(k => [k, 'Saved ' + k]));
const row = {id: 'cat', label: 'Cat', revision: '1', profile, blueprints: [], defaults: {profile, blueprints: []}};
const data = {draft_scope: 'test', templates: [row]};
const first = new Editor(element(), () => {});
first.render(data);
first.$('lore').value = 'An unsaved background';
first.$('blueprints').value = 'my_cat, snowcat';
first.stash();
assert.equal(first.dirty, true);
assert.equal(first.savedDraft, true);
// A reload must offer the draft without silently changing saved values.
const second = new Editor(element(), () => {});
second.render(data);
assert.equal(second.recovering, true);
assert.equal(second.$('lore').value, profile.lore);
second.$('draft').children[1].onclick();
assert.equal(second.$('lore').value, 'An unsaved background');
assert.equal(second.$('blueprints').value, 'my_cat, snowcat');
assert.equal(second.recovering, false);
// Polling after another DM's save must keep our draft and stale revision.
second.render({...data, templates: [{...row, revision: '2', profile: {...profile, lore: 'Another editor'}}]});
assert.equal(second.$('lore').value, 'An unsaved background');
assert.equal(second.version, '1');
assert.match(second.$('notice').textContent, /changed elsewhere/);
// Saved draft values use the flat string representation accepted by DraftStore.
second.drafts.saved(second.key(), second.draftValues(second.read()));
assert.equal(second.drafts.read(second.key()), null);
const third = new Editor(element(), () => {});
third.render(data);
assert.equal(third.recovering, false);
third.$('lore').value = 'Discard me'; third.stash();
const fourth = new Editor(element(), () => {});
fourth.render(data);
fourth.$('draft').children[3].onclick();
assert.equal(fourth.$('lore').value, profile.lore);
assert.equal(fourth.recovering, false);
assert.equal(fourth.drafts.read(fourth.key()), null);
console.log('Template editor: draft recovery, conflict preservation, save cleanup and discard passed.');
