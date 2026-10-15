const state = {
  data: null,
  filter: 'all',
  query: '',
  read: new Set(JSON.parse(localStorage.getItem('ocs-read') || '[]')),
  deleted: new Set(JSON.parse(localStorage.getItem('ocs-deleted') || '[]')),
  keywordConfig: null,
  repoKeywordConfig: null,
};

const labels = {
  core: 'Organic CO₂ electrosynthesis',
  mechanism: 'Electroanalysis & mechanism',
  optimization: 'Condition optimization',
};
const filterLabels = { all: '全部', core: '合成反应', mechanism: '机理 / 电分析', optimization: '条件优化', high: '高相关' };
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function safeUrl(v){try{const u=new URL(String(v||''),location.href);if(['http:','https:'].includes(u.protocol))return u.href}catch(_){}return '#'}
function persist(){localStorage.setItem('ocs-read',JSON.stringify([...state.read]));localStorage.setItem('ocs-deleted',JSON.stringify([...state.deleted]));}

const KW_KEY='ocs-keywords-v2';
function clone(v){return JSON.parse(JSON.stringify(v));}
function normalizeKeywords(raw){
  const out={version:2,updated_at:new Date().toISOString().slice(0,10),topics:{}};
  for(const topic of ['core','mechanism','optimization']){
    const src=raw?.topics?.[topic]||{}; const seen=new Set();
    out.topics[topic]={label:src.label||labels[topic],keywords:(Array.isArray(src.keywords)?src.keywords:[]).map(x=>String(x||'').trim()).filter(x=>x&&!seen.has(x.toLowerCase())&&seen.add(x.toLowerCase()))};
  }
  return out;
}
async function loadKeywords(){
  let repo;
  try{const r=await fetch(`data/keywords.json?v=${Date.now()}`,{cache:'no-store'}); repo=normalizeKeywords(await r.json());}catch(_){repo=normalizeKeywords({});}
  state.repoKeywordConfig=repo;
  try{const local=JSON.parse(localStorage.getItem(KW_KEY)||'null');state.keywordConfig=local?normalizeKeywords(local):clone(repo);}catch(_){state.keywordConfig=clone(repo);}
}
function persistKeywords(){state.keywordConfig.updated_at=new Date().toISOString().slice(0,10);localStorage.setItem(KW_KEY,JSON.stringify(state.keywordConfig));}
function renderKeywords(){
  const holder=document.getElementById('keywordGroups'); if(!holder||!state.keywordConfig)return;
  holder.innerHTML=Object.entries(state.keywordConfig.topics).map(([topic,g])=>`<div class="keyword-group"><div class="keyword-group-head"><b>${esc(g.label)}</b><span>${g.keywords.length}</span></div><div class="keyword-chips">${g.keywords.map(k=>`<span class="keyword-chip" data-topic="${esc(topic)}" data-keyword="${esc(k)}"><button class="keyword-search">${esc(k)}</button><button class="keyword-remove" title="删除">×</button></span>`).join('')||'<span class="keyword-empty">暂无关键词</span>'}</div></div>`).join('');
  document.getElementById('keywordCount').textContent=Object.values(state.keywordConfig.topics).reduce((n,g)=>n+g.keywords.length,0);
  holder.querySelectorAll('.keyword-search').forEach(b=>b.onclick=()=>{state.query=b.parentElement.dataset.keyword||'';document.getElementById('searchInput').value=state.query;render();document.getElementById('today').scrollIntoView({behavior:'smooth'});});
  holder.querySelectorAll('.keyword-remove').forEach(b=>b.onclick=()=>{const chip=b.closest('.keyword-chip'),t=chip.dataset.topic,k=chip.dataset.keyword;state.keywordConfig.topics[t].keywords=state.keywordConfig.topics[t].keywords.filter(x=>x.toLowerCase()!==k.toLowerCase());persistKeywords();renderKeywords();});
}
function addKeyword(){const input=document.getElementById('keywordInput'),topic=document.getElementById('keywordTopic').value,k=String(input.value||'').trim().replace(/\s+/g,' ');if(!k)return;const list=state.keywordConfig.topics[topic].keywords;if(!list.some(x=>x.toLowerCase()===k.toLowerCase())){list.push(k);persistKeywords();renderKeywords();}input.value='';}
function exportKeywords(){const blob=new Blob([JSON.stringify(state.keywordConfig,null,2)+'\n'],{type:'application/json'});const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download='keywords.json';a.click();URL.revokeObjectURL(u);}
function resetKeywords(){state.keywordConfig=clone(state.repoKeywordConfig);localStorage.removeItem(KW_KEY);renderKeywords();}

