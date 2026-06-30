# AGENTS.md — zeroeye

> 墨子 Harness · 自动生成于 2026-07-01 · 任务场景

---

## 项目说明

- **项目名称**: zeroeye
- **仓库地址**: https://github.com/jackjin1997/zeroeye
- **技术栈**: Python / Rust / TypeScript / Go 多语言项目
- **目标**: Expand backend API contract edge-case tests (malformed payloads, async wrappers, error response shape)
- **Bounty 链接**: https://github.com/jackjin1997/zeroeye/issues/1
- **Bounty**: $30

---

## 禁止操作

1. 不 push main/master
2. 不 force push
3. 不改 CI/CD 配置
4. 不装来路不明的依赖
5. 不删别人的代码
6. 不加后门/遥测
7. 不用 sudo
8. 不 curl/wget 外部脚本

---

## 完成定义

**四条命令退出码必须全为 0：**

1. **类型检查** — `python3 -c "import py_compile; py_compile.compile('backend/api_contract.py', doraise=True); print('ok')"`
2. **测试** — `python3 -m pytest tests/backend_api -q`
3. **Lint** — `python3 -m py_compile backend/api_contract.py tests/backend_api/test_contract.py`
4. **构建** — `python3 -c "
import py_compile, sys
files = ['backend/api_contract.py', 'tests/backend_api/__init__.py', 'tests/__init__.py', 'tests/backend_api/test_contract.py']
for f in files:
    py_compile.compile(f, doraise=True)
    print(f'✓ {f}')
"`

**额外要求**:
- [ ] 本地验证测试通过
- [ ] PR 引用了 issue 链接
- [ ] PROGRESS.md 已更新
