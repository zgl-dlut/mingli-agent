import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'

const ARTIFACT_DIR = path.resolve(process.cwd(), '../../.trae/documents/artifacts/v3-mvp')
const PHONE = '13800138000'
let authToken = ''

async function login(page: Page) {
  const sms = await page.request.post('/api/auth/send-sms', { data: { phone: PHONE } })
  expect(sms.ok()).toBeTruthy()
  const smsBody = await sms.json()
  const auth = await page.request.post('/api/auth/login', {
    data: { phone: PHONE, code: smsBody.code || '111111' },
  })
  expect(auth.ok()).toBeTruthy()
  const data = await auth.json()
  await page.goto('/login')
  await page.evaluate(
    ({ token, user }) => {
      localStorage.setItem('mingli_token', token)
      localStorage.setItem('mingli_user', JSON.stringify(user))
    },
    {
      token: data.access_token,
      user: {
        id: data.user_id,
        phone: data.phone,
        name: data.name,
        avatar: null,
        points: data.points,
        created_at: new Date().toISOString(),
      },
    },
  )
  return data.access_token as string
}

function authHeaders() {
  return { Authorization: `Bearer ${authToken}` }
}

async function expectNoHorizontalOverflow(page: Page) {
  const result = await page.evaluate(() => ({
    body: document.body.scrollWidth <= document.body.clientWidth + 1,
    overflowing: [...document.querySelectorAll('main *')].filter(
      (element) => element.scrollWidth > element.clientWidth + 1,
    ).length,
  }))
  expect(result.body).toBeTruthy()
  expect(result.overflowing).toBe(0)
}

async function screenshot(page: Page, project: string, name: string) {
  await expectNoHorizontalOverflow(page)
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, `${name}-${project}.png`),
    fullPage: false,
  })
}

test.beforeEach(async ({ page }) => {
  authToken = await login(page)
})

test('V3 navigation, reports, persona safety and subscription states', async ({ page }, testInfo) => {
  const project = testInfo.project.name
  await page.request.post('/api/subscriptions/mock-expire', {
    headers: authHeaders(),
  })

  await page.goto('/today')
  await expect(page.getByText('今日能量状态')).toBeVisible()
  await expect(page.getByRole('navigation').getByRole('button')).toHaveCount(4)
  const todayText = await page.locator('main').innerText()
  for (const term of ['吉', '凶', '宜', '忌', '改运', '化解']) {
    expect(todayText).not.toContain(term)
  }
  await screenshot(page, project, '01-today-rhythm')

  await page.goto('/reading')
  await expect(page.getByRole('heading', { name: '解读' })).toBeVisible()
  await expect(page.getByText('基础解读')).toBeVisible()
  await screenshot(page, project, '02-reading-home')

  const persons = await page.request.get('/api/persons', { headers: authHeaders() })
  const personList = await persons.json()
  expect(personList.length).toBeGreaterThan(0)
  const primaryPersonId = personList[0].id
  const imported = await page.request.post('/api/reports/import-legacy', {
    headers: authHeaders(),
  })
  expect(imported.ok()).toBeTruthy()
  const reports = await page.request.get('/api/reports?page_size=100', {
    headers: authHeaders(),
  })
  const reportList = await reports.json()
  expect(reportList.items.length).toBeGreaterThan(0)
  const reportPersonId = reportList.items[0].primary_person_id
  await page.goto(`/reading/reports?person_id=${reportPersonId}`)
  await expect(page.getByRole('heading', { name: '报告库' })).toBeVisible()
  await expect(page.getByText('正在整理报告…')).toBeHidden()
  await expect(page.getByText('已完成').first()).toBeVisible()
  await screenshot(page, project, '03-report-library')

  await page.goto('/subscription?required=light')
  await expect(page.getByRole('heading', { name: '订阅权益' })).toBeVisible()
  await expect(page.getByText('当前内容需要升级订阅后查看。')).toBeVisible()
  await screenshot(page, project, '04-free-subscription-wall')

  const activate = await page.request.post('/api/subscriptions/mock-activate', {
    headers: authHeaders(),
    data: { plan_code: 'full', billing_cycle: 'monthly' },
  })
  expect(activate.ok()).toBeTruthy()
  await page.reload()
  await expect(page.getByText('当前计划')).toBeVisible()
  await screenshot(page, project, '05-full-subscription')

  let personasResponse = await page.request.get('/api/personas', { headers: authHeaders() })
  let personas = await personasResponse.json()
  if (personas.length === 0) {
    const selfPerson = personList.find((person: { is_self: boolean }) => person.is_self)
    expect(selfPerson).toBeTruthy()
    const created = await page.request.post('/api/personas', {
      headers: authHeaders(),
      data: { person_id: selfPerson.id },
    })
    expect(created.ok()).toBeTruthy()
    personasResponse = await page.request.get('/api/personas', { headers: authHeaders() })
    personas = await personasResponse.json()
  }
  const personaId = personas[0].persona_id
  await page.goto('/persona')
  await expect(page.getByText('AI 生成 · 命局人格模拟')).toBeVisible()
  await screenshot(page, project, '06-persona-home')

  let conversations = await (
    await page.request.get(`/api/personas/${personaId}/conversations`, { headers: authHeaders() })
  ).json()
  if (conversations.length === 0) {
    const created = await page.request.post(`/api/personas/${personaId}/conversations`, {
      headers: authHeaders(),
      data: {},
    })
    expect(created.ok()).toBeTruthy()
    conversations = [await created.json()]
  }
  const conversationId = conversations[0].conversation_id
  const messages = await page.request.get(`/api/persona-conversations/${conversationId}/messages`, {
    headers: authHeaders(),
  })
  const messageData = await messages.json()
  if (!messageData.items.some((item: { safety_category: string | null }) => item.safety_category === 'crisis')) {
    const crisis = await page.request.post(`/api/persona-conversations/${conversationId}/messages`, {
      headers: authHeaders(),
      data: { content: '我不想活了' },
    })
    expect(crisis.ok()).toBeTruthy()
  }
  await page.goto(`/persona/chat/${conversationId}`)
  await expect(page.getByText('我先退出命局人格的角色。', { exact: false })).toBeVisible()
  await expect(page.getByText('0/20')).toBeVisible()
  await screenshot(page, project, '07-persona-crisis')

  await page.goto(`/persona/${personaId}/memory`)
  await expect(page.getByRole('heading', { name: '人格记忆' })).toBeVisible()
  await screenshot(page, project, '08-persona-memory')

  await page.goto(`/chat/${primaryPersonId}`)
  await expect(page).toHaveURL(new RegExp(`/reading/chat/${primaryPersonId}$`))
})
