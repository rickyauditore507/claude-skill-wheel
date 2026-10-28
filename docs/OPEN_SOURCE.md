# 开源发布清单（GitHub 先行）

> 决策：Apache-2.0；首发 GitHub + VSIX artifact；Marketplace 等打包 exe、图标、publisher 就绪后再上。

## 已完成

- [x] `LICENSE`（Apache-2.0 原文）
- [x] `extension/package.json` 标注 `license`
- [x] `.github/workflows/ci.yml`：Python 语法、扩展语法、VSIX 打包 artifact
- [x] `.gitignore`（.venv / __pycache__ / *.png / *.log）
- [x] 中英文 README（英文版见 `extension/README.md` 与后续 `README.en.md`）
- [x] 社区索引边界文档 `docs/COMMUNITY_CATALOG.md`
- [x] `THIRD_PARTY_NOTICES.md` + `LICENSES/LGPL-3.0.txt`（PySide6/pynput 的 LGPL 义务）
- [x] `requirements.txt` 改为 `PySide6-Essentials`（不再拉 WebEngine/Addons，~650MB → 目标 <120MB）
- [x] 扩展 `LICENSE` / `CHANGELOG.md` / `.vscodeignore`，版本 0.1.1
- [x] CI 改为在 `extension/` 下执行 vsce

## 发布前必须补齐

| 项 | 说明 | 谁来做 |
| --- | --- | --- |
| GitHub 仓库 | 名称建议 `claude-skill-wheel`；public；开 Issues | 维护者建仓 |
| README 英文版 | Marketplace 与海外用户 | worker |
| CONTRIBUTING / SECURITY / CODE_OF_CONDUCT | CONTRIBUTING、SECURITY 已有；CODE_OF_CONDUCT 缺 | worker |
| Issue / PR 模板 | `.github/ISSUE_TEMPLATE/*` | worker |
| 截图与 GIF | 圆盘 + 翻页 + 松开确认，别用带隐私的桌面 | 维护者录屏 / 用 demo 渲染 |
| 图标 | 512×512 PNG，圆盘 + 中心点 | 维护者 |
| PyInstaller onefile | 用户没装 Python 也能用；目标 < 120MB | worker（任务 a5394eb8） |
| 版本策略 | SemVer；扩展与 overlay 同步 0.2.0 起 | manager |
| Marketplace publisher | Microsoft 账号 + PAT；扩展 `publisher` 目前是 `ricky` | 维护者注册 |
| VSIX 打包 | `npx @vscode/vsce package --no-dependencies` | CI 已配 |

## Marketplace 阻断项（发布前确认）

1. **Python 依赖**：不能要求用户自己装 Python + PySide6。必须 bundle exe 或首次运行自动建 venv（需要系统 Python）。推荐 bundle exe。
2. **体积**：PySide6 onefile 通常 60–120MB；Marketplace 接受，但首次下载慢。只保留 Qt Core/Gui/Widgets，裁剪 Qt 插件。
3. **签名**：Windows 未签名 exe 会触发 SmartScreen；个人项目可接受，企业分发需签名。
4. **自动启动**：overlay 会注册全局热键；Marketplace 审核可能要求明确说明。README 与设置里写清楚。
5. **隐私**：无网络请求（除可选的社区索引）；扩展只在 `127.0.0.1` 监听随机端口。

## 发布步骤（GitHub）

```bash
git init
git add .
git commit -m "feat: Skill Wheel v0.2.0"
git branch -M main
git remote add origin https://github.com/<owner>/claude-skill-wheel.git
git push -u origin main
```

> 推之前先跑一遍 CI 等价命令：
> `python -m compileall overlay && node --check extension/extension.js`
