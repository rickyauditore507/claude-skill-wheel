# 社区技能库 · 设计与边界

> 目标：让轮盘能自动填充"别人做好的公开 skill"，同时不踩隐私和供应链的坑。
> 决策（2026-10-28）：独立圆盘入口；只索引公开来源；导入必须用户确认。

## 1. 绝对边界（不可协商）

- **只索引公开来源**：GitHub 公开仓库里带 `.claude/skills/**/SKILL.md` 的项目、公开 `marketplace.json`、公开的 awesome 列表。
- **禁止**：抓个人用户主页、私有仓库、需要登录才能看的数据、把别人的 skill 列表当"用户画像"聚合。
- **只存元数据**：`name / description / repo / path / license / source_url / updated_at`。不缓存 SKILL.md 正文。
- **不自动安装、不自动执行**。导入是一个显式动作，界面上显示来源、许可证、目标路径。
- **许可证可追溯**：导入前展示 `license`；非宽松许可证（GPL/AGPL/未知）默认阻止，除非用户在配置里显式放行。
- **供应链提示**：skill 正文可能包含 hook / 脚本；界面必须提示"只导入你信任的仓库"。

## 2. 索引格式

仓库根目录 `catalog/index.json`，由 PR 维护（比实时爬取稳，也便于审核）：

```json
{
  "version": 1,
  "updated_at": "2026-10-28",
  "entries": [
    {
      "name": "diagram-design",
      "description": "Create diagrams as HTML/SVG/PNG.",
      "repo": "owner/repo",
      "path": ".claude/skills/diagram-design/SKILL.md",
      "ref": "main",
      "license": "MIT",
      "source_url": "https://github.com/owner/repo/blob/main/.claude/skills/diagram-design/SKILL.md",
      "tags": ["diagram", "design"]
    }
  ]
}
```

### 校验规则

| 字段 | 规则 |
| --- | --- |
| `name` | `^[a-z0-9][a-z0-9-]{0,63}$` |
| `description` | 非空，≤ 300 字符 |
| `repo` | `owner/name` |
| `path` | 以 `SKILL.md` 结尾，且包含 `/skills/` |
| `license` | SPDX 标识；宽松白名单：MIT、Apache-2.0、BSD-2-Clause、BSD-3-Clause、ISC、CC0-1.0、Unlicense |
| `source_url` | 必须是 `https://`，且域名与 `repo` 匹配（github.com） |

## 3. 轮盘交互（独立入口）

- 主盘翻到**最后一页**时，多出一个扇形：`社区技能库 · N`。
- 选中它 → 进入"社区盘"（同样的圆环布局，按 tags/热度分页）。
- 悬停显示：名称、描述、`owner/repo`、license 徽标。
- 松开确认后**不直接插入**，先弹出导入确认（overlay 内绘制一层，不抢焦点）：
  - 展示来源、license、将写入的路径 `~/.claude/skills/<name>/SKILL.md`
  - 提示"只导入你信任的仓库"
  - 需要再按一次确认键（例如再按住 `Alt+`` 0.4s）或 `Enter`；`Esc` 取消
- 导入成功后，该 skill 进入本地列表（下一次打开轮盘即可用），并在 `usage.json` 里标记来源。

> 备选（如果二次确认交互太绕）：社区盘选中后仅写入"待导入队列"，在 VS Code 命令面板里逐条确认。v0 先做圆盘内确认，失败再退化。

## 4. 数据来源策略

1. **首选：本仓库 `catalog/index.json`**（PR 审核，可追溯）。
2. **可选：GitHub API 搜索**（用户自备 token，`skillWheel.catalogToken`）：
   - `GET /search/code?q=filename:SKILL.md+path:.claude/skills`（需要认证，速率受限）
   - 只在用户点"刷新社区库"时触发，结果缓存 24h。
3. **可选：导入用户提供的索引 URL**（团队/公司内部 registry）。

不做"爬某个用户的全部 skill"这种功能。

## 5. 安全与合规检查表

- [ ] 索引条目有 license 且在白名单（或用户显式放行）
- [ ] 导入前展示 source_url 与目标路径
- [ ] 下载走 HTTPS，校验 host 属于 github.com / raw.githubusercontent.com
- [ ] 文件大小限制（≤ 200KB），拒绝二进制
- [ ] 覆盖已有同名 skill 前提示 diff
- [ ] 失败可回滚（先写临时目录，成功再移动）
- [ ] README / 扩展描述里明确"第三方 skill 风险自负"
