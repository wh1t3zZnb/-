import { callLLM } from './llm';
import { aiSearch } from './baidu';

export async function* runAnalysisFlow(query, { apiUrl, model = 'doubao-seed-1-6-251015', service = 'volc', baiduModel = 'ERNIE-4.0-mini' } = {}) {
  yield { type: 'planning', plan: { timelimit: 'm', use_rss: true }, version: '0.6.0-workers' };

  yield { type: 'baidu_search_start' };
  let items = [];
  let brief = '';
  try {
    const { items: found, summary } = await aiSearch(query, { apiUrl, model: baiduModel, topK: 10, modelCandidates: [baiduModel, 'ERNIE-3.5', 'ERNIE-Speed-128k'] });
    items = Array.isArray(found) ? found : [];
    brief = String(summary || '').trim();
    yield { type: 'baidu_search_ok', items: items.length };
  } catch (e) {
    items = [];
    brief = '';
    yield { type: 'baidu_search_failed', message: e.message || 'Baidu AI 搜索失败' };
  }

  yield { type: 'phase_change', to: 'filter' };
  const kw = String(query || '').toLowerCase().split(/\s+/).filter(Boolean);
  const accepted = [];
  const rejected = [];
  for (const it of items) {
    const t = String(it.title || '').toLowerCase();
    const s = String(it.source || '').toLowerCase();
    const hit = kw.length ? kw.some(k => t.includes(k)) : true;
    const bad = ['baidu.com', 'image.baidu.com', 'v.baidu.com'].some(x => s.includes(x));
    if (hit && !bad) accepted.push(it); else rejected.push(it);
  }
  yield { type: 'filter', accepted_this_round: accepted.length };
  if (rejected.length) yield { type: 'filter_rejects', count: rejected.length };
  yield { type: 'filter_detail', accepted: accepted.length, rejected: rejected.length };
  if (rejected.length) {
    const samples = rejected.slice(0, 3).map(it => ({ title: it.title || it.href || '', source: it.source || '' }));
    yield { type: 'filter_reject_samples', samples };
  }

  const fetchUrl = (() => {
    try { return apiUrl.replace('/api/chat', '/api/fetch'); } catch { return apiUrl; }
  })();
  let success = 0, fail = 0;
  const cleaned = [];
  const strip = (html) => String(html || '').replace(/<script[\s\S]*?<\/script>/gi,'').replace(/<style[\s\S]*?<\/style>/gi,'').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
  yield { type: 'phase_change', to: 'fetch' };
  for (const it of accepted) {
    try {
      const res = await fetch(fetchUrl, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'text/plain' }, body: JSON.stringify({ url: it.href || it.url }) });
      if (!res.ok) throw new Error('fetch_fail_' + res.status);
      const html = await res.text();
      const text = strip(html).slice(0, 4000);
      cleaned.push({ ...it, body: text });
      success++;
      yield { type: 'fetch_item_ok', title: it.title || it.href };
    } catch (e) {
      fail++;
      yield { type: 'fetch_item_fail', title: it.title || it.href, message: e?.message || 'fetch_failed' };
    }
  }
  yield { type: 'fetch', success, fail };

  let report = '';
  try {
    const refsText = cleaned.map((it, i) => `${i + 1}. ${it.title || it.href} ${it.href || ''}`).join('\n');
    const messages = [
      { role: 'system', content: '你是专业的舆情分析报告撰写专家。' },
      { role: 'user', content: `请按Markdown结构撰写《舆情分析报告》，主题：${query}。以下是参考材料链接（可用于提取要点与论证）：\n${refsText || '（未使用百度材料，本报告为直出）'}` }
    ];
    yield { type: 'phase_change', to: 'llm' };
    report = await callLLM(apiUrl, messages, model, service);
  } catch (e) {
    report = '';
    yield { type: 'error', message: e.message || 'LLM 生成报告失败' };
  }

  yield { type: 'final', summary: brief, detailed_report: report, items: cleaned };
}
