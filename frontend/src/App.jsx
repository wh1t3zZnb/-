import { useState, useEffect, useRef } from 'react'
import { Activity, Download, Search, Terminal, FileText, ExternalLink } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { runAnalysisFlow } from './lib/orchestrator'

function App() {
  const [query, setQuery] = useState('')
  const [apiUrl] = useState(localStorage.getItem('api_url') || '')
  const [baiduModel] = useState(localStorage.getItem('baidu_model') || 'ERNIE-4.0-mini')
  const [version] = useState('0.3.2-frontend-ai')
  const [logs, setLogs] = useState([])
  const [summary, setSummary] = useState('')
  const [detailedReport, setDetailedReport] = useState('')
  const [items, setItems] = useState([])
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')
  const [showResult, setShowResult] = useState(false)

  const logEndRef = useRef(null)

  useEffect(() => {
    localStorage.setItem('api_url', apiUrl)
  }, [apiUrl])



  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  const appendLog = (text) => {
    const d = new Date()
    const p = (x) => String(x).padStart(2, '0')
    const time = `[${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}]`
    setLogs(prev => [...prev, `${time} > ${text}`])
  }

  const start = async () => {
    if (!query.trim()) {
      setError('请填写查询主题')
      return
    }
    if (!apiUrl.trim()) {
      setError('请填写 Cloudflare Worker 接口地址')
      return
    }
    setError('')
    setLogs([])
    setSummary('')
    setDetailedReport('')
    setItems([])
    setShowResult(false)
    setIsBusy(true)

    appendLog('查询主题：' + query)
    appendLog('模式：Workers 接口（百度检索 + 豆包生成）')

    let phase = 'init'

    try {
      for await (const ev of runAnalysisFlow(query, { apiUrl, model: 'doubao-seed-1-6-251015', service: 'volc', baiduModel })) {
        switch (ev.type) {
          case 'planning':
            appendLog('规划：时间窗 ' + (ev.plan.timelimit || 'm') + '，RSS ' + (ev.plan.use_rss ? '启用' : '关闭'))
            break

          case 'baidu_search_start':
            appendLog('百度检索：开始')
            break

          case 'baidu_search_ok':
            appendLog('百度检索：成功，材料数量 ' + (ev.items || 0))
            break

          case 'baidu_search_failed':
            appendLog('百度检索：失败，原因 ' + ev.message)
            break

          case 'doubao_gate':
            break

          case 'filter':
            appendLog('阶段：' + phase + ' → 筛选：本轮通过 ' + ev.accepted_this_round)
            break

          case 'filter_rejects':
            appendLog('筛选：被驳回 ' + ev.count)
            break

          case 'filter_detail':
            appendLog('筛选详情：通过 ' + ev.accepted + '，驳回 ' + ev.rejected)
            break

          case 'filter_reject_samples':
            if (Array.isArray(ev.samples) && ev.samples.length) {
              ev.samples.forEach((s, i) => appendLog('被驳回示例 ' + (i + 1) + '：' + (s.title || '') + (s.source ? '（' + s.source + '）' : '')))
            }
            break

          case 'fetch':
            appendLog('阶段：' + phase + ' → 抓取全文：成功 ' + ev.success + '，失败 ' + ev.fail)
            break

          case 'fetch_item_ok':
            appendLog('抓取成功：' + ev.title)
            break

          case 'fetch_item_fail':
            appendLog('抓取失败：' + ev.title + '（' + (ev.message || '未知原因') + '）')
            break

          case 'phase_change':
            appendLog('阶段：' + phase + ' → ' + ev.to)
            phase = ev.to || phase
            break

          case 'final':
            setIsBusy(false)
            setShowResult(true)
            if (ev.summary) setSummary(ev.summary)
            if (ev.detailed_report) setDetailedReport(ev.detailed_report)
            if (Array.isArray(ev.items)) setItems(ev.items)
            appendLog('完成：共输出 ' + (ev.items ? ev.items.length : 0) + ' 条代表材料')
            break

          case 'error':
            appendLog('错误：' + ev.message)
            setError(ev.message)
            setIsBusy(false)
            break

          default:
            appendLog('事件：' + (ev.type || 'unknown'))
        }
      }
    } catch (err) {
      console.error(err)
      appendLog('运行时错误：' + err.message)
      setError(err.message)
      setIsBusy(false)
    }
  }

  const exportMarkdown = () => {
    const title = '# 舆情报告：' + (query || '查询')
    const ts = new Date()
    const p = (x) => String(x).padStart(2, '0')
    const tstr = ts.getFullYear() + '-' + p(ts.getMonth() + 1) + '-' + p(ts.getDate()) + ' ' + p(ts.getHours()) + ':' + p(ts.getMinutes())
    const summaryText = summary ? ('\n\n## 快速摘要\n' + summary) : ''
    const detailText = detailedReport ? ('\n\n## 详细分析报告\n' + detailedReport) : ''
    let refs = ''
    if (items.length) {
      refs = '\n\n## 代表材料\n'
      items.forEach((it, idx) => {
        const line = `${idx + 1}. ${it.title || it.href || ''}\n   来源：${it.source || ''}  链接：${it.href || ''}`
        refs += (line + '\n')
      })
    }
    const md = `${title}\n\n> 生成时间：${tstr}${summaryText}${detailText}${refs}`
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `舆情报告-${(query || '查询')}-${p(ts.getMonth() + 1)}${p(ts.getDate())}${p(ts.getHours())}${p(ts.getMinutes())}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="container">
      <div className="title flex items-center gap-2">
        <Activity className="w-6 h-6 text-primary" style={{ color: 'var(--primary-color)' }} />
        舆情分析 MVP (Pure Frontend) v{version}
      </div>

      {error && <div className="error">{error}</div>}

      <div className="panel">

        <div className="form-group mt-4">
          <label className="block mb-2 font-medium">请输入你的问题（示例：王家卫最近风评如何？）</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !isBusy && start()}
              placeholder="例如：某事件的舆情怎么看？"
              className="flex-1 input-primary"
              disabled={isBusy}
            />
            <button onClick={start} disabled={isBusy} className="flex items-center gap-2 whitespace-nowrap btn-primary">
              {isBusy ? <div className="spinner"></div> : <Search size={18} />}
              {isBusy ? '分析中...' : '开始分析'}
            </button>
          </div>
        </div>
        {isBusy && (
          <div className="muted mt-2 flex items-center">
            <span className="spinner"></span> 正在执行，请稍候…（过程可视化如下）
          </div>
        )}
      </div>

      {(isBusy || logs.length > 0) && (
        <div id="progressPanel" className="panel">
          <div className="muted mb-2 flex items-center gap-2" style={{ color: '#9aa0a6' }}>
            <Terminal size={16} /> 执行过程（CMD风格）
          </div>
          <div className="log">
            {logs.map((log, i) => (
              <div key={i} className="step">{log}</div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {showResult && (
        <div id="resultPanel" className="panel animate-fade-in">
          <div className="muted mb-4">结果</div>

          {summary && (
            <>
              <h3>【快速摘要】</h3>
              <div className="markdown">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" />,
                  }}
                >
                  {summary}
                </ReactMarkdown>
              </div>
            </>
          )}

          {detailedReport && (
            <>
              <h3>【详细分析报告】</h3>
              <div className="markdown report">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" />,
                  }}
                >
                  {detailedReport}
                </ReactMarkdown>
              </div>
              <div className="mt-4">
                <button onClick={exportMarkdown} className="flex items-center gap-2 btn-secondary" style={{ backgroundColor: 'var(--surface-color)', color: 'var(--primary-color)', border: '1px solid var(--border-color)' }}>
                  <Download size={18} /> 导出 Markdown
                </button>
              </div>
            </>
          )}

          {items.length > 0 && (
            <>
              <h3>代表材料</h3>
              <div className="items">
                {items.map((it, idx) => (
                  <div key={idx} className="item">
                    <a href={it.href || '#'} target="_blank" rel="noopener noreferrer" className="flex items-start gap-2">
                      <span className="min-w-[20px]">{idx + 1}.</span>
                      <span className="break-all">{it.title || it.href}</span>
                      <ExternalLink size={14} className="mt-1 shrink-0 opacity-50" />
                    </a>
                    {it.source && (
                      <span className="muted ml-6 block mt-1">({it.source})</span>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default App
