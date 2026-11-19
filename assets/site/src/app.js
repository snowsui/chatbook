'use strict';
(() => {
  const CATS = {'人生节点':['k-life','var(--zhu)'],'聚会出行':['k-meet','var(--song)'],'群内热议':['k-talk','var(--dai)'],'名场面':['k-meme','var(--huang)']};
  const $ = selector => document.querySelector(selector);
  const el = (tag, cls, text) => { const node=document.createElement(tag); if(cls)node.className=cls; if(text!=null)node.textContent=text; return node; };
  const monthName = value => ['', '一','二','三','四','五','六','七','八','九','十','十一','十二'][Number(value)]+'月';
  const state = {big:false,cat:'',who:'',from:''};
  const list=$('#list'), status=$('#page-status');
  const cache=new Map();
  let index, revision=0, pendingJump=false, matching=[], cursor=0, loading=false, lastYear='', fontScheduled=false;
  let drawerRevision=0, drawerTrigger=null, current='', pendingCard='';
  const moreObserver=new IntersectionObserver(entries=>{
    if(entries.some(entry=>entry.isIntersecting)&&index&&!loading&&cursor<matching.length)loadMore(revision);
  },{rootMargin:'500px 0px'});
  addEventListener('scroll',()=>{if(matching.length&&list.getBoundingClientRect().top>innerHeight*.35)setNow(matching[0].month);},{passive:true});
  const monthObserver=new IntersectionObserver(entries=>{
    const visible=entries.filter(entry=>entry.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top);
    if(visible.length)setNow(visible[0].target.parentNode.id.slice(2));
  },{rootMargin:'-70px 0px -65% 0px'});

  async function getJSON(url){
    if(!cache.has(url)){
      const request=fetch(url,{credentials:'same-origin'}).then(async response=>{
        if(response.status===401){const error=new Error('登录已过期，请重新登录。');error.auth=true;throw error;}
        if(!response.ok)throw new Error('暂时没能载入，请重试。');
        if(!response.headers.get('content-type')?.includes('application/json'))throw new Error('连接暂时中断，请刷新页面重试。');
        return response.json();
      }).catch(error=>{
        cache.delete(url);
        if(error instanceof TypeError)throw new Error('网络连接中断，请检查网络后重试。');
        if(error instanceof SyntaxError)throw new Error('内容暂时无法读取，请稍后重试。');
        throw error;
      });
      cache.set(url,request);
    }
    return cache.get(url);
  }
  function showStatus(message, action, label='重试'){
    status.replaceChildren();status.hidden=false;
    if(message)status.append(el('p',null,message));
    if(action){const button=el('button',null,label);button.type='button';button.onclick=action;status.append(button);}
  }
  function showError(error,retry){
    showStatus(error.message,error.auth?()=>location.assign('/'):retry,error.auth?'重新登录':'重试');
  }
  const countKey=()=>JSON.stringify([state.cat,state.big?1:0,state.who]);
  const countFor=month=>month.counts[countKey()]||0;
  const eventMatches=event=>(!state.big||event.heat===3)&&(!state.cat||event.category===state.cat)&&(!state.who||event.people.includes(state.who));

  function renderBar(){
    const bar=$('#bar');bar.replaceChildren();
    const major=el('button','big'+(state.big?' on':''),'只看大事');major.setAttribute('aria-pressed',String(state.big));
    major.onclick=()=>{state.big=!state.big;render();};bar.append(major,el('span','vr'));
    for(const category of ['',...Object.keys(CATS)]){
      const button=el('button','tg'+(state.cat===category?' on':''));button.setAttribute('aria-pressed',String(state.cat===category));
      if(category){button.style.setProperty('--c',CATS[category][1]);button.append(el('i'));}
      button.append(category||'全部');button.onclick=()=>{state.cat=state.cat===category?'':category;render();};bar.append(button);
    }
    bar.append(el('span','vr'));
    function select(label,value,options,onchange){
      const node=el('select','who');node.setAttribute('aria-label',label);
      options.forEach(([text,key])=>node.append(new Option(text,key)));node.value=value;
      node.onchange=()=>onchange(node.value);bar.append(node);
    }
    select('人物',state.who,[['所有人',''],...Object.entries(index.people).sort((a,b)=>b[1]-a[1]).map(([person,count])=>[person+' · '+count,person])],value=>{state.who=value;render();});
  }
  function setNow(month){
    if(month===current)return;current=month;
    const now=$('#now');now.firstChild.textContent=month.slice(0,4);now.children[1].textContent=monthName(month.slice(5));
  }
  // 跳到某个月：从那个月往后接着翻，不是只看那一个月
  function jumpToMonth(month){
    closePanel();
    const target=index.months.find(item=>item.month===month);
    if(target&&!countFor(target)){state.big=false;state.cat='';state.who='';}
    state.from=month===index.months[0].month?'':month;render(true);
  }
  function renderPanel(){
    const panel=$('#tpanel'),top=el('div','tp-top','跳到哪个月？');panel.replaceChildren(top);
    const head=el('button',null,'从头看');head.type='button';head.onclick=()=>jumpToMonth(index.months[0].month);top.append(head);
    const byYear=new Map();index.months.forEach(month=>{const year=month.month.slice(0,4);if(!byYear.has(year))byYear.set(year,[]);byYear.get(year).push(month);});
    for(const [year,months] of byYear){
      const row=el('div','tp-y'),label=el('button','tp-yr',year),grid=el('div','tp-ms');label.type='button';label.onclick=()=>jumpToMonth(months[0].month);
      for(let m=1;m<=12;m++){
        const month=months.find(item=>Number(item.month.slice(5))===m);
        if(!month){grid.append(el('span'));continue;}
        const button=el('button',(countFor(month)?'':'dim')+(month.month===current?' cur':''),monthName(m).slice(0,-1));button.type='button';
        button.setAttribute('aria-label',year+'年'+monthName(m));button.onclick=()=>jumpToMonth(month.month);grid.append(button);
      }
      row.append(label,grid);panel.append(row);
    }
  }
  function openPanel(){renderPanel();$('#tpanel').hidden=false;$('#now').setAttribute('aria-expanded','true');$('#tpanel').querySelector('.cur')?.scrollIntoView({block:'center'});}
  function closePanel(){$('#tpanel').hidden=true;$('#now').setAttribute('aria-expanded','false');}
  $('#now').onclick=()=>$('#tpanel').hidden?openPanel():closePanel();
  addEventListener('click',event=>{if(!$('#tpanel').hidden&&!event.target.closest('#tpanel,#now'))closePanel();});
  addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('#tpanel').hidden){closePanel();$('#now').focus();}});
  function renderPulse(){
    const svg=$('#pulse'),activity=index.activity,width=1000,base=118,max=Math.max(...activity.map(item=>item[1]));
    const step=width/(activity.length-1||1),points=activity.map(([,count],i)=>[i*step,base-(count/max)*104]);
    const make=(tag,attributes)=>{const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value] of Object.entries(attributes))node.setAttribute(key,value);return node;};
    svg.replaceChildren();
    svg.append(make('path',{d:'M0 '+base+' L'+points.map(point=>point.join(' ')).join(' L')+' L'+width+' '+base+' Z',fill:'url(#inkfill)'}));
    svg.append(make('path',{d:points.map((point,i)=>(i?'L':'M')+point.join(' ')).join(' '),fill:'none',stroke:'#1c1915','stroke-width':1.4,'vector-effect':'non-scaling-stroke'}));
    svg.append(make('line',{x1:0,x2:width,y1:base,y2:base,stroke:'#1c1915','stroke-width':1}));
    let last='';
    activity.forEach(([month,count],i)=>{
      const x=i*step,year=month.slice(0,4);
      if(year!==last){last=year;svg.append(make('line',{x1:x,x2:x,y1:base,y2:base+8,stroke:'#b5321d','stroke-width':2}));const text=make('text',{x,y:base+26,class:'yr','text-anchor':i?'middle':'start'});text.textContent=year;svg.append(text);}
      const hit=make('rect',{x:x-step/2,y:0,width:step,height:base,class:'hit',tabindex:0,role:'button','aria-label':month+'，'+count+'条消息'});
      const tip=make('text',{x,y:Math.max(points[i][1]-6,10),class:'tip','text-anchor':'middle'});tip.textContent=monthName(month.slice(5))+' '+count;
      hit.addEventListener('click',()=>jumpToMonth(month));hit.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();jumpToMonth(month);}});svg.append(hit,tip);
    });
  }
  function card(event){
    const major=event.heat===3,[kind,color]=CATS[event.category]||CATS['群内热议'];
    const node=el('article','ev '+(major?'k-big':kind));node.dataset.id=event.id;node.style.setProperty('--c',color);
    if(kind==='k-meme'&&!major)node.style.setProperty('--r',((event.title.length%5)-2)*.45+'deg');
    const [,month,day]=event.date.split('-');
    if(major){const date=el('div','bd',Number(day));date.append(el('small',null,monthName(month)));node.append(date,el('div','seal','大事'));}
    const date=el('div','d');date.append(el('b',null,Number(month)+'·'+day),el('span','cat',event.category),el('span','h','●'.repeat(event.heat)));node.prepend(date);
    node.append(el('h3',null,event.title),el('p',null,event.summary));
    if(event.people.length){const people=el('div','ppl');event.people.forEach(person=>people.append(el('span',null,person)));node.append(people);}
    if(event.chat){const button=el('button','go','翻当时的聊天');button.onclick=()=>openSheet(event,button);node.append(button);}
    else if(event.lock)node.append(el('div','lock',event.lock));
    return node;
  }
  function appendMonth(month,events,fragment){
    const year=month.month.slice(0,4);
    if(lastYear!==year){
      lastYear=year;const section=el('section','year');section.append(el('div','num',year));
      const cycle='甲乙丙丁戊己庚辛壬癸'[(year-4)%10]+'子丑寅卯辰巳午未申酉戌亥'[(year-4)%12];
      const gz=el('div','gz',cycle);gz.append(el('small',null,'鼠牛虎兔龙蛇马羊猴鸡狗猪'[(year-4)%12]+'年'));
      const total=index.months.filter(item=>item.month.startsWith(year)).reduce((sum,item)=>sum+countFor(item),0);
      const count=el('div','cnt');count.append(el('b',null,total),'件事');section.append(gz,count);fragment.append(section);
    }
    const section=el('section','month');section.id='m-'+month.month;
    const heading=el('div','mhead');heading.dataset.year=year;heading.dataset.month=monthName(month.month.slice(5));
    const column=el('div','mhead-col');column.append(el('div','myear',year),el('div','mname',heading.dataset.month));
    const count=el('div','mmeta');count.append(el('b',null,month.count),' 条消息');heading.append(column,count);section.append(heading);
    if(month.summary)section.append(el('p','msum',month.summary));
    const cards=el('div','evs');events.filter(eventMatches).forEach(event=>cards.append(card(event)));section.append(cards);fragment.append(section);
    monthObserver.observe(heading);
  }
  function scheduleFonts(){
    if(fontScheduled)return;fontScheduled=true;
    const href=document.documentElement.dataset.fonts;if(!href)return;
    setTimeout(()=>{const link=document.createElement('link');link.rel='stylesheet';link.href=href;document.head.append(link);},1200);
  }
  async function loadMore(version){
    if(version!==revision||loading||cursor>=matching.length)return;
    loading=true;moreObserver.unobserve(status);showStatus('正在载入…');
    const batch=matching.slice(cursor,cursor+2);
    try{
      const rows=await Promise.all(batch.map(month=>getJSON(month.url)));
      if(version!==revision)return;
      const fragment=document.createDocumentFragment();batch.forEach((month,i)=>appendMonth(month,rows[i],fragment));list.append(fragment);cursor+=batch.length;
      if(pendingJump){pendingJump=false;jumpToList();}
      if(pendingCard){const target=list.querySelector('[data-id="'+pendingCard+'"]');pendingCard='';if(target){target.scrollIntoView({block:'center'});target.classList.add('flash');setTimeout(()=>target.classList.remove('flash'),2400);}}
      scheduleFonts();
      if(cursor<matching.length){showStatus('',()=>loadMore(revision),'继续往下翻');moreObserver.observe(status);}
      else showStatus(matching.length?'已经翻到底了':'这里还空着，换个条件看看');
    }catch(error){if(version===revision)showError(error,()=>loadMore(revision));}
    finally{if(version===revision)loading=false;}
  }
  function jumpToList(){scrollTo({top:list.getBoundingClientRect().top+scrollY-$('.bar').offsetHeight});}
  function render(jump=false){
    revision++;loading=false;cursor=0;lastYear='';monthObserver.disconnect();moreObserver.unobserve(status);
    list.replaceChildren();renderBar();
    matching=index.months.filter(month=>(!state.from||month.month>=state.from)&&countFor(month)>0);
    if(state.from){
      const note=el('div','from-note','从 '+state.from.slice(0,4)+' 年'+monthName(state.from.slice(5))+'看起'),back=el('button',null,'从头看');
      back.type='button';back.onclick=()=>jumpToMonth(index.months[0].month);note.append(back);list.append(note);
    }
    current='';if(matching.length)setNow(matching[0].month);
    if(!matching.length)showStatus('这里还空着，换个条件看看');else loadMore(revision);
    // 内容载入后再跳，空列表时页面不够高，滚不到位
    pendingJump=jump;if(!matching.length&&jump){pendingJump=false;jumpToList();}
  }
  const palette=['#b5321d','#2e4a5e','#4d6a45','#b0832f','#7a4a6b','#8a5a3b','#3d6b6b','#6b4f9a'];
  const colors=new Map();
  function colorFor(person){if(!colors.has(person))colors.set(person,palette[colors.size%palette.length]);return colors.get(person);}
  async function openSheet(event,trigger){
    const version=++drawerRevision;drawerTrigger=trigger;
    $('#shd').textContent=event.date.replaceAll('-','.')+' · '+event.category;$('#sht').textContent=event.title;
    const body=$('#shb');body.replaceChildren(el('p',null,'正在载入当时的聊天…'));
    $('#veil').classList.add('on');$('#sheet').classList.add('on');$('#sheet').setAttribute('aria-hidden','false');document.body.style.overflow='hidden';$('#shx').focus();
    try{
      const messages=await getJSON(event.chat);if(version!==drawerRevision)return;
      const fragment=document.createDocumentFragment();
      messages.forEach(message=>{
        if(message.gap){fragment.append(el('div','gap','· · ·'));return;}
        const row=el('div','m'+(message.k?' key':' dim'));const avatar=el('div','av',[...message.s][0]);avatar.style.setProperty('--c',colorFor(message.s));
        const box=el('div','mb'),name=el('div','n',message.s);name.append(el('em',null,message.t.slice(6)));box.append(name,el('div','bub',message.c.replaceAll(' ⏎ ','\n')));row.append(avatar,box);fragment.append(row);
      });body.replaceChildren(fragment);body.scrollTop=0;
    }catch(error){if(version!==drawerRevision)return;body.replaceChildren(el('p',null,error.message));const retry=el('button','go',error.auth?'重新登录':'重试');retry.onclick=error.auth?()=>location.assign('/'):()=>openSheet(event,trigger);body.append(retry);}
  }
  // 跳到某件事：从它所在的月往后排，载入后滚到那张卡片并闪一下
  function jumpToEvent(event){
    if(!eventMatches(event)){state.big=false;state.cat='';state.who='';}
    pendingCard=event.id;jumpToMonth(event.month);
  }
  // 事件搜索：标题、经过、人名；空格分开的几个词要同时出现
  const srch=$('#srch'),sq=$('#sq'),sqb=$('#sqb');
  let allEvents=null,hits=[],shown=0,searchTimer=0,searchTrigger=null,searchRevision=0;
  function tip(text,action,label){const node=el('p','sq-tip',text);if(action){const button=el('button',null,label);button.type='button';button.onclick=action;node.append(button);}return node;}
  function highlight(cls,text,words,limit){
    const node=el('div',cls),low=text.toLowerCase(),marks=[];
    words.forEach(word=>{for(let at=low.indexOf(word);at>=0;at=low.indexOf(word,at+word.length))marks.push([at,at+word.length]);});
    marks.sort((x,y)=>x[0]-y[0]);
    let from=0;if(limit&&marks.length&&marks[0][0]>limit*.4){from=marks[0][0]-20;node.append('…');}
    const end=limit?Math.min(text.length,from+limit):text.length;
    for(const [start,stop] of marks){if(start<from)continue;if(start>=end)break;node.append(text.slice(from,start),el('mark',null,text.slice(start,stop)));from=stop;}
    node.append(text.slice(from,end)+(end<text.length?'…':''));return node;
  }
  function showMore(words){
    sqb.querySelector('.sb-more')?.remove();
    const fragment=document.createDocumentFragment();
    hits.slice(shown,shown+50).forEach(event=>{
      const row=el('button','sr');row.type='button';
      row.append(el('div','sr-meta',event.date.replaceAll('-','.')+' · '+event.category+' · '+'●'.repeat(event.heat)),highlight('sr-t',event.title,words),highlight('sr-c',event.summary,words,90));
      if(event.people.length)row.append(highlight('sr-p',event.people.join(' · '),words));
      row.onclick=()=>{closeSearch();jumpToEvent(event);};fragment.append(row);
    });
    shown+=50;
    if(shown<hits.length){const more=el('button','sb-more','再显示 50 件');more.type='button';more.onclick=()=>showMore(words);fragment.append(more);}
    sqb.append(fragment);
  }
  async function runSearch(){
    const version=++searchRevision,words=sq.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if(!words.length){sqb.replaceChildren(tip('搜标题、经过或人名，几个词用空格隔开。'));return;}
    if(!allEvents){
      sqb.replaceChildren(tip('正在载入全部事件…'));
      try{const rows=await getJSON(index.events);allEvents=rows.map(([id,date,category,heat,title,summary,people])=>({id,month:date.slice(0,7),date,category,heat,title,summary,people,text:(title+' '+summary+' '+people.join(' ')).toLowerCase()}));}
      catch(error){if(version===searchRevision)sqb.replaceChildren(tip(error.message,error.auth?()=>location.assign('/'):runSearch,error.auth?'重新登录':'重试'));return;}
      if(version!==searchRevision)return;
    }
    hits=allEvents.filter(event=>words.every(word=>event.text.includes(word)));
    shown=0;sqb.replaceChildren(tip(hits.length?'找到 '+hits.length+' 件事，点一件跳过去':'没有找到「'+sq.value.trim()+'」'));showMore(words);sqb.scrollTop=0;
  }
  function openSearch(){
    searchTrigger=document.activeElement;closePanel();
    $('#veil').classList.add('on');srch.classList.add('on');srch.setAttribute('aria-hidden','false');document.body.style.overflow='hidden';sq.focus();
    if(!sqb.childNodes.length)runSearch();
  }
  function closeSearch(){$('#veil').classList.remove('on');srch.classList.remove('on');srch.setAttribute('aria-hidden','true');document.body.style.overflow='';searchTrigger?.focus();}
  $('#sbtn').onclick=openSearch;$('#sqx').onclick=closeSearch;
  sq.oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(runSearch,250);};
  sq.onkeydown=event=>{if(event.key==='Enter'){clearTimeout(searchTimer);runSearch();sq.blur();}};
  function closeSheet(){drawerRevision++;$('#veil').classList.remove('on');$('#sheet').classList.remove('on');$('#sheet').setAttribute('aria-hidden','true');document.body.style.overflow='';drawerTrigger?.focus();}
  $('#veil').onclick=()=>srch.classList.contains('on')?closeSearch():closeSheet();$('#shx').onclick=closeSheet;
  addEventListener('keydown',event=>{
    const sheet=document.querySelector('.sheet.on');if(!sheet)return;
    if(event.key==='Escape')sheet===srch?closeSearch():closeSheet();
    if(event.key==='Tab'){
      const focusable=[...sheet.querySelectorAll('button,a,input,select,[tabindex="0"]')];const first=focusable[0],last=focusable.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    }
  });
  // 年度十大 + 群友榜
  let topYear='';
  function renderTop(){
    const years=Object.keys(index.top||{}).reverse();if(!years.length){$('#top').hidden=true;return;}
    if(!topYear)topYear=years[0];
    $('#top-tabs').replaceChildren(...years.map(year=>{
      const button=el('button','tg'+(year===topYear?' on':''),year);button.type='button';button.setAttribute('aria-pressed',String(year===topYear));
      button.onclick=()=>{topYear=year;renderTop();};return button;
    }));
    const data=index.top[topYear],body=$('#top-body');body.replaceChildren();
    if(data.note)body.append(el('p','top-note','※ '+data.note));
    const grid=el('div','top-body'),ranks=el('ol','top-list'),boards=el('div','boards');
    data.events.forEach((event,i)=>{
      const button=el('button','top-ev');button.type='button';
      button.append(el('span','top-n',i+1),el('div','top-m',event.date.replaceAll('-','.')+' · '+event.category),el('div','top-t',event.title),el('div','top-r',event.reason));
      button.onclick=()=>jumpToEvent(event);const item=el('li');item.append(button);ranks.append(item);
    });
    data.boards.forEach(([title,unit,rows])=>{
      const board=el('div','board'),max=rows[0]?.[1]||1;board.append(el('h4',null,title),el('small',null,unit));
      rows.forEach(([name,count],i)=>{const row=el('div','br'),bar=el('i');bar.style.width=Math.max(4,count/max*100)+'%';const track=el('div');track.append(bar);row.append(el('b',null,i+1),el('span',null,name),track,el('em',null,count.toLocaleString()));board.append(row);});
      boards.append(board);
    });
    grid.append(ranks,boards);body.append(grid);
  }
  async function init(){try{index=await getJSON(document.documentElement.dataset.index);renderPulse();renderTop();render();}catch(error){showError(error,init);}}
  init();
})();
