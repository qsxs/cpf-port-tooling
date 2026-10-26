# CPF port tooling

用于固定版本 CPF/OHOS 库端口的最小 Python 标准库工具。提供 `physical/load/record/write/copy_exact` 及完整组件 Maven 快照，不导入应用或其他库的配置。

`mirror_cache(work, pins, cache_root=..., gradle_api=(9, 5, 0), tool_allowlist=[...])` 只镜像 pins 与显式工具白名单内的组件。`cache_root=None` 生成缺件清单并交给正常远端解析。白名单规则指定 `group` 或 `groupPrefix`、`versions`，可加 `modules`。快照保留原 GMM/POM 字节、available-at 与 URL 布局；完整预判必需文件，遇缺件不暴露半成品。函数不会下载、运行 Gradle 或删除文件。

`write` 与 `copy_exact` 保留不可变输入语义，已有内容不一致会失败。缓存根与 Gradle API 由调用方传入，不能根据工作目录猜测。源说明见 `PROVENANCE.json`。维护者已明确批准采用 Apache-2.0 公开发布；原项目来源和记录作者见 `PROVENANCE.json` 与 `NOTICE`。

运行轻量语义检查：`python -B tests/test_tooling.py`。输出保留在仓库 `.local`，不自动清理。消费方必须锁定真实工具 commit 和逐文件 SHA256；尚未提交时允许显式本地目录并核验文件，不能据此声称公开发布通过。
