/* Live scenes have their own API, state and controls. User text is rendered as text. */
(() => {
  'use strict';
  const host = document.getElementById('page-live-encounters');
  host.innerHTML += `<section>
    <h2>1. Describe your encounter</h2>
    <p>Ask the AI DM Assistant to prepare a live scene, or open manual setup below. Nothing is placed until you review and confirm.</p>
    <label>Instructions for the assistant<textarea id="live-assistant-instruction" maxlength="3000" placeholder="Two nervous travelers ask for help. Let players decline peacefully."></textarea></label>
    <label><input type="checkbox" id="live-assistant-combat" style="width:auto"> Allow the proposal to include combat (timed or conversation-driven)</label>
    <button type="button" id="live-assistant-draft">Prepare proposal</button>
    <p id="live-assistant-state" role="status"></p>
    <div id="live-assistant-result" hidden><h3>Assistant proposal</h3><p id="live-assistant-summary"></p><ul id="live-assistant-limits"></ul><p>The proposal has filled the editable setup below. Check its profile, limits and attack permissions before previewing.</p></div>
    <details id="live-setup"><summary><strong>2. Review and place / manual setup</strong></summary>
    <p>Creatures stay until cleanup or a module/server reset, even when the DM logs out. Your original NPC profiles and world creatures stay in place.
    This screen creates separate copies with new memories. The server must use -reloadwhenempty 0 to avoid resetting when everyone logs out. The assistant currently prepares one cast of 1–8 copies from an existing profile. Create a suitable NPC profile first if needed; mixed casts and new scripted mechanics are not supported in this first version.</p>
    <p id="live-health" role="status"></p><p id="live-notice" role="status"></p>
    <form id="live-form">
    <label>Scene name<input id="live-name" required maxlength="100" placeholder="A troll blocks the road"></label>
    <div class="grid"><div><label>NPC personality and creature profile<select id="live-profile" required></select></label></div>
    <div><label>Number of creatures<input id="live-count" type="number" min="1" max="8" value="1" required></label></div></div>
    <label>Creature source<select id="live-source"><option value="profile">Use the profile’s creature settings</option><option value="blueprint">Use an installed creature blueprint</option></select></label>
    <label id="live-blueprint-label" hidden>Blueprint resref<input id="live-blueprint" maxlength="16" pattern="[a-z][a-z0-9_]{0,15}" placeholder="Existing server blueprint"></label>
    <p>Profile creatures use the saved appearance, class and level. Monster appearance alone does not grant monster abilities.
    An installed blueprint keeps its native statistics, equipment and scripts; its normal AI may initiate combat independently of this trigger.</p>
    <label>Facts shared by the cast<textarea id="live-facts" maxlength="4000"></textarea></label>
    <label>Purpose and opening situation<textarea id="live-goal" maxlength="2000" placeholder="Demand food, listen to offers and allow travelers to leave."></textarea></label>
    <label>Behavioral limits<textarea id="live-boundaries" maxlength="3000">Allow negotiation and withdrawal. Do not invent payments, injuries or rewards.</textarea></label>
    <h3>1. Mark locations</h3>
    <label>Connected, unpossessed DM<select id="live-dm"></select></label>
    <p>Stand where the creatures should appear and mark the spawn point. Then stand at the centre of the desired trigger and mark it.
    Both points must be in the same area, no more than 20 metres apart. Marks expire after 15 minutes.</p>
    <button type="button" id="live-mark-spawn">Mark spawn at DM</button><p id="live-spawn-position">Spawn point not marked.</p>
    <button type="button" id="live-mark-trigger">Mark trigger at DM</button>
    <button type="button" id="live-same-point">Use spawn point for trigger</button><p id="live-trigger-position">Trigger point not marked.</p>
    <h3>2. Configure activation</h3>
    <label>Activation<select id="live-activation"><option value="manual">Conversation only — DM starts the scene</option><option value="conversation">Conversation-driven combat — DM-authorized decisions</option><option value="proximity">Proximity warning — after DM starts the scene</option></select></label>
    <div id="live-trigger-settings" hidden>
    <p>This is a circular game-script proximity region, not a visible trigger object. Actors are placed immediately. In proximity mode, entering the region starts the warning. Conversation combat opens with a greeting or demand when a player enters, then waits for the NPC to choose a combat warning; the timer alone never starts combat.</p>
    <div class="grid"><div><label>Trigger radius (metres)<input id="live-radius" type="number" min="1" max="8" value="5"></label></div>
    <div><label>Required leave distance (metres)<input id="live-leave" type="number" min="2" max="30" value="10"></label></div>
    <div><label>Warning grace period (seconds)<input id="live-grace" type="number" min="5" max="120" value="15"></label></div>
    <div><label>Pursuit limit (metres; 0 disables)<input id="live-pursuit" type="number" min="0" max="60" value="20"></label></div>
    <div><label>Retreat health percentage (0 disables)<input id="live-hp" type="number" min="0" max="90" value="25"></label></div></div>
    <label>Opening line for conversation combat<textarea id="live-opening" maxlength="500">A moment, traveler. I would like a word.</textarea></label><p>Spoken once when a visible player enters the trigger. This starts a conversation, not the combat warning or grace timer.</p>
    <label>Exact warning<textarea id="live-warning" maxlength="500">Leave this place. Move away now and we will not attack.</textarea></label>
    <label style="display:flex;align-items:flex-start;gap:12px;padding:12px;border:1px solid #666083;border-radius:8px"><input id="live-attack" type="checkbox" style="width:20px;height:20px;flex:0 0 20px;margin:0"> Authorize the cast to attack: after the timer in proximity mode, or after a later conversation decision in conversation mode</label><p>Unchecked means warning only, even if the warning text threatens an attack. This permission is saved when you preview and place the scene.</p>
    <label>DM conditions for conversation combat<textarea id="live-combat-conditions" maxlength="2000" placeholder="Negotiate first. Warn after refusal; attack only if the player then clearly refuses again. Back down for an acceptable peaceful solution."></textarea></label><p>Only the first actor decides for the cast. A delivered warning, grace period and later player reply are required. Leaving is safe. No reply means no attack; warnings expire two minutes after the grace period. A peaceful resolution ends this activation.</p><label>Reset behavior<select id="live-repeat"><option value="no">Run once</option><option value="yes">Repeat after return and 10 quiet seconds</option></select></label>
    </div>
    <h3>3. Preview before placing</h3><button type="submit" id="live-preview">Preview scene</button>
    </form>
    <div id="live-preview-panel" hidden><pre id="live-preview-text" style="white-space:pre-wrap"></pre>
    <canvas id="live-map" width="560" height="300" style="max-width:100%;background:#151525;border-radius:8px" aria-label="Relative spawn and trigger position preview; not a terrain map"></canvas>
    <p>Relative position diagram only; terrain, walls and walkability are not represented. Preview expires after two minutes.</p>
    <button id="live-place" class="primary">Place creatures until server reset</button></div>
    </details></section><section><h2>3. Manage live scenes</h2><label>Live scene<select id="live-select"></select></label>
    <p id="live-scene-status" role="status"></p><p>Placement starts with AI paused. Start enables dialogue and arms the configured trigger.
    Pause disables trigger renewal and AI dialogue; it is not an instant combat freeze. Cleanup removes only this scene’s creatures, retaining their profiles and memories.</p>
    <div class="row"><button id="live-start">Start / resume</button><button id="live-pause">Pause</button><button id="live-cleanup" class="stop">Clean up creatures and trigger</button></div>
    <div id="live-confirm" hidden role="group" aria-label="Confirm scene action"><p id="live-confirm-text"></p><button id="live-confirm-yes" class="stop">Confirm</button><button id="live-confirm-no">Keep current scene</button></div>
    <details><summary>Optional NWN social checks</summary>
    <p>Configure after placement, before starting (or while paused). Dice are optional. Each player gets one roll per enabled skill against each NPC per activation; repeated attempts reuse the result. A fresh Start resets checks.</p>
    <form id="live-checks-form"><label><input type="checkbox" id="live-checks-enabled" style="width:auto"> Resolve social influence using NWN skill checks</label>
    <div class="grid"><div><label><input type="checkbox" id="live-check-intimidate" checked style="width:auto"> Intimidate</label><label>Difficulty (DC)<input id="live-dc-intimidate" type="number" min="1" max="60" value="15" required></label></div><div><label><input type="checkbox" id="live-check-persuade" checked style="width:auto"> Persuade</label><label>Difficulty (DC)<input id="live-dc-persuade" type="number" min="1" max="60" value="15" required></label></div><div><label><input type="checkbox" id="live-check-bluff" checked style="width:auto"> Bluff</label><label>Difficulty (DC)<input id="live-dc-bluff" type="number" min="1" max="60" value="15" required></label></div></div>
    <label>Limits on what success can achieve<textarea id="live-checks-limits" maxlength="1000" required>May influence the NPC's immediate response within the encounter boundaries. No mind control, rewards or automatic combat.</textarea></label>
    <button id="live-checks-save">Save skill checks</button></form><p id="live-checks-state"></p>
    <h4>Confirmed rolls</h4><div id="live-checks-log"></div></details>
    <section><h3>Autonomous AI DM</h3>
    <p>Enable after placing the scene. Once started, the director works without an online DM. It reviews meaningful changes, guides NPC goals and can end an activation peacefully. Combat uses the scene’s existing permissions and warning checks.</p>
    <div class="row"><button type="button" id="live-director-enable">Enable autonomous direction</button><button type="button" id="live-director-pause">Pause director</button><button type="button" id="live-director-resume">Resume director</button></div>
    <p>Pausing the director keeps NPC dialogue available and holds new conversation-combat decisions. It does not stop combat already underway.</p>
    <p id="live-director-state" role="status"></p><h4>Current situation</h4><p id="live-director-summary"></p>
    <label>Give direction<textarea id="live-director-direction" maxlength="2000" placeholder="Let the robber consider an offer of honest work. Keep the existing combat limits."></textarea></label>
    <button type="button" id="live-director-send">Apply direction</button><p id="live-director-current"></p>
    <h4>Recent decisions</h4><div id="live-director-decisions"></div>
    <p>Reviews are at least 10 seconds apart, share request limits, and stop after 60 attempts per activation. Usage appears as live_director. No automatic rewards, payments, new spawning or scripts.</p></section>
    <details><summary>Ask the assistant about this scene</summary><p>On-demand review of this scene’s current status and game log. It does not continuously monitor or control the encounter.</p><label>Question or direction<textarea id="live-assistant-direction" maxlength="3000" placeholder="Review the scene and suggest whether to pause or continue."></textarea></label><button type="button" id="live-assistant-review">Review selected scene</button><p id="live-assistant-review-text" role="status"></p><ul id="live-assistant-review-limits"></ul><button type="button" id="live-assistant-operation" hidden></button></details>
    <div id="live-actors"></div><h3>Game confirmations</h3><div id="live-log"></div></section>`;
  const $ = id => document.getElementById('live-' + id);
  let data = null, world = null, selected = '', preview = null, busy = false, sequence = 0;
  let checksLoaded='',checksDirty=false;
  const points = {spawn:null, trigger:null};
  async function api(path, body) {
    const r = await fetch('/api/' + path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d = await r.json(); if (!r.ok) throw Error(d.error || 'Request failed'); return d;
  }
  function option(select, value, label) { const o=document.createElement('option'); o.value=value; o.textContent=label; select.append(o); }
  function options(select, rows) {const previous=select.value; select.replaceChildren(); for(const [id,label] of rows)option(select,id,label); if([...select.options].some(o=>o.value===previous))select.value=previous;}
  function invalidate() {preview=null; $('preview-panel').hidden=true;}
  function position(p) {return p ? `${p.area_name}: ${p.x.toFixed(1)}, ${p.y.toFixed(1)}` : 'Not marked';}
  function render() {
    $('health').textContent=!data?.ready?'Waiting for the updated game bridge.':!data.spawn_enabled?'DM spawning is disabled in this world.':'Live encounter bridge connected.';
    options($('select'),Object.entries(data?.scenes||{}).map(([id,s])=>[id,s.run.template.name+' — '+s.run.status]));
    if(!selected && $('select').value)selected=$('select').value;
    $('select').value=selected;
    const scene=data?.scenes[selected], status=scene?.run.status;
    $('scene-status').textContent=scene?scene.run.template.name+' — '+status+(scene.run.template.reaction.enabled?(scene.run.template.reaction.attack?(scene.run.template.reaction.combat_mode==='conversation'?' · Conversation-driven combat authorized':' · Attack authorized after the grace period'):' · WARNING ONLY — attacks are not authorized'):' · Conversation only'):'No live scenes placed.';
    $('start').disabled=busy||!data?.ready||!['staged','paused'].includes(status);
    $('pause').disabled=busy||!['active','paused'].includes(status);
    $('cleanup').disabled=busy||!data?.ready||!scene||['cleaned','expired'].includes(status);
    for(const id of ['mark-spawn','mark-trigger','preview','place'])$(id).disabled=busy||!data?.ready||!data?.spawn_enabled||!$('dm').value;
    $('assistant-draft').disabled=busy;$('assistant-review').disabled=busy||!scene;
    const checks=scene?.checks;
    const checkStamp=selected+JSON.stringify(checks||null);
    if(!checksDirty && checksLoaded!==checkStamp){
      $('checks-enabled').checked=!!checks?.enabled;
      for(const skill of ['intimidate','persuade','bluff']){$('check-'+skill).checked=checks?.skills?.[skill]?.enabled??true;$('dc-'+skill).value=checks?.skills?.[skill]?.dc??15;}
      $('checks-limits').value=checks?.limits||"May influence the NPC's immediate response within the encounter boundaries. No mind control, rewards or automatic combat.";
      checksLoaded=checkStamp;
    }
    for(const input of $('checks-form').elements)input.disabled=busy||!['staged','paused'].includes(status);
    $('checks-state').textContent=checks?.enabled?'NWN skill checks enabled. Dice and effective skill modifiers come from the server.':'Dice checks are disabled; ordinary narrative dialogue is unchanged.';
    $('checks-log').replaceChildren();
    for(const row of Object.values(scene?.check_results||{}).slice(-20).reverse()){
      const line=document.createElement('p');const r=row.result;
      line.textContent=(scene.actors[row.npc]?.name||row.npc)+' · '+(row.participant||'visitor')+' · '+row.skill+' · '+row.intent+' — '+(r?'d20 '+r.roll+' + '+r.modifier+' = '+r.total+' vs DC '+r.dc+' · '+(r.success?'SUCCESS':'FAILED'):'Awaiting game confirmation; no outcome assumed')+(row.reuse_count?' · Result reused '+row.reuse_count+' time(s); no new roll':'');$('checks-log').append(line);
    }
    const director=scene?.director||{};
    const ended=!scene||['cleaned','expired','cleaning'].includes(status);
    $('director-enable').disabled=busy||ended||!!director.enabled;
    $('director-pause').disabled=busy||ended||!director.enabled||director.paused||director.resolved;
    $('director-resume').disabled=busy||ended||!director.enabled||!director.paused||director.resolved;
    $('director-send').disabled=busy||ended;
    $('director-state').textContent=!director.enabled?'Autonomous direction is off.':
      (director.resolved?'Finished':director.paused?'Director paused':status!=='active'?'Waiting for scene start':'Autonomous direction active')+
      ' · '+(director.phase||'waiting')+' · '+(director.reviews||0)+'/60 reviews'+(director.error?' · '+director.error:'');
    $('director-summary').textContent=director.summary||'No scene review yet.';
    $('director-current').textContent=director.direction?'Current DM direction: '+director.direction:'';
    $('director-decisions').replaceChildren();
    for(const entry of [...(director.decisions||[])].reverse()){
      const line=document.createElement('p');line.textContent=new Date(entry.time*1000).toLocaleTimeString()+' · '+entry.operation+' — '+entry.reason;$('director-decisions').append(line);
    }
    $('actors').replaceChildren();
    for(const row of Object.values(scene?.actors||{})) {
      const p=document.createElement('p');p.textContent=row.name+' — placement: '+row.placement+(row.cleanup?' · cleanup: '+row.cleanup:'')+' · '+(!row.connected?'not connected':row.dead?'dead':row.combat?'in combat':row.mode);$('actors').append(p);
    }
    $('log').replaceChildren();for(const line of scene?.run.events||[]){const p=document.createElement('p');p.textContent=line;$('log').append(p);}
  }
  async function action(fn) {
    if(busy)return; busy=true; ++sequence;render();
    try {await fn();} catch(e){$('notice').textContent=e.message;} finally {busy=false;render();}
  }
  async function refresh() {
    if(busy)return;const seq=++sequence;
    try {const results=await Promise.all([api('live-encounters'),api('state')]);if(busy||seq!==sequence)return;
      [data,world]=results;
      options($('dm'),(world.dms||[]).map(d=>[d.id,d.name]));
      options($('profile'),(world.npcs||[]).filter(p=>!p.id.startsWith('live_')).map(p=>[p.id,p.name]));render();
    } catch(e){$('health').textContent=e.message;}
  }
  for(const kind of ['spawn','trigger'])$('mark-'+kind).onclick=()=>action(async()=>{
    points[kind]=await api('live-capture',{dm:$('dm').value});invalidate();
    $(kind+'-position').textContent=position(points[kind].point);
    if(kind==='spawn'&&!points.trigger){points.trigger=points.spawn;$('trigger-position').textContent=position(points.trigger.point);}
    $('notice').textContent='Location marked. Nothing spawned.';
  });
  $('same-point').onclick=()=>{if(!points.spawn)return;points.trigger=points.spawn;invalidate();$('trigger-position').textContent=position(points.trigger.point);};
  $('source').onchange=()=>{$('blueprint-label').hidden=$('source').value!=='blueprint';$('blueprint').required=$('source').value==='blueprint';invalidate();};
  $('activation').onchange=()=>{$('trigger-settings').hidden=$('activation').value==='manual';invalidate();};
  $('form').oninput=invalidate;
  $('form').onsubmit=e=>{e.preventDefault();action(async()=>{
    const enabled=$('activation').value!=='manual';
    preview=await api('live-preview',{dm:$('dm').value,name:$('name').value,profile:$('profile').value,
      count:Number($('count').value),blueprint:$('source').value==='profile'?'rw_custom':$('blueprint').value,
      spawn:points.spawn?.capture||'',trigger:points.trigger?.capture||'',public_facts:$('facts').value,
      goal:$('goal').value,boundaries:$('boundaries').value,repeat:enabled&&$('repeat').value==='yes',
      reaction:{enabled,opening:$('opening').value,combat_mode:$('activation').value==='conversation'?'conversation':'timed',combat_conditions:$('combat-conditions').value,attack:enabled&&$('attack').checked,trigger_radius:Number($('radius').value),
        leave_radius:Number($('leave').value),grace_seconds:Number($('grace').value),pursuit_radius:Number($('pursuit').value),
        retreat_hp_percent:Number($('hp').value),warning:$('warning').value}});
    const s=preview.spec,r=s.reaction;
    $('preview-text').textContent=`${s.name}\n${s.count} × ${s.profile.name}\nCreature source: ${s.blueprint}\nSpawn: ${position(s.points.spawn)}\nTrigger: ${enabled?position(s.points.trigger)+' · radius '+r.trigger_radius+' m':'None; conversation scene'}\n${r.enabled?'Warning: '+r.warning+'\n'+(r.combat_mode==='conversation'?'Conversation-driven attack only after warning and a later reply. Opening: '+r.opening+' Conditions: '+r.combat_conditions:r.attack?'Attack after '+r.grace_seconds+' seconds unless the player leaves '+r.leave_radius+' m.':'No trigger-authorized attack.')+'\n'+(s.repeat?'Repeats after quiet reset.':'One activation only.'):'DM starts dialogue manually.'}\nPurpose: ${s.goal}\nShared facts: ${s.public_facts}\nLimits: ${s.boundaries}\nTemporary copies only. Cleanup retains profiles and memories.\n${preview.note}`;
    draw(s);$('preview-panel').hidden=false;$('notice').textContent='Review the frozen preview, then place. Editing invalidates it.';
  });};
  function draw(s) {
    const c=$('map').getContext('2d'),w=560,h=300,a=s.points.spawn,b=s.points.trigger;
    c.clearRect(0,0,w,h);const radius=s.reaction.enabled?s.reaction.trigger_radius:0;
    const extent=Math.max(12,Math.abs(a.x-b.x)+radius+4,Math.abs(a.y-b.y)+radius+4),scale=120/extent;
    const x=p=>w/2+(p.x-b.x)*scale,y=p=>h/2-(p.y-b.y)*scale;
    c.strokeStyle='#a992ff';c.fillStyle='#a992ff33';c.beginPath();c.arc(x(b),y(b),radius*scale,0,2*Math.PI);c.fill();c.stroke();
    c.font='14px sans-serif';c.fillStyle='#ddd';c.fillText('Trigger centre',x(b)+8,y(b)-10);
    c.fillStyle='#f1c66e';c.beginPath();c.arc(x(a),y(a),5,0,2*Math.PI);c.fill();c.fillText('Spawn × '+s.count,x(a)+10,y(a)+22);
    c.fillStyle='#ddd';c.fillText('Relative positions · '+s.points.spawn.area_name,12,24);
  }
  $('place').onclick=()=>action(async()=>{
    if(!preview)throw Error('Preview the scene first.');const token=preview.preview;invalidate();
    const before=new Set(Object.keys(data?.scenes||{}));data=await api('live-place',{preview:token,dm:$('dm').value});
    selected=Object.keys(data.scenes).find(k=>!before.has(k))||selected;
    $('notice').textContent='Placement requested. Check game confirmations, then Start / resume.';
  });
  $('select').onchange=()=>{checksDirty=false;checksLoaded='';$('director-direction').value='';selected=$('select').value;confirmation=null;$('confirm').hidden=true;render();};
  let confirmation=null;
  for(const op of ['start','pause','cleanup'])$(op).onclick=()=>{
    const id=selected;
    if(op==='cleanup'||(op==='start'&&data?.scenes[id]?.run.template.reaction.attack)) {
      confirmation={id,op};$('confirm').hidden=false;
      $('confirm-text').textContent=op==='cleanup'?'Remove only this live scene’s creatures and disable its trigger? Profiles and memories remain.':'Start this scene and authorize its configured combat behavior?';
      return;
    }
    action(async()=>{data=await api('live-control',{id,operation:op});$('notice').textContent='Request sent; watch game confirmations below.';});
  };
  $('confirm-no').onclick=()=>{confirmation=null;$('confirm').hidden=true;};
  $('confirm-yes').onclick=()=>{
    if(!confirmation||busy)return;const {id,op}=confirmation;confirmation=null;$('confirm').hidden=true;
    action(async()=>{data=await api('live-control',{id,operation:op});$('notice').textContent='Request sent; watch game confirmations below.';});
  };
  $('checks-form').oninput=()=>{checksDirty=true;};
  $('checks-form').onsubmit=e=>{e.preventDefault();action(async()=>{
    const skills={};for(const skill of ['intimidate','persuade','bluff'])skills[skill]={enabled:$('check-'+skill).checked,dc:Number($('dc-'+skill).value)};
    data=await api('live-checks',{id:selected,settings:{enabled:$('checks-enabled').checked,skills,limits:$('checks-limits').value}});
    checksDirty=false;checksLoaded='';$('notice').textContent='Skill-check settings saved. Start the scene to apply them.';
  });};
  for(const [button,operation] of [['enable','enable'],['pause','pause'],['resume','resume'],['send','direction']])
    $('director-'+button).onclick=()=>action(async()=>{
      const id=selected;if(!id)throw Error('Select a live scene first.');
      data=await api('live-director',{id,operation,direction:operation==='direction'?$('director-direction').value:''});
      if(operation==='direction')$('director-direction').value='';
      $('notice').textContent='Director settings saved. NPC dialogue remains available.';
    });
  function listLimits(id, rows) {$(id).replaceChildren();for(const text of rows){const li=document.createElement('li');li.textContent=text;$(id).append(li);}}
  $('assistant-draft').onclick=()=>action(async()=>{
    const instruction=$('assistant-instruction').value.trim();if(!instruction)throw Error('Describe the scene you want first.');
    $('assistant-state').textContent='Preparing a proposal…';$('assistant-result').hidden=true;invalidate();
    try {
      const result=await api('live-assistant',{instruction,scene:'',allow_combat:$('assistant-combat').checked});
      const d=result.draft;
      if(![...$('profile').options].some(o=>o.value===d.profile))throw Error('The proposed profile is no longer available. Refresh and try again.');
      $('name').value=d.name;$('profile').value=d.profile;$('count').value=d.count;
      $('source').value='profile';$('blueprint-label').hidden=true;$('blueprint').required=false;
      $('facts').value=d.public_facts;$('goal').value=d.goal;$('boundaries').value=d.boundaries;
      $('activation').value=d.reaction.enabled?(d.reaction.combat_mode==='conversation'?'conversation':'proximity'):'manual';$('combat-conditions').value=d.reaction.combat_conditions||'';$('trigger-settings').hidden=!d.reaction.enabled;
      for(const [field,key] of Object.entries({radius:'trigger_radius',leave:'leave_radius',grace:'grace_seconds',pursuit:'pursuit_radius',hp:'retreat_hp_percent',warning:'warning',opening:'opening'}))$(field).value=d.reaction[key];
      $('attack').checked=d.reaction.attack;$('repeat').value=d.repeat?'yes':'no';
      $('assistant-summary').textContent=result.summary;listLimits('assistant-limits',result.limitations);
      $('assistant-result').hidden=false;$('setup').open=true;
      $('assistant-state').textContent='Proposal ready. Review the setup, mark locations, then preview and place.';
    } catch(e){$('assistant-state').textContent='Proposal not applied: '+e.message;throw e;}
  });
  let recommendation=null;
  $('assistant-review').onclick=()=>action(async()=>{
    const scene=selected;if(!scene)throw Error('Select a scene first.');
    recommendation=null;$('assistant-operation').hidden=true;$('assistant-review-text').textContent='Reviewing current scene…';
    try {
      const result=await api('live-assistant',{instruction:$('assistant-direction').value.trim()||'Summarize the current scene and suggest the next supported step.',scene,allow_combat:false});
      $('assistant-review-text').textContent=result.summary;listLimits('assistant-review-limits',result.limitations);
      if(result.operation!=='none'){recommendation={scene,operation:result.operation};$('assistant-operation').textContent='Review '+result.operation+' request';$('assistant-operation').hidden=false;}
    } catch(e){$('assistant-review-text').textContent='Review unavailable: '+e.message;throw e;}
  });
  $('assistant-operation').onclick=()=>{
    if(!recommendation||recommendation.scene!==selected){$('assistant-review-text').textContent='Select the reviewed scene or request a new review.';return;}
    const button=$(recommendation.operation);
    if(button.disabled){$('assistant-review-text').textContent='That operation is unavailable in the current scene state. Review again.';return;}
    button.click();
  };
  window.addEventListener('hashchange',()=>{if(location.hash==='#live-encounters')refresh();});
  setInterval(()=>{if(!document.hidden&&location.hash==='#live-encounters')refresh();},3000);
  refresh();
})();
