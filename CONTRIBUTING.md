# 参与开发

提交改动前，请先说明问题和预期行为。涉及飞书写入、安全限制或画板格式的修改，需要附带可复现的测试材料；材料中不要放真实账号、文档 token 或课堂内容。

## 本地检查

```bash
python skill/feishu-visual-notes/scripts/self_test.py
python tests/test_portability.py
```

修改安装器、打包器或平台检测后，还要在带空格和中文字符的临时路径中运行安装测试。

## 代码约定

- Python 最低版本为 3.10，只使用标准库，除非新增依赖有明确收益。
- 核心行为写在跨平台 Python 中，PowerShell 和 Bash 保持为薄入口。
- 新增飞书写入路径必须保留 user identity、dry-run、revision 和写后验证。
- 不增加静默身份切换、图片降级或自动恢复文档。
- 说明文档写清操作和限制，不添加无法验证的兼容性结论。

Pull Request 中请列出改动范围、测试命令、结果和剩余风险。commit message 使用简洁英文。
