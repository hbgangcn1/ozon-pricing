## ADDED Requirements

### Requirement: 定价结果按4个Tab分组展示
系统 SHALL 在定价计算时，按 fulfillment_type 和 destination 将用户物流规则分为4组，分别计算并返回结果；前端以 Tab 页形式展示4组结果。4个分组为：rFBS-Russia、rFBS-CIS（各国分别展示）、FBP-仅Russia、FBP-Russia+CIS。

#### Scenario: 用户触发定价计算
- **WHEN** 用户提交定价计算请求（精准模式或快速模式）
- **THEN** 系统同时计算4个分组的结果，每组含 best_land（陆运）和 best_air（空运）以及价格、利润等信息，以单一响应返回

#### Scenario: 前端 Tab 展示
- **WHEN** 前端收到含4组结果的定价响应
- **THEN** 显示4个 Tab 页：rFBS-俄罗斯、rFBS-独联体（含KZ/BY/KGZ/UZ/GE/AZ子Tab或列表）、FBP-仅俄罗斯、FBP-俄罗斯+CIS；用户可在 Tab 间切换查看不同结果

#### Scenario: 某分组无可用物流
- **WHEN** 某个分组（如 FBP-CIS）下用户没有任何对应物流规则
- **THEN** 该 Tab 显示"暂无可用物流方式"提示，不报错

#### Scenario: rFBS-CIS 按国家细分
- **WHEN** 用户有多个 rFBS CIS 物流记录，destination 分别为 KZ、BY、KGZ
- **THEN** rFBS-CIS Tab 下按国家分别展示最优结果（KZ 最优、BY 最优、KGZ 最优等）

### Requirement: 保留陆运/空运区分
系统 SHALL 在所有4个分组中，继续按物流记录的 type 字段区分陆运（land）和空运（air），各自选出最优方案。

#### Scenario: 陆运空运各显最优
- **WHEN** 某分组（如 rFBS-Russia）计算完成
- **THEN** 该分组结果包含 best_land 和 best_air 两个最优物流方案及对应的建议售价和利润

### Requirement: Smart 物流重点标注
系统 SHALL 在计算结果中，对 is_smart=1 的物流方式以醒目方式标注"Smart"，优先于显示具体物流方法名称。

#### Scenario: Smart 物流出现在结果中
- **WHEN** 某分组的 best_land 或 best_air 对应一条 is_smart=1 的物流记录
- **THEN** 前端在该物流方式名称旁显示"Smart"标签或醒目标注，而非仅显示具体方法名称（如 "RETS FBP Economy Budget"）
