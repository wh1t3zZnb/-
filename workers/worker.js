export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    const path = url.pathname.replace(/\/+$/,'')
    const origin = request.headers.get('Origin') || ''
    const allowOrigin = 'https://wh1t3zznb.github.io'
    const setCORS = (h) => {
      h.set('Access-Control-Allow-Origin', origin === allowOrigin ? allowOrigin : 'null')
      h.set('Vary', 'Origin')
      h.set('Access-Control-Allow-Methods', 'POST,OPTIONS')
      h.set('Access-Control-Allow-Headers', 'Content-Type, Accept')
    }
    if (request.method === 'OPTIONS') {
      const h = new Headers(); setCORS(h)
      return new Response('', { status: 200, headers: h })
    }
    if (request.method === 'POST' && (path === '/api/chat')) {
      let payload = {}; try { payload = await request.json() } catch {}
      let resp
      const svcRaw = Reflect.get(Object(payload), 'service');
      const svc = typeof svcRaw === 'string' ? svcRaw.toLowerCase() : String(svcRaw || '').toLowerCase();
      if (svc === 'baidu') {
        const bkey = env.BAIDU_API_KEY
        if (!bkey) {
          const h = new Headers({ 'Content-Type': 'application/json' }); setCORS(h)
          return new Response(JSON.stringify({ error: 'missing_baidu_api_key' }), { status: 401, headers: h })
        }
        const body = (() => { const o = { ...payload }; Reflect.deleteProperty(o, 'service'); return o })();
        const endpoint = 'https://qianfan.baidubce.com/v2/ai_search/web_search';
        let scheme = 'authorization_bearer';
        resp = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': `Bearer ${bkey}`
          },
          body: JSON.stringify(body)
        });
        if (resp.status === 401) {
          scheme = 'x_appbuilder_authorization';
          resp = await fetch(endpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
              'X-Appbuilder-Authorization': `Bearer ${bkey}`
            },
            body: JSON.stringify(body)
          });
        }
        if (resp.status === 401) {
          scheme = 'access_token_query';
          const urlWithToken = 'https://qianfan.baidubce.com/v2/ai_search/web_search?access_token=' + encodeURIComponent(bkey);
          resp = await fetch(urlWithToken, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json'
            },
            body: JSON.stringify(body)
          });
        }
        if (!resp.ok) {
          const text = await resp.text().catch(() => '');
          let data = {}; try { data = JSON.parse(text) } catch {}
          const h = new Headers({ 'Content-Type': 'application/json' }); setCORS(h)
          return new Response(JSON.stringify({ error: data?.error || { message: text || 'baidu_upstream_error' }, request_id: data?.id || data?.request_id || null, scheme_tried: scheme }), { status: resp.status, headers: h })
        }
      } else {
        const apiKey = env.VOLC_API_KEY
        if (!apiKey) {
          const h = new Headers({ 'Content-Type': 'application/json' }); setCORS(h)
          return new Response(JSON.stringify({ error: 'missing_api_key' }), { status: 401, headers: h })
        }
        const body = (() => { const o = { ...payload }; Reflect.deleteProperty(o, 'service'); return o })();
        resp = await fetch('https://ark.cn-beijing.volces.com/api/v3/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': `Bearer ${apiKey}`
          },
          body: JSON.stringify(body)
        })
      }
      const text = await resp.text()
      const h = new Headers({ 'Content-Type': 'application/json' }); setCORS(h)
      return new Response(text, { status: resp.status, headers: h })
    }
    const h = new Headers({ 'Content-Type': 'application/json' }); setCORS(h)
    return new Response(JSON.stringify({ error: 'not_found', path }), {
      status: 404, headers: h
    })
  }
}