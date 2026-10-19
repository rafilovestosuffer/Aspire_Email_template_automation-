const SAMPLE = `<!doctype html>
<html><body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:24px">
  <table width="560" style="margin:auto;background:#fff;border:1px solid #ddd">
    <tr><td style="background:#1a73e8;color:#fff;padding:18px 24px;font-size:18px;font-weight:bold">{{brand_name}}</td></tr>
    <tr><td style="padding:24px">
      <p>Hello {{first_name}},</p>
      <p>We detected a new sign-in to your {{brand_name}} account. If this was not you,
         please verify your account to keep it secure.</p>
      <p style="text-align:center;margin:28px 0">
        <a href="{{phishing_link}}" style="background:#1a73e8;color:#fff;padding:12px 26px;
           text-decoration:none;border-radius:4px">Verify account</a></p>
      <p style="color:#777;font-size:12px">If you did not request this, you can ignore this email.</p>
    </td></tr>
  </table>
</body></html>`;
const $ = s=>document.querySelector(s);
const esc = s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let variants=[],events=[],langs=[],selected=new Set(),view='sources',page=0,openId=null,raw=false,busy=false,translating=false,stop=false,libOffset=0,libTotal=0,cmpSel=null,lastSourceId=null,lastSourceHtml='';
const pageSize=8;
const ARCH={plain_memo:'Plain memo',branded_notice:'Branded notice',modern_card:'Modern card',corporate:'Corporate'};
const varMode=()=>document.querySelector('input[name=varmode]:checked')?.value||'wording';
let hasEngine=true;
const title=v=>v.title || `Source ${v.id.slice(0,8)}`;
const translations=()=>variants.flatMap(v=>(v.locales||[]).map(r=>({...r,source:v})));
const groupKey=v=>v.group_id||v.id;                 // a source and its wording variants share one key
const groupOf=item=>variants.filter(v=>groupKey(v)===groupKey(item));
const scope=()=>variants.filter(v=>selected.has(v.id));
const targets=()=>scope().filter(v=>v.status==='approved');
const languages=()=>[...document.querySelectorAll('#langs input:checked')].map(c=>c.value);
const exportable=()=>translations().filter(r=>selected.has(r.source.id)&&r.source.status==='approved'&&r.status==='approved'&&r.mode==='openrouter');
function notice(message,type='info'){const n=$('#notice');n.hidden=false;n.textContent=message;n.className='notice '+type;}
async function api(url,body){
 const response=await fetch(url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
 if(!response.headers.get('content-type')?.includes('application/json'))throw Error(`Server unavailable (${response.status}). Retry or restart the console.`);
 const data=await response.json();
 if(!response.ok){if(response.status===404)throw Error('Item or feature unavailable. Refresh the workspace; restart the server if it persists.');throw Error(typeof data.detail==='string'?data.detail:'Check the input fields and try again.');}return data;
}
async function reload(){const data=await api('/api/workspace');variants=data.variants;selected=new Set([...selected].filter(id=>variants.some(v=>v.id===id)));render();}
function refreshButtons(){
 const n=languages().length,a=targets().length,count=exportable().length;
 $('#selcount').textContent=`${n} selected`;
 $('#scope').textContent=`${selected.size} selected sources · ${a} approved · ${a*n} language outputs requested. Existing successful translations are reused.`;
 $('#localize').disabled=busy||!a||!n;$('#localize').textContent=busy?'Processing…':`Translate ${a} source${a===1?'':'s'} into ${n} language${n===1?'':'s'}`;
 for(const id of ['genVar','saveSeed','refresh'])$('#'+id).disabled=busy;
 $('#export').disabled=busy||!count;$('#exportHint').textContent=`${count} approved translation${count===1?'':'s'} ready from selected sources.`;
 const approvedSources=variants.filter(v=>v.status==='approved').length;$('#publish').disabled=busy||!approvedSources;$('#publishHint').textContent=approvedSources?`${approvedSources} approved source${approvedSources===1?'':'s'} ready to publish (with their approved translations).`:'Approve at least one source to publish.';
 $('#selectionCount').textContent=`${selected.size} source${selected.size===1?'':'s'} selected`;
 $('#stop').hidden=!translating;document.querySelectorAll('[data-review]').forEach(b=>b.disabled=busy);
}
function filtered(){
 const q=$('#workspaceSearch').value.trim().toLowerCase(),status=$('#statusFilter').value;
 const items=view==='sources'?variants:translations();
 return items.filter(i=>{
  const text=[title(i.source||i),i.company||i.source?.company,i.name,i.id].join(' ').toLowerCase();
  return text.includes(q)&&(status==='all'||(status==='error'?['error','mock'].includes(i.mode):i.status===status));
 }).slice().reverse();
}
function frame(html,rtl){
 const doc=new DOMParser().parseFromString(html,'text/html');doc.documentElement.dir=rtl?'rtl':'ltr';
 doc.querySelectorAll('script,meta[http-equiv],base,iframe,object,embed').forEach(el=>el.remove());
 const policy=doc.createElement('meta');policy.httpEquiv='Content-Security-Policy';policy.content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'";doc.head.prepend(policy);
 return `<iframe title="${rtl?'Right-to-left':'Template'} preview" sandbox="" referrerpolicy="no-referrer" srcdoc="${esc(doc.documentElement.outerHTML)}"></iframe>`;
}
function card(i){
 const locale=!!i.source,source=i.source||i,isOpen=openId===i.id,failed=i.mode==='error',mock=i.mode==='mock';
 const label=locale?`${i.name} translation`:'Source · original language';
 const status=failed?'Failed':mock?'Mock — not approvable':({pending:'Needs review',approved:'Approved',rejected:'Rejected'}[i.status]);
 const canApprove=!failed&&!mock&&i.status!=='approved'&&(!locale||source.status==='approved');
 return `<article class="item" data-id="${i.id}"><div class="itemhead"><input type="checkbox" data-select="${source.id}" aria-label="Select ${esc(title(source))}" ${selected.has(source.id)?'checked':''}><div class="iteminfo"><div class="itemtitle">${esc(title(source))}${!locale&&i.mode!=='source'?` · ${i.kind==='redesign'?`Redesign ${i.index} · ${esc(ARCH[i.archetype]||i.archetype||'design')}`:`Variant ${i.index}`}${i.humanized?' · humanized':''}`:''}</div><div class="itemmeta">${esc(label)} · ${esc(source.company||'No company context')} · ${esc(i.id.slice(0,8))}</div></div><span class="badge ${failed||mock?'error':i.status}">${status}</span></div>
 ${failed?`<div class="errorbox">Translation/generation failed: ${esc(i.error||'Provider request failed')}. The source was preserved; this is not a translated result.</div>`:''}
 <div class="itemactions"><button class="secondary" data-open="${i.id}">${isOpen?'Close preview':locale?'Preview translation':'Preview source'}</button>${canApprove?`<button class="secondary" data-review="approved">Approve ${locale?'translation':'source'}</button>`:''}${i.status!=='rejected'?'<button class="textbutton" data-review="rejected">Reject</button>':''}${!locale?`<button class="textbutton" data-translations="${i.id}">Translations (${(i.locales||[]).length})</button>`:''}<span class="status itemmeta">${i.reviewed_by?'Reviewed by '+esc(i.reviewed_by):locale?'Independent language review required':i.status==='approved'?'Ready to translate':'Approve before translation'}</span></div>
 ${isOpen?(locale?localePreview(i):comparePanel(i)):''}</article>`;
}
// A translation card shows the main template it came from on the left, the translation on the right.
function localePreview(i){
 const base=i.source,bad=i.mode==='error';
 const lpane=raw?`<pre class="raw">${esc(base.html)}</pre>`:`<div class="preview">${frame(base.html,base.rtl)}</div>`;
 const rpane=bad?'<div class="comparenote">This translation attempt failed; no preview is available. The source is unchanged.</div>':raw?`<pre class="raw">${esc(i.html)}</pre>`:`<div class="preview">${frame(i.html,i.rtl)}</div>`;
 return `<div class="previewbody">
  <div class="previewlabel"><span>Main template vs. ${esc(i.name)} translation · source unchanged</span><span><button class="textbutton" data-raw>${raw?'Rendered':'HTML'}</button>${bad?'':' · <button class="textbutton" data-copy>Copy translation HTML</button>'}</span></div>
  <div class="compare"><div class="comparepane"><div class="previewlabel"><span>Main template · original</span></div>${lpane}</div><div class="comparepane"><div class="previewlabel"><span>${esc(i.name)} translation</span></div>${rpane}</div></div>`;
}
// Right-side compare & pick: main template on the left, a chosen variant or translation on the right.
function comparePanel(openItem){
 const group=groupOf(openItem);
 const srcMain=group.find(v=>v.mode==='source');          // a real saved original, if one exists
 const vars=group.filter(v=>v.mode!=='source');            // wording variants (disjoint from srcMain)
 const bases=srcMain?[srcMain,...vars]:vars;               // unique base drafts, no overlap
 const leftRef=srcMain||openItem;                          // left pane = saved original, else the opened draft
 const baseLabel=v=>v.mode==='source'?'Main':`${v.kind==='redesign'?'Redesign':'Variant'} ${v.index}${v.humanized?' · humanized':''}`;
 const rightOpts=[];                                       // what you can show on the right and pick
 bases.filter(v=>v.id!==leftRef.id).forEach(v=>rightOpts.push({id:v.id,item:v,rtl:v.rtl,kind:'base',label:`${baseLabel(v)} · original language`}));
 bases.forEach(v=>(v.locales||[]).forEach(r=>rightOpts.push({id:r.id,item:{...r,source:v},rtl:r.rtl,kind:'translation',label:`${baseLabel(v)} · ${r.name} translation`})));
 if(rightOpts.length&&!rightOpts.some(o=>o.id===cmpSel))cmpSel=(rightOpts.find(o=>o.kind==='translation')||rightOpts[0]).id;
 const sel=rightOpts.find(o=>o.id===cmpSel);
 const pane=(it,rtl,lbl,human)=>{
  const bad=it&&it.mode==='error';
  const body=!it?'<div class="comparenote">Create wording variants, or translate this draft in step 02, to compare and pick here.</div>':bad?'<div class="comparenote">This attempt failed; no preview is available.</div>':raw?`<pre class="raw">${esc(it.html)}</pre>`:`<div class="preview">${frame(it.html,rtl)}</div>`;
  return `<div class="comparepane"><div class="previewlabel"><span>${esc(lbl)}</span>${human?'<span class="badge approved">human voice</span>':''}</div>${body}</div>`;
 };
 const leftLbl=leftRef.mode==='source'?'Main template · original':'This draft · original language';
 const bar=rightOpts.length?`<div class="comparebar"><label for="cmp-${openItem.id}">Right panel</label><select id="cmp-${openItem.id}" data-cmp aria-label="Choose what to compare and pick">${rightOpts.map(o=>`<option value="${o.id}"${o.id===cmpSel?' selected':''}>${esc(o.label)}</option>`).join('')}</select><button class="secondary" data-usepick="${cmpSel}">Use this version</button><button class="textbutton" data-copyitem="${cmpSel}">Copy right HTML</button></div>`:'<p class="help">Create wording variants, or translate this draft in step 02, to compare versions side by side and pick one.</p>';
 return `<div class="previewbody">
  <div class="previewlabel"><span>Compare &amp; pick — main vs. a variant or translation</span><span><button class="textbutton" data-raw>${raw?'Rendered':'HTML'}</button></span></div>
  ${bar}
  <div class="compare">${pane(leftRef,leftRef.rtl,leftLbl,leftRef.humanized)}${pane(sel&&sel.item,sel&&sel.rtl,sel?sel.label:'Nothing selected yet',sel&&sel.item&&sel.item.humanized)}</div></div>`;
}
function render(){
 const all=translations(),good=all.filter(r=>r.status==='approved'&&r.mode==='openrouter'&&r.source.status==='approved');
 $('#metrics').innerHTML=[[variants.length,'Source drafts'],[all.length,'Translation attempts'],[all.filter(r=>r.status==='pending'&&r.mode==='openrouter').length,'Translations to review'],[good.length,'Approved translations']].map(([n,label])=>`<div class="metric"><strong>${n}</strong><span>${label}</span></div>`).join('');
 document.querySelectorAll('[data-tab]').forEach(b=>{b.setAttribute('aria-selected',b.dataset.tab===view);b.tabIndex=b.dataset.tab===view?0:-1;});
 $('#results').setAttribute('aria-labelledby',view+'Tab');
 $('.filters').hidden=view==='activity';$('.selection').hidden=view==='activity';$('.bottom').hidden=view==='activity';
 if(view==='activity'){
  $('#results').innerHTML=events.length?events.map(e=>`<div class="activityrow"><b>${esc(e.actor)}</b> · ${esc(e.action.replaceAll('_',' '))}<small>${esc(e.item_id.slice(0,8))} · ${esc(e.created_at)} UTC</small></div>`).join(''):'<div class="empty"><strong>No review activity yet</strong>Review decisions will appear here.</div>';
 }else{
  const items=filtered();page=Math.min(page,Math.max(0,Math.ceil(items.length/pageSize)-1));
  $('#results').innerHTML=items.slice(page*pageSize,(page+1)*pageSize).map(card).join('')||`<div class="empty"><strong>${view==='sources'?'No source drafts match':'No translations match'}</strong>${view==='sources'?'Load a template and save it for review, or clear your filters.':'Approve and select a source, choose languages, then translate. Clear filters to see other outputs.'}</div>`;
  $('#pageInfo').textContent=`${items.length} items · Page ${page+1} of ${Math.max(1,Math.ceil(items.length/pageSize))}`;
  $('#pagePrev').disabled=page===0;$('#pageNext').disabled=(page+1)*pageSize>=items.length;
  $('#selectPage').hidden=view!=='sources';
 }refreshButtons();
}
async function setView(next){view=next;page=0;openId=null;raw=false;if(view==='activity')events=(await api('/api/activity')).events;render();}
async function searchLibrary(reset=true){
 if(reset)libOffset=0;$('#searchLibrary').disabled=true;$('#loadLibrary').disabled=true;$('#libPrev').disabled=true;$('#libNext').disabled=true;$('#libraryMeta').textContent='Searching…';$('#librarySelect').replaceChildren();
 try{const d=await api(`/api/library?q=${encodeURIComponent($('#librarySearch').value.trim())}&offset=${libOffset}&limit=50`);libTotal=d.matched;
  $('#librarySelect').replaceChildren(...d.items.map(i=>{const o=document.createElement('option');o.value=i.id;o.textContent=i.name+(i.needs_recovery?' — needs recovery':'');o.disabled=i.needs_recovery;return o;}));
  const usable=d.items.find(i=>!i.needs_recovery);if(usable){$('#librarySelect').value=usable.id;$('#loadLibrary').disabled=false;}
  $('#libraryMeta').textContent=d.matched?`${libOffset+1}–${libOffset+d.items.length} of ${d.matched} matches`:'No matches. Try another name.';
  $('#libPrev').disabled=libOffset===0;$('#libNext').disabled=libOffset+50>=libTotal;
 }catch(e){$('#libraryMeta').textContent=e.message;}finally{$('#searchLibrary').disabled=false;}
}
async function createDraft(original){
 if(busy)return;if(!$('#tpl').value.trim()){notice('Paste or load source HTML first.','error');return;}
 const amount=Number($('#amount').value);if(!original&&(!Number.isInteger(amount)||amount<1||amount>8)){notice('Choose 1–8 versions.','error');return;}
 const redesign=!original&&varMode()==='redesign';
 busy=true;refreshButtons();notice(original?'Saving source…':redesign?'Creating redesigns (new aligned layouts)…':'Creating wording variants in the source language…');
 const tpl=$('#tpl').value;
 const body={template_html:tpl,company_name:$('#company').value.trim(),title:$('#title').value.trim(),amount:original?1:amount};
 if(!original){body.humanize=$('#humanize').checked;if(lastSourceId&&tpl===lastSourceHtml)body.source_id=lastSourceId;}
 try{const d=await api(original?'/api/seeds':redesign?'/api/redesign':'/api/variants',body);
 if(original){lastSourceId=d.id;lastSourceHtml=tpl;}
 const added=original?[d]:d.variants;selected=new Set(added.map(i=>i.id));view='sources';page=0;$('#workspaceSearch').value='';$('#statusFilter').value='all';await reload();
 const failures=added.filter(i=>i.mode==='error').length,humanized=original?0:added.filter(i=>i.humanized).length,word=redesign?'redesign':'variant';
 notice(failures?`${failures} ${word} attempt${failures===1?'':'s'} failed. Review the error details; failed outputs cannot be approved.`:original?'Saved. Preview and approve the source, then translate it into your selected languages.':`Created ${added.length} ${word}${added.length===1?'':'s'}${humanized?` · ${humanized} humanized`:''}. Open one to compare against the main and pick.`,failures?'error':'success');
 }catch(e){notice(e.message,'error');}finally{busy=false;refreshButtons();}
}
async function localize(){
 if(busy)return;const todo=targets(),codes=languages();if(!todo.length||!codes.length)return;
 busy=true;translating=true;stop=false;refreshButtons();let completed=0,failed=0,mock=0;const total=todo.length*codes.length;$('#progress').hidden=false;$('#progress').max=total;$('#progress').value=0;
 try{outer:for(const source of todo){for(const code of codes){if(stop)break outer;notice(`Translating ${title(source)} → ${langs.find(l=>l.code===code).name} (${completed+1}/${total})…`);
 const d=await api('/api/generate',{variant_id:source.id,languages:[code]});failed+=d.results.filter(r=>r.mode==='error').length;mock+=d.results.filter(r=>r.mode==='mock').length;completed++;$('#progress').value=completed;await reload();}}
 view='translations';page=0;$('#statusFilter').value='all';$('#workspaceSearch').value='';await reload();notice(`${stop?'Stopped. ':''}${completed-failed-mock} successful/reused · ${failed} failed · ${mock} mock · ${total-completed} not processed. Review translations before export.`,failed||mock?'error':'success');
 }catch(e){notice(e.message+' Completed outputs remain saved. Retry to continue.','error');}
 finally{busy=false;translating=false;refreshButtons();}
}
$('#results').addEventListener('change',e=>{if(e.target.hasAttribute('data-cmp')){cmpSel=e.target.value;render();return;}const id=e.target.dataset.select;if(!id)return;e.target.checked?selected.add(id):selected.delete(id);render();});
$('#results').addEventListener('click',async e=>{
 const b=e.target.closest('button');if(!b)return;const id=b.closest('[data-id]')?.dataset.id;
 try{
 if(b.dataset.open){openId=openId===id?null:id;raw=false;cmpSel=null;render();}
 else if(b.hasAttribute('data-raw')){raw=!raw;render();}
 else if(b.hasAttribute('data-copy')){const i=[...variants,...translations()].find(i=>i.id===id);await navigator.clipboard.writeText(i.html);notice('HTML copied.','success');}
 else if(b.dataset.copyitem){const it=[...variants,...translations()].find(x=>x.id===b.dataset.copyitem);if(it){await navigator.clipboard.writeText(it.html);notice('HTML copied.','success');}}
 else if(b.dataset.usepick){const pid=b.dataset.usepick,top=variants.find(v=>v.id===pid);if(top){selected.add(top.id);notice(`Picked ${top.mode==='source'?'the main template':'Variant '+top.index}. It is selected for translate/export.`,'success');}else{const tr=translations().find(r=>r.id===pid);if(tr){selected.add(tr.source.id);notice(`Picked the ${tr.name} translation of ${title(tr.source)}. Its source is selected for export.`,'success');}}render();}
 else if(b.dataset.translations){$('#workspaceSearch').value=title(variants.find(v=>v.id===id));$('#statusFilter').value='all';await setView('translations');}
 else if(b.dataset.review){if(busy)return;const actor=$('#reviewer').value.trim();if(!actor){notice('Enter your reviewer name in step 03.','error');$('#reviewer').focus();return;}busy=true;refreshButtons();try{await api(`/api/items/${id}/review`,{status:b.dataset.review,actor});await reload();notice('Review decision saved.','success');}finally{busy=false;refreshButtons();}}
 }catch(err){notice(err.message,'error');}
});
$('.tabs').addEventListener('click',e=>{if(e.target.dataset.tab)setView(e.target.dataset.tab).catch(e=>notice(e.message,'error'));});
$('.tabs').addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const tabs=['sources','translations','activity'];const next=tabs[(tabs.indexOf(view)+(e.key==='ArrowRight'?1:2))%3];setView(next).then(()=>$('#'+next+'Tab').focus()).catch(e=>notice(e.message,'error'));});
for(const id of ['workspaceSearch','statusFilter'])$('#'+id).addEventListener(id==='workspaceSearch'?'input':'change',()=>{page=0;render();});
$('#pagePrev').onclick=()=>{page--;openId=null;render();};$('#pageNext').onclick=()=>{page++;openId=null;render();};
$('#selectPage').onclick=()=>{filtered().slice(page*pageSize,(page+1)*pageSize).forEach(i=>selected.add(i.id));render();};$('#clearSelection').onclick=()=>{selected.clear();render();};
$('#searchLibrary').onclick=()=>searchLibrary();$('#librarySearch').onkeydown=e=>{if(e.key==='Enter'&&!$('#searchLibrary').disabled)searchLibrary();};
$('#libPrev').onclick=()=>{libOffset=Math.max(0,libOffset-50);searchLibrary(false);};$('#libNext').onclick=()=>{libOffset+=50;searchLibrary(false);};
$('#loadLibrary').onclick=async()=>{try{const i=await api('/api/library/'+$('#librarySelect').value);$('#tpl').value=i.html;$('#title').value=i.name;notice(`Loaded ${i.name}. This workspace currently localizes the body; the email subject is not included.`);}catch(e){notice(e.message,'error');}};
$('#saveSeed').onclick=()=>createDraft(true);$('#genVar').onclick=()=>createDraft(false);$('#localize').onclick=localize;$('#stop').onclick=()=>{stop=true;notice('Stopping after the current request finishes. Completed work stays saved.');};
$('#refresh').onclick=()=>reload().then(()=>notice('Workspace refreshed.','success')).catch(e=>notice(e.message,'error'));
$('#langs').onchange=refreshButtons;
function updateRedesignNote(){const r=varMode()==='redesign';const n=$('#redesignNote');if(!n)return;n.hidden=!r;if(r)n.textContent=hasEngine?'Each version uses a different curated design + palette. Placeholders stay intact and nothing is sent.':'Redesign needs the local MJML engine, which is not installed. Run: python -m pip install mjml-python';}
document.querySelectorAll('input[name=varmode]').forEach(el=>el.addEventListener('change',updateRedesignNote));
$('#languageSearch').oninput=()=>{const q=$('#languageSearch').value.toLowerCase();document.querySelectorAll('#langs label').forEach(l=>l.hidden=!l.textContent.toLowerCase().includes(q));};
$('.langbar').onclick=e=>{if(!e.target.dataset.sel)return;document.querySelectorAll('#langs input').forEach(c=>c.checked=e.target.dataset.sel==='all');refreshButtons();};
$('#export').onclick=async()=>{try{const q=new URLSearchParams();selected.forEach(id=>q.append('source_ids',id));const data=await api('/api/export?'+q);if(!data.items.length){notice('No approved translations in this selection.');return;}const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='asat-approved-translations.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice(`Exported ${data.items.length} approved translations. This JSON is a review handoff, not a database publish.`,'success');}catch(e){notice(e.message,'error');}};
$('#publish').onclick=async()=>{try{const d=await api('/api/publish',{dry_run:true});if(!d.templates){notice('No approved content to publish yet. Approve a source first.');return;}$('#confirmPublish').hidden=false;notice(`Dry run: would publish ${d.templates} template${d.templates===1?'':'s'} and ${d.translations} translation${d.translations===1?'':'s'} (sendable=false). ${d.has_db?'Press Confirm to write to the database.':'No database connected yet — set DATABASE_URL and restart; Confirm will stay a dry run.'}`,d.has_db?'info':'error');}catch(e){notice(e.message,'error');}};
$('#confirmPublish').onclick=async()=>{try{const d=await api('/api/publish',{dry_run:false});$('#confirmPublish').hidden=true;if(d.dry_run){notice('No database connected (DATABASE_URL unset). Nothing written — set DATABASE_URL and restart, then publish again.','error');return;}notice(`Published ${d.written.templates} template${d.written.templates===1?'':'s'}, ${d.written.versions} version${d.written.versions===1?'':'s'} and ${d.written.translations} translation${d.written.translations===1?'':'s'} to the database (sendable=false).`,'success');await reload();}catch(e){notice(e.message,'error');}};
window.addEventListener('beforeunload',e=>{if(busy){e.preventDefault();e.returnValue='';}});
async function init(){
 $('#tpl').value=SAMPLE;
 const health=await api('/api/health');$('#keychip').textContent=health.has_key?'AI configured':'Mock mode';$('#keychip').className='badge '+(health.has_key?'live':'pending');hasEngine=health.has_engine!==false;updateRedesignNote();
 langs=await api('/api/languages');$('#langs').innerHTML=langs.map(l=>`<label><input type="checkbox" value="${l.code}">${esc(l.name)}${l.rtl?' ↔':''}</label>`).join('');
 await Promise.all([reload(),searchLibrary()]);
}
init().catch(e=>notice(e.message,'error'));
