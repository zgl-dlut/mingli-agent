import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { subscriptionApi, type SubscriptionPlan } from '../api/subscription'
import type { PlanCode } from '../api/entitlement'
import { useEntitlementStore } from '../store/entitlementStore'
import { color, radius } from '../theme/tokens'

export default function SubscriptionPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { entitlement, fetchEntitlement, setEntitlement } = useEntitlementStore()
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
  const [activating, setActivating] = useState<PlanCode | null>(null)
  const required = searchParams.get('required')

  useEffect(() => {
    void Promise.all([
      subscriptionApi.getPlans().then(({ data }) => setPlans(data)),
      fetchEntitlement(),
    ])
  }, [fetchEntitlement])

  const activate = async (planCode: 'light' | 'full') => {
    setActivating(planCode)
    try {
      const { data } = await subscriptionApi.mockActivate(planCode)
      setEntitlement(data.entitlement)
    } catch (error: any) {
      alert(error?.response?.data?.message || error?.response?.data?.detail || '模拟开通失败')
    } finally {
      setActivating(null)
    }
  }

  return (
    <div className="px-4 pb-8">
      <div className="flex items-center mb-4">
        <button onClick={() => navigate(-1)} aria-label="返回" className="w-8 text-xl" style={{ color: color.ink }}>‹</button>
        <h1 className="m-0 flex-1 text-center text-lg font-bold" style={{ color: color.ink }}>订阅权益</h1>
        <span className="w-8" />
      </div>
      {required && (
        <div className="mb-3 px-3 py-2.5 text-xs" style={{ color: color.gold, backgroundColor: '#F8F0DF', borderRadius: '10px' }}>
          当前内容需要升级订阅后查看。
        </div>
      )}
      <div className="space-y-3">
        {plans.map((plan) => {
          const active = entitlement?.plan_code === plan.plan_code
          return (
            <section
              key={plan.plan_code}
              className="p-4"
              style={{
                backgroundColor: color.card,
                borderRadius: radius.card,
                border: active ? `1.5px solid ${color.brand}` : `1px solid ${color.divider}`,
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-base font-bold" style={{ color: color.ink }}>{plan.name}</div>
                  <div className="mt-1 text-xs" style={{ color: color.ink2 }}>
                    {plan.monthly_price_yuan === 0 ? '基础体验' : `¥${plan.monthly_price_yuan}/月`}
                  </div>
                </div>
                {active && <span className="px-2 py-1 text-[10px]" style={{ color: color.brand, backgroundColor: color.brandSoft, borderRadius: radius.pill }}>当前计划</span>}
              </div>
              <ul className="m-0 mt-3 pl-4 space-y-1.5 text-xs leading-5" style={{ color: color.ink2 }}>
                {plan.highlights.map((item) => <li key={item}>{item}</li>)}
              </ul>
              {plan.plan_code !== 'free' && (
                <button
                  onClick={() => void activate(plan.plan_code as 'light' | 'full')}
                  disabled={active || activating !== null}
                  className="mt-4 w-full py-2.5 text-sm font-semibold disabled:opacity-50"
                  style={{ color: '#fff', backgroundColor: color.brand, borderRadius: '10px' }}
                >
                  {active ? '已开通' : activating === plan.plan_code ? '开通中…' : '模拟开通'}
                </button>
              )}
            </section>
          )
        })}
      </div>
      <p className="mt-4 text-center text-[11px]" style={{ color: color.ink2 }}>MVP 内部测试使用模拟权益，不会产生真实扣款。</p>
    </div>
  )
}
