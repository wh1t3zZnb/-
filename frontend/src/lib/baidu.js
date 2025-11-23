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
  const msg = (data?.choices?.[0]?.message) || {};
  const summary = String(msg?.content || '').trim();
  let refs = Array.isArray(msg?.references) ? msg.references : [];
  if (!refs?.length && Array.isArray(data?.references)) refs = data.references;

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

export async function aiSearch(query, { apiUrl, model = 'ERNIE-4.0-mini', topK = 10, sites = null } = {}) {
  if (!query?.trim()) return { items: [], summary: '' };
  if (!apiUrl?.trim()) throw new Error('API URL is required');
  const base = buildPayload(query, { model, topK, sites });
  const body = { service: 'baidu', ...base };
  const res = await fetch(apiUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    throw new Error(`Baidu AI Search Error: ${res.status} ${errText}`);
  }
  const data = await res.json();
  return parseItemsAndSummary(data, topK);
}