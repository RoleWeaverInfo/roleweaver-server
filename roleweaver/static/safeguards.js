/* Owner settings remain mounted while navigating; polling never replaces edits. */
(() => {
  const host = document.getElementById('page-guardrails');
  const panel = document.createElement('section');
  panel.id = 'safeguard-panel';
  panel.innerHTML = `<h2>Guardrails settings</h2>
    <p id="safeguard-engine" class="muted" role="status"></p>
    <form id="safeguard-form">
      <h3>Content sensitivity</h3>
      <p class="muted">Optional AI-assisted checks use your existing provider. Low catches severe content; High also flags milder or ambiguous content. These are model estimates, not certainty. Fantasy combat may be flagged at higher violence settings.</p>
      <div class="safeguard-grid" id="safeguard-levels"></div>
      <label for="safeguard-topics">Sensitive topics (one per line)</label>
      <textarea id="safeguard-topics" maxlength="1000" rows="3"></textarea>
      <label for="safeguard-action">When content or lore is flagged</label>
      <select id="safeguard-action"><option value="log">Log only — allow the dialogue</option><option value="fallback">Fallback — send a safe reply</option><option value="block">Block — NPC stays silent for this turn</option></select>
      <p class="muted">Every flag is logged. Blocking stops Role Weaver’s reply, not the player’s original game chat. Injection protections remain enforced. If an enabled AI review fails, the NPC stays silent regardless of this choice.</p>
      <h3>Catch lore mistakes</h3>
      <label><input type="checkbox" id="safeguard-lore" style="width:auto"> Check NPC answers against trusted lore</label>
      <p class="muted">Checks factual claims against World Lore, the NPC’s own lore, permitted Lore Access entries and DM-curated memories. Paste source-document text into those existing sections. DM-only and other NPCs’ private lore are excluded. Unsupported or conflicting claims are flagged; greetings and ordinary roleplay need no source. AI review can still make mistakes.</p>
      <h3>Protect privacy</h3>
      <div class="safeguard-grid"><label><input id="safeguard-cards" type="checkbox" style="width:auto"> Card numbers</label><label><input id="safeguard-phones" type="checkbox" style="width:auto"> Phone numbers</label><label><input id="safeguard-addresses" type="checkbox" style="width:auto"> Street addresses</label></div>
      <p class="muted">Local masking runs before new player dialogue is stored or sent to the provider, and before NPC replies are displayed. Also masks older context when sent to the AI. Recognizes card checksums, common phone formats and numbered English street-address formats; unusual formats may be missed and fictional addresses may match. Does not erase older records, backups or NWN chat logs.</p>
      <p id="safeguard-cost" class="instructions"></p>
      <button id="safeguard-save" type="submit" class="primary" disabled>Save settings</button>
      <button id="safeguard-reload" type="button">Reload saved settings</button>
      <p id="safeguard-notice" role="status">Loading settings…</p>
    </form>
    <h3>Recent safeguard events</h3><p class="muted">Latest 20 of up to 200 saved events. Records categories and actions, never dialogue or detected private data.</p>
    <div id="safeguard-events"></div>`;
  host.append(panel);
  const get = id => document.getElementById('safeguard-' + id);
  const categories = {profanity:'Profanity', hate:'Hate speech', violence:'Violence', sensitive:'Sensitive topics'};
  for (const [key, title] of Object.entries(categories)) {
    const label = document.createElement('label'); label.htmlFor='safeguard-'+key; label.textContent=title;
    const select = document.createElement('select'); select.id='safeguard-'+key;
    for (const value of ['off','low','medium','high']) {
      const option=document.createElement('option'); option.value=value; option.textContent=value[0].toUpperCase()+value.slice(1); select.append(option);
    }
    label.append(select); get('levels').append(label);
  }
  let loaded=false, dirty=false, loading=false;
  const read = () => ({levels:Object.fromEntries(Object.keys(categories).map(k=>[k,get(k).value])),
    topics:get('topics').value, action:get('action').value, lore_check:get('lore').checked,
    privacy:Object.fromEntries(['cards','phones','addresses'].map(k=>[k,get(k).checked]))});
  function cost() {
    const p=read(), content=Object.values(p.levels).some(v=>v!=='off');
    get('cost').textContent=content?'Content checks add up to two AI review requests per dialogue turn, increasing token usage and response time. Lore checking shares the output review.':p.lore_check?'Lore checking adds one AI review request per NPC reply, increasing token usage and response time.':'No extra AI review requests. Privacy masking and existing local checks do not use tokens.';
  }
  function populate(p) {
    for(const k of Object.keys(categories))get(k).value=p.levels[k];
    get('topics').value=p.topics;get('action').value=p.action;get('lore').checked=p.lore_check;
    for(const k of ['cards','phones','addresses'])get(k).checked=p.privacy[k];
    loaded=true;dirty=false;get('save').disabled=true;cost();
  }
  async function request(body) {
    const response=await fetch('/api/safeguards',body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
    const data=await response.json();if(!response.ok)throw Error(data.error||'Unable to load safeguard settings');return data;
  }
  function status(data) {
    get('engine').textContent=(data.sdk.active?'Guardrails AI '+data.sdk.version+' active. ':data.sdk.enabled?data.sdk.error+' ':'Built-in protections active. ')+(data.provider_ready?'AI review uses your configured provider.':'Connect an AI provider before enabling content or lore review.');
    get('events').replaceChildren();
    for(const event of data.events) {
      const row=document.createElement('p');row.className='entry';
      row.textContent=new Date(event.created*1000).toLocaleString()+' · '+event.npc+' · '+event.stage+' · '+event.categories+' · '+event.action;
      get('events').append(row);
    }
    if(!data.events.length)get('events').textContent='No safeguard events recorded yet.';
  }
  async function refresh(reload=false) {
    if(loading)return;loading=true;
    try {const data=await request();status(data);if(!loaded||reload){populate(data.settings);get('notice').textContent='Saved settings loaded.';}}
    catch(error){get('notice').textContent=error.message;}
    finally{loading=false;}
  }
  get('form').addEventListener('input',()=>{if(!loaded)return;dirty=true;get('save').disabled=false;get('notice').textContent='Unsaved changes.';cost();});
  get('reload').onclick=()=>{if(!dirty||confirm('Discard unsaved safeguard changes?'))refresh(true);};
  get('form').onsubmit=async event=>{
    event.preventDefault();if(!loaded||loading)return;
    loading=true;const value=read();const fields=[...get('form').querySelectorAll('input,select,textarea,button')];fields.forEach(e=>e.disabled=true);
    try{const data=await request(value);populate(data.settings);status(data);get('notice').textContent='Settings saved. Applies to new dialogue; older in-progress replies are discarded.';}
    catch(error){get('notice').textContent=error.message;}
    finally{loading=false;fields.forEach(e=>e.disabled=false);get('save').disabled=!dirty;}
  };
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  window.addEventListener('hashchange',()=>{if(!host.hidden)refresh();});
  refresh();setInterval(()=>{if(!host.hidden)refresh();},10000);
})();
