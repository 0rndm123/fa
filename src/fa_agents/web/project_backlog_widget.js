/* Read-only project progress: explicit requests and real Git commits.
 * Loaded only when the user opens the Backlog tab; no global polling.
 */
(function () {
  'use strict';
  const STATUS = {todo:'To do',doing:'In progress',blocked:'Blocked',done:'Done'};
  const fmt = input => {
    if (!input) return '—';
    const d = new Date(input);
    if (Number.isNaN(d.getTime())) return '—';
    const p = v => String(v).padStart(2, '0');
    return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+
      ' '+p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());
  };
  function node(tag, cls='', value) {
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(value!==undefined)n.textContent=String(value);
    return n;
  }
  function mount(container, options={}) {
    if(!container)throw new Error('Backlog container missing');
    const pt=String(options.locale||'').toLowerCase().startsWith('pt');
    const tr=(en,ptPT)=>pt?ptPT:en;
    const statusLabel=status=>pt?({todo:'Por fazer',doing:'Em curso',blocked:'Bloqueado',done:'Concluído'}[status]||status):(STATUS[status]||status);
    let active='pending',data=null,loading=false;
    container.classList.add('project-backlog');
    container.replaceChildren();
    const head=node('div','pb-head'),title=node('div','pb-heading');
    title.append(node('h2','', tr('Project backlog','Backlog do projeto')));
    title.append(node('p','pb-help',tr('Requested work is tracked separately from committed changes. A commit does not prove deployment, testing or approval.','Os pedidos estão separados das alterações com commit. Um commit não comprova instalação, teste ou aprovação.')));
    const refresh=node('button','pb-refresh',tr('Refresh','Atualizar'));
    refresh.type='button';
    head.append(title,refresh);
    const tabs=node('nav','pb-tabs');
    tabs.setAttribute('aria-label','Backlog views');
    const counters=node('div','pb-counters');
    const content=node('div','pb-content');
    content.setAttribute('role','status');
    container.append(head,counters,tabs,content);
    const filters=[
      ['pending',tr('Pending','Pendentes')],['doing',tr('In progress','Em curso')],['blocked',tr('Blocked','Bloqueados')],
      ['done',tr('Done','Concluídos')],['commits',tr('Recent commits','Últimos commits')]
    ];
    function render() {
      tabs.replaceChildren();
      const items=Array.isArray(data?.items)?data.items:[];
      const commits=Array.isArray(data?.commits)?data.commits:[];
      const pending=items.filter(x=>x.status!=='done');
      const counts={pending:pending.length,doing:items.filter(x=>x.status==='doing').length,
        blocked:items.filter(x=>x.status==='blocked').length,
        done:items.filter(x=>x.status==='done').length,commits:commits.length};
      counters.replaceChildren(
        node('span','pb-summary',tr('Open ','Pendentes ')+pending.length),
        node('span','pb-summary',tr('Committed ','Commits ')+commits.length)
      );
      filters.forEach(([key,label])=>{
        const b=node('button','pb-tab'+(active===key?' active':''),label+' · '+counts[key]);
        b.type='button';b.setAttribute('aria-pressed',String(active===key));
        b.onclick=()=>{active=key;render()};
        tabs.append(b);
      });
      content.replaceChildren();
      if(!data){content.append(node('p','pb-muted',tr('Select Refresh to load the project history.','Selecione Atualizar para consultar o histórico do projeto.')));return}
      const view=active==='pending'?pending:active==='commits'?commits:items.filter(x=>x.status===active);
      const warning=data.warnings||[];
      if(warning.length){
        const n=node('p','pb-warning',warning.join(' · '));content.append(n);
      }
      if(!view.length){
        content.append(node('p','pb-empty',active==='commits'
          ?tr('No Git commits are accessible from this checkout.','Não está disponível histórico Git neste repositório.')
          :tr('No registered items in this view. This does not prove that no requests exist.','Não existem itens registados nesta vista. Isso não prova que não existam pedidos.')));
        return;
      }
      const list=node('div','pb-list');
      view.forEach(item=>{
        const card=node('article','pb-item');
        const top=node('div','pb-item-head');
        const name=node('strong','pb-item-title',active==='commits'?item.title:item.title);
        top.append(name);
        if(active==='commits'){
          top.append(node('code','pb-sha',String(item.sha||'').slice(0,8)));
          const date=node('time','pb-date',fmt(item.timestamp));top.append(date);
          const linkBase=options.repositoryUrl;
          if(/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+$/.test(linkBase||'')&&item.sha){
            const a=node('a','pb-commit-link',tr('View commit ↗','Ver commit ↗'));
            a.href=linkBase+'/commit/'+encodeURIComponent(item.sha);
            a.target='_blank';a.rel='noopener noreferrer';top.append(a);
          }
        } else {
          top.append(node('span','pb-status pb-'+item.status,statusLabel(item.status)));
          if(item.priority)top.append(node('span','pb-priority',item.priority));
          if(item.id)top.append(node('code','pb-id',item.id));
        }
        card.append(top);
        if(active!=='commits'){
          if(item.description)card.append(node('p','pb-description',item.description));
          const meta=node('div','pb-meta');
          if(item.updated_at)meta.append(node('span','',fmt(item.updated_at)));
          if(item.source)meta.append(node('span','', tr('Source: ','Origem: ')+item.source));
          if(item.evidence)meta.title=item.evidence;
          card.append(meta);
        }
        list.append(card);
      });
      content.append(list);
    }
    async function load() {
      if(loading)return;
      loading=true;refresh.disabled=true;content.replaceChildren(node('p','pb-muted',tr('Loading project history…','A carregar histórico do projeto…')));
      try {
        const more=typeof options.fetchOptions==='function'?await options.fetchOptions():{};
        const response=await fetch(options.endpoint,{cache:'no-store',credentials:'same-origin',...more});
        if(!response.ok)throw Error('HTTP '+response.status);
        const body=await response.json();
        if(!body||!Array.isArray(body.items)||!Array.isArray(body.commits))throw Error('Invalid backlog response');
        data=body;render();
      }catch(err){
        content.replaceChildren(node('p','pb-error',tr('Backlog unavailable: ','Backlog indisponível: ')+(err?.message||String(err))));
      }finally{loading=false;refresh.disabled=false}
    }
    refresh.onclick=load;
    render();
    void load();
    return {refresh:load};
  }
  window.ProjectBacklog={mount};
})();
