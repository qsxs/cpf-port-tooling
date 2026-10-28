# CPF port tooling

固定版本 CPF/OHOS 库端口的最小 Python 标准库工具。提供 `physical/load/record/write/copy_exact` 与完整组件 Maven 快照；不导入应用或其他库配置。维护者已批准 Apache-2.0 公开，原来源、作者 Lihb 及授权说明见 `PROVENANCE.json`/`NOTICE`，许可证不因本次文档收口改变。

`mirror_cache(work, pins, cache_root=..., gradle_api=(9, 5, 0), tool_allowlist=[...])` 只镜像 pins/显式工具白名单内的完整组件，保留原 GMM/POM 字节、available-at 与 URL。缺件交给正常远端解析，不暴露半个组件。`write/copy_exact` 遇既有不同内容会失败；不下载或删除文件。Grid helper 仍锁 [`d063c7c70ffbc3f241d7e8bdd184add33dc9a009`](https://github.com/qsxs/cpf-port-tooling/commit/d063c7c70ffbc3f241d7e8bdd184add33dc9a009) 及逐文件 hash，和下面的工作流提交明确区分。

## Grid 已验交付

根坐标：`com.github.qsxs.gridlayout-compose:grid:2.8.0-cpf11-preview-ed3472803fdb-40432726650-1`，公开 Maven 根为 `https://qsxs.github.io/cpf-maven/`（[GitHub 制品仓库](https://github.com/qsxs/cpf-maven)）。115 文件/474253B 已逐字节核验；隔离 consumer metadata/双 Native 编译已过，link/runtime 与设备/Android/iOS 回归未执行。这是 Grid 批次的验收结果；App 引用尚未切换。

| 工作流 | 手动输入 | 已验提交与成功记录 |
| --- | --- | --- |
| [producer](https://github.com/qsxs/cpf-port-tooling/blob/30c5b7079193ae26440f6dc80fe6047df102348e/.github/workflows/grid-producer.yml) | `grid_sha=ed3472803fdb637d601391f62f43aba1bfea551f` | tooling `30c5b7079193ae26440f6dc80fe6047df102348e`；[40432726650/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40432726650/attempts/1) |
| [consumer](https://github.com/qsxs/cpf-port-tooling/blob/5ee338b3847ae0395726a46b9d95bb7f8c5fb3e4/.github/workflows/grid-consumer.yml) | `version=2.8.0-cpf11-preview-ed3472803fdb-40432726650-1`、`source_sha=ed3472803fdb637d601391f62f43aba1bfea551f` | tooling `5ee338b3847ae0395726a46b9d95bb7f8c5fb3e4`；[40440852307/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40440852307/attempts/1) |

工作流位于默认分支 `codex/initial-port-tooling`。表中 commit 是成功时的代码身份；重新运行应先核对所选分支/标签与锁，记录新 tooling SHA。Producer 版本自动含 source SHA12/run id/attempt，重跑生成新版本，不覆盖已发版本；consumer 重验既有版本不改写 GAV。Consumer source_sha 仅是验收标识，其十三份构建工具来自 `toolchain-inputs.json` 固定的 Grid `ed3472803fdb637d601391f62f43aba1bfea551f`，不是 checkout 库源码。

## 隔离、证据与未验边界

两流程均手动、Ubuntu24.04/JDK17/Python3.13、固定官方 Actions commit、contents:read、checkout 不持久化凭据、单并发且不取消运行。不恢复缓存，Gradle/Konan/work/temp 均为每次独立临时目录；子进程只保留必要宿主变量及 LD_LIBRARY_PATH，不转发 Actions/GitHub/GitCode token。

Producer 直接使用 Grid 的 Native bootstrap 与八阶段 Publish/Verify，只上传完整 `staging/` 和小 `evidence/` 两个 artifact。Root 核对后手动推 Pages 的 `codex/initial-maven` 分支；`--repository` 仅本地 staging，不是 Pages 部署。Actions artifact 不是匿名 Maven 分发；不自动 deploy，不部署 MavenCentral/R2。

Consumer 只 checkout 工具仓，目标 group 只走匿名 Pages，通过 root GMM 选择两 leaf，不直引 leaf、不用 MavenLocal/文件仓/includeBuild/producer work。真实 HTTP/GMM/metadata与双 Klib摘要、Gradle组件/边/attributes、20文件 metadata payload 转换追溯以及三个编译任务的输入/输出已核验。HTTP 完整 read/Content-Length 检查，IncompleteRead 是传输失败，最多三次普通请求，不加 Range 或客户端 fallback。

Consumer 只有一个332B的 `VerticalGrid(SimpleGridCells.Fixed(2))` 编译探针；三个任务同源，metadata 输出3文件、Native各19文件。Grid producer 18份原源/API/注解整体编译，不等于所有 API 已运行。`link=NOT_RUN`、`runtime=NOT_RUN`，无设备或 Android/iOS 回归。前两轮 consumer 失败是私有验收 DSL 类型/冗余诊断和 JSON合法null，已在工具侧修正；标准 consumer metadata 已过，不泛化 Grid producer 公共 metadata CLI 入口为所有库的规则。

本机 Windows urllib 对十个大文件出现6890B截断，curl完整匹配；云 consumer 已完整匿名HTTP成功，保留观察，不归因库损坏。今后只有官方真实制品满足双 ABI/API/当时工具链并独立消费通过，才另行决定替换；不编造官方 GAV 或自动升级。

轻量测试仍只在相应提交门禁按变更运行：`python -B tests/test_tooling.py`、producer/consumer 对应 static 与语义用例。本次纯 Markdown 收口不重复测试或构建，既有 `.local` 证据不自动清理。

## Kotlin/Native .08 共享宿主输入

`toolchains/kotlin-native/2.4.20-0.1.0-08/` 从 Grid 固定提交 `ed3472803fdb637d601391f62f43aba1bfea551f` 提取宿主输入；Grid 原 producer/consumer 已通过冷 Linux 验收；共享 `.08` bootstrap 也已用于下述 Poko 成功云端运行，其他模块仍需独立核验。四份锁和 16 份上游 POM 原件保留 Grid 字节与各自 URL、大小及 SHA256，POM 位于 `vendor/`，不会将 JAR、Native 分发包、Android SDK 或缓存放进 Git。来源与原始 blob 的 SHA256 见 `PROVENANCE.json`。

各 Fork 按实际编译需求分别选用配置：metadata CLI launcher 为 8 项 JVM 输入；标准 commonizer 额外包含自身 1 项并继承这 8 项；Native compiler 使用独立 14 项宿主闭包；只有实际使用 Compose compiler 时才选其单项插件锁。metadata/commonizer 的 annotations 为 13.0，Native compiler 的 annotations 为 23.0.0，不能把一套版本选择强加给另一套，也不能将宿主 JAR 当作库的 runtime 图。Poko 编译插件 0.23.2 不属于这些公共 runtime 依赖。每个 Fork 仍应核对自己的实际解析集合、GAV、大小、SHA256 和配置边；这些锁不会自动注入 repository、凭据、环境变量或 Gradle 配置。

Linux x86_64 可在隔离输出根显式提供该库锁定的 Kotlin 版本：

```sh
python -B toolchains/kotlin-native/2.4.20-0.1.0-08/bootstrap-native.py --destination <isolated-bootstrap-root> --kotlin-version 2.4.20-0.1.0-08
```

脚本只下载锁定的 Native 包、核对大小和 SHA256，解压后核实原 `konan.properties` 的 `compilerVersion` 并留下 receipt；不改配置或 sysroot。下载、解压或校验失败时保留现场，重试使用新的隔离输出根；不执行 Gradle/Native 编译。`python -B tests/check_native_08_host.py` 检查四类锁和 POM 闭包，`python -B tests/test_bootstrap_native_08.py` 以保留在 `.local/` 的微型夹具检查版本门禁和失败现场。

## Poko OHOS producer 与匿名 consumer

新增手动 `poko-producer.yml` 只 checkout 工具仓和指定完整 SHA 的 `qsxs/Poko`；`poko-consumer.yml` 只 checkout 工具仓，从 Pages 的 `io.github.qsxs.cpf.poko:poko-annotations` root GAV 选择 metadata 和两 Native leaf。Producer 完整 Verify 后上传 staging 和证据，Pages 仍由维护者人工审核发布。两个工作流均使用 JDK 17、Python 3.13、隔离的 Gradle/Konan/work/temp，不恢复缓存，子进程不传递 Actions 凭据。

工作流运行时所在的工具仓 commit B 与 Poko 端口固定共享工具 commit `d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285` A 分别记录：producer 从固定 A 的公开归档读取 20 个文件并逐项核大小/SHA256；consumer 从 A 的固定 raw URL 逐项读取同一文件身份。Gradle 9.5.0 wrapper 由固定 Grid commit `ed3472803fdb637d601391f62f43aba1bfea551f` 的四项工具文件供 consumer 使用，均核内容，不 checkout Grid 或 Poko 源码。

Gradle 9.5 consumer 使用官方 Poko compiler plugin 0.23.2 和普通 `@Poko` 类，移除该插件自动注入的原 `poko-annotations:0.23.2`，仅声明 Pages 的新 root。它记录匿名 HTTP 字节、GMM owner/available-at、实际变体、metadata 转换、编译输入/输出，并使用该 `.08` Native 分发的 `klib dump-metadata` 与 `dump-metadata-signatures` 检查三个编译输出中的 probe 类自身的 `equals`、`hashCode`、`toString`，双 Native 另检查非空 IR。未检查 Native IR 中各方法的方法体。

同一 workflow 的独立 Gradle 8.11.1 job 对同一公开 root GAV 运行标准 metadata 和双 Native 编译；它不声明、解析或加载 Poko Gradle/compiler 插件，probe 只引用 `Poko` 注解类型，不检查或声称生成成员。两个 job 串行并各有独立工程、Gradle/Konan 和临时目录，不使用 producer 输出或缓存。Gradle 8 的 compiler/commonizer JVM 工具依据实际解析记录，只核同版工具和可对应的既有字节身份，不强制 Gradle 9 的 14 项闭包。

Gradle 8 wrapper JAR 与 properties 的原件来自 App 冻结 commit `35ce89e5f91a23aaa5657c21510afd6ee593fad9` 的 `harmony-build/application-gradle/gradle/wrapper/`，逐文件大小/SHA256 及 Gradle 官方 Apache-2.0 许可来源记录在 `consumers/poko/wrapper-inputs-gradle8.json`；Gradle 8.11.1 官方 distribution SHA256 为 `f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6`。两种 consumer 结论分别保存，`link=NOT_RUN`、`runtime=NOT_RUN`。

已验根 GAV 为 `io.github.qsxs.cpf.poko:poko-annotations:0.23.1-cpf11-preview-cbaa758d0b76-40451679040-1`。[producer 40451679040/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40451679040/attempts/1) 使用 [Poko source `cbaa758d0b76`](https://github.com/qsxs/Poko/commit/cbaa758d0b7610e0e445b8fd50739aa05afaea6e) 和[工作流提交 B `be203a175c85`](https://github.com/qsxs/cpf-port-tooling/commit/be203a175c8592bea3b13819e4fa31a666438c07)；共享宿主工具内容锁 A 为 [`d0cff88fd1ea`](https://github.com/qsxs/cpf-port-tooling/commit/d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285)，两者不能混淆。[Pages 制品提交 `7c7abe30bb95`](https://github.com/qsxs/cpf-maven/commit/7c7abe30bb9510d0290794522471cb99469f6dac) 的 110 个文件、158468 字节与 staging 匿名逐字节对齐。

[consumer 第 1 次](https://github.com/qsxs/cpf-port-tooling/actions/runs/40457201932/attempts/1)的 Gradle 8 job 和[第 2 次](https://github.com/qsxs/cpf-port-tooling/actions/runs/40457201932/attempts/2)的 Gradle 9 job 均完成 metadata、OHOS x64 和 arm64 的真实编译；第 2 次两个 job 均报告成功，详细 artifact 核对分别采用 Gradle 8 第 1 次和 Gradle 9 第 2 次。第 1 次 Gradle 9 在下载官方 sysroot 时超时，随后第 2 次成功，不能把第 1 次整体记为成功。只核验 Gradle 9 自有 probe 的三个生成声明签名及 Native 非空 IR，未检查方法体、link、runtime、设备或 Android/iOS 回归。Pages 是临时验收仓，App 尚未切换。

轻量来源静态检查：`python -B tests/check_poko_port_static.py <Poko-ohos-directory>`。对应声明检查的语义测试 `python -B tests/test_poko_declarations.py` 仅在授权门禁运行，夹具留在 `.local/`。

## Colormath OHOS producer 与匿名 consumer

[Fork source `86f87c1c333f0eb68af52afc88b73d82a536d6cf`](https://github.com/qsxs/colormath/commit/86f87c1c333f0eb68af52afc88b73d82a536d6cf) 保留上游 [ajalt/colormath 3.6.1](https://github.com/ajalt/colormath/commit/5e776b66ea6ffc5dc5dc360ab88ca5aefbd2a310) 的 45 份原源与 MIT 许可证。已验 GAV 为 `io.github.qsxs.cpf.colormath:colormath:3.6.1-cpf11-preview-86f87c1c333f-40461897858-1`；临时 Maven 根 `https://qsxs.github.io/cpf-maven/`，可查看[根 POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/colormath/colormath/3.6.1-cpf11-preview-86f87c1c333f-40461897858-1/colormath-3.6.1-cpf11-preview-86f87c1c333f-40461897858-1.pom)或 [GitHub 制品仓库](https://github.com/qsxs/cpf-maven)。

| 已验工作流 | 手动输入 | 本次运行身份 |
| --- | --- | --- |
| [producer 历史源码](https://github.com/qsxs/cpf-port-tooling/blob/49d54d239482838dc187ba6b1ce8c9f8cd8231c0/.github/workflows/colormath-producer.yml) | `colormath_sha=86f87c1c333f0eb68af52afc88b73d82a536d6cf` | 工作流 `49d54d239482838dc187ba6b1ce8c9f8cd8231c0`；[40461897858/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40461897858/attempts/1) |
| [consumer 历史源码](https://github.com/qsxs/cpf-port-tooling/blob/b606affac816befd3b33269e57d9b79b89c31b0f/.github/workflows/colormath-consumer.yml) | `version=3.6.1-cpf11-preview-86f87c1c333f-40461897858-1`、`source_sha=86f87c1c333f0eb68af52afc88b73d82a536d6cf` | 工作流 `b606affac816befd3b33269e57d9b79b89c31b0f`；[40668960640/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40668960640/attempts/1) |

两次运行均将共享工具内容锁 A `d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285` 与各自实际工作流提交区分。Actions 选择器使用当前分支或标签；手动运行前须核对所选 ref 实际指向并记录新运行的 `github.sha`，不能假定当前分支仍指向表中历史提交。需要精确运行历史源码时须选择实际指向该提交的可选 ref。Producer 重跑生成含新 run id/attempt 的版本，仅上传 staging 和证据；维护者核对后手动发布，不能覆盖已验版本。Consumer 可重验已发布 GAV，不改写它。

[Pages 制品提交 `8b5e6932bb24`](https://github.com/qsxs/cpf-maven/commit/8b5e6932bb2490bca64f40e29e1f113090628274) 的 125 个文件、1,106,922 字节与 staging 经匿名 HTTP 逐字节对齐。Consumer 只从公开根 GAV 经 GMM 选择依赖，使用 Gradle 9.5.0 对 `Color.toHSL()` 完成 common metadata、OHOS x64、arm64 真实编译，并核对 9 个公开对象及编译输入。未单独验证 Gradle 8.11.1；link、runtime、设备与 Android/iOS 回归均未运行，App 尚未切换，不能据此认定 MaterialKolor 整体已完成。

保留的失败轨迹：producer [40459063023/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40459063023/attempts/1) 在官方 sysroot 下载超时，证据收集又遇 2 MiB 上限缺陷；`49d54d` 对超限证据做可校验的无损 gzip，并在证据收集出错时保留原始失败，随后 `40461897858/1` 成功。Consumer [40463827222/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40463827222/attempts/1) 的 Native 分发包下载超时，[/2](https://github.com/qsxs/cpf-port-tooling/actions/runs/40463827222/attempts/2) 因 Tasks 失败日志缺少首部而无法定位；`c0abe52ec39ede92238336d7bc1e84dd93789be7` 增加日志采集，[40466510798/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40466510798/attempts/1) 定位到 consumer DSL 中 nullable path；`b606affac816befd3b33269e57d9b79b89c31b0f` 修复后 `40668960640/1` 成功。
