/* Local knowledge inspection and content-free provider telemetry. */
(() => {
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  async function api(path, body) {
    const r=await fetch('/api/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;
  }
  const style=el('style');style.textContent=`
    .insight-controls,.insight-cards,.insight-charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:18px 0}
    .insight-controls label{margin:0;min-width:0}.insight-controls select,.insight-controls input{display:block;width:100%;margin-top:8px}
    .insight-charts{grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}.insight-card{background:#202236;border:1px solid #383c53;border-radius:12px;padding:18px;min-width:0}
    .insight-value{font-size:1.65rem;color:#eee;font-weight:650;margin:8px 0}.insight-card small{display:block;color:#abb2c8}
    .insight-chart svg{width:100%;height:auto;display:block}.insight-chart h3{margin:0 0 12px}.insight-legend{font-size:.85rem;display:flex;gap:16px;flex-wrap:wrap}
    .insight-scroll{overflow:auto}.insight-table{border-collapse:collapse;width:100%;font-size:.85rem}.insight-table th,.insight-table td{padding:10px;border-bottom:1px solid #383c53;text-align:left;white-space:nowrap}
    .knowledge-item{margin:12px 0;padding:14px;border:1px solid #383c53;border-radius:8px}.knowledge-item summary{cursor:pointer;font-weight:600}.knowledge-text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}.insight-muted{color:#abb2c8}.knowledge-editor{margin-top:12px}.knowledge-editor textarea{width:100%;min-height:110px}
    @media(max-width:600px){.insight-charts{grid-template-columns:minmax(0,1fr)}}`;
  document.head.append(style);
  $('page-knowledge').insertAdjacentHTML('beforeend',`<section>
    <div class="insight-controls"><label>NPC<select id="ki-npc"></select></label><label>Player context<select id="ki-player"><option value="">Shared knowledge only</option></select></label><label>Find in this view<input id="ki-search" type="search" placeholder="Search facts or sources"></label></div>
    <button id="ki-refresh">Refresh knowledge</button><p id="ki-status" role="status"></p>
    <p class="insight-muted">This is the saved context available for future replies, not a readout of the model’s thoughts. Player statements and NPC replies are conversation history, not verified facts. Privacy masking, legacy name filtering and dialogue safeguards still apply before requests are sent.</p>
    <div id="ki-content"></div></section>`);
  let knowledgeLoaded=false, knowledgeSequence=0;
  const dirtyKnowledge=()=>!!document.querySelector('#ki-content textarea[data-dirty="yes"]');
  function allowRefresh(){return !dirtyKnowledge()||confirm('Discard unsaved memory edits and reload this view?');}
  function option(select,value,label){const o=el('option',label);o.value=value;select.append(o);}
  function source(parent,title,text,note,open=false){const box=el('details',undefined,'knowledge-item');box.open=open;box.append(el('summary',title),el('p',note,'insight-muted'),el('div',text||'(No text supplied.)','knowledge-text'));parent.append(box);return box;}
  async function knowledge(reloadRoster=false) {
    const seq=++knowledgeSequence;
    $('ki-status').textContent='Loading knowledge…';
    try {
      if(!knowledgeLoaded||reloadRoster){const state=await api('state');if(seq!==knowledgeSequence)return;const old=$('ki-npc').value;$('ki-npc').replaceChildren();for(const p of state.npcs)option($('ki-npc'),p.id,p.name+' · '+p.id);if(state.npcs.some(p=>p.id===old))$('ki-npc').value=old;knowledgeLoaded=true;}
      const npc=$('ki-npc').value, player=$('ki-player').value;
      if(!npc){$('ki-content').replaceChildren();$('ki-status').textContent='Create an NPC first.';return;}
      const d=await api('knowledge?'+new URLSearchParams({npc,player}));if(seq!==knowledgeSequence)return;
      $('ki-player').replaceChildren();option($('ki-player'),'','Shared knowledge only');for(const p of d.players)option($('ki-player'),p.player,'Player '+p.player.slice(0,12)+' · '+new Date(p.last_seen*1000).toLocaleDateString());$('ki-player').value=d.player;
      const host=$('ki-content');host.replaceChildren();
      host.append(el('h3',d.name+' — profile and personal knowledge'));
      for(const [key,value] of Object.entries(d.profile))source(host,key[0].toUpperCase()+key.slice(1),value,'Saved NPC profile. Edit in NPCs.');
      host.append(el('h3','World documents'));
      for(const doc of d.documents)source(host,doc.title+' · '+(doc.available?'Included':'Excluded'),doc.text,doc.reason+' · Edit in World Lore.');
      if(!d.documents.length)host.append(el('p','No world documents.'));
      host.append(el('h3','Lore access'));
      for(const item of d.access_lore)source(host,item.title+' · '+(item.available?'Included':'Excluded'),item.text,item.reason+(item.available?' · Disclosure: '+(item.disclosure||'May discuss naturally.'):'')+' · Edit in Lore Access.');
      if(!d.access_lore.length)host.append(el('p','No additional lore entries.'));
      host.append(el('h3','DM-curated memories'),el('p',`Showing ${d.memories.length} of ${d.memory_total} applicable memories. Requests use the newest ${d.memory_limit}, combining shared and selected-player memories.`,'insight-muted'));
      for(const memory of d.memories){
        const row=source(host,memory.player?'Selected player memory':'Shared NPC memory',memory.text,new Date(memory.created*1000).toLocaleString(),true);
        const edit=el('button','Edit'),forget=el('button','Forget');row.append(edit,document.createTextNode(' '),forget);
        edit.onclick=()=>{if(row.querySelector('textarea'))return;const form=el('form',undefined,'knowledge-editor'),area=el('textarea');area.value=memory.text;area.maxLength=2000;area.required=true;area.setAttribute('aria-label','Edit memory');area.oninput=()=>area.dataset.dirty=area.value===memory.text?'no':'yes';const save=el('button','Save memory'),cancel=el('button','Cancel');cancel.type='button';cancel.onclick=()=>form.remove();form.append(area,save,cancel);form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{await api('memory-edit',{npc,id:memory.id,text:area.value});area.dataset.dirty='no';memory.text=area.value;row.querySelector('.knowledge-text').textContent=area.value;form.remove();$('ki-status').textContent='Memory updated. Future replies use the corrected memory.';}catch(err){$('ki-status').textContent=err.message;}finally{save.disabled=false;}};row.append(form);area.focus();};
        forget.onclick=async()=>{if(!confirm('Forget this curated memory? Related conversation text, other lore and older backups remain.'))return;forget.disabled=true;try{await api('forget',{npc,id:memory.id});row.remove();$('ki-status').textContent='Memory removed. Related conversation text and other sources remain; refresh to update the count.';}catch(err){$('ki-status').textContent=err.message;forget.disabled=false;}};
      }
      host.append(el('h3','Recent conversation context'));
      if(!d.player)host.append(el('p','Select a player above to inspect their recent conversation and personal memories. Identifiers are private references, not character names supplied to the AI.'));
      else {host.append(el('p',`Up to ${d.history_limit} stored messages for this NPC and player. Old unsafe text may be filtered before generation; this view shows the stored record.`,'insight-muted'));for(const message of d.history)source(host,message.speaker==='npc'?'NPC reply':'Player statement — unverified',message.text,new Date(message.created*1000).toLocaleString(),true);if(!d.history.length)host.append(el('p','No recent conversation messages.'));}
      $('ki-status').textContent='Knowledge loaded. Refresh after changing lore or playing.';filterKnowledge();
    } catch(err){if(seq===knowledgeSequence)$('ki-status').textContent=err.message;}
  }
  function filterKnowledge(){const q=$('ki-search').value.toLowerCase();document.querySelectorAll('#ki-content .knowledge-item').forEach(n=>n.hidden=!n.textContent.toLowerCase().includes(q));}
  $('ki-search').oninput=filterKnowledge;
  let previousNpc='',previousPlayer='';
  $('ki-npc').onfocus=()=>previousNpc=$('ki-npc').value;$('ki-player').onfocus=()=>previousPlayer=$('ki-player').value;
  $('ki-npc').onchange=()=>{if(!allowRefresh()){$('ki-npc').value=previousNpc;return;}$('ki-player').value='';knowledge();};
  $('ki-player').onchange=()=>{if(!allowRefresh()){$('ki-player').value=previousPlayer;return;}knowledge();};
  $('ki-refresh').onclick=()=>{if(allowRefresh())knowledge(true);};

  $('page-usage').insertAdjacentHTML('beforeend',`<section>
    <div class="insight-controls"><label>Time range<select id="um-window"><option value="1h">Last hour</option><option value="24h" selected>Last 24 hours</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option></select></label><label>NPC<select id="um-npc"><option value="">All NPCs</option></select></label><label>Request category<select id="um-phase"><option value="">All requests</option><option value="dialogue">NPC dialogue</option><option value="input_review">Input safeguard review</option><option value="connection_test">Connection tests</option><option value="output_review">Output safeguard review</option></select></label><label>Model<select id="um-model"><option value="">All models</option></select></label></div>
    <button id="um-refresh">Refresh usage</button><p id="um-status" role="status"></p>
    <div id="um-cards" class="insight-cards"></div>
    <p id="um-coverage" class="insight-muted"></p>
    <div id="um-charts" class="insight-charts"></div>
    <details class="knowledge-item"><summary>Model pricing — USD per million tokens</summary><p>Enter rates from your provider’s pricing page for your exact model and service tier. Prices apply to future requests only; existing estimates retain the rates used at request time. These are estimates, not an invoice.</p>
    <form id="um-pricing"><div class="insight-controls"><label>Model name<input id="um-price-model" maxlength="128" required></label><label>Input rate ($ / 1M tokens)<input id="um-price-input" type="number" min="0" max="10000" step="any" required></label><label>Output rate ($ / 1M tokens)<input id="um-price-output" type="number" min="0" max="10000" step="any" required></label><label>Cached input rate (optional)<input id="um-price-cached" type="number" min="0" max="10000" step="any"></label></div><label>Optional input-token ceiling for these rates<input id="um-price-max_input_tokens" type="number" min="1" max="1000000000" step="1" placeholder="Leave blank for a flat rate"></label><button id="um-price-save">Save rates</button><p id="um-price-status" role="status"></p></form>
    <p class="insight-muted">Blank cached rate uses the ordinary input rate. If cached usage is unreported, all input is estimated at the ordinary rate. Reasoning tokens are included in reported output, not charged twice. Requests above the optional ceiling have unknown cost. Cache-write surcharges, long-context surcharges, discounts, tools, taxes and provider-specific charges are not included.</p></details>
    <h3>Breakdown</h3><div id="um-breakdown" class="insight-scroll"></div>
    <h3>Recent requests</h3><p class="insight-muted">Latest 50 matching attempts. Response time is the complete provider request, including network time; it excludes game delivery and other requests in the same turn. Request size is the JSON body, excluding HTTP headers.</p><div id="um-recent" class="insight-scroll"></div>
    <p class="insight-muted">Monitoring starts with this version. Retains up to 30 days or 50,000 requests, whichever is reached first. Stored locally in usage.sqlite3, separately from gameplay backups; survives app restarts. No prompts, replies, player identifiers or API keys are stored in usage records. Offline replies and local-only checks do not count as provider requests.</p>
    </section>`);
  const fmt=n=>n===null||n===undefined?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:2});
  const usd=n=>n===null||n===undefined?'Unknown':'$'+Number(n).toFixed(6);
  const ms=n=>n===null||n===undefined?'—':fmt(n/1000)+' s';
  const kb=n=>n===null||n===undefined?'—':fmt(n/1024)+' KiB';
  let usageLoading=false, usageDirty=false, rates={}, pricingLoaded=false;
  function card(title,value,detail){const box=el('div',undefined,'insight-card');box.append(el('small',title),el('div',value,'insight-value'),el('small',detail));$('um-cards').append(box);}
  function table(host,headers,rows){host.replaceChildren();if(!rows.length){host.append(el('p','No matching requests recorded yet.'));return;}const t=el('table',undefined,'insight-table'),head=el('thead'),hr=el('tr');for(const h of headers)hr.append(el('th',h));head.append(hr);const body=el('tbody');for(const values of rows){const tr=el('tr');for(const value of values)tr.append(el('td',String(value)));body.append(tr);}t.append(head,body);host.append(t);}
  const svgEl=(tag,attrs,text)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;};
  function chart(title,series,lines,format){
    const box=el('div',undefined,'insight-card insight-chart');box.append(el('h3',title));const legend=el('div',undefined,'insight-legend');for(const line of lines){const label=el('span',line.label);label.style.color=line.color;legend.append(label);}box.append(legend);
    const svg=svgEl('svg',{viewBox:'0 0 520 230',role:'img','aria-label':title});svg.append(svgEl('title',{},title+' over the selected time range. Hover over points for values.'));
    const values=series.flatMap(b=>lines.map(l=>l.value(b))).filter(v=>v!==null&&Number.isFinite(v));
    if(!values.length){box.append(el('p','No reported data in this period.','insight-muted'));$('um-charts').append(box);return;}
    const max=Math.max(...values,0.000001),x=i=>65+i*440/Math.max(1,series.length-1),y=v=>185-v/max*145;
    for(const f of [0,.5,1]){const yy=y(max*f);svg.append(svgEl('line',{x1:65,y1:yy,x2:505,y2:yy,stroke:'#383c53'}),svgEl('text',{x:59,y:yy+4,'text-anchor':'end',fill:'#abb2c8','font-size':11},format(max*f)));}
    for(const line of lines){let points=[];const flush=()=>{if(points.length)svg.append(svgEl('polyline',{points:points.join(' '),fill:'none',stroke:line.color,'stroke-width':2}));points=[];};series.forEach((b,i)=>{const v=line.value(b);if(v===null||!Number.isFinite(v)){flush();return;}points.push(x(i)+','+y(v));const dot=svgEl('circle',{cx:x(i),cy:y(v),r:2.4,fill:line.color});dot.append(svgEl('title',{},new Date(b.time*1000).toLocaleString()+' · '+line.label+': '+format(v)));svg.append(dot);});flush();}
    for(const i of [0,Math.floor((series.length-1)/2),series.length-1])svg.append(svgEl('text',{x:x(i),y:211,'text-anchor':i===0?'start':i===series.length-1?'end':'middle',fill:'#abb2c8','font-size':10},new Date(series[i].time*1000).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})));
    box.append(svg);$('um-charts').append(box);
  }
  function choices(id,values,label){const target=$(id),old=target.value;target.replaceChildren();option(target,'',label);for(const value of values)option(target,value,value);if(values.includes(old))target.value=old;}
  function loadRates(){const p=rates[$('um-price-model').value];for(const k of ['input','output','cached','max_input_tokens'])$('um-price-'+k).value=p&&p[k]!==null?p[k]:'';}
  async function usage(){
    if(usageLoading){usageDirty=true;return;}usageLoading=true;
    try {
      const q=new URLSearchParams(Object.fromEntries(['window','npc','phase','model'].map(k=>[k,$('um-'+k).value]))),d=await api('usage?'+q),s=d.summary;
      if(q.toString()!==new URLSearchParams(Object.fromEntries(['window','npc','phase','model'].map(k=>[k,$('um-'+k).value]))).toString()){usageDirty=true;return;}
      choices('um-npc',d.choices.npc,'All NPCs');choices('um-model',d.choices.model,'All models');rates=d.prices;
      if(!pricingLoaded){$('um-price-model').value=d.current_model;loadRates();pricingLoaded=true;}
      $('um-cards').replaceChildren();card('Provider requests',fmt(s.requests),fmt(s.errors)+' errors · '+(s.requests?fmt(s.errors/s.requests*100):'0')+'% error rate');
      card('Reported input tokens',s.input_reporting?fmt(s.input_tokens):'—',fmt(s.cached_tokens)+' reported cached tokens (included)');
      card('Reported output tokens',s.output_reporting?fmt(s.output_tokens):'—',fmt(s.reasoning_tokens)+' reported reasoning tokens (included)');
      card('Estimated cost',usd(s.cost_usd),s.priced_requests+' of '+s.requests+' requests priced');
      card('Average response time',ms(s.average_ms),'95th percentile: '+ms(s.p95_ms));card('Average request size',kb(s.average_bytes),'Largest request: '+kb(s.max_bytes));
      $('um-coverage').textContent=`${s.token_requests} of ${s.requests} requests reported both token counts. Totals include only reported tokens and priced requests; missing usage or rates are not zero cost. Graphs use ${fmt(d.bucket_seconds/60)}-minute buckets. `+(d.earliest?'Earliest retained request: '+new Date(d.earliest*1000).toLocaleString()+'.':'No history yet.');
      $('um-charts').replaceChildren();
      chart('Reported tokens',d.series,[{label:'Input',color:'#b794ff',value:b=>b.input_reporting?b.input_tokens:null},{label:'Output',color:'#58d6c7',value:b=>b.output_reporting?b.output_tokens:null}],fmt);
      chart('Requests',d.series,[{label:'All attempts',color:'#b794ff',value:b=>b.requests},{label:'Errors',color:'#ff987f',value:b=>b.errors}],fmt);
      chart('Provider response time',d.series,[{label:'Average',color:'#58d6c7',value:b=>b.average_ms},{label:'95th percentile',color:'#f0c66b',value:b=>b.p95_ms}],ms);
      chart('Estimated cost',d.series,[{label:'Known cost only (USD)',color:'#b794ff',value:b=>b.cost_usd}],usd);
      chart('Request size',d.series,[{label:'Average JSON body',color:'#58d6c7',value:b=>b.average_bytes},{label:'Largest JSON body',color:'#f0c66b',value:b=>b.max_bytes}],kb);
      table($('um-breakdown'),['NPC','Model','Category','Requests','Errors','Input','Output','Estimated USD','Priced','Avg response'],d.breakdown.map(r=>[r.npc,r.model,r.phase,r.requests,r.errors,r.input_reporting?fmt(r.input_tokens):'—',r.output_reporting?fmt(r.output_tokens):'—',usd(r.cost_usd),r.priced_requests+'/'+r.requests,ms(r.average_ms)]));
      table($('um-recent'),['Time','NPC','Model','Category','Result','Response','Request size','Input / output','Cached / reasoning','Estimated USD'],d.recent.map(r=>[new Date(r.created*1000).toLocaleString(),r.npc,r.model,r.phase,r.status+(r.error?' · '+r.error:'')+(r.http_status?' · HTTP '+r.http_status:''),ms(r.duration_ms),kb(r.request_bytes)+' · '+fmt(r.request_chars)+' chars',fmt(r.input_tokens)+' / '+fmt(r.output_tokens),fmt(r.cached_tokens)+' / '+fmt(r.reasoning_tokens),usd(r.cost_usd)]));
      $('um-status').textContent=d.error||'Updated '+new Date().toLocaleTimeString()+'. Refreshes every 15 seconds while this page is visible.';
    }catch(err){$('um-status').textContent=err.message;}finally{usageLoading=false;if(usageDirty){usageDirty=false;usage();}}
  }
  for(const key of ['window','npc','phase','model'])$('um-'+key).onchange=usage;
  $('um-refresh').onclick=usage;$('um-price-model').onchange=loadRates;
  $('um-pricing').onsubmit=async e=>{e.preventDefault();const button=$('um-price-save');button.disabled=true;try{const model=$('um-price-model').value;rates[model]=await api('usage-pricing',{model,rates:Object.fromEntries(['input','output','cached','max_input_tokens'].map(k=>[k,$('um-price-'+k).value===''?null:Number($('um-price-'+k).value)]))});$('um-price-status').textContent='Rates saved for future requests.';usage();}catch(err){$('um-price-status').textContent=err.message;}finally{button.disabled=false;}};
  function route(){if(location.hash==='#knowledge'&&!knowledgeLoaded)knowledge();if(location.hash==='#usage')usage();}
  window.addEventListener('hashchange',route);window.addEventListener('beforeunload',e=>{if(dirtyKnowledge()){e.preventDefault();e.returnValue='';}});
  setInterval(()=>{if(!document.hidden&&location.hash==='#usage')usage();},15000);route();
})();
