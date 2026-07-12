# Feishu Visual Notes

`feishu-visual-notes` 是一个 Codex Skill，用来把课堂 PPT、图片讲义、录音转写和模拟面试记录整理成飞书学习笔记。它会读完整份材料，重建课程框架，再处理正文、高亮、拓展内容、面试题和可编辑画板。

这个项目不附带 OCR 模型，也不保存飞书账号。图片识别由运行 Skill 的 Codex 或 Agent 完成；飞书读写依赖 Lark/Feishu CLI 与用户授权。

## 能处理什么

- PPT、课件截图、扫描讲义和多张课堂图片
- 飞书 Wiki、飞书文档和已有笔记
- 课堂录音转写、访谈记录、模拟面试记录
- 需要新增笔记的材料，以及需要在原文档局部修改的任务

默认输出包含课程框架、课程主体、核心知识点、拓展内容和面试问题。用户可以指定自己的章节结构，也可以明确省略某一部分。

## 工作方式

一份材料会经过这些检查：

1. 记录页数、顺序、未识别页面和重要图表。
2. 读完全部材料，长课件按不重叠批次处理。
3. 合并重复内容，把零散信息放回对应章节。
4. 判断哪些关系需要画板，哪些更适合正文或表格。
5. 生成笔记、高亮清单、拓展内容和面试题。
6. 写入前检查 XML、SVG、重点覆盖率和长课件清单。
7. 写入后重新读取文档并逐张检查画板预览。

课件中的实体白板、手写板书、教室背景、窗口边框和拍摄杂物会被忽略。看不清的正文标记为“识别不确定”，不会自行补字。

## 三种运行模式

| 模式 | 适用请求 | 是否写飞书 |
|---|---|---|
| Analyze | “先扫描一下”“先给我看框架” | 否 |
| Create | 根据材料生成一份新笔记 | 新建文档，原材料不变 |
| Update | “在原文档上添加”“修改当前文档” | 只修改指定文档和区块 |

Update 模式要求读取最新 revision，并在提交前保存该 revision 的完整快照。文档在读取和提交之间发生变化时，更新会停止，不会覆盖别人刚改的内容。

## 内容边界

正文分为三层：

- 课件笔记：保留原始定义、流程、案例、公式和结论。
- 拓展内容：放在单独章节，说明它来自课程主题的延伸，不冒充课件原文。
- 面试问题：从课程主题和真实岗位场景中出题，不替用户编造项目经历。

课件存在疑似错误、过时步骤或不严谨表述时，笔记会单列核对说明，不会悄悄改成另一种结论。

## 高亮规则

高亮用于回看，不用于装饰。定义、结论、阈值、约束、风险和方法选择会标出；标题、整段正文、重复术语和普通连接句不会反复上色。

默认使用飞书原生浅黄色高亮，禁止或高风险内容可以使用浅红色。高亮文字最多占正文的 30%，这是上限，不是目标值。每个重点都要进入清单，并在写入前与 XML 做一致性检查。

## 可编辑画板

画板使用飞书可编辑 SVG，不以 PNG、代码块或文字箭头代替。图表数量由材料中的关系决定，没有固定张数。

| 关系 | 图表 |
|---|---|
| 顺序、阶段、迭代 | 横向流程、纵向流程、闭环 |
| 层级、分类、课程主线 | 放射知识图、分层知识图 |
| 时间和生命周期 | 线性或交错时间线 |
| 多维方案比较 | 对比矩阵 |
| 条件选择 | 决策图 |
| 多角色交接 | 泳道图 |
| 筛选和逐步收窄 | 漏斗图 |
| 两个独立维度 | 四象限 |
| 根因分析 | 鱼骨图 |

简单列表不会强行画图。生成后的 SVG 还要检查节点数量、文字溢出、重叠、画布占用和不受支持的元素。

## 长课件

超过 40 页或一次无法可靠读完的材料会拆成连续批次。批次清单必须证明：

- 页码完整，没有缺页和重叠；
- 每一批已经完成；
- OCR 不确定页面查看过原图；
- 重要表格、公式和流程图查看过原图；
- 批次输出文件真实存在。

清单没有通过时，Skill 不会声称已经完整整理。

## 平台与版本

| 项目 | 最低版本 | 当前验证情况 |
|---|---:|---|
| Python | 3.10 | Windows 已验证 3.11 |
| Node.js | 18 | Windows 已验证 20.18 |
| Lark/Feishu CLI | 1.0.67 | Windows 已验证 1.0.67 |
| Whiteboard CLI | 0.2.12 | Windows 已验证 0.2.12 |
| Windows | 10/11 | 本机隔离安装、dry-run 已通过 |
| macOS Intel | 待 CI 和真机验证 | 实验性支持 |
| macOS Apple Silicon | 待 CI 和真机验证 | 实验性支持 |

仓库已经提供 macOS Python/Bash 入口，并分别配置 `macos-latest`（arm64）和 `macos-15-intel` 测试。在两套 CI 与真机检查完成前，不把它写成正式支持。

## 安装前检查

Windows：

```powershell
.\preflight.ps1 -Offline
```

macOS：

```bash
chmod +x preflight.sh install.sh
./preflight.sh --offline
```

离线检查只验证本地整理能力，不访问飞书。

## 安装 Skill

Windows：

```powershell
.\install.ps1
```

macOS：

```bash
./install.sh
```

