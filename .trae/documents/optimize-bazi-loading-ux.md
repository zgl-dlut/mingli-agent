# 排盘数据加载流程优化

## 问题总结

用户不希望感知到"排盘数据加载"这个后端处理逻辑。当前流程中，排盘数据在 Chat 页面异步加载，用户可能在加载完成前点击追问，导致"命理数据未就绪"错误。

## 当前流程分析

```
AddPerson 页面                    Chat 页面
    ↓                                ↓
创建 person（只存基本信息）    →    跳转到 /chat/:personId
    ↓                                ↓
保存到数据库                      useEffect 检测到 person.id 变化
    ↓                                ↓
navigate('/chat/:personId')      调用 analyzeBazi（异步，100-500ms）
                                      ↓
                                 等待后端返回排盘结果
                                      ↓
                                 setBaziResult(result)
```

**问题**：

* 排盘数据加载被放在 Chat 页面，用户感知到等待

* 异步竞态条件：用户可能在加载完成前点击追问

## 排盘计算耗时分析

从 `orchestrator.py` 代码分析：

* `generate_full_analysis` 是纯 CPU 计算函数

* 包含：基础八字排盘、地支关系、旺衰、格局、调候、大运流年等

* **没有 AI 调用**，纯算法计算

* 预计耗时：10-50ms（后端计算）+ 100-500ms（网络往返）

## 优化方案

### 方案：在 AddPerson 页面预加载排盘数据

**核心思路**：

* 在 AddPerson 页面提交时，同步调用排盘 API

* 等待排盘数据返回后，再跳转到 Chat 页面

* 将排盘数据通过 store 传递给 Chat 页面

* Chat 页面检测到已有数据，跳过异步加载

**实现步骤**：

1. **扩展 personStore**

   * 添加 `baziResults` 字段，存储每个 person 的排盘数据

   * 添加 `setBaziResult(personId, result)` 方法

   * 添加 `getBaziResult(personId)` 方法

2. **修改 AddPerson.tsx**

   * 在 `handleSubmit` 中，创建 person 后立即调用 `analyzeBazi`

   * 等待排盘数据返回后，存入 personStore

   * 再跳转到 Chat 页面

3. **修改 Chat.tsx**

   * useEffect 中先检查 personStore 是否已有排盘数据

   * 如果有，直接使用，跳过异步加载

   * 如果没有（刷新页面等场景），才调用异步加载

4. **UI 优化**

   * AddPerson 页面提交按钮显示"正在分析..."加载状态

   * Chat 页面不再显示"正在排盘分析..."加载动画

## 实施细节

### 1. personStore 扩展

```typescript
// frontend/src/store/personStore.ts

interface PersonStore {
  persons: Person[]
  baziResults: Record<number, AnalyzeResult>  // 新增
  // ...
  setBaziResult: (personId: number, result: AnalyzeResult) => void
  getBaziResult: (personId: number) => AnalyzeResult | undefined
}
```

### 2. AddPerson.tsx 修改

```typescript
const handleSubmit = async (e: React.FormEvent) => {
  // ... 现有逻辑
  
  const person = await createPerson({...})
  
  // 新增：同步调用排盘 API
  setIsLoading(true)
  try {
    const baziResult = await analyzeBazi({
      birth_date: person.birth_date,
      birth_time: person.birth_time,
      longitude: person.longitude,
      latitude: person.latitude,
      gender: person.gender,
      location: person.birth_place,
    })
    
    // 存入 store
    setBaziResult(person.id, baziResult)
    
    // 跳转
    navigate(`/chat/${person.id}`)
  } catch (err) {
    setError('排盘分析失败，请稍后重试')
  } finally {
    setIsLoading(false)
  }
}
```

### 3. Chat.tsx 修改

```typescript
useEffect(() => {
  if (!person) return
  
  // 检查是否已有排盘数据
  const cachedResult = getBaziResult(person.id)
  if (cachedResult) {
    setBaziResult(cachedResult)
    setCardPhase(hasFirstReading(person.id) ? 'done' : 'ready')
    return  // 跳过异步加载
  }
  
  // 没有缓存，才调用异步加载（刷新页面等场景）
  setBaziLoading(true)
  analyzeBazi({...})
    .then((result) => {
      setBaziResult(result)
      setBaziResult(person.id, result)  // 存入缓存
      // ...
    })
    // ...
}, [person?.id])
```

## 验证步骤

1. 创建新人物，观察 AddPerson 页面显示"正在分析..."
2. 等待分析完成后跳转到 Chat 页面
3. 确认 Chat 页面立即可用，无加载动画
4. 立即点击追问按钮，确认不会报错
5. 刷新 Chat 页面，确认仍能正常加载（走异步加载兜底）

## 风险点

1. **AddPerson 页面等待时间增加**：用户需要等待排盘计算完成才能跳转

   * 缓解：显示加载动画和进度提示

   * 预计总耗时：500ms-1s（可接受）

2. **排盘失败处理**：如果排盘 API 失败，用户无法进入 Chat 页面

   * 缓解：显示错误提示，允许重试

   * Chat 页面有兜底逻辑，即使 AddPerson 失败也能异步加载

3. **Store 持久化**：baziResults 是否需要持久化到 localStorage？

   * 建议：不持久化，每次刷新重新加载

   * 原因：排盘数据较大，localStorage 有 5MB 限制

