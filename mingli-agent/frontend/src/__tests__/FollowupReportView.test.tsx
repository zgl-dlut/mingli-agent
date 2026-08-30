/**
 * FollowupReportView 组件单元测试
 *
 * 直接测试 renderBold 和 isStructuredReport 的行为
 * 覆盖加粗解析、换行处理、JSON判断等边界条件
 */
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { renderBold, isStructuredReport } from '../components/FollowupReportView'

/** 将 renderBold 的返回值渲染为 HTML，方便查询 DOM */
function renderText(text: string) {
  const { container } = render(<>{renderBold(text)}</>)
  return container
}

describe('renderBold 加粗解析', () => {

  // ============================================================
  // 加粗标记
  // ============================================================

  it('① 无加粗标记，普通文本正常渲染', () => {
    const container = renderText('普通文本无加粗')
    expect(container.textContent).toContain('普通文本无加粗')
    expect(container.querySelectorAll('strong').length).toBe(0)
  })

  it('② 单个**加粗**标记渲染为<strong>', () => {
    const container = renderText('**重要**文本')
    const strongs = container.querySelectorAll('strong')
    expect(strongs.length).toBe(1)
    expect(strongs[0].textContent).toBe('重要')
  })

  it('③ 多个**加粗**标记全部渲染', () => {
    const container = renderText('**第一**和**第二**')
    const strongs = container.querySelectorAll('strong')
    expect(strongs.length).toBe(2)
    expect(strongs[0].textContent).toBe('第一')
    expect(strongs[1].textContent).toBe('第二')
  })

  it('④ 加粗标记在开头 **加粗**后面', () => {
    const container = renderText('**开头加粗**后面文字')
    const strong = container.querySelector('strong')
    expect(strong?.textContent).toBe('开头加粗')
  })

  it('⑤ 加粗标记在结尾 前面**加粗**', () => {
    const container = renderText('前面文字**结尾加粗**')
    const strong = container.querySelector('strong')
    expect(strong?.textContent).toBe('结尾加粗')
  })

  it('⑥ 未闭合的加粗 **加粗 不渲染为strong', () => {
    const container = renderText('未闭合**加粗')
    const strongs = container.querySelectorAll('strong')
    expect(strongs.length).toBe(0)
    expect(container.textContent).toContain('未闭合')
  })

  it('⑦ 空加粗 **** 不渲染为strong', () => {
    const container = renderText('前面****后面')
    const strongs = container.querySelectorAll('strong')
    expect(strongs.length).toBe(0)
  })

  it('⑧ 连续加粗 **a****b**', () => {
    const container = renderText('**a****b**')
    const strongs = container.querySelectorAll('strong')
    expect(strongs.length).toBe(2)
    expect(strongs[0].textContent).toBe('a')
    expect(strongs[1].textContent).toBe('b')
  })

  it('⑨ 加粗内容含特殊字符 **2026-2027年**', () => {
    const container = renderText('**2026-2027年**')
    const strong = container.querySelector('strong')
    expect(strong?.textContent).toBe('2026-2027年')
  })

  // ============================================================
  // 换行处理
  // ============================================================

  it('⑩ 普通文本含\\n换行渲染为<br/>', () => {
    const container = renderText('第一行\n第二行')
    expect(container.querySelectorAll('br').length).toBe(1)
  })

  it('⑪ 加粗标记内含换行 **第一行\\n第二行**', () => {
    const container = renderText('**第一行\n第二行**')
    const strong = container.querySelector('strong')
    expect(strong?.textContent).toContain('第一行')
    expect(strong?.textContent).toContain('第二行')
  })

  it('⑫ 空字符串不崩溃', () => {
    const container = renderText('')
    expect(container).toBeTruthy()
  })
})


describe('isStructuredReport JSON判断', () => {

  /** 构造最小报告JSON */
  function buildReport(overrides: Record<string, any> = {}): string {
    const base = {
      opening: { lead: '测试开篇', verdict: '测试结论' },
      subtopics: [
        { title: '子问题1', blocks: [
          { type: 'keyword', keyword: '关键词', narrative: '描述内容' }
        ]}
      ],
      summary: { title: '总结', items: [{ keyword: '阶段', text: '描述' }] },
      ...overrides,
    }
    return JSON.stringify(base)
  }

  // ============================================================
  // 合法 JSON 报告
  // ============================================================

  it('① JSON格式报告返回true', () => {
    expect(isStructuredReport(buildReport())).toBe(true)
  })

  it('② Markdown格式返回false', () => {
    expect(isStructuredReport('## 一、标题\n\n**关键词**：描述')).toBe(false)
  })

  it('③ 空字符串返回false', () => {
    expect(isStructuredReport('')).toBe(false)
  })

  it('④ 无效JSON返回false', () => {
    expect(isStructuredReport('{invalid json')).toBe(false)
  })

  it('⑤ 缺少opening字段返回false', () => {
    const json = JSON.stringify({ subtopics: [], summary: { title: 'x' } })
    expect(isStructuredReport(json)).toBe(false)
  })

  it('⑥ 缺少subtopics字段返回false', () => {
    const json = JSON.stringify({ opening: {}, summary: { title: 'x' } })
    expect(isStructuredReport(json)).toBe(false)
  })

  it('⑦ 缺少summary字段返回false', () => {
    const json = JSON.stringify({ opening: {}, subtopics: [] })
    expect(isStructuredReport(json)).toBe(false)
  })

  it('⑧ JSON前有空白仍能识别', () => {
    expect(isStructuredReport('  \n  ' + buildReport())).toBe(true)
  })

  it('⑨ JSON数组（非对象）返回false', () => {
    expect(isStructuredReport('[1,2,3]')).toBe(false)
  })

  it('⑩ JSON字符串值（非对象）返回false', () => {
    expect(isStructuredReport('"hello"')).toBe(false)
  })
})