安装器会把 Skill 放进 `CODEX_HOME/skills`、`~/.agents/skills` 或 `~/.codex/skills`。目标已存在时不会直接覆盖；使用 `--force` 或 `-Force` 后，旧版本会先移入 `.backups`，新版本通过自检才会生效。

自定义目录：

```powershell
.\install.ps1 -DestinationRoot "D:\Codex\skills"
```

```bash
./install.sh --destination-root "$HOME/custom-skills"
```

## 配置飞书

缺少依赖时安装固定的已验证版本：

```bash
npm install -g @larksuite/cli@1.0.67
npm install -g @larksuite/whiteboard-cli@0.2.12
```

登录用户身份：

```bash
lark-cli auth login
```

执行完整检查：

```powershell
.\preflight.ps1 -CheckFeishu -Interactive -Save
```

```bash
./preflight.sh --check-feishu --interactive --save
```

预检会报告操作系统、处理器、Python、Node.js、npm、npx、两个 CLI、UTF-8、临时目录和飞书用户身份。它不会替用户安装软件或登录账号。

## MCP 和插件

宿主 Agent 可以把已安装的飞书 MCP、Connector 或插件能力写入临时 JSON，格式见 [`examples/runtime-capabilities.json`](examples/runtime-capabilities.json)。只有同时验证文档读取、文档写入和可编辑画板时，MCP 才算完整后端。

CLI 是当前经过真实 dry-run 验证的默认后端。插件名称看起来相关，但缺少某项能力时，预检会继续提示安装 CLI。Skill 不会在失败后自动切换身份、后端或输出格式。

## 使用示例

```text
使用 $feishu-visual-notes 完整扫描这份 PPT，先给我看课程框架。
```

```text
使用 $feishu-visual-notes 把这份课堂课件整理成新的飞书笔记，流程图必须使用可编辑画板。
```

```text
使用 $feishu-visual-notes 在当前飞书文档中补充面试问题，不要恢复我已经删除的章节。
```

```text
使用 $feishu-visual-notes 整理这份模拟面试转写，保留问题、回答、追问和改进建议。
```

## 目录

```text
feishu-visual-notes/
├── README.md
├── LICENSE
├── install.ps1 / install.sh
├── preflight.ps1 / preflight.sh
├── skill/feishu-visual-notes/
│   ├── SKILL.md
│   ├── VERSION
│   ├── agents/
│   ├── references/
│   └── scripts/
├── tests/
└── tools/
```

仓库说明、贡献指南和版本记录留在仓库根目录，不进入可安装 Skill 包。

## 测试

```bash
python skill/feishu-visual-notes/scripts/self_test.py
python tests/test_portability.py
python tools/package_release.py --output-directory dist
```

Windows 还可以检查 PowerShell 入口；macOS CI 会执行 Bash 语法、中文路径安装和 tar.gz 打包测试。公开 CI 不保存飞书账号，真实文档读写只做手动集成测试。

## 打包

```powershell
.\tools\package_release.ps1 -OutputDirectory dist
```

```bash
./tools/package_release.sh --output-directory dist
```

输出包含 ZIP、tar.gz 和各自的 SHA-256 文件。打包器采用允许列表，只收录 Skill 运行文件。

## 更新与卸载

解压新版本后再次运行安装命令并添加 `--force` 或 `-Force`。旧版本保存在 Skill 根目录下的 `.backups`。

卸载时删除目标 Skill 目录 `feishu-visual-notes`。飞书登录状态由 Lark CLI 管理，需要清除时运行：

```bash
lark-cli auth logout
```

## 常见问题

### 安装后为什么仍然无法读取飞书？

Skill 文件和飞书授权是两件事。运行完整预检，查看 CLI、用户身份和文档权限中哪一项未通过。

### 没有飞书 CLI 能否整理本地材料？

可以。Analyze 模式和本地内容整理只需要宿主 Agent 的文件与视觉能力。创建或修改飞书文档时仍需一个经过验证的飞书后端。

### 为什么不直接把流程图生成图片？

图片不能在飞书画板里逐项编辑。这个 Skill 对图表使用原生可编辑节点，并在写入后查询节点和导出预览。

### 为什么有些章节没有图？

图表只处理顺序、层级、比较、决策和交接等关系。正文或表格已经足够清楚时，不增加画板。

## 安全与隐私

- 不分发飞书 token、Cookie、OAuth 状态或个人文档。
- 内容文件必须位于当前工作目录内，防止误读其他路径。
- Update 模式使用 revision 和 block ID 检查，并在提交前备份。
- 用户身份不可用时停止，不自动换成机器人身份。
- 可编辑画板失败时停止，不自动改成图片。
- 发布包排除缓存、备份、密钥、测试输出和用户数据。

安全问题请按 [SECURITY.md](SECURITY.md) 中的方式报告。

## 已知限制

- OCR 质量取决于宿主 Agent 的视觉能力和原图清晰度。
- macOS 入口已经实现，但尚未完成公开 CI 和 Intel/Apple Silicon 真机双重验证。
- 飞书 CLI、文档 XML 和画板格式升级后可能需要重新验证兼容版本。
- 当前图表生成器限制单图信息密度，复杂关系需要拆成多张图。
- MCP 后端只有在宿主运行时暴露并验证全部必要能力后才能使用。

## 许可证

项目采用 [MIT License](LICENSE)。
