/* Refresh diagnostics separately so an owner's unsaved settings/corrections survive. */
(() => {
 'use strict';
 const host=document.getElementById('page-translations');if(!host)return;
 const panel=document.createElement('section');
 panel.innerHTML=`<style>.trd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.trd-card{border:1px solid #485972;border-radius:8px;padding:14px}.trd-card strong{display:block;font-size:1.4em}.trd-table{width:100%;border-collapse:collapse}.trd-table td,.trd-table th{text-align:left;padding:8px;border-bottom:1px solid #485972}.trd-scroll{overflow:auto}</style>
 <h2>Translation diagnostics</h2><p id="trd-status" role="status" aria-live="polite">Loading translation status…</p><p id="trd-worker"></p>
 <div id="trd-metrics" class="trd-grid"></div><p id="trd-last"></p><p id="trd-cost"></p>
 <p><button id="trd-refresh" type="button">Refresh diagnostics</button> <a href="#health">Health &amp; Support</a></p>
 <h3>Cache by language</h3><div class="trd-scroll"><table class="trd-table"><thead><tr><th>Language</th><th>Ready</th><th>Pending</th><th>Failed</th><th>Needs another visit</th><th>Obsolete</th></tr></thead><tbody id="trd-languages"></tbody></table></div>
 <p>Pending includes queued and active jobs. Failed jobs retry only when requested again after their cooldown. Missing text waits for another visit. Obsolete entries are retained but no longer used for the changed source. Cache hits and queue-full counts reset when the addon restarts.</p>
 <h3>Recent translation request errors</h3><div id="trd-errors"></div>
 <details><summary>Why might text remain untranslated?</summary><ul><li>New or changed text needs a first request. Close and reopen it once ready; hover labels refresh automatically.</li><li>The player must enable translation in <code>/rw language</code> and choose a language different from the source.</li><li>Translation may be disabled, the queue may be full, or the provider or rate limit may delay it.</li><li>Excluded objects, unsupported text surfaces, oversized text and dialogue with dynamic markup keep their original text.</li><li>Existing standard dialogues need offline preparation. This panel cannot prove that every module dialogue or event hook was installed correctly.</li></ul><p>Supported now: ordinary object Examine text, public NPC/player descriptions, NPC/placeable hover labels, and prepared standard NPC dialogue. Player names, chat, tells and logs stay unchanged. Journals, custom quests, message-board systems and custom menus need separate integration later.</p><p id="trd-adapter"></p></details>`;
 const first=host.querySelector('section');host.insertBefore(panel,first);
 const $=id=>document.getElementById('trd-'+id);
 const language={en:'English',fr:'French',es:'Spanish',de:'German',it:'Italian',pt:'Portuguese'};
 const element=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
 let current,busy=false;
 function render(d){
  current=d;$('status').textContent=d.message;
  $('worker').textContent=`Worker: ${d.worker_running?'running':'stopped'} · Provider: ${d.provider} · Source: ${language[d.source]||d.source} · Limit: ${d.per_minute} jobs/minute · Updated ${new Date(d.sampled_at*1000).toLocaleTimeString()}`;
  const request=d.requests_last_hour;
  const values=[['Ready in cache',d.counts.ready],['Queued jobs',d.pending],['Current request',d.active_seconds===null?'Idle':d.active_seconds+' seconds'],['Rate-limit wait',d.rate_wait_seconds+' seconds'],['Cache hits',d.cache_hits],['Queue-full deferrals',d.queue_full_since_start],['HTTP attempts / last hour',request.attempts],['Failed attempts / last hour',request.failed]];
  $('metrics').replaceChildren();for(const [label,value] of values){const card=element('div','');card.className='trd-card';card.append(element('strong',String(value)),element('span',label));$('metrics').append(card);}
  const last=d.last_job;$('last').textContent=last?`Last job: ${last.status} · ${(last.duration_ms/1000).toFixed(1)} seconds · ${new Date(last.finished_at*1000).toLocaleTimeString()}${last.error?' · '+last.error+'. '+last.advice:''}`:'No translation job has finished since this addon started.';
  $('cost').textContent=`Last hour: ${request.input_tokens??'unknown'} input tokens · ${request.output_tokens??'unknown'} output tokens · ${request.mean_ms===null?'no response-time data':(request.mean_ms/1000).toFixed(1)+' seconds average per HTTP attempt'} · Estimated cost: ${request.estimated_cost_usd===null?(request.attempts?'unavailable — check model pricing and token usage in Usage & Performance':'no requests in this period'):'$'+request.estimated_cost_usd.toFixed(4)+' USD ('+request.priced_attempts+' of '+request.attempts+' attempts priced)'}. Token totals include only reported usage. Fallback attempts can produce more than one HTTP request per translation job.`;
  $('languages').replaceChildren();for(const [code,counts] of Object.entries(d.by_language)){const row=element('tr','');for(const value of [language[code]||code,counts.ready,counts.pending,counts.failed,counts.missing,counts.obsolete])row.append(element('td',String(value)));$('languages').append(row);}
  $('errors').replaceChildren();if(!d.recent_failures.length)$('errors').append(element('p','No recorded translation request errors.'));
  for(const failure of d.recent_failures)$('errors').append(element('p',`${failure.time?new Date(failure.time*1000).toLocaleString():''} · ${failure.error}${failure.http_status?' / HTTP '+failure.http_status:''}. ${failure.advice}`));
  $('adapter').textContent=d.native_adapter.detail;
 }
 async function load(){if(busy)return;busy=true;$('refresh').disabled=true;try{const response=await fetch('/api/translation-diagnostics');if(!response.ok)throw Error('Unavailable');render(await response.json());}catch(e){current=null;$('status').textContent='Translation diagnostics are unavailable. Open Health & Support to check the addon and databases. Previously displayed values may be stale.';}finally{busy=false;$('refresh').disabled=false;}}
 $('refresh').onclick=load;
 document.getElementById('tr-diagnostics').onclick=()=>{window.location.href='/api/translation-diagnostics/download';};
 window.addEventListener('hashchange',()=>{if(location.hash==='#translations')load();});
 setInterval(()=>{if(!document.hidden&&location.hash==='#translations')load();},5000);
 load();
})();
