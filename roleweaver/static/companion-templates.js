/* Starting profiles only. Saving a template never rewrites existing companions. */
class CompanionTemplateEditor {
  constructor(host, onChange) {
    this.onChange = onChange;
    this.rows = []; this.selected = ''; this.version = ''; this.baseline = null;
    this.dirty = false; this.savedDraft = false; this.recovering = false;
    this.loading = false; this.saving = false; this.sequence = 0; this.drafts = null;
    this.fields = ['role', 'personality', 'voice', 'lore', 'boundaries', 'guidance'];
    this.node = document.createElement('section');
    this.node.innerHTML = `<details id="cp-tpl-details"><summary><strong>Familiar starting templates</strong></summary>
      <p>New companions automatically receive the matching template on their first AI chat. Edit these defaults before players summon and speak to their familiars.
        Existing personalities and memories stay as they are. No LLM request is needed to choose a template.</p>
      <label for="cp-tpl-select">Familiar type</label><select id="cp-tpl-select" disabled></select>
      <p id="cp-tpl-draft" class="context-note" role="status"></p>
      <form id="cp-tpl-form"><fieldset id="cp-tpl-fields" disabled style="border:0;padding:0;margin:0">
        <div class="grid">
          <div class="full"><label for="cp-tpl-role">Role and relationship</label><textarea id="cp-tpl-role" maxlength="6000"></textarea></div>
          <div><label for="cp-tpl-personality">Personality, likes and dislikes</label><textarea id="cp-tpl-personality" maxlength="6000"></textarea></div>
          <div><label for="cp-tpl-voice">Speaking style</label><textarea id="cp-tpl-voice" maxlength="6000"></textarea></div>
          <div class="full"><label for="cp-tpl-lore">Background and personal knowledge</label><textarea id="cp-tpl-lore" maxlength="6000" style="min-height:140px"></textarea></div>
          <div><label for="cp-tpl-boundaries">Boundaries and secrets</label><textarea id="cp-tpl-boundaries" maxlength="6000"></textarea></div>
          <div><label for="cp-tpl-guidance">DM guidance</label><textarea id="cp-tpl-guidance" maxlength="6000"></textarea></div>
          <div class="full"><label for="cp-tpl-blueprints">Custom creature blueprints (optional)</label>
            <input id="cp-tpl-blueprints" maxlength="543" placeholder="my_familiar, custom_pet">
            <p class="muted">Exact creature blueprint names, separated by commas. Use lowercase letters, digits and underscores, up to 16 characters per name.
              These override the normal familiar type match. Leave blank for the standard game types. Unknown types use Other / unknown familiar.</p></div>
        </div>
        <div class="row"><button id="cp-tpl-save" class="primary" disabled>Save template</button>
          <button id="cp-tpl-reload" type="button">Reload saved template</button>
          <button id="cp-tpl-defaults" type="button">Load shipped defaults into draft</button></div>
      </fieldset></form><p id="cp-tpl-notice" role="status"></p>
    </details>`;
    host.append(this.node);
    this.$('select').onchange = () => {
      if (this.dirty && !this.savedDraft && !confirm('Discard unsaved template edits?')) {
        this.$('select').value = this.selected; return;
      }
      this.load(this.rows.find(r => r.id === this.$('select').value));
    };
    this.$('form').oninput = () => this.stash();
    this.$('form').onsubmit = e => { e.preventDefault(); this.save(); };
    this.$('reload').onclick = () => {
      if (this.dirty && !confirm(this.savedDraft ? 'Reload the saved template? Your edits remain as a browser recovery draft.' : 'Discard unsaved template edits and reload?')) return;
      this.refresh(true);
    };
    this.$('defaults').onclick = () => {
      if (!confirm('Replace this draft with the shipped defaults? Save template to apply the change to future companions.')) return;
      this.fill(this.rows.find(r => r.id === this.selected).defaults); this.stash();
    };
    this.$('details').ontoggle = () => { if (this.$('details').open) this.refresh(); };
    window.addEventListener('hashchange', () => { if (location.hash === '#companions') this.refresh(); });
    window.addEventListener('beforeunload', e => { if (this.dirty) { e.preventDefault(); e.returnValue = ''; } });
    setInterval(() => { if (!document.hidden && location.hash === '#companions') this.refresh(); }, 15000);
    if (location.hash === '#companions') this.refresh();
  }
  $(id) { return this.node.querySelector('#cp-tpl-' + id); }
  key() { return 'familiar-template:' + this.selected; }
  draftValues(value) { return {...value.profile, blueprints: value.blueprints.join(', ')}; }
  read() {
    return {profile: Object.fromEntries(this.fields.map(k => [k, this.$(k).value])),
      blueprints: this.$('blueprints').value.split(',').map(s => s.trim()).filter(Boolean)};
  }
  fill(value) {
    this.fields.forEach(k => { this.$(k).value = value.profile[k]; });
    this.$('blueprints').value = value.blueprints.join(', ');
  }
  buttons() {
    this.$('fields').disabled = !this.selected || this.saving || this.recovering;
    this.$('select').disabled = !this.rows.length || this.saving;
    this.$('save').disabled = !this.dirty || this.saving || this.recovering;
  }
  stash() {
    this.dirty = JSON.stringify(this.read()) !== JSON.stringify(this.baseline);
    this.$('draft').replaceChildren();
    try {
      if (!this.drafts) throw Error('No storage');
      this.drafts.write(this.key(), this.draftValues(this.read()), this.draftValues(this.baseline)); this.savedDraft = true;
      this.$('draft').textContent = this.dirty ? 'Unsaved template edits kept in this browser. Save to use them for new companions.' : '';
    } catch (_) {
      this.savedDraft = false;
      this.$('draft').textContent = 'Browser draft recovery is unavailable. Save before leaving this template.';
    }
    this.buttons();
  }
  load(row) {
    this.selected = row.id; this.version = row.revision;
    this.baseline = {profile: row.profile, blueprints: row.blueprints};
    this.fill(this.baseline); this.$('select').value = row.id;
    this.dirty = this.savedDraft = this.recovering = false;
    this.$('notice').textContent = ''; this.$('draft').replaceChildren();
    try {
      const draft = this.drafts?.read(this.key());
      if (draft && JSON.stringify(draft.values) !== JSON.stringify(this.draftValues(this.baseline))) {
        this.recovering = true;
        const label = document.createElement('span');
        label.textContent = 'An unsaved template draft is available. ' +
          (JSON.stringify(draft.base) !== JSON.stringify(this.draftValues(this.baseline)) ? 'The saved template has changed; review before saving. ' : '');
        const restore = document.createElement('button'), discard = document.createElement('button');
        restore.type = discard.type = 'button'; restore.textContent = 'Restore draft'; discard.textContent = 'Discard draft';
        restore.onclick = () => {
          const values = draft.values;
          this.fields.forEach(k => { if (typeof values[k] === 'string') this.$(k).value = values[k].slice(0, 6000); });
          if (typeof values.blueprints === 'string') this.$('blueprints').value = values.blueprints.slice(0, 543);
          this.recovering = false; this.stash();
        };
        discard.onclick = () => {
          try { this.drafts.remove(this.key()); this.recovering = false; this.$('draft').replaceChildren(); this.buttons(); }
          catch (_) { this.$('notice').textContent = 'Could not discard the browser draft.'; }
        };
        this.$('draft').append(label, restore, document.createTextNode(' '), discard);
      }
    } catch (_) { this.$('draft').textContent = 'Browser draft recovery is unavailable.'; }
    this.buttons();
  }
  render(result, reload = false) {
    this.rows = result.templates;
    // Scope changes after a world restore must not reuse a different world's drafts.
    if (this.scope !== result.draft_scope) {
      this.scope = result.draft_scope; this.drafts = null;
      try { this.drafts = new DraftStore(localStorage, this.scope); } catch (_) {}
    }
    this.$('select').replaceChildren();
    for (const row of this.rows) {
      const option = document.createElement('option'); option.value = row.id; option.textContent = row.label;
      this.$('select').append(option);
    }
    const row = this.rows.find(r => r.id === this.selected) || this.rows[0];
    if (row.id !== this.selected || reload) this.load(row);
    this.$('select').value = this.selected;
    if (row.revision !== this.version) this.$('notice').textContent = 'This template changed elsewhere. Reload to review the saved version; your edits have been kept.';
    this.buttons(); this.onChange(this.rows);
  }
  async request(body) {
    const response = await fetch(body ? '/api/companion-template' : '/api/companion-templates', body ? {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    } : {});
    const result = await response.json();
    if (!response.ok) throw Error(result.error || 'Could not load familiar templates');
    return result;
  }
  async refresh(reload = false) {
    if (this.loading || this.saving) return;
    this.loading = true; const ticket = this.sequence;
    try { const result = await this.request(); if (ticket === this.sequence) this.render(result, reload); }
    catch (e) { this.$('notice').textContent = e.message; }
    finally { this.loading = false; }
  }
  async save() {
    if (!this.selected || !this.dirty || this.saving || this.recovering) return;
    this.saving = true; this.sequence++; this.buttons();
    const values = this.read(), key = this.key();
    try {
      const result = await this.request({id: this.selected, revision: this.version, ...values});
      try { this.drafts?.saved(key, this.draftValues(values)); } catch (_) {}
      this.render(result, true);
      this.$('notice').textContent = 'Template saved for new companions. Existing profiles and memories were preserved.';
    } catch (e) { this.$('notice').textContent = e.message; }
    finally { this.saving = false; this.buttons(); }
  }
}
