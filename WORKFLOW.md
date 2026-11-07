# 双 Agent 跟进工作流（本地演示）

`opc.workflow` 是固定状态编排：数据增长 Agent 确定性分层，并依据同意状态与近七日模拟触达次数生成任务；服务运营 Agent 生成提醒、执行独立审核并在老板批准正文和完整名单后写入本地草稿。审核仍是独立的强制步骤，失败不放行；模拟回执记为事件供后续统计。历史轨迹保留旧角色名。入站消息与 SOP 也可登记为共享运行记录，保留每步轨迹；人工明确的客户阶段变更留痕。使用 SQLite 保存状态，不调用外部消息渠道。30 个示例客户和事件均为模拟数据；不能将它们说成真实用户行为。三天未互动不代表流失或购买意愿，单次变化不能视为因果效果。

在 `junction` 目录执行：

```bash
python -m opc.workflow seed
python -m opc.workflow analyze
# 另一条入站链：消息 ID 防止重复处理；模拟审批不等于实际授权
python -m opc.workflow inbound --customer demo-001 --message "你好" --message-id MSG-1 --simulate-approval
python -m opc.workflow sop --day D4 --simulate-approval
# 用返回的 run_id 代替 BATCH 查看处理轨迹
python -m opc.workflow list --batch RUN_ID
python -m opc.workflow stage --customer demo-001 --stage 已结束 --reason "人工确认完成"
python -m opc.workflow plan
# 将 plan 返回的 batch_id 替换为 BATCH；内容生成和审核需配置模型服务
python -m opc.workflow content --batch BATCH
python -m opc.workflow list --batch BATCH
# 检查正文、审核和完整名单后，提供 list 返回的 material_hash 明确批准
python -m opc.workflow approve --batch BATCH --artifact ARTIFACT --decision APPROVED --material-hash HASH
python -m opc.workflow queue --batch BATCH --artifact ARTIFACT
python -m opc.workflow list --batch BATCH
python -m opc.workflow receipt --draft DRAFT
python -m opc.workflow analyze
```

`REJECTED` 和 `SIMULATED_APPROVAL` 不允许生成待发送草稿。审核异常、正文更改、名单更改或触达条件变化均会阻止进入草稿队列，需重新规划或审批。记录模拟回执时会再次检查客户阶段、同意状态和频次；一条草稿只允许记录一次。当前演示不提供真实发送、客户资料导入、自动定时、漏斗归因或对照实验；客服和 SOP 的内容仍保存在各自的本地工单及运营包，共享运行记录保存其结果与轨迹。
