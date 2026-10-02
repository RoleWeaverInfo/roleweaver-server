/* DM administration. Player opt-in and native familiar commands remain in game. */
(() => {
  const host = document.getElementById('page-companions');
  const panel = document.createElement('section');
  panel.innerHTML = `
    <h2>Companion AI on this server</h2>
    <p>Allow players to use Role Weaver with their wizard or sorcerer familiars.
      Players still enable their own familiar with <code>/rw companion on</code>.</p>
    <p id="cp-admin-status" class="context-note" role="status">Loading companion settings…</p>
    <div class="row"><button id="cp-admin-enable" class="primary" disabled>Enable companion AI</button>
      <button id="cp-admin-disable" class="stop" disabled>Disable companion AI</button></div>
    <p class="muted">Disabling ends Role Weaver replies and errands when the game applies the change.
      Familiars remain summoned, normal game commands still work, and satchel items can be recovered.
      Profiles, memories and player preferences are kept. This setting is saved across restarts.</p>
    <p id="cp-admin-notice" role="status"></p>`;
  const editor = document.createElement('section');
  editor.innerHTML = `
    <h2>Companion personalities</h2>
    <p>Profiles appear after a player first speaks to an enabled familiar.
      Select one to shape its background and personality, including while its owner is offline.</p>
    <label for="cp-admin-select">Companion</label><select id="cp-admin-select" disabled></select>
    <p id="cp-admin-identity" class="muted"></p>
    <p id="cp-admin-empty">No companion profiles loaded.</p>
    <div id="cp-admin-editor" hidden>
      <label for="cp-admin-template">Copy a saved starting template into this profile</label>
      <div class="row"><select id="cp-admin-template" disabled></select>
        <button id="cp-admin-use-template" type="button" disabled>Load template into profile draft</button></div>
      <p class="muted">Review the copied fields, then Save companion profile to apply them. Memories and inventory are preserved.</p>
      <p id="cp-admin-draft" class="context-note" role="status"></p>
      <form id="cp-admin-form"><fieldset id="cp-admin-fields" style="border:0;padding:0;margin:0">
        <div class="grid">
          <div class="full"><label for="cp-admin-role">Role and relationship</label><textarea id="cp-admin-role" maxlength="6000"></textarea></div>
          <div><label for="cp-admin-personality">Personality</label><textarea id="cp-admin-personality" maxlength="6000"></textarea></div>
          <div><label for="cp-admin-voice">Speaking style</label><textarea id="cp-admin-voice" maxlength="6000"></textarea></div>
          <div class="full"><label for="cp-admin-lore">Background and personal knowledge</label><textarea id="cp-admin-lore" maxlength="6000" style="min-height:160px"></textarea></div>
          <div><label for="cp-admin-boundaries">Boundaries and secrets</label><textarea id="cp-admin-boundaries" maxlength="6000"></textarea></div>
          <div><label for="cp-admin-guidance">DM guidance</label><textarea id="cp-admin-guidance" maxlength="6000"></textarea></div>
        </div>
        <p class="muted">These edits preserve memories, inventories and player preferences. Player tone settings adapt the delivery;
          the saved character background still applies. This editor does not change the familiar's in-game name, type, level or owner.</p>
        <div class="row"><button id="cp-admin-save" class="primary" disabled>Save companion profile</button>
          <button id="cp-admin-reload" type="button">Reload saved profile</button></div>
      </fieldset></form><p id="cp-admin-profile-notice" role="status"></p>
    </div>`;
  host.append(panel);
  const $ = id => document.getElementById('cp-admin-' + id);
  const fields = ['role', 'personality', 'voice', 'lore', 'boundaries', 'guidance'];
  let data = null, selected = '', baseline = null, version = '', drafts = null;
  let dirty = false, draftSaved = false, recovering = false, loading = false, saving = false, switching = false, sequence = 0;
  const templateEditor = new CompanionTemplateEditor(host, rows => {
    const value = $('template').value;
    $('template').replaceChildren();
    for (const row of rows) {
      const option = document.createElement('option'); option.value = row.id; option.textContent = row.label;
      $('template').append(option);
    }
    $('template').value = rows.some(r => r.id === value) ? value : (data?.companions.find(r => r.id === selected)?.suggested_template || 'default');
    buttons();
  });
  host.append(editor);
  const read = () => Object.fromEntries(fields.map(k => [k, $(k).value]));
  const fill = p => fields.forEach(k => { $(k).value = p[k]; });
  const draftKey = () => 'companion-profile:' + selected;

  async function request(path = 'companions', body) {
    const response = await fetch('/api/' + path, body === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || 'Companion settings could not be loaded');
    return result;
  }
  function buttons() {
    $('enable').disabled = !data || switching || data.enabled;
    $('disable').disabled = !data || switching || !data.enabled;
    $('fields').disabled = saving || recovering;
    $('select').disabled = saving || !data?.companions.length;
    $('save').disabled = !selected || !dirty || saving || recovering;
    $('template').disabled = $('use-template').disabled = !selected || !templateEditor.rows.length || saving || recovering;
  }
  function stash() {
    if (!selected || recovering) return;
    dirty = JSON.stringify(read()) !== JSON.stringify(baseline);
    try {
      if (!drafts) throw Error('No storage');
      drafts.write(draftKey(), read(), baseline);
      draftSaved = true;
      $('draft').textContent = dirty ? 'Unsaved edits kept in this browser. Save to apply them.' : '';
    } catch (_) {
      draftSaved = false;
      $('draft').textContent = 'Browser draft recovery is unavailable. Save before leaving this profile.';
    }
    buttons();
  }
  function loadProfile(row) {
    selected = row.id; baseline = row.profile; version = row.revision;
    $('template').value = row.suggested_template || 'default';
    fill(baseline); dirty = false; draftSaved = false; recovering = false;
    $('profile-notice').textContent = '';
    $('draft').replaceChildren();
    try {
      const draft = drafts?.read(draftKey());
      if (draft && JSON.stringify(draft.values) !== JSON.stringify(baseline)) {
        recovering = true;
        const label = document.createElement('span');
        label.textContent = 'An unsaved browser draft is available. ' +
          (JSON.stringify(draft.base) !== JSON.stringify(baseline) ? 'The saved profile has changed; review before saving. ' : '');
        const restore = document.createElement('button'), discard = document.createElement('button');
        restore.type = discard.type = 'button';
        restore.textContent = 'Restore draft'; discard.textContent = 'Discard draft';
        restore.onclick = () => {
          fields.forEach(k => { if (typeof draft.values[k] === 'string') $(k).value = draft.values[k].slice(0, 6000); });
          recovering = false; stash();
        };
        discard.onclick = () => {
          try { drafts.remove(draftKey()); recovering = false; $('draft').replaceChildren(); buttons(); }
          catch (_) { $('profile-notice').textContent = 'Could not discard the browser draft.'; }
        };
        $('draft').append(label, restore, document.createTextNode(' '), discard);
      }
    } catch (_) { $('draft').textContent = 'Browser draft recovery is unavailable. Save your edits regularly.'; }
    buttons();
  }
  function render(result, reload = false) {
    data = result;
    if (!drafts) { try { drafts = new DraftStore(localStorage, result.draft_scope); } catch (_) {} }
    $('status').textContent = `Saved setting: companion AI ${data.enabled ? 'enabled' : 'disabled'}. ` + ({
      applied: 'Confirmed by the game.',
      pending: 'Waiting for the game to apply the change.',
      offline: 'Game offline; this setting will apply when it connects.',
      upgrade_required: 'The game has older bridge scripts. Update the bridge to display confirmation here.'
    }[data.status] || 'Checking game confirmation.');
    $('select').replaceChildren();
    for (const row of data.companions) {
      const option = document.createElement('option'); option.value = row.id;
      option.textContent = `${row.name} · ${row.owner || 'Owner not yet observed'} · ${row.status}`;
      $('select').append(option);
    }
    const row = data.companions.find(r => r.id === selected) || data.companions[0];
    $('empty').hidden = !!row; $('editor').hidden = !row;
    $('empty').textContent = 'No familiar profiles yet. Enable companion AI, summon a familiar, use /rw companion on and speak to it.';
    if (row) {
      if (row.id !== selected || reload) loadProfile(row);
      $('select').value = row.id;
      $('identity').textContent = `${row.name} · ${row.owner ? 'Owner: ' + row.owner : 'Owner will be shown after the next connection'} · ${row.status}` +
        (row.species ? ` · Creature blueprint: ${row.species}` : '');
      if (row.revision !== version) $('profile-notice').textContent = 'This profile changed elsewhere. Reload to see its saved version; your current edits are kept.';
    } else { selected = ''; $('identity').textContent = ''; }
    buttons();
  }
  async function refresh(reload = false) {
    if (loading || saving) return;
    loading = true; const ticket = sequence;
    try { const result = await request(); if (ticket === sequence) render(result, reload); }
    catch (e) { $('status').textContent = e.message; }
    finally { loading = false; }
  }
  $('select').onchange = () => {
    const row = data.companions.find(r => r.id === $('select').value);
    if (dirty && !draftSaved && !confirm('Discard unsaved companion edits?')) { $('select').value = selected; return; }
    if (row) { loadProfile(row); render(data); }
  };
  $('form').oninput = stash;
  $('use-template').onclick = () => {
    if (saving || recovering) return;
    const row = templateEditor.rows.find(r => r.id === $('template').value);
    if (!row || (dirty && !confirm('Replace the current profile draft with this saved template?'))) return;
    fill(row.profile); stash();
    $('profile-notice').textContent = `${row.label} copied into the draft. Review it and Save companion profile to apply.`;
  };
  $('reload').onclick = () => {
    if (dirty && !confirm(draftSaved
      ? 'Reload the saved profile? Your current edits will remain as a browser recovery draft.'
      : 'Discard unsaved edits and reload the saved profile? Browser draft recovery is unavailable.')) return;
    refresh(true);
  };
  $('form').onsubmit = async e => {
    e.preventDefault(); if (saving || recovering) return;
    saving = true; sequence++; buttons(); const values = read(); const key = draftKey();
    try {
      const result = await request('companion-profile', {npc: selected, revision: version, profile: values});
      try { drafts?.saved(key, values); } catch (_) {}
      render(result, true); $('profile-notice').textContent = 'Companion profile saved. Memories and player preferences were preserved.';
    } catch (err) { $('profile-notice').textContent = err.message; }
    finally { saving = false; buttons(); }
  };
  for (const enabled of [true, false]) $(enabled ? 'enable' : 'disable').onclick = async () => {
    if (switching) return; switching = true; sequence++; buttons();
    try { render(await request('companion-settings', {enabled})); $('notice').textContent = 'Setting saved. Check game confirmation above.'; }
    catch (err) { $('notice').textContent = err.message; }
    finally { switching = false; buttons(); }
  };
  window.addEventListener('hashchange', () => { if (location.hash === '#companions') refresh(); });
  window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
  setInterval(() => { if (!document.hidden && location.hash === '#companions' && !switching) refresh(); }, 2000);
  if (location.hash === '#companions') refresh();
})();
