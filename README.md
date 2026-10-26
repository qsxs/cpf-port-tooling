# CPF port tooling

用于固定版本 CPF/OHOS 库端口的最小 Python 标准库工具。提供 `physical/load/record/write/copy_exact` 及完整组件 Maven 快照，不导入应用或其他库的配置。

`mirror_cache(work, pins, cache_root=..., gradle_api=(9, 5, 0), tool_allowlist=[...])` 只镜像 pins 与显式工具白名单内的组件。`cache_root=None` 生成缺件清单并交给正常远端解析。白名单规则指定 `group` 或 `groupPrefix`、`versions`，可加 `modules`。快照保留原 GMM/POM 字节、available-at 与 URL 布局；完整预判必需文件，遇缺件不暴露半成品。函数不会下载、运行 Gradle 或删除文件。

`write` 与 `copy_exact` 保留不可变输入语义，已有内容不一致会失败。缓存根与 Gradle API 由调用方传入，不能根据工作目录猜测。源说明见 `PROVENANCE.json`。维护者已明确批准采用 Apache-2.0 公开发布；原项目来源和记录作者见 `PROVENANCE.json` 与 `NOTICE`。

运行轻量语义检查：`python -B tests/test_tooling.py`。输出保留在仓库 `.local`，不自动清理。消费方必须锁定真实工具 commit 和逐文件 SHA256；尚未提交时允许显式本地目录并核验文件，不能据此声称公开发布通过。

## 手动受控 Grid producer

`.github/workflows/grid-producer.yml` 放在默认分支 `codex/initial-port-tooling`，仅 `workflow_dispatch` 启动。输入固定仓库 `qsxs/gridlayout-compose` 的完整 40 位 commit；版本自动生成为 `2.8.0-cpf11-preview-<SHA12>-<run-id>-<attempt>`，供本次不可覆盖的预览验收。当前实现尚未执行远程 CI，不能据此宣布构建或发布通过。

runner 固定 Ubuntu 24.04，显式 JDK17/Python3.13，官方 Actions 均使用已核对的不可变 commit；只读仓库权限，两次 checkout 均关闭凭据持久化，并发一个且不取消正在运行。每次使用独立临时 Gradle/Konan/work/staging，不恢复缓存。producer 不伪造 JitPack 环境，直接调用 Grid 自身 Native bootstrap 和 Prepare→Tasks→Resolve→Metadata→NativeX64→NativeArm64→Publish→Verify；Grid 仍按自身 `d063...` 内容锁匿名取得 helper。

只上传两项 Actions artifacts：完整 Verify 通过的 `staging/` Maven 仓，以及 `evidence/` 下的小 manifest、必要回执与每阶段有界日志尾部。失败也尝试上传 evidence；不上传 Native/Gradle 缓存、整 work 或源码副本。Actions artifact 是中转材料，需要 Root 下载验收，不能视作匿名公共 Maven 分发；不自动部署 Pages。

当前临时公开验收目标为独立 `qsxs/cpf-maven` GitHub Pages 仓。Root 完整检查后再手动发布完整 Maven 目录，版本不得覆盖；本工作流不配置 Pages、不向 MavenCentral/R2 部署，也不修改应用引用。App 切换等待 CPF 适配整体完成。
