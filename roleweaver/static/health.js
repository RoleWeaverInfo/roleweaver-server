/* Health is a separate read-only surface: it stays usable during DB recovery. */
(() => {
 'use strict';
 const host=document.getElementById('health-root')||document.getElementById('page-health');
 if(!host)return;
 const panel=document.createElement('section');
 panel.innerHTML=`<style>
 .health-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:14px;margin:18px 0}
 .health-card{padding:16px;border:1px solid #485972;border-radius:8px;background:#192333}
 .health-card h3{margin:0 0 8px}.health-card p{margin:8px 0}.health-card dl{font-size:.92em}.health-card dt{color:#b8c8df}.health-card dd{margin:0 0 8px;overflow-wrap:anywhere}
 .health-state{font-weight:bold;color:#b7c4d8}.health-state[data-state=healthy]{color:#9ee2b2}.health-state[data-state=error]{color:#ffa5a5}.health-state[data-state=warning],.health-state[data-state=offline]{color:#ffd58a}
 .health-table{width:100%;border-collapse:collapse}.health-table th,.health-table td{padding:8px;text-align:left;border-bottom:1px solid #485972}.health-scroll{overflow:auto}
 .health-code{overflow-wrap:anywhere;white-space:pre-wrap}.health-links{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
 </style><h2>System status</h2>
 <p>Connection, workers, storage and recent provider results in one place. Checks run every five seconds and make no LLM requests.</p>
 <p class="health-links"><button id="health-refresh" type="button">Refresh status</button><a href="/api/support-report" download="roleweaver-support.zip">Download support report</a><a href="/recovery">Database &amp; Recovery</a></p>
 <p id="health-status" role="status" aria-live="polite">Loading health status…</p><p id="health-build" class="muted"></p>
 <div id="health-cards" class="health-grid"></div>
 <h3>Game bridge and loaded plugins</h3><p id="health-plugin-note"></p><div class="health-scroll"><table class="health-table"><thead><tr><th>Plugin</th><th>Last observation</th></tr></thead><tbody id="health-plugins"></tbody></table></div>
 <h3>Recent technical errors</h3><p id="health-log-status"></p><div class="health-scroll"><table class="health-table"><thead><tr><th>Time</th><th>Event</th><th>Error type</th><th>HTTP</th></tr></thead><tbody id="health-errors"></tbody></table></div>
 <details><summary>What the support report includes</summary><p>The ZIP contains health.json, errors.jsonl and an explanation. It includes versions, a source fingerprint, component states, counters and filtered Python error locations. It excludes credentials, addresses, player/NPC identities, conversations, lore, prompts, translated text and database contents. No raw configuration, engine logs, exception messages or local variables are collected.</p><p>Logs are limited to four 1 MiB files; reports include up to 1,000 saved records and 20 recent in-memory errors. Repeated errors are coalesced for 60 seconds. Review the report before sharing, and include your reproduction steps and NWN/NWNX versions separately.</p></details>
 <details><summary>Technical health snapshot</summary><pre id="health-raw" class="health-code"></pre></details>`;
 host.append(panel);
 const $=id=>document.getElementById('health-'+id);
 const labels={companion:'Role Weaver Addon',redis:'Redis connection',bridge:'NWN game bridge',workers:'Background workers',translations:'Translation cache',provider:'LLM requests',databases:'Databases',backups:'Recovery backups',disk:'Disk space',error_log:'Error log',monitor:'Health monitor',application_probe:'Health check'};
 const names={uptime_seconds:'Uptime',heartbeat_age_seconds:'Last heartbeat (seconds ago)',active_replies:'Active replies',pending_commands:'Awaiting game confirmation',queued:'Queued translations',cache_hits_since_start:'Cache hits since start',provider:'Provider',attempts_last_hour:'LLM attempts in the last hour',failures_last_hour:'Failed attempts in the last hour',mean_duration_ms:'Average request time (ms)',last_attempt_age_seconds:'Last request (seconds ago)',last_attempt_ok:'Last request succeeded',usage_write_failed:'Usage logging failed',automatic:'Automatic backups',verified_points:'Verified recovery points',latest_age_seconds:'Latest backup (seconds ago)',free_bytes:'Free disk space',reserve_bytes:'Backup disk reserve',latency_ms:'PING response (ms)',translation_protocol:'Dialogue adapter protocol',bridge:'Bridge thread running',translation:'Translation thread running',checked_at:'Database check time'};
 const size=n=>(n/1048576).toLocaleString(undefined,{maximumFractionDigits:1})+' MiB';
 function el(tag,text){const node=document.createElement(tag);node.textContent=text;return node;}
 function render(data){
  $('status').textContent=`Sample age: ${data.sample_age_seconds??'pending'} seconds · Role Weaver Addon uptime: ${data.uptime_seconds??0} seconds`;
  $('build').textContent=data.build?`Role Weaver ${data.build.application} · Python ${data.build.python} · SQLite ${data.build.sqlite} · ${data.build.platform} ${data.build.architecture} · Source ${data.build.source_sha256.slice(0,12)}`:'';
  $('cards').replaceChildren();
  for(const [key,part] of Object.entries(data.components||{})){
   const card=el('article','');card.className='health-card';card.append(el('h3',labels[key]||key));
   const badge=el('span',part.state);badge.className='health-state';badge.dataset.state=part.state;card.append(badge,el('p',part.detail));
   const metrics=el('dl','');
   for(const [name,value] of Object.entries(part)){
    if(!names[name])continue;
    const text=value===null?'Not observed':typeof value==='boolean'?(value?'Yes':'No'):name.endsWith('_bytes')?size(value):name==='checked_at'?new Date(value*1000).toLocaleString():String(value);
    metrics.append(el('dt',names[name]),el('dd',text));
   }
   if(part.entries)metrics.append(el('dt','Cached entries'),el('dd',Object.entries(part.entries).map(([s,n])=>`${s}: ${n}`).join(' · ')));
   if(part.databases)for(const [kind,value] of Object.entries(part.databases))metrics.append(el('dt',kind),el('dd',`${value.missing?'Missing':value.ok?'Check passed':'Check failed'} · ${size(value.bytes+value.wal_bytes)}`));
   card.append(metrics);$('cards').append(card);
  }
  const bridge=data.components?.bridge;
  $('plugin-note').textContent=bridge?.detail||'No plugin report is available yet. Start NWN with the updated bridge to populate this table.';
  $('plugins').replaceChildren();
  for(const [name,loaded] of Object.entries(bridge?.plugins||{})){
   const row=el('tr','');row.append(el('td','NWNX_'+name),el('td',loaded===null?'Not reported':loaded?'Loaded':'Not loaded'));$('plugins').append(row);
  }
  const log=data.diagnostics||{};
  const total=Object.values(log.counts||{}).reduce((a,b)=>a+b,0);
  $('log-status').textContent=`${total} error events since startup. ${log.pending_repeats||0} repeats pending log coalescing.${log.write_failed?' Log file writing has failed; the list below is held in memory.':''}`;
  $('errors').replaceChildren();
  for(const error of [...(log.recent||[])].reverse()){
   const row=el('tr','');row.append(el('td',new Date(error.time*1000).toLocaleTimeString()),el('td',error.event.replaceAll('_',' ')),el('td',error.error),el('td',error.http_status??'—'));$('errors').append(row);
  }
  $('raw').textContent=JSON.stringify(data,null,2);
 }
 let loading=false;
 async function load(){
  if(loading)return;loading=true;$('refresh').disabled=true;
  try{const response=await fetch('/api/health');if(!response.ok)throw Error('Health endpoint unavailable');render(await response.json());}
  catch(e){$('status').textContent='Cannot reach the health panel. Check that the Role Weaver Addon is running and your SSH tunnel is open. Previously displayed information may be stale.';}
  finally{loading=false;$('refresh').disabled=false;}
 }
 $('refresh').addEventListener('click',load);
 window.addEventListener('hashchange',()=>{if(location.hash==='#health')load();});
 setInterval(()=>{if(!document.hidden&&(!host.hidden)&&(host.id==='health-root'||location.hash==='#health'))load();},5000);
 load();
})();
