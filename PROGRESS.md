# PROGRESS.md — zeroeye

> 墨子 Harness 进度跟踪

---

## 已完成

- [x] backend/api_contract.py — API 合约验证工具函数
  - `validate_payload()` 含 schema 类型/约束/required/nullable 检查
  - `ContractError` 异常结构
  - `make_response()` / `success_response()` / `error_response()` 响应封装
  - `merge_contracts()` / `async_validate()` 辅助函数
- [x] tests/backend_api/test_contract.py — 35 个测试用例
  - Happy path 验证
  - Missing required / None 字段
  - 类型违反（str→int, list→str 等）
  - 字符串长度约束（min_len, max_len）
  - email 正则模式
  - choices 枚举
  - 数值范围（min/max）
  - 列表长度约束
  - Extra fields 拒绝/允许
  - ContractError.to_dict() / to_response() 结构
  - Response helper 形状
  - async_validate 包装器
  - 空 payload / None payload 边界
  - merge_contracts 合并/覆盖
- [x] 四命令全绿：type-check / test (35 passed) / lint / build

## 进行中

- (无)

## 待办

- (无)

## 已知问题

- build.py 的 Python 3.9 兼容性（f-string 反斜杠）已修复
- Rust/cargo 等工具链缺少不影响本任务