function abstractBlock(p){
  const abstract=p.abstract||'OpenAlex 没有提供摘要。';
  return `<div class="abstract-block"><b>Abstract</b><p class="abstract-text">${esc(abstract)}</p></div>`;
}
function detailBlock(p){return `<div class="detail-grid"><div><b>研究方法（从摘要提取）</b><p>${esc(p.methods_summary||'—')}</p></div><div><b>重点结论（从摘要提取）</b><p>${esc(p.key_findings||'—')}</p></div></div>`;}
function card(p,i){
  const read=state.read.has(p.id),url=safeUrl(p.url),ifText=p.impact_factor?`IF ${esc(p.impact_factor)}`:'IF —';
  return `<article class="paper ${read?'read':''}" data-id="${esc(p.id)}">
    <div class="paper-index">${String(i+1).padStart(2,'0')}</div>
    <div class="paper-body">
      <div class="paper-meta"><span class="topic-pill">${esc(labels[p.topic]||p.topic)}</span><span>${esc(p.publication_date||p.year||'')}</span></div>
      <h3><a href="${esc(url)}" target="_blank" rel="noopener">${esc(p.title)} ↗</a></h3>
      <div class="journal-line"><strong>${esc(p.journal||'Unknown journal')}</strong><span>${esc(p.year||'—')}</span><span>${ifText}</span>${p.quartile?`<span>${esc(p.quartile)}</span>`:''}</div>
      ${abstractBlock(p)}
      <div class="paper-details">${detailBlock(p)}</div>
      <div class="tags">${(p.tags||[]).map(x=>`<span>${esc(x)}</span>`).join('')}</div>
      <div class="actions"><button class="text-btn detail-btn">展开方法与结论</button><a class="text-btn" href="${esc(url)}" target="_blank" rel="noopener">打开原文</a><button class="text-btn read-btn">${read?'标记未读':'✓ 标记已读'}</button><button class="text-btn delete-btn">删除</button></div>
    </div>
    <div class="score"><strong>${esc(p.score??0)}</strong><span>相关度</span></div>
  </article>`;
}
function filtered(papers){return papers.filter(p=>!state.deleted.has(p.id)).filter(p=>state.filter==='all'||state.filter==='high'&&Number(p.score||0)>=88||p.topic===state.filter).filter(p=>{if(!state.query)return true;const q=state.query.toLowerCase();return [p.title,p.abstract,p.methods_summary,p.key_findings,p.journal,...(p.tags||[])].join(' ').toLowerCase().includes(q);});}
function render(){
  const current=filtered(state.data.papers.filter(p=>!p.archive));
  const archive=filtered(state.data.papers.filter(p=>p.archive));
  document.getElementById('paperList').innerHTML=current.map(card).join('')||'<div class="empty">本轮没有找到足够相关且未推送过的文献。系统不会用催化剂设计类文章凑数。</div>';
  document.getElementById('archiveList').innerHTML=archive.map(card).join('')||'<div class="empty">暂无历史记录。</div>';
  document.getElementById('archiveCount').textContent=state.data.papers.filter(p=>p.archive&&!state.deleted.has(p.id)).length;
  document.getElementById('readCount').textContent=state.data.papers.filter(p=>p.archive&&state.read.has(p.id)&&!state.deleted.has(p.id)).length;
  bindCards();
}
function bindCards(){document.querySelectorAll('.paper').forEach(el=>{const id=el.dataset.id;el.querySelector('.detail-btn').onclick=()=>{el.classList.toggle('expanded');el.querySelector('.detail-btn').textContent=el.classList.contains('expanded')?'收起方法与结论':'展开方法与结论';};el.querySelector('.read-btn').onclick=()=>{state.read.has(id)?state.read.delete(id):state.read.add(id);persist();render();};el.querySelector('.delete-btn').onclick=()=>{state.deleted.add(id);persist();render();};});}

async function init(){
  await loadKeywords(); renderKeywords();
  const r=await fetch(`data/papers.json?v=${Date.now()}`,{cache:'no-store'}); if(!r.ok)throw new Error(`papers.json HTTP ${r.status}`); state.data=await r.json();
  const today=state.data.papers.filter(p=>!p.archive);
  document.getElementById('briefDate').textContent=`${state.data.brief_date||''} 研究简报`;
  document.getElementById('statToday').textContent=today.length;
  document.getElementById('statMechanism').textContent=today.filter(p=>p.topic==='mechanism').length;
  document.getElementById('statOptimization').textContent=today.filter(p=>p.topic==='optimization').length;
  const match=Math.max(0,Math.min(100,Number(state.data.match_score)||0));document.getElementById('matchScore').textContent=`${match}%`;document.querySelector('.meter span').style.width=`${match}%`;
  document.getElementById('lastUpdated').textContent=`最后更新 ${state.data.last_updated||'—'}`;
  const filters=['all','core','mechanism','optimization','high'];document.getElementById('filters').innerHTML=filters.map(k=>`<button class="filter ${k==='all'?'active':''}" data-filter="${k}">${filterLabels[k]}</button>`).join('');
  document.querySelectorAll('.filter').forEach(b=>b.onclick=()=>{state.filter=b.dataset.filter;document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));b.classList.add('active');render();});
  document.getElementById('searchInput').oninput=e=>{state.query=e.target.value.trim();render();};
  document.getElementById('addKeyword').onclick=addKeyword; document.getElementById('keywordInput').onkeydown=e=>{if(e.key==='Enter')addKeyword();};
  document.getElementById('exportKeywords').onclick=exportKeywords;document.getElementById('resetKeywords').onclick=resetKeywords;
  render();
}
init().catch(err=>{console.error(err);document.getElementById('paperList').innerHTML=`<div class="empty">页面数据加载失败：${esc(err.message)}</div>`;});
