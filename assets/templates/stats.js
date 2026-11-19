// 「数据」页：读 build_stats.py 产出的统计（单文件版内嵌在 #data，网站版由 data-stats 指向带哈希的 json），全部图表用 SVG 自绘
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ZHU = '181,50,29';
  let D, L, st = { g: 'all', y: 'all', gran: null, mx: 'at', who: null };

  // ---------- 文案（lang = zh / en） ----------
  const I18N = {
    zh: {
      locale: 'zh-CN', week: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      cats: {}, group: '群', year: '年份', all: '全部', allYears: '全部年份', yearN: y => y + ' 年',
      merged: (y0, n) => `含 ${y0} 年的 ${n} 个月`, failed: '数据没载入成功，<a href="" style="color:var(--zhu)">刷新试试</a>。', none: '这段时间没有消息。',
      ov: '概览', range: (a, b) => `${a} 至 ${b}`, tMsgs: '条消息', tPeople: '位说过话的群友', tSpan: '天跨度', tActive: p => `天有人说话（${p}）`,
      trend: '发言趋势', gran: { day: '按日', week: '按周', month: '按月' }, unitOf: { day: '天', week: '周', month: '月' },
      trendCap: u => `每${u}的消息条数，移到图上看具体数字。`, weekOf: d => d + ' 起一周', monthOf: m => m.replace('-', ' 年 ') + ' 月', monthAxis: m => +m + '月',
      msgs: n => `${n} 条`, times: n => `${n} 次`, days: n => `${n} 天`, pics: n => `${n} 张`, mins: n => `${n} 分钟`,
      hot: '最热的十天', hotCap: '那天说话最多的人记作“当天龙王”。', hotTip: (d, n, w) => `${d}：${n} 条，${w} 说得最多`,
      time: '时间', timeSub: '几点最热闹，每个人什么时候冒泡', heat: '一周 × 24 小时', heatCap: '格子越红，这个时段的消息越多。',
      heatTip: (w, h, n) => `${w} ${h}:00–${h + 1}:00<br><b>${n}</b> 条`, hourAxis: h => h + '时', less: '少', more: n => `多（最热一格 ${n} 条）`,
      clock: '每个人的活跃时段', clockCap: '24 根柱是 0–23 点，红柱是 TA 最常说话的那个小时。', peak: h => `峰值 ${h} 时`,
      clockTip: (w, h, a, b, p) => `${w}：最常在 ${h} 点说话<br>${a}–${b} 点占 ${p}`,
      types: '消息类型', typesSub: '打字、发图、斗表情还是发语音', typesAll: '全群', typesAllCap: '“链接”含公众号文章与音乐，“其他”含红包、位置、名片、文件、接龙等。',
      typesP: '每个人', typesPCap: '右边的数字是文字消息的占比。',
      boards: '榜单', boardsSub: y => `${y}，切换上方年份看年度榜`, nobody: '这段时间没人够格。', since: d => d + ' 起',
      b: {
        king: ['龙王', '发言条数'], daily: ['每日龙王', '当天说话最多的次数'], streak: ['打卡', '连续每天发言的最长天数'], pic: ['斗图', '表情 + 图片条数'],
        night: (a, b, n) => ['夜猫子', `${a}–${b} 点发言占比，≥${n} 条才上榜`], early: (a, b, n) => ['早鸟', `${a}–${b} 点发言占比，≥${n} 条才上榜`],
      },
      divers: '深海潜水员', diversSub: '核心成员里发言最少', diversCap: n => `核心成员里偶尔浮上来换口气的 ${n} 位（纯属娱乐）。`,
      rep: '复读', repSub: (n, w, t) => `同一句短话，${w} 分钟内 ≥${n} 个人接连发出，算一次复读（共 ${t} 次）`,
      lead: '带头的人', leadCap: '第一个说这句话的人。', follow: '跟上的人', followCap: '跟着复读的次数。', noRep: '这段时间没有复读。',
      phr: '最火复读句', phrCap: n => `只取允许展示原文的群、≤${n} 个字，并滤掉涉及钱、健康、住址、感情、工作等的句子和“好的”“我也是”这类应答。`,
      phrHidden: '这个群的原文不公开，复读句只算次数。', phrNone: '这段时间没有可展示的复读句。', phrRow: (n, p) => `${n} 次 · 最多 ${p} 人`,
      words: '口头禅与词云', wordsSub: '不随筛选变化：全部群、全部年份一起算',
      catch: '每个人的口头禅', catchCap: (m, c, mo) => `≤${m} 个字的整句，说过 ≥${c} 次、分布在 ≥${mo} 个月；笑声和问句不算，笑法单列。`,
      saidN: n => `说过 ${n} 次`, laughFav: (t, n, t2) => `最爱的笑法：「${t}」×${n}${t2 ? `，其次「${t2}」` : ''}`,
      cloud: '群词云', cloudCap: '出现在最多条消息里的词（已去掉人名外号、常用虚词，以及钱、健康、住址、感情、工作相关的词）；红色是前十。',
      cloudTip: (w, n) => `「${w}」出现在 ${n} 条消息里`, cloudNone: '词太少，画不出词云。', q: t => `「${t}」`,
      inter: '互动', interSub: '行 = 做这件事的人，列 = 对象',
      mx: { at: ['@', '谁 @ 谁', (a, b, v) => `${a} @ ${b}：${v} 次`], next: ['接话', '谁最常接谁的话（10 分钟内紧接着发言）', (a, b, v) => `${a} 接 ${b} 的话：${v} 次`], quote: ['引用', '谁引用回复谁', (a, b, v) => `${a} 引用 ${b}：${v} 次`] },
      mxCap: t => `${t}。颜色越深次数越多（开方刻度，小数也看得见）。`,
      lat: '回得多快', latCap: '被 @ 或被引用后，TA 下一条消息隔多久（中位数，12 小时内、样本 ≥10 次才算）。', latTip: (w, m, n) => `${w}：中位 ${m} 分钟（${n} 次）`, few: '样本不够。',
      open: '冷场救星', openCap: '群里安静 3 小时以上之后，第一个开口的次数。', nil: '无',
      graph: '小团体', graphSub: '两人越常出现在同一段对话里，线越粗、靠得越近',
      graphCap: (c, o) => `聊天间隔超过 30 分钟就切成新的一段对话。亲密度 = 共同出现的段数 ÷ √(两人各自出现的段数之积)，去掉了“话多的人跟谁都同框”的偏差；每人只画最强的 3 条线。圆的大小 = 参与的对话段数${o ? `；<span style="color:var(--zhu)">●</span> ${c} <span style="color:var(--c2)">●</span> ${o}` : ''}。`,
      core: '核心成员', other: '其他群友', graphFew: '人太少，画不出关系图。',
      edgeTip: (a, b, n, s) => `${a} × ${b}<br>同在 ${n} 段对话里（亲密度 ${s}）`, nodeTip: (w, n) => `${w}：出现在 ${n} 段对话里`,
      cards: '数据卡', cardsSub: '每人一张，跟着上方筛选变', champs: l => ' · 本榜：' + l.join('、'),
      dt: { n: '发言', days: '有发言的天数', streak: '最长连续打卡', king: '当上每日龙王', peak: '最活跃时段', pic: '斗图', atTo: '最常 @', atFrom: '最常被谁 @', nextTo: '最爱接谁的话', med: '被 @/引用后回复', open: '冷场后开话题', rep: '复读', buddy: '最铁的搭子' },
      rankOf: (r, n, p) => `第 ${r} / ${n}，占 ${p}`, monthsN: n => `${n} 个月`, hourN: h => `${h} 点`, nightShare: (a, b, p) => `${a}–${b} 点占 ${p}`, share: p => '占 ' + p,
      median: '中位数', noSample: '样本不足', repDetail: (a, b) => `带头 ${a} · 跟读 ${b}`, closeness: s => '亲密度 ' + s,
      says: '口头禅：', laughs: '笑法：', sep: '　',
      noTime: gs => `「${gs.join('、')}」的记录没有真实时刻，热力图、夜猫子、早鸟、活跃时段、回复时延都不含这些群。`,
      note: d => `口径：只数能对上人的消息，系统消息、撤回提示不算；按人统计只算成员名单里的人。全部统计在本地离线算好，页面里没有聊天原文。数据截至 ${d}。`,
    },
    en: {
      locale: 'en-US', week: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      cats: { '文字': 'Text', '图片': 'Photo', '表情': 'Sticker', '语音': 'Voice', '视频': 'Video', '链接': 'Link', '小程序': 'Mini app', '其他': 'Other' },
      group: 'Group', year: 'Year', all: 'All', allYears: 'All years', yearN: y => y,
      merged: (y0, n) => `includes ${n} month(s) of ${y0}`, failed: 'Could not load the data. <a href="" style="color:var(--zhu)">Reload</a>.', none: 'No messages in this period.',
      ov: 'Overview', range: (a, b) => `${a} to ${b}`, tMsgs: 'messages', tPeople: 'people who spoke', tSpan: 'days spanned', tActive: p => `days with messages (${p})`,
      trend: 'Activity', gran: { day: 'Daily', week: 'Weekly', month: 'Monthly' }, unitOf: { day: 'day', week: 'week', month: 'month' },
      trendCap: u => `Messages per ${u}. Hover the chart for exact numbers.`, weekOf: d => 'Week of ' + d, monthOf: m => m, monthAxis: m => ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][+m],
      msgs: n => `${n} msgs`, times: n => `${n}×`, days: n => `${n} days`, pics: n => `${n}`, mins: n => `${n} min`,
      hot: 'Ten busiest days', hotCap: 'Whoever talked most that day is the day’s top talker.', hotTip: (d, n, w) => `${d}: ${n} messages, most from ${w}`,
      time: 'Time', timeSub: 'When the group is loudest, and when each person shows up', heat: 'Week × 24 hours', heatCap: 'The redder the cell, the more messages in that hour.',
      heatTip: (w, h, n) => `${w} ${h}:00–${h + 1}:00<br><b>${n}</b> messages`, hourAxis: h => h + 'h', less: 'fewer', more: n => `more (busiest cell: ${n})`,
      clock: 'Everyone’s hours', clockCap: '24 bars for 0–23h; the red bar is the hour they talk most.', peak: h => `peak ${h}h`,
      clockTip: (w, h, a, b, p) => `${w}: most active at ${h}h<br>${a}–${b}h: ${p}`,
      types: 'Message types', typesSub: 'Typing, photos, stickers or voice notes', typesAll: 'Whole group', typesAllCap: '“Link” includes articles and music; “Other” covers red packets, locations, contacts, files, polls, etc.',
      typesP: 'Per person', typesPCap: 'The number on the right is the share of text messages.',
      boards: 'Leaderboards', boardsSub: y => `${y} — pick a year above for that year’s boards`, nobody: 'Nobody qualifies in this period.', since: d => 'from ' + d,
      b: {
        king: ['Top talker', 'messages sent'], daily: ['Daily top talker', 'days as the day’s top talker'], streak: ['Streak', 'longest run of consecutive days'], pic: ['Sticker fiend', 'stickers + photos'],
        night: (a, b, n) => ['Night owl', `share of messages ${a}–${b}h, ≥${n} messages to qualify`], early: (a, b, n) => ['Early bird', `share of messages ${a}–${b}h, ≥${n} messages to qualify`],
      },
      divers: 'Deep-sea diver', diversSub: 'quietest of the core members', diversCap: n => `The ${n} core members who surface only now and then (just for fun).`,
      rep: 'Echoes', repSub: (n, w, t) => `The same short line sent by ≥${n} people in a row within ${w} minutes counts as one echo (${t} total)`,
      lead: 'Starters', leadCap: 'Who said it first.', follow: 'Followers', followCap: 'How often they joined in.', noRep: 'No echoes in this period.',
      phr: 'Top echoed lines', phrCap: n => `Only from groups whose messages may be shown, ≤${n} words, with anything about money, health, addresses, dating or work filtered out, plus plain replies like “ok” or “same”.`,
      phrHidden: 'Messages from this group are private; echoes are only counted.', phrNone: 'No lines to show for this period.', phrRow: (n, p) => `${n}× · up to ${p} people`,
      words: 'Catchphrases & word cloud', wordsSub: 'Not filtered: all groups, all years',
      catch: 'Catchphrases', catchCap: (m, c, mo) => `Whole messages of ≤${m} words, said ≥${c} times across ≥${mo} months; laughs and questions excluded (laughs listed separately).`,
      saidN: n => `said ${n} times`, laughFav: (t, n, t2) => `Favourite laugh: “${t}” ×${n}${t2 ? `, then “${t2}”` : ''}`,
      cloud: 'Word cloud', cloudCap: 'Words that appear in the most messages (names, nicknames, filler words and anything about money, health, addresses, dating or work removed); top ten in red.',
      cloudTip: (w, n) => `“${w}” appears in ${n} messages`, cloudNone: 'Not enough words for a cloud.', q: t => `“${t}”`,
      inter: 'Interactions', interSub: 'Row = who does it, column = to whom',
      mx: { at: ['@', 'Who @-mentions whom', (a, b, v) => `${a} @ ${b}: ${v}×`], next: ['Replies', 'Who speaks right after whom (within 10 minutes)', (a, b, v) => `${a} right after ${b}: ${v}×`], quote: ['Quotes', 'Who quote-replies to whom', (a, b, v) => `${a} quotes ${b}: ${v}×`] },
      mxCap: t => `${t}. Darker = more often (square-root scale so small numbers still show).`,
      lat: 'Response time', latCap: 'After being @-mentioned or quoted, how long until their next message (median; within 12 hours, ≥10 samples).', latTip: (w, m, n) => `${w}: median ${m} min (${n} samples)`, few: 'Not enough samples.',
      open: 'Silence breakers', openCap: 'First to speak after the group was quiet for 3+ hours.', nil: 'None',
      graph: 'Circles', graphSub: 'The more often two people are in the same conversation, the thicker and closer the line',
      graphCap: (c, o) => `A gap of 30+ minutes starts a new conversation. Closeness = shared conversations ÷ √(product of each person’s conversations), which removes the “talkative people co-occur with everyone” bias; each person keeps their 3 strongest links. Circle size = conversations joined${o ? `; <span style="color:var(--zhu)">●</span> ${c} <span style="color:var(--c2)">●</span> ${o}` : ''}.`,
      core: 'core members', other: 'others', graphFew: 'Too few people for a graph.',
      edgeTip: (a, b, n, s) => `${a} × ${b}<br>${n} shared conversations (closeness ${s})`, nodeTip: (w, n) => `${w}: in ${n} conversations`,
      cards: 'Data cards', cardsSub: 'One per person, following the filters above', champs: l => ' · Top of: ' + l.join(', '),
      dt: { n: 'Messages', days: 'Active days', streak: 'Longest streak', king: 'Daily top talker', peak: 'Peak hour', pic: 'Stickers & photos', atTo: 'Mentions most', atFrom: 'Mentioned most by', nextTo: 'Replies most to', med: 'Response time', open: 'Silence breaks', rep: 'Echoes', buddy: 'Closest buddy' },
      rankOf: (r, n, p) => `#${r} of ${n}, ${p}`, monthsN: n => `${n} months`, hourN: h => `${h}h`, nightShare: (a, b, p) => `${a}–${b}h: ${p}`, share: p => p,
      median: 'median', noSample: 'too few samples', repDetail: (a, b) => `started ${a} · joined ${b}`, closeness: s => 'closeness ' + s,
      says: 'Says: ', laughs: 'Laughs: ', sep: ' ',
      noTime: gs => `${gs.join(', ')}: no real timestamps, so the heatmap, night owls, early birds, active hours and response times leave these chats out.`,
      note: d => `Method: only messages that map to a person are counted; system notices and recalls are excluded, and per-person stats cover the member list only. Everything was computed offline; there is no chat history on this page. Data up to ${d}.`,
    },
  };
  const fmt = n => Number(n).toLocaleString(L.locale);
  const pct = (a, b) => b ? (100 * a / b).toFixed(a / b < 0.1 ? 1 : 0) + '%' : '—';
  const catName = k => L.cats[k] || k;
  const hidden = k => D.cfg.hide.includes(k);

  // ---------- 提示框：任何带 data-tip 的元素 ----------
  // 提示文字按纯文本处理（昵称、词云词等群友数据可能带尖括号），转义后只放回模板自带的 <br>、<b>
  const tip = $('#tip');
  const tipHtml = s => esc(s).replace(/&lt;(br|\/?b)&gt;/g, '<$1>');
  function showTip(text, e) {
    tip.innerHTML = tipHtml(text); tip.classList.add('on');
    const r = tip.getBoundingClientRect();
    let x = e.clientX + 14, y = e.clientY + 14;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
    tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, y) + 'px';
  }
  const hideTip = () => tip.classList.remove('on');
  document.addEventListener('pointermove', e => {
    const t = e.target.closest && e.target.closest('[data-tip]');
    if (t) showTip(t.getAttribute('data-tip'), e); else if (!e.target.closest('.trend-hit')) hideTip();
  });
  document.addEventListener('pointerdown', e => {
    const t = e.target.closest && e.target.closest('[data-tip]');
    if (t) showTip(t.getAttribute('data-tip'), e);
  });
  addEventListener('scroll', hideTip, { passive: true });

  const name = i => D.people[i].n;
  const yearOf = day => { const y = day.slice(0, 4); for (const [to, [from]] of Object.entries(D.merge)) if (y === from) return to; return y; };
  const combo = () => D.combos[st.g + '|' + st.y];
  const members = c => Object.keys(c.p).map(Number).sort((a, b) => c.p[b].n - c.p[a].n || a - b);
  const width = el => Math.max(260, el.clientWidth);
  const groupLabel = g => g === 'all' ? L.all : (D.groups.find(x => x.k === g) || { label: g }).label;
  const repeatEvents = () => D.repeat.events.filter(([d, g]) => (st.g === 'all' || g === st.g) && (st.y === 'all' || yearOf(d) === st.y));
  const sum = arr => arr.reduce((a, b) => a + b, 0);
  const hoursShare = (h, [a, b]) => sum(h.slice(a, b));

  // ---------- 筛选 ----------
  function renderFilters() {
    const fg = $('#f-g'), fy = $('#f-y');
    fg.replaceChildren(); fy.replaceChildren();
    fg.setAttribute('aria-label', L.group); fy.setAttribute('aria-label', L.year);
    const label = text => { const s = document.createElement('span'); s.textContent = text; return s; };
    if (D.groups.length > 1) {
      fg.append(label(L.group));
      for (const k of ['all', ...D.groups.map(g => g.k)]) {
        const b = document.createElement('button');
        b.type = 'button'; b.textContent = groupLabel(k); b.setAttribute('aria-pressed', st.g === k);
        b.onclick = () => { st.g = k; if (!combo()) st.y = 'all'; render(); };
        fg.append(b);
      }
    } else fg.hidden = true;
    fy.append(label(L.year));
    for (const y of ['all', ...D.years]) {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = y === 'all' ? L.all : y; b.setAttribute('aria-pressed', st.y === y);
      b.disabled = !D.combos[st.g + '|' + y];
      if (D.merge[y]) b.title = L.merged(...D.merge[y]);
      b.onclick = () => { st.y = y; render(); };
      fy.append(b);
    }
  }

  // ---------- 概览 ----------
  function trendPoints() {
    const arr = D.daily[st.g], start = new Date(D.daily.start + 'T00:00:00Z');
    const day = i => new Date(start.getTime() + i * 864e5).toISOString().slice(0, 10);
    let lo = 0, hi = arr.length - 1;
    if (st.y !== 'all') {
      while (lo < arr.length && yearOf(day(lo)) !== st.y) lo++;
      hi = lo; while (hi + 1 < arr.length && yearOf(day(hi + 1)) === st.y) hi++;
    }
    while (lo < hi && !arr[lo]) lo++;  // 去掉首尾没消息的天（某个群晚建）
    while (hi > lo && !arr[hi]) hi--;
    const gran = st.gran || (st.y === 'all' ? 'month' : 'week');
    const pts = [];
    for (let i = lo; i <= hi; i++) {
      const d = day(i);
      let key = d, label = d;
      if (gran === 'week') { const dt = new Date(d + 'T00:00:00Z'); const back = (dt.getUTCDay() + 6) % 7; key = day(i - back); label = L.weekOf(key); }
      if (gran === 'month') { key = d.slice(0, 7); label = L.monthOf(key); }
      const last = pts[pts.length - 1];
      if (last && last.key === key) last.v += arr[i]; else pts.push({ key, label, d, v: arr[i] });
    }
    return { pts, gran };
  }

  function niceMax(v) {
    const p = Math.pow(10, Math.floor(Math.log10(v || 1))), m = v / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }

  function drawTrend(box) {
    const { pts, gran } = trendPoints();
    const W = width(box), H = W < 500 ? 170 : 220, Lp = 44, R = 10, T = 12, B = 24;
    const max = niceMax(Math.max(1, ...pts.map(p => p.v)));
    const x = i => Lp + (pts.length < 2 ? 0 : i * (W - Lp - R) / (pts.length - 1));
    const y = v => T + (H - T - B) * (1 - v / max);
    let g = '';
    for (let k = 0; k <= 4; k++) {
      const v = max * k / 4;
      g += `<line x1="${Lp}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)" stroke-width="1"${k ? ' stroke-dasharray="2 3"' : ''}/><text x="${Lp - 6}" y="${y(v) + 4}" text-anchor="end">${fmt(v)}</text>`;
    }
    let lastLab = '';  // 横轴：跨年按年标，单年按月标
    pts.forEach((p, i) => {
      const mo = p.d.slice(5, 7);
      const lab = st.y === 'all' ? yearOf(p.d) : L.monthAxis(mo);
      if (lab !== lastLab) {
        lastLab = lab;
        if (st.y !== 'all' && W < 500 && +mo % 2 === 0) return;
        g += `<text x="${x(i)}" y="${H - 6}" text-anchor="start">${lab}</text><line x1="${x(i)}" x2="${x(i)}" y1="${H - B}" y2="${H - B + 4}" stroke="var(--ink-3)"/>`;
      }
    });
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join('');
    const area = line + `L${x(pts.length - 1)},${y(0)}L${x(0)},${y(0)}Z`;
    box.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(L.trend)}">${g}
      <path d="${area}" fill="rgba(${ZHU},.1)"/><path d="${line}" fill="none" stroke="var(--zhu)" stroke-width="${gran === 'day' ? 1 : 2}" stroke-linejoin="round"/>
      <line class="cross" y1="${T}" y2="${H - B}" stroke="var(--ink)" stroke-width="1" opacity="0"/><circle class="dot" r="4" fill="var(--zhu)" stroke="var(--paper-hi)" stroke-width="2" opacity="0"/>
      <rect class="trend-hit" x="${Lp}" y="0" width="${W - Lp - R}" height="${H}" fill="transparent"/></svg>`;
    const svg = box.firstChild, cross = $('.cross', svg), dot = $('.dot', svg);
    const move = e => {
      const r = svg.getBoundingClientRect();
      const i = Math.max(0, Math.min(pts.length - 1, Math.round((e.clientX - r.left - Lp) / ((W - Lp - R) / Math.max(1, pts.length - 1)))));
      cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('opacity', .35);
      dot.setAttribute('cx', x(i)); dot.setAttribute('cy', y(pts[i].v)); dot.setAttribute('opacity', 1);
      showTip(`${pts[i].label}<br><b>${L.msgs(fmt(pts[i].v))}</b>`, e);
    };
    const hit = $('.trend-hit', svg);
    hit.addEventListener('pointermove', move);
    hit.addEventListener('pointerdown', move);
    hit.addEventListener('pointerleave', () => { cross.setAttribute('opacity', 0); dot.setAttribute('opacity', 0); hideTip(); });
  }

  function overview(c) {
    const gran = st.gran || (st.y === 'all' ? 'month' : 'week');
    const maxHot = c.hot[0] ? c.hot[0][1] : 1;
    const who = k => k >= 0 ? esc(name(k)) : '—';
    return `<section id="s-overview"><div class="kicker"><h2>${L.ov}</h2><span>${L.range(c.first, c.last)}</span></div>
      <div class="tiles">
        <div><b>${fmt(c.total)}</b><span>${L.tMsgs}</span></div>
        <div><b>${fmt(c.members)}</b><span>${L.tPeople}</span></div>
        <div><b>${fmt(c.span)}</b><span>${L.tSpan}</span></div>
        <div><b>${fmt(c.activeDays)}</b><span>${L.tActive(pct(c.activeDays, c.span))}</span></div>
      </div>
      <div class="grid">
        <div class="panel wide"><div class="chart-head"><h3>${L.trend}</h3>
          <div class="tabs" id="gran">${['day', 'week', 'month'].map(k => `<button type="button" data-gran="${k}" aria-pressed="${gran === k}">${L.gran[k]}</button>`).join('')}</div></div>
          <p class="cap" id="trendcap">${L.trendCap(L.unitOf[gran])}</p><div id="trend"></div></div>
        <div class="panel wide"><h3>${L.hot}</h3><p class="cap">${L.hotCap}</p>
          <ol class="hot">${c.hot.map(([d, n, k]) => `<li data-tip="${esc(L.hotTip(d, fmt(n), k >= 0 ? name(k) : '—'))}"><span>${d}</span><i style="width:${100 * n / maxHot}%"></i><em>${L.msgs(fmt(n))} · ${who(k)}</em></li>`).join('')}</ol></div>
      </div></section>`;
  }

  // ---------- 时间 ----------
  function drawHeat(box, c) {
    const W = width(box), Lw = 34, cw = (W - Lw) / 24, ch = Math.min(26, Math.max(16, cw)), H = ch * 7 + 22;
    const max = Math.max(1, ...c.heat.flat());
    let s = '';
    c.heat.forEach((row, d) => {
      s += `<text x="0" y="${d * ch + ch / 2 + 4}">${L.week[d]}</text>`;
      row.forEach((v, h) => {
        s += `<rect x="${Lw + h * cw + 1}" y="${d * ch + 1}" width="${cw - 2}" height="${ch - 2}" rx="2" fill="rgba(${ZHU},${(0.04 + 0.96 * v / max).toFixed(3)})" data-tip="${esc(L.heatTip(L.week[d], h, fmt(v)))}"/>`;
      });
    });
    for (let h = 0; h < 24; h += 3) s += `<text x="${Lw + h * cw + 1}" y="${7 * ch + 16}">${L.hourAxis(h)}</text>`;
    box.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(L.heat)}">${s}</svg>
      <div class="legend"><span>${L.less}</span><i style="width:90px;background:linear-gradient(90deg,rgba(${ZHU},.04),rgba(${ZHU},1))"></i><span>${L.more(fmt(max))}</span></div>`;
  }

  function clocks(c) {
    const [na, nb] = D.cfg.night;
    return members(c).map(i => {
      const p = c.p[i], m = Math.max(1, ...p.h), bw = 5;
      const bars = p.h.map((v, h) => `<rect x="${h * bw}" y="${26 - 24 * v / m}" width="${bw - 1}" height="${Math.max(0.5, 24 * v / m)}" fill="${h === p.peak ? 'var(--zhu)' : 'rgba(28,25,21,.28)'}"/>`).join('');
      return `<div data-tip="${esc(L.clockTip(name(i), p.peak, na, nb, pct(hoursShare(p.h, D.cfg.night), Math.max(1, sum(p.h)))))}">${esc(name(i))}<small>${p.peak == null ? '—' : L.peak(p.peak)}</small>
        <svg width="${24 * bw}" height="28" viewBox="0 0 ${24 * bw} 28" aria-hidden="true">${bars}<line x1="0" x2="${24 * bw}" y1="27.5" y2="27.5" stroke="var(--rule)"/></svg></div>`;
    }).join('');
  }

  function timeSec(c) {
    return `<section id="s-time"><div class="kicker"><h2>${L.time}</h2><span>${L.timeSub}</span></div>
      <div class="grid"><div class="panel wide"><h3>${L.heat}</h3><p class="cap">${L.heatCap}</p><div id="heat"></div></div>
      ${hidden('clock') ? '' : `<div class="panel wide"><h3>${L.clock}</h3><p class="cap">${L.clockCap}</p><div class="clock">${clocks(c)}</div></div>`}</div></section>`;
  }

  // ---------- 消息类型 ----------
  const STACK = [['文字', 'var(--c1)', [0]], ['图片', 'var(--c2)', [1]], ['表情', 'var(--c3)', [2]], ['语音', 'var(--c4)', [3]], ['其他', 'var(--c0)', [4, 5, 6, 7]]];
  function typesSec(c) {
    const tot = sum(c.types), order = D.cats.map((k, i) => [k, c.types[i]]).filter(r => r[1]).sort((a, b) => b[1] - a[1]);
    const rows = members(c).map(i => {
      const t = c.p[i].t, n = c.p[i].n;
      const segs = STACK.map(([k, col, idx]) => { const v = idx.reduce((a, j) => a + t[j], 0); return v ? `<i style="flex:${v};background:${col}" data-tip="${esc(name(i))} · ${catName(k)}<br><b>${fmt(v)}</b> (${pct(v, n)})"></i>` : ''; }).join('');
      return `<div class="stack"><span>${esc(name(i))}</span><div class="s">${segs}</div><em>${pct(t[0], n)}</em></div>`;
    }).join('');
    return `<section id="s-types"><div class="kicker"><h2>${L.types}</h2><span>${L.typesSub}</span></div>
      <div class="grid"><div class="panel"><h3>${L.typesAll}</h3><p class="cap">${L.typesAllCap}</p>
        <ul class="bars">${order.map(([k, v]) => `<li data-tip="${esc(catName(k))}: ${fmt(v)} (${pct(v, tot)})"><span>${esc(catName(k))}</span><i style="width:${100 * v / order[0][1]}%"></i><em>${pct(v, tot)}</em></li>`).join('')}</ul></div>
      <div class="panel"><h3>${L.typesP}</h3><p class="cap">${L.typesPCap}</p><div class="legend">${STACK.map(([k, col]) => `<span><i style="background:${col}"></i>${esc(catName(k))}</span>`).join('')}</div>${rows}</div></div></section>`;
  }

  // ---------- 榜单 ----------
  function boardsData(c) {
    const ids = members(c), P = i => c.p[i], cf = D.cfg;
    const share = (i, r) => hoursShare(P(i).h, r) / Math.max(1, sum(P(i).h));  // 分母只算有真实时刻的消息
    const top = (arr, val, n = 5) => arr.slice().sort((a, b) => val(b) - val(a) || a - b).slice(0, n).filter(i => val(i) > 0);
    const big = ids.filter(i => P(i).n >= cf.boardMin);
    const B = L.b, out = [
      { key: 'king', t: B.king, ids: top(ids, i => P(i).n), v: i => P(i).n, f: v => L.msgs(fmt(v)) },
      { key: 'daily', t: B.daily, ids: top(ids, i => P(i).king), v: i => P(i).king, f: v => L.times(fmt(v)) },
      { key: 'streak', t: B.streak, ids: top(ids, i => P(i).streak[0]), v: i => P(i).streak[0], f: v => L.days(v), extra: i => L.since(P(i).streak[1]) },
      { key: 'pic', t: B.pic, ids: top(ids, i => P(i).t[1] + P(i).t[2]), v: i => P(i).t[1] + P(i).t[2], f: v => L.pics(fmt(v)) },
      { key: 'night', t: B.night(...cf.night, cf.boardMin), ids: top(big, i => share(i, cf.night)), v: i => share(i, cf.night), f: v => (100 * v).toFixed(1) + '%' },
      { key: 'early', t: B.early(...cf.early, cf.boardMin), ids: top(big, i => share(i, cf.early)), v: i => share(i, cf.early), f: v => (100 * v).toFixed(1) + '%' },
    ];
    return out.filter(b => !hidden(b.key));
  }
  function boardsSec(c) {
    const ids = members(c);
    const card = b => {
      const [title, desc] = b.t;
      if (!b.ids.length) return `<div class="panel board"><h3>${title}<small>${desc}</small></h3><p class="empty">${L.nobody}</p></div>`;
      const max = b.v(b.ids[0]) || 1;
      return `<div class="panel board"><h3>${title}<small>${desc}</small></h3>
        <p class="crown"><b>${esc(name(b.ids[0]))}</b>${b.f(b.v(b.ids[0]))}${b.extra ? ' (' + b.extra(b.ids[0]) + ')' : ''}</p>
        <ul class="bars">${b.ids.map(i => `<li data-tip="${esc(name(i))}: ${b.f(b.v(i))}${b.extra ? '<br>' + b.extra(i) : ''}"><span>${esc(name(i))}</span><i style="width:${100 * b.v(i) / max}%"></i><em>${b.f(b.v(i))}</em></li>`).join('')}</ul></div>`;
    };
    let divers = '';
    if (!hidden('divers')) {  // 只在核心成员里排发言最少的几位，不做全员倒序
      const ds = ids.filter(i => D.people[i].core).sort((a, b) => c.p[a].n - c.p[b].n || a - b).slice(0, D.cfg.diversN);
      if (ds.length) divers = `<div class="panel board"><h3>${L.divers}<small>${D.text.divers_note || L.diversSub}</small></h3>
        <p class="cap">${L.diversCap(ds.length)}</p>
        <ul class="bars">${ds.map(i => `<li><span>${esc(name(i))}</span><em>${L.msgs(fmt(c.p[i].n))}</em></li>`).join('')}</ul></div>`;
    }
    return `<section id="s-boards"><div class="kicker"><h2>${L.boards}</h2><span>${L.boardsSub(st.y === 'all' ? L.allYears : L.yearN(st.y))}</span></div>
      <div class="boards">${boardsData(c).map(card).join('')}${divers}</div></section>`;
  }

  // ---------- 复读 ----------
  function repeatSec() {
    const ev = repeatEvents();
    const init = {}, foll = {}, phr = {};
    for (const [, , pid, a, fs] of ev) {
      init[a] = (init[a] || 0) + 1;
      for (const f of fs) foll[f] = (foll[f] || 0) + 1;
      if (pid >= 0) { const r = phr[pid] || (phr[pid] = { n: 0, ppl: 0 }); r.n++; r.ppl = Math.max(r.ppl, fs.length + 1); }
    }
    const list = o => {
      const ids = Object.keys(o).map(Number).sort((a, b) => o[b] - o[a] || a - b).slice(0, 6);
      if (!ids.length) return `<p class="empty">${L.noRep}</p>`;
      return `<ul class="bars">${ids.map(i => `<li data-tip="${esc(name(i))}: ${L.times(o[i])}"><span>${esc(name(i))}</span><i style="width:${100 * o[i] / o[ids[0]]}%"></i><em>${L.times(o[i])}</em></li>`).join('')}</ul>`;
    };
    const top = Object.entries(phr).sort((a, b) => b[1].n - a[1].n || b[1].ppl - a[1].ppl || a[0] - b[0]).slice(0, 20);
    const quotable = st.g === 'all' ? D.groups.some(g => g.quote) : (D.groups.find(g => g.k === st.g) || {}).quote;
    const phrBox = !quotable ? `<p class="empty">${L.phrHidden}</p>`
      : top.length ? `<ul class="phr">${top.map(([pid, r]) => `<li><span>${esc(L.q(D.repeat.phrases[pid]))}</span><em>${L.phrRow(r.n, r.ppl)}</em></li>`).join('')}</ul>` : `<p class="empty">${L.phrNone}</p>`;
    return `<section id="s-repeat"><div class="kicker"><h2>${L.rep}</h2><span>${L.repSub(D.cfg.repeatMin, D.cfg.repeatWin, fmt(ev.length))}</span></div>
      <div class="grid"><div class="panel"><h3>${L.lead}</h3><p class="cap">${L.leadCap}</p>${list(init)}</div>
      <div class="panel"><h3>${L.follow}</h3><p class="cap">${L.followCap}</p>${list(foll)}</div>
      ${hidden('repeat_phrases') ? '' : `<div class="panel"><h3>${L.phr}</h3><p class="cap">${L.phrCap(D.cfg.phraseMax)}</p>${phrBox}</div>`}</div></section>`;
  }

  // ---------- 口头禅 / 词云 ----------
  function wordsSec() {
    const panels = [];
    if (!hidden('catch')) {
      const cards = D.people.map((p, i) => [p, i]).filter(([, i]) => (D.catch[i] || []).length || (D.laugh[i] || []).length).map(([p, i]) => {
        const ca = D.catch[i] || [], la = D.laugh[i] || [];
        return `<div><b>${esc(p.n)}</b>${ca.length ? `<p>${ca.map(([t, n]) => `<q data-tip="${esc(L.saidN(n))}">${esc(t)}</q>`).join(L.sep)}</p>` : ''}
          ${la.length ? `<small>${esc(L.laughFav(la[0][0], la[0][1], la[1] && la[1][0]))}</small>` : ''}</div>`;
      }).join('');
      panels.push(`<div class="panel wide"><h3>${L.catch}</h3><p class="cap">${L.catchCap(D.cfg.phraseMax, D.cfg.catchMin, D.cfg.catchMonths)}</p>${cards ? `<div class="catch">${cards}</div>` : `<p class="empty">${L.nil}</p>`}</div>`);
    }
    if (!hidden('cloud')) {
      const ws = D.cloud;
      let cloud = `<p class="empty">${L.cloudNone}</p>`;
      if (ws.length) {
        const max = ws[0][1], min = ws[ws.length - 1][1];
        const h = s => [...s].reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) % 9973, 7);  // 大词打散：按词的确定性哈希排一遍
        cloud = '<div class="cloud">' + ws.map((w, r) => [...w, r]).sort((a, b) => h(a[0]) - h(b[0]) || a[2] - b[2]).map(([w, n, r]) =>
          `<span class="${r < 10 ? 'hi' : ''}" style="font-size:${(13 + 25 * Math.sqrt((n - min) / ((max - min) || 1))).toFixed(1)}px" data-tip="${esc(L.cloudTip(w, fmt(n)))}">${esc(w)}</span>`).join('') + '</div>';
      }
      panels.push(`<div class="panel wide"><h3>${L.cloud}</h3><p class="cap">${L.cloudCap}</p>${cloud}</div>`);
    }
    if (!panels.length) return '';
    return `<section id="s-words"><div class="kicker"><h2>${L.words}</h2><span>${L.wordsSub}</span></div><div class="grid">${panels.join('')}</div></section>`;
  }

  // ---------- 互动 ----------
  function matrixCells(c) {
    const m = {};
    for (const [a, b, v] of c[st.mx]) { const [r, col] = st.mx === 'next' ? [b, a] : [a, b]; m[r + ',' + col] = v; }
    return m;
  }
  function drawMatrix(box, c) {
    const ids = members(c), cells = matrixCells(c), n = ids.length, MX = L.mx[st.mx];
    const W = width(box), Lw = 64, Tw = 64, cs = Math.max(8, Math.min(40, (W - Lw) / Math.max(1, n))), H = Tw + cs * n;
    const max = Math.max(1, ...Object.values(cells));
    let s = '';
    ids.forEach((i, k) => {
      s += `<text class="lb" x="${Lw - 6}" y="${Tw + k * cs + cs / 2 + 4}" text-anchor="end">${esc(name(i))}</text>`;
      s += `<text class="lb" transform="translate(${Lw + k * cs + cs / 2 + 4},${Tw - 6}) rotate(-90)">${esc(name(i))}</text>`;
    });
    ids.forEach((a, r) => ids.forEach((b, col) => {
      if (a === b) return;
      const v = cells[a + ',' + b] || 0;
      s += `<rect x="${Lw + col * cs + 1}" y="${Tw + r * cs + 1}" width="${cs - 2}" height="${cs - 2}" rx="2" fill="${v ? `rgba(${ZHU},${(0.06 + 0.94 * Math.sqrt(v / max)).toFixed(3)})` : 'rgba(28,25,21,.04)'}" data-tip="${esc(MX[2](name(a), name(b), fmt(v)))}"/>`;
    }));
    box.innerHTML = `<svg width="${Lw + cs * n}" height="${H}" viewBox="0 0 ${Lw + cs * n} ${H}" role="img" aria-label="${esc(MX[1])}">${s}</svg>`;
  }
  function topPairs(c) {
    const rows = Object.entries(matrixCells(c)).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).slice(0, 5);
    return rows.map(([k, v]) => { const [a, b] = k.split(',').map(Number); return `<li><span style="white-space:normal">${esc(L.mx[st.mx][2](name(a), name(b), fmt(v)))}</span></li>`; }).join('');
  }
  function interactSec(c) {
    const ids = members(c);
    const lat = ids.filter(i => c.p[i].med != null).sort((a, b) => c.p[a].med - c.p[b].med || a - b);
    const maxLat = Math.max(1, ...lat.map(i => c.p[i].med));
    const open = ids.filter(i => c.p[i].open).sort((a, b) => c.p[b].open - c.p[a].open || a - b).slice(0, 6);
    const latPanel = hidden('latency') ? '' : `<div class="panel"><h3>${L.lat}</h3><p class="cap">${L.latCap}</p>
        ${lat.length ? `<ul class="bars">${lat.map(i => `<li data-tip="${esc(L.latTip(name(i), c.p[i].med, c.p[i].medN))}"><span>${esc(name(i))}</span><i style="width:${100 * c.p[i].med / maxLat}%"></i><em>${L.mins(c.p[i].med)}</em></li>`).join('')}</ul>` : `<p class="empty">${L.few}</p>`}</div>`;
    return `<section id="s-interact"><div class="kicker"><h2>${L.inter}</h2><span>${L.interSub}</span></div>
      <div class="grid"><div class="panel wide"><div class="tabs" id="mxtabs">${Object.entries(L.mx).map(([k, [l]]) => `<button type="button" data-mx="${k}" aria-pressed="${st.mx === k}">${l}</button>`).join('')}</div>
        <p class="cap" id="mxcap">${L.mxCap(L.mx[st.mx][1])}</p><div class="mx" id="mx"></div>
        <ul class="phr" id="mxtop" style="margin-top:12px">${topPairs(c)}</ul></div>
      ${latPanel}
      <div class="panel"><h3>${L.open}</h3><p class="cap">${L.openCap}</p>
        ${open.length ? `<ul class="bars">${open.map(i => `<li data-tip="${esc(name(i))}: ${L.times(c.p[i].open)}"><span>${esc(name(i))}</span><i style="width:${100 * c.p[i].open / c.p[open[0]].open}%"></i><em>${L.times(fmt(c.p[i].open))}</em></li>`).join('')}</ul>` : `<p class="empty">${L.nil}</p>`}</div></div></section>`;
  }

  // ---------- 小团体关系图（确定性力导向：圆周起点，不用随机数，每次打开同一张图） ----------
  function layout(nodes, edges) {
    const n = nodes.length, pos = nodes.map((_, k) => [Math.cos(2 * Math.PI * k / n), Math.sin(2 * Math.PI * k / n)]);
    const idx = Object.fromEntries(nodes.map(([i], k) => [i, k]));
    const maxS = Math.max(...edges.map(e => e[3]), 0.01);
    for (let it = 0; it < 500; it++) {
      const f = pos.map(() => [0, 0]), temp = 0.08 * (1 - it / 500) + 0.002;
      for (let a = 0; a < n; a++) for (let b = a + 1; b < n; b++) {
        const dx = pos[a][0] - pos[b][0], dy = pos[a][1] - pos[b][1], d2 = dx * dx + dy * dy + 1e-4, k = 0.06 / d2;
        f[a][0] += dx * k; f[a][1] += dy * k; f[b][0] -= dx * k; f[b][1] -= dy * k;
      }
      for (const [i, j, , s] of edges) {
        const a = idx[i], b = idx[j], dx = pos[b][0] - pos[a][0], dy = pos[b][1] - pos[a][1], d = Math.sqrt(dx * dx + dy * dy) + 1e-6;
        const want = 0.35 + 0.9 * (1 - s / maxS), k = 0.5 * (s / maxS) * (d - want) / d;
        f[a][0] += dx * k; f[a][1] += dy * k; f[b][0] -= dx * k; f[b][1] -= dy * k;
      }
      pos.forEach((p, k) => {
        f[k][0] -= 0.05 * p[0]; f[k][1] -= 0.05 * p[1];
        const m = Math.hypot(f[k][0], f[k][1]), step = Math.min(m, temp) / (m || 1);
        p[0] += f[k][0] * step; p[1] += f[k][1] * step;
      });
    }
    return pos;
  }
  function drawGraph(box, c) {
    const { nodes, edges } = c.graph;
    if (nodes.length < 2) { box.innerHTML = `<p class="empty">${L.graphFew}</p>`; return; }
    const W = width(box), H = W < 500 ? 420 : 460, pad = 36, small = W < 500;
    const raw = layout(nodes, edges), xs = raw.map(p => p[0]), ys = raw.map(p => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const idx = Object.fromEntries(nodes.map(([i], k) => [i, k])), maxSeg = nodes[0][1];
    const rad = nodes.map(([, segs]) => (small ? 5 : 6) + (small ? 10 : 14) * Math.sqrt(segs / maxSeg));
    // 换到屏幕坐标后再把重叠的圆（连同头顶的名字）推开
    const pos = raw.map(([x, y]) => [pad + (W - 2 * pad) * (x - x0) / ((x1 - x0) || 1), pad + 10 + (H - 2 * pad - 10) * (y - y0) / ((y1 - y0) || 1)]);
    for (let it = 0; it < 200; it++) {
      for (let a = 0; a < pos.length; a++) for (let b = a + 1; b < pos.length; b++) {
        const dx = pos[b][0] - pos[a][0], dy = pos[b][1] - pos[a][1], d = Math.hypot(dx, dy) || 0.01, need = rad[a] + rad[b] + 18;
        if (d < need) { const m = (need - d) / 2 / d; pos[a][0] -= dx * m; pos[a][1] -= dy * m; pos[b][0] += dx * m; pos[b][1] += dy * m; }
      }
      pos.forEach((p, k) => { p[0] = Math.max(pad, Math.min(W - pad, p[0])); p[1] = Math.max(pad + rad[k], Math.min(H - rad[k] - 4, p[1])); });
    }
    const sc = edges.map(e => e[3]), sMax = Math.max(...sc), sMin = Math.min(...sc);
    let s = '';
    for (const [i, j, cnt, sco] of edges.slice().reverse()) {
      const a = pos[idx[i]], b = pos[idx[j]], t = (sco - sMin) / ((sMax - sMin) || 1);
      s += `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="rgba(${ZHU},${(0.18 + 0.6 * t).toFixed(2)})" stroke-width="${(1 + 5 * t).toFixed(1)}" stroke-linecap="round"/>`;
      s += `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="transparent" stroke-width="12" data-tip="${esc(L.edgeTip(name(i), name(j), fmt(cnt), sco))}"/>`;
    }
    nodes.forEach(([i, segs], k) => {
      const r = rad[k], x = pos[k][0], y = pos[k][1];
      s += `<g data-tip="${esc(L.nodeTip(name(i), fmt(segs)))}"><circle cx="${x}" cy="${y}" r="${r}" fill="${D.people[i].core ? 'var(--zhu)' : 'var(--c2)'}" stroke="var(--paper-hi)" stroke-width="2"/>
        <text x="${x}" y="${y - r - 5}" text-anchor="middle" paint-order="stroke" stroke="var(--paper-hi)" stroke-width="3">${esc(name(i))}</text></g>`;
    });
    box.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(L.graph)}">${s}</svg>`;
  }
  function graphSec() {
    if (hidden('graph')) return '';
    const core = esc(D.text.core_label || L.core), other = D.cfg.coreAll ? '' : esc(D.text.other_label || L.other);
    return `<section id="s-graph"><div class="kicker"><h2>${L.graph}</h2><span>${L.graphSub}</span></div>
      <div class="panel graph"><p class="cap">${L.graphCap(core, other)}</p><div id="graph"></div></div></section>`;
  }

  // ---------- 数据卡 ----------
  function cardHtml(c, i) {
    const p = c.p[i], ids = members(c), rank = ids.indexOf(i) + 1, T = L.dt;
    const row = (m, key) => { let best = null; for (const [a, b, v] of c[m]) { const [r, col] = key(a, b); if (r === i && (!best || v > best[1])) best = [col, v]; } return best; };
    const atTo = row('at', (a, b) => [a, b]), atFrom = row('at', (a, b) => [b, a]), nextTo = row('next', (a, b) => [b, a]);
    const ev = repeatEvents();
    const lead = ev.filter(e => e[3] === i).length, follow = ev.filter(e => e[4].includes(i)).length;
    let buddy = null;
    for (const [a, b, , s] of c.graph.edges) if ((a === i || b === i) && (!buddy || s > buddy[1])) buddy = [a === i ? b : a, s];
    const pic = p.t[1] + p.t[2], [na, nb] = D.cfg.night;
    const champs = boardsData(c).filter(b => b.ids[0] === i).map(b => b.t[0]);
    const ca = hidden('catch') ? [] : D.catch[i] || [], la = hidden('catch') ? [] : D.laugh[i] || [];
    const dd = (k, v, small = '') => `<div><dt>${k}</dt><dd>${v}${small ? `<small>${small}</small>` : ''}</dd></div>`;
    const gl = D.groups.length > 1 ? groupLabel(st.g) + ' · ' : '';
    return `<div class="card">${champs.length ? `<span class="seal">${esc(champs[0])}</span>` : ''}
      <h3>${esc(name(i))}</h3><p class="sub">${esc(gl)}${st.y === 'all' ? L.allYears : L.yearN(st.y)}${champs.length ? esc(L.champs(champs)) : ''}</p>
      <dl>${dd(T.n, L.msgs(fmt(p.n)), L.rankOf(rank, ids.length, pct(p.n, c.total)))}
        ${dd(T.days, L.days(fmt(p.days)), L.monthsN(p.months))}
        ${dd(T.streak, L.days(p.streak[0]), L.since(p.streak[1]))}
        ${dd(T.king, L.times(fmt(p.king)))}
        ${hidden('clock') ? '' : dd(T.peak, p.peak == null ? '—' : L.hourN(p.peak), L.nightShare(na, nb, pct(hoursShare(p.h, D.cfg.night), Math.max(1, sum(p.h)))))}
        ${dd(T.pic, L.pics(fmt(pic)), L.share(pct(pic, p.n)))}
        ${dd(T.atTo, atTo ? esc(name(atTo[0])) : '—', atTo ? L.times(atTo[1]) : '')}
        ${dd(T.atFrom, atFrom ? esc(name(atFrom[0])) : '—', atFrom ? L.times(atFrom[1]) : '')}
        ${dd(T.nextTo, nextTo ? esc(name(nextTo[0])) : '—', nextTo ? L.times(fmt(nextTo[1])) : '')}
        ${hidden('latency') ? '' : dd(T.med, p.med != null ? L.mins(p.med) : '—', p.med != null ? L.median : L.noSample)}
        ${dd(T.open, L.times(fmt(p.open)))}
        ${dd(T.rep, L.times(lead + follow), L.repDetail(lead, follow))}
        ${hidden('graph') ? '' : dd(T.buddy, buddy ? esc(name(buddy[0])) : '—', buddy ? L.closeness(buddy[1]) : '')}</dl>
      ${ca.length || la.length ? `<p class="says">${ca.length ? L.says + ca.slice(0, 3).map(([t]) => esc(L.q(t))).join('') : ''}${la.length ? `${ca.length ? L.sep : ''}${L.laughs}${esc(L.q(la[0][0]))}` : ''}</p>` : ''}</div>`;
  }
  function cardsSec(c) {
    const ids = members(c);
    if (!ids.length) return '';
    if (!ids.includes(st.who)) st.who = ids[0];
    return `<section id="s-cards"><div class="kicker"><h2>${L.cards}</h2><span>${L.cardsSub}</span></div>
      <div class="chips" id="chips">${ids.map(i => `<button type="button" data-who="${i}" aria-pressed="${i === st.who}">${esc(name(i))}</button>`).join('')}</div>
      <div id="card">${cardHtml(c, st.who)}</div></section>`;
  }

  // ---------- 总装 ----------
  function drawCharts(c) {
    drawTrend($('#trend')); drawHeat($('#heat'), c); drawMatrix($('#mx'), c);
    if ($('#graph')) drawGraph($('#graph'), c);
  }
  function render() {
    renderFilters();
    const c = combo(), main = $('#main');
    if (!c) { main.innerHTML = `<p class="status">${L.none}</p>`; return; }
    const last = D.groups.map(g => g.last).sort().pop();
    main.innerHTML = overview(c) + timeSec(c) + typesSec(c) + boardsSec(c) + repeatSec() + wordsSec() + interactSec(c) + graphSec() + cardsSec(c) +
      `<p class="note">${D.text.note ? esc(D.text.note) : L.note(last)}${(D.noTime || []).length ? ' ' + esc(L.noTime(D.noTime)) : ''}</p>`;
    drawCharts(c);
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b || !D) return;
    const c = combo();
    if (b.dataset.gran) { st.gran = b.dataset.gran; document.querySelectorAll('#gran button').forEach(x => x.setAttribute('aria-pressed', x === b)); drawTrend($('#trend')); $('#trendcap').textContent = L.trendCap(L.unitOf[st.gran]); }
    if (b.dataset.mx) { st.mx = b.dataset.mx; document.querySelectorAll('#mxtabs button').forEach(x => x.setAttribute('aria-pressed', x === b)); $('#mxcap').textContent = L.mxCap(L.mx[st.mx][1]); drawMatrix($('#mx'), c); $('#mxtop').innerHTML = topPairs(c); }
    if (b.dataset.who) { st.who = Number(b.dataset.who); document.querySelectorAll('#chips button').forEach(x => x.setAttribute('aria-pressed', x === b)); $('#card').innerHTML = cardHtml(c, st.who); }
  });
  let lastW = innerWidth, timer;
  addEventListener('resize', () => { clearTimeout(timer); timer = setTimeout(() => { if (D && innerWidth !== lastW && combo()) { lastW = innerWidth; drawCharts(combo()); } }, 150); });

  const start = d => { D = d; L = I18N[d.lang] || I18N.zh; render(); };
  const fail = () => { L = L || I18N[document.documentElement.lang === 'en' ? 'en' : 'zh']; $('#status').innerHTML = L.failed; };
  const inline = document.getElementById('data');
  if (inline && inline.textContent.trim()) {
    try { start(JSON.parse(inline.textContent)); } catch (err) { console.error(err); fail(); }
  } else {
    fetch(document.documentElement.dataset.stats, { credentials: 'same-origin' })
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(start)
      .catch(err => { console.error(err); fail(); });
  }
})();
