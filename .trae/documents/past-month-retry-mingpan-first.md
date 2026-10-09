# 过去月份重试提示优化：命盘结果优先

## 问题描述

当前"过去月份建议"检测触发重试时，retry_hint 只说"禁止建议已过去的月份"，LLM 可能随意改成一个未来月份（如"9月拿offer"），而没有基于命盘流月数据找到下一个真正的吉月。

**正确行为**：命盘结果优先——如果流月数据显示6月是最佳窗口但已过，应该：
1. 承认"6月确实是窗口但已过"（复盘参考）
2. 从剩余月份的流月数据中找到下一个吉月
3. 基于命盘数据给出有依据的未来月份建议

## 当前状态

- **重试提示**（`_build_retry_hint` 第2048-2054行）：只说"禁止建议已过去的月份"，没有告诉 LLM 剩余月份的流月数据
- **prompt 规则**（第209行）：说"只能作为复盘参考"，但没有强调"命盘结果优先，找下一个吉月"
- **重试不支持 function calling**：retry 调用不传 `tools`，LLM 无法在重试时调用 `get_liuyue_detail` 获取流月数据

## 方案

**在 retry_hint 中直接注入剩余月份的流月数据**（不需要给 retry 加 function calling）：
- `_build_retry_hint` 是闭包，可以访问 `liuyue_data` 和 `current_month`
- 在 past_month 提示中，格式化当前年份剩余月份（>current_month）的流月吉凶数据
- 告诉 LLM："以下是剩余月份的流月数据，请基于命盘找到下一个吉月作为建议"

## 改动文件

### 1. `followup_structured.py` — `_build_retry_hint` 的 past_month 部分（第2048-2054行）

**改前**：
```python
if v["past_month"]:
    parts.append(
        f"出现了过去月份建议——行动建议的时间点早于当前咨询月份，用户无法执行'穿越式建议'。"
        f"用户现在问'几月拿offer/几月入职'，说明当前还没发生，建议必须是未来月份。"
        f"禁止建议已过去的月份（如当前8月却建议'6月拿offer'），若流月数据显示过去月份是吉月，"
        f"只能作为'复盘参考'（如'6月确实是窗口但已过，现在要抓住下一个窗口'），不能作为行动建议。"
    )
```

**改后**：
```python
if v["past_month"]:
    # 从 liuyue_data 提取当前年份剩余月份的流月数据，注入 retry_hint
    remaining_liuyue = ""
    current_year = datetime.now().year
    if current_year in liuyue_data:
        future_months = [
            lm for lm in liuyue_data[current_year]
            if isinstance(lm, dict) and lm.get('solar_month', 0) > current_month
        ]
        if future_months:
            month_parts = [f"{lm.get('solar_month')}月({lm.get('month_ganzhi','')}){lm.get('judge','')}" for lm in future_months]
            remaining_liuyue = f"当前{current_month}月之后剩余月份的流月数据：{' '.join(month_parts)}。"
    parts.append(
        f"出现了过去月份建议——行动建议的时间点早于当前咨询月份（{current_month}月），用户无法执行'穿越式建议'。"
        f"【命盘结果优先】修正时必须基于流月吉凶数据找下一个吉月，禁止随意改成未来月份。"
        f"{remaining_liuyue}"
        f"若流月数据显示过去月份是吉月，先承认'X月确实是窗口但已过'（复盘参考），"
        f"再从上述剩余月份中找到下一个吉/平月作为行动建议，给出命盘依据。"
        f"禁止毫无根据地把'6月拿offer'改成'9月拿offer'——必须说清为什么是9月（流月数据显示9月是吉月）。"
    )
```

### 2. `followup_structured.py` — prompt 规则（第209行）

在"时间建议必须是未来时间"规则末尾追加"命盘结果优先"强调：

**改前**：
```
若流月数据显示过去的月份是吉月，只能作为"复盘参考"（如"6月确实是窗口但已过，现在要抓住下一个窗口"），不能作为行动建议。违反此规则=给用户一个无法执行的"穿越式建议"，严重损害可信度
```

**改后**：
```
若流月数据显示过去的月份是吉月，只能作为"复盘参考"（如"6月确实是窗口但已过，现在要抓住下一个窗口"），不能作为行动建议。**命盘结果优先**：修正时必须从剩余月份的流月数据中找到下一个吉月作为建议，禁止随意改成未来月份——必须说清"为什么是这个月"（流月数据显示该月是吉月）。违反此规则=给用户一个无法执行的"穿越式建议"，严重损害可信度
```

## 验证步骤

1. 语法检查：`python3 -c "import py_compile; py_compile.compile('app/services/followup_structured.py', doraise=True)"`
2. 确认 `_build_retry_hint` 中 past_month 部分包含 `remaining_liuyue` 变量
3. 硬刷新浏览器重新追问，观察日志中 `past_month` 重试提示是否包含流月数据
