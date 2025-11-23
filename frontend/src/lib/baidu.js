/**
 * Baidu AI Search Chat Completions (V2)
 * Pure frontend implementation. Requires BAIDU_AI_SEARCH_APIKEY provided by user.
 */

function buildPayload(query, { model = 'deepseek-r1', topK = 10, sites = null } = {}) {
  const k = Math.max(1, Math.min(parseInt(topK || 10, 10), 20));
  const payload = {
    messages: [{ role: 'user', content: query }],
    stream: false,
    model,
    search_source: 'baidu_search_v2',
    resource_type_filter: [{ type: 'web', top_k: k }],
    enable_corner_markers: true,
  };
  if (Array.isArray(sites) && sites.length) {
    payload.search_filter = { match: { site: sites.slice(0, 5) } };
  }
  return payload;
}


function parseItemsAndSummary(data, topK) {
  const k = Math.max(1, Math.min(parseInt(topK || 10, 10), 20));
  let refs = Array.isArray(data?.references) ? data.references : [];
  if (!refs?.length && Array.isArray(data?.choices?.[0]?.message?.references)) {
    refs = data.choices[0].message.references;
  }
  const summary = '';

  const blockedDomains = new Set(['baidu.com', 'www.baidu.com', 'image.baidu.com', 'v.baidu.com']);
  const blockedPatterns = ['image.baidu.com', '/image', '/img', '/video', '/vod', 'v.qq.com', 'tv.'];
  const items = [];
  for (const it of (refs || [])) {
    const url = it.url || it.href || '';
    const title = it.title || it.name || '来源';
    if (!url) continue;
    const src = (() => {
      try { return new URL(url).hostname.toLowerCase(); } catch { return ''; }
    })();
    if (blockedDomains.has(src)) continue;
    if (blockedPatterns.some(p => url.toLowerCase().includes(p))) continue;
    items.push({ title, href: url, body: '', source: src || 'baidu.ai' });
    if (items.length >= k) break;
  }
  return { items, summary };
}

export async function aiSearch(query, { apiUrl, model = 'ERNIE-4.0-mini', topK = 10, sites = null, modelCandidates = [] } = {}) {
  if (!query?.trim()) return { items: [], summary: '' };
  if (!apiUrl?.trim()) throw new Error('API URL is required');
  const candidates = Array.isArray(modelCandidates) && modelCandidates.length ? modelCandidates : [model, 'ERNIE-3.5', 'ERNIE-Speed-128k'];
  let lastErr = '';
  for (const m of candidates) {
    const base = buildPayload(query, { model: m, topK, sites });
    const body = { service: 'baidu', ...base };
    try {
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const errText = await res.text().catch(() => '');
        lastErr = `Baidu AI Search Error: ${res.status} ${errText}`;
        continue;
      }
      const data = await res.json();
      return parseItemsAndSummary(data, topK);
    } catch (e) {
      lastErr = e?.message || String(e);
      continue;
    }
  }
  throw new Error(lastErr || 'Baidu AI Search failed');
}