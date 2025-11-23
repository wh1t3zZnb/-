import { callLLM } from './llm';

export async function* runAnalysisFlow(query, { apiUrl, model = 'qwen-plus' } = {}) {
  yield { type: 'planning', plan: { timelimit: 'm', use_rss: false }, version: '0.4.0-workers' };
  let brief = '';
  let report = '';
  try {
    brief = await callLLM(apiUrl, [
      { role: 'system', content: '只输出简要摘要。' },
      { role: 'user', content: `请给主题【${query}】写一段100字内的摘要。` }
    ], model);
  } catch {
    brief = ''
  }
  try {
    report = await callLLM(apiUrl, [
      { role: 'system', content: '你是专业的舆情分析报告撰写专家。' },
      { role: 'user', content: `请按Markdown结构撰写《舆情分析报告》，主题：${query}` }
    ], model);
  } catch {
    report = ''
  }
  yield { type: 'final', summary: brief, detailed_report: report, items: [] };
}
