# CPF port tooling

用于固定版本 CPF/OHOS 库端口的最小 Python 标准库工具。提供 `physical/load/record/write/copy_exact` 及完整组件 Maven 快照，不导入应用或其他库的配置。

`mirror_cache(work, pins, cache_root=..., gradle_api=(9, 5, 0), tool_allowlist=[...])` 只镜像 pins 与显式工具白名单内的组件。`cache_root=None` 生成缺件清单并交给正常远端解析。白名单规则指定 `group` 或 `groupPrefix`、`versions`，可加 `modules`。快照保留原 GMM/POM 字节、available-at 与 URL 布局；完整预判必需文件，遇缺件不暴露半成品。函数不会下载、运行 Gradle 或删除文件。

`write` 与 `copy_exact` 保留不可变输入语义，已有内容不一致会失败。缓存根与 Gradle API 由调用方传入，不能根据工作目录猜测。源说明见 `PROVENANCE.json`。维护者已明确批准采用 Apache-2.0 公开发布；原项目来源和记录作者见 `PROVENANCE.json` 与 `NOTICE`。

运行轻量语义检查：`python -B tests/test_tooling.py`。输出保留在仓库 `.local`，不自动清理。消费方必须锁定真实工具 commit 和逐文件 SHA256；尚未提交时允许显式本地目录并核验文件，不能据此声称公开发布通过。

## 手动受控 Grid producer

`.github/workflows/grid-producer.yml` 放在默认分支 `codex/initial-port-tooling`，仅 `workflow_dispatch` 启动。输入固定仓库 `qsxs/gridlayout-compose` 的完整 40 位 commit；版本自动生成为 `2.8.0-cpf11-preview-<SHA12>-<run-id>-<attempt>`，供本次不可覆盖的预览验收。producer `40432726650/1` 已完整通过；版本已由 Root 发布并完成 Pages 全部115文件匿名字节验收，隔离远程 consumer 的真实编译尚待验证。

runner 固定 Ubuntu 24.04，显式 JDK17/Python3.13，官方 Actions 均使用已核对的不可变 commit；只读仓库权限，两次 checkout 均关闭凭据持久化，并发一个且不取消正在运行。每次使用独立临时 Gradle/Konan/work/staging，不恢复缓存。producer 不伪造 JitPack 环境，直接调用 Grid 自身 Native bootstrap 和 Prepare→Tasks→Resolve→Metadata→NativeX64→NativeArm64→Publish→Verify；Grid 仍按自身 `d063...` 内容锁匿名取得 helper。

只上传两项 Actions artifacts：完整 Verify 通过的 `staging/` Maven 仓，以及 `evidence/` 下的小 manifest、必要回执与每阶段有界日志尾部。失败也尝试上传 evidence；不上传 Native/Gradle 缓存、整 work 或源码副本。Actions artifact 是中转材料，需要 Root 下载验收，不能视作匿名公共 Maven 分发；不自动部署 Pages。

当前临时公开验收目标为独立 `qsxs/cpf-maven` GitHub Pages 仓。Root 完整检查后再手动发布完整 Maven 目录，版本不得覆盖；本工作流不配置 Pages、不向 MavenCentral/R2 部署，也不修改应用引用。App 切换等待 CPF 适配整体完成。

## Grid Pages 隔离远程消费者

`grid-consumer.yml` 只 checkout 本工具仓，手动输入 Pages 已发布的具体不可变 `version` 与 producer 的完整 `source_sha`。目标固定为 `https://qsxs.github.io/cpf-maven/` 和 `com.github.qsxs.gridlayout-compose:grid`；producer `40432726650/1` 已通过八阶段，Pages 的 115 文件/474253B 已完成匿名字节验收；consumer 本身尚未实际云编译。

新 runner 使用固定官方 Actions/JDK17/Python3.13，不恢复缓存。只按 `consumers/grid/toolchain-inputs.json` 的固定 SHA256 从 Grid commit `ed3472803fdb637d601391f62f43aba1bfea551f` 下载十三份构建工具（锁、wrapper、Native bootstrap）；不 checkout/download Grid 库源、producer work/staging，也不使用 MavenLocal、文件仓或 includeBuild。Native 分发沿原 `.08` bootstrap，随后再核实际 compilerVersion；目标 Grid group 被 Gradle exclusiveContent 限定到匿名 Pages，其余 CPF/插件只走公开远端。

先匿名解析 root GMM/available-at/两 leaf owner，按声明核 root metadata JAR 与双 ABI Klib 的 URL、size/SHA256、target/IR，再由只声明 root GAV 的 Gradle 重新解析。标准 metadata 与 Native x64/arm64 任务先实际发现，探针只调用 `VerticalGrid(SimpleGridCells.Fixed(2))`。证据包括实际组件/边/attributes/文件 SHA、编译器输入/真实非空 metadata/IR 输出；metadata 编译库内容必须可追溯到 HTTP 根档的 commonMain payload，双 Native Grid Klib 必须等于 HTTP 摘要。标准任务没有源码或编译失败会明确失败，不删除注解、不伪造成功；无 UI、设备、可执行链接或运行验收。

工作流仅上传非隐藏 `evidence/`，含 HTTP/GMM/工具来源、解析/编译/metadata trace 与有界日志；不上传 Native/Gradle缓存或下载数据目录。consumer 子进程只保留必要宿主变量（包括 LD_LIBRARY_PATH），排除 Actions/GitHub/GitCode token；HTTP 客户端不发送 Authorization/Cookie，不使用认证代理环境；完整读取并核 Content-Length，IncompleteRead 单列为传输失败，最多三次正常请求重试，不拼装 Range 或把部分响应当制品摘要变化。

本批语义测试合并到提交门禁：在本仓运行 `python -B tests/check_grid_consumer_static.py`、`python -B tests/test_grid_remote_consumer.py`。不运行本机 Gradle/Native。Root 审查提交后，用实际已发布 version 和 source SHA 触发远程 workflow；只有 metadata 与双 ABI 编译证据齐备才标记消费通过，link/runtime 始终单列 `NOT_RUN`。Grid 匿名验收完成后暂停，不迁移其他库或切换 App 引用。
