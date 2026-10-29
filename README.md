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

## MaterialKolor 两模块 producer 与匿名 consumer

上游 [jordond/MaterialKolor 5.0.0](https://github.com/jordond/MaterialKolor/commit/13c67cfa5a724cb6dca7d15674b3ad2acf894853) 的主模块 23 份和 MCI 42 份原源来自 [Fork source `c5ef77766b6098677d541e82f362b666a8a0fff2`](https://github.com/qsxs/MaterialKolor/commit/c5ef77766b6098677d541e82f362b666a8a0fff2)。两模块已验版本均为 `5.0.0-cpf11-preview-c5ef77766b60-40672306467-1`，临时 Maven 根 `https://qsxs.github.io/cpf-maven/`（[主模块根 POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/materialkolor/material-kolor/5.0.0-cpf11-preview-c5ef77766b60-40672306467-1/material-kolor-5.0.0-cpf11-preview-c5ef77766b60-40672306467-1.pom)、[MCI 根 POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/materialkolor/material-color-utilities/5.0.0-cpf11-preview-c5ef77766b60-40672306467-1/material-color-utilities-5.0.0-cpf11-preview-c5ef77766b60-40672306467-1.pom)）。

| 已验工作流 | 实际工作流提交 | 运行 |
| --- | --- | --- |
| [producer 历史源码](https://github.com/qsxs/cpf-port-tooling/blob/b606affac816befd3b33269e57d9b79b89c31b0f/.github/workflows/materialkolor-producer.yml) | `b606affac816befd3b33269e57d9b79b89c31b0f` | [40672306467/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40672306467/attempts/1) |
| [consumer 历史源码](https://github.com/qsxs/cpf-port-tooling/blob/abadbfb0b5c33b35dfafdb966e8e759276c5de45/.github/workflows/materialkolor-consumer.yml) | `abadbfb0b5c33b35dfafdb966e8e759276c5de45` | [40675388144/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40675388144/attempts/1) |

两次运行的共享工具内容锁 A 均为 `d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285`，与表中工作流提交 B 区分。Actions 选择器使用当前分支或标签；重跑须核对所选 ref 的实际指向并记录该次 `github.sha`，不能假定当前分支仍指向历史 B。需要精确运行历史源码时须选择实际指向该提交的可选 ref。Producer 成功时上传验收通过的 staging，并另上传证据；维护者核对后手动发布。重跑使用新 run id/attempt 生成新版本，不覆盖已验版本。

本次 producer 输入：

```json
{"materialkolor_sha":"c5ef77766b6098677d541e82f362b666a8a0fff2","poko_version":"0.23.1-cpf11-preview-cbaa758d0b76-40451679040-1","poko_source_sha":"cbaa758d0b7610e0e445b8fd50739aa05afaea6e","poko_root_gmm_sha256":"297a49f82436065a6091bac3a3a98ad0825731cabdd1a25b0e05866972a88bca","colormath_version":"3.6.1-cpf11-preview-86f87c1c333f-40461897858-1","colormath_source_sha":"86f87c1c333f0eb68af52afc88b73d82a536d6cf","colormath_root_gmm_sha256":"9a518cc72bf41370bcf2848bd2a13b86c1ed6c5a714dad15ab98fde50af5087c"}
```

本次 consumer 输入：

```json
{"version":"5.0.0-cpf11-preview-c5ef77766b60-40672306467-1","source_sha":"c5ef77766b6098677d541e82f362b666a8a0fff2"}
```

[Pages 制品提交 `b2652094e033`](https://github.com/qsxs/cpf-maven/commit/b2652094e03379619138c7ec83ff614d5863a2a1) 的 280 个文件、1,994,693 字节与 staging 经匿名 HTTP 逐字节对齐。Consumer 使用 Gradle 9.5.0，只直接依赖 `material-kolor` 根，通过 GMM 传递解析 MCI、Poko、Colormath；真实主题 API 探针在 common metadata、OHOS x64、arm64 编译，39 条公开 HTTP 记录（38 个不同 URL）与各自 staging 记录对齐。Producer 和 consumer 各检查 54 项：6 个 MCI 类的 `equals`、`hashCode`、`toString` 在三个目标的 metadata 声明及签名，双 Native 另检查 IR 签名与非空 IR。未检查方法体，未单独验证 Gradle 8.11.1 消费；link、runtime、设备和 Android/iOS 回归未运行，App 尚未切换。

许可事实分别为：上游仓库根 LICENSE 与主模块发布 POM 为 MIT；MCI sources JAR 内 LICENSE 为 Apache-2.0，MCI 上游 POM 标注 MIT，而现 CPF MCI POM 沿用旧 OHOS 配置标注 Apache-2.0。原始 POM 与 LICENSE 保留，不推断双许可。

首轮 [40670139990/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40670139990/attempts/1) 的 Gradle `tasks --all` 已成功，随后发现脚本报告缺项；日志未捕获具体缺项。Fork `c5ef77766b6098677d541e82f362b666a8a0fff2` 改为检查带子模块限定的任务名并输出缺项，之后 `40672306467/1` 成功；不能从首轮尾日志断言具体缺项。

## ColorPicker producer 与匿名 consumer

上游 [skydoves/colorpicker-compose 1.2.0](https://github.com/skydoves/colorpicker-compose/commit/85f81afbccaf5c0837e402686b8db9d67cc74c59) 的 21 份原始 common 源与 Apache-2.0 许可证由 [Fork source `779519a9bc21278c9496a11c43828dc194cbe64c`](https://github.com/qsxs/colorpicker-compose/commit/779519a9bc21278c9496a11c43828dc194cbe64c) 保留。已验根 GAV 为 `io.github.qsxs.cpf.colorpicker:colorpicker-compose:1.2.0-cpf11-preview-779519a9bc21-40674004251-1`；临时 Maven 根 `https://qsxs.github.io/cpf-maven/`（[实际根 POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/colorpicker/colorpicker-compose/1.2.0-cpf11-preview-779519a9bc21-40674004251-1/colorpicker-compose-1.2.0-cpf11-preview-779519a9bc21-40674004251-1.pom)）。

| 已验工作流 | 本次输入 | 运行 |
| --- | --- | --- |
| [producer 历史源码](https://github.com/qsxs/cpf-port-tooling/blob/abadbfb0b5c33b35dfafdb966e8e759276c5de45/.github/workflows/colorpicker-producer.yml) | `colorpicker_sha=779519a9bc21278c9496a11c43828dc194cbe64c` | [40674004251/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40674004251/attempts/1) |
| [consumer 历史源码](https://github.com/qsxs/cpf-port-tooling/blob/abadbfb0b5c33b35dfafdb966e8e759276c5de45/.github/workflows/colorpicker-consumer.yml) | `version=1.2.0-cpf11-preview-779519a9bc21-40674004251-1`、`source_sha=779519a9bc21278c9496a11c43828dc194cbe64c` | [40676245219/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40676245219/attempts/1) |

两次已验工作流的实际提交 B 均为 `abadbfb0b5c33b35dfafdb966e8e759276c5de45`，共享工具内容锁 A 为 `d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285`，两者分别记录。Actions 选择器使用当前分支或标签；重跑前须核对所选 ref 实际指向并记录该次 `github.sha`，不能假定当前分支仍指向历史 B。精确运行历史源码须选择实际指向该提交的可选 ref。Producer 成功时上传验收通过的 staging，并另上传证据；维护者审核后手动发布。重跑产生带新 run id/attempt 的版本，不覆盖已验版本。

[Pages 制品提交 `af5af74fb640`](https://github.com/qsxs/cpf-maven/commit/af5af74fb6409cb9d2bc165253594e583ac8c4c2) 的 140 个文件、606,736 字节与 staging 经匿名 HTTP 逐字节对齐。Producer 编译全部 21 份原源，x64/arm64 各核验 53 个不同 API 名称：Native metadata 签名检查 50 个名称，另外检查 8 个枚举生成成员的 Native IR 签名；三个目标均验证实际使用的原有 Compose 和 serialization 两个 `2.4.20-0.1.0-08` 编译器插件，Compose runtime/foundation/ui 库依赖仍为 `implementation`。

Consumer 使用 Gradle 9.5.0 以公开根 GAV 经 GMM 完成 metadata、OHOS x64 和 arm64 真实编译；唯一探针覆盖 `HsvColorPicker` 的 `initialColor`/`onColorChanged`、`BrightnessSlider`、`ColorEnvelope.color` 和 `selectByColor(color, true)`。12 个公开对象与 staging 对齐、每次首次请求成功。Gradle 8.11.1 消费、link、runtime、设备和 Android/iOS 回归未运行，App 尚未切换。

审查阶段的 3 个 P1、1 个 P2 及复审 2 个 P2 均在首个云端构建之前修复；上述 producer 和 consumer 均为各自 attempt 1，不是云端重试。本机 Pages 字节核对有 4 条 curl stderr 出现超时，但最终均退出 0 且哈希匹配；云 consumer 的 12 次公开请求均首次成功。

## Koin producer 与匿名 consumer

上游 [InsertKoinIO/koin 4.2.2](https://github.com/InsertKoinIO/koin/commit/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb) 的 114 份原始 common/Native 源和 Apache-2.0 许可证由 [Fork source `4165003410d767a5281441312f70d21dea4d6aab`](https://github.com/qsxs/koin/commit/4165003410d767a5281441312f70d21dea4d6aab) 保留。[producer 40684515113/2](https://github.com/qsxs/cpf-port-tooling/actions/runs/40684515113/attempts/2) 完成生产和 Verify，工作流 B `4d01825448f83e87619888dade7e919562e8ecd4` 与共享内容锁 A `d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285` 分别记录。四模块根 GAV 的 group 为 `io.github.qsxs.cpf.koin`、版本为 `4.2.2-cpf11-preview-4165003410d7-40684515113-2`，模块为 `koin-core`、`koin-core-viewmodel`、`koin-compose` 和 `koin-compose-viewmodel`。

[Pages 制品提交 `4a430bb48508`](https://github.com/qsxs/cpf-maven/commit/4a430bb48508ba7ac948be3f052499262ce40957) 的 380 个文件、3,455,187 字节与 staging 经匿名 HTTP 逐字节对齐。临时 Maven 根为 `https://qsxs.github.io/cpf-maven/`（[koin-core 根 POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/koin/koin-core/4.2.2-cpf11-preview-4165003410d7-40684515113-2/koin-core-4.2.2-cpf11-preview-4165003410d7-40684515113-2.pom)）。15 条项目边在上传的输入/输出记录间匹配：7 条 metadata、8 条 Native；这不是对已删除 runner 输入重新哈希。Metadata CLI 参数在 runner 内验证，但原始 `producer.json` 与 `arguments.txt` 未上传，无法独立复核各参数；Native 任务输入不是完整 compiler argv。

项目依赖保持 `koin-core-viewmodel → koin-core`、`koin-compose → koin-core` 和 `koin-compose-viewmodel → koin-compose + koin-core-viewmodel`，均为项目 `api` 边；`koin-core` 无其他 Koin 项目依赖。Stately 沿用匿名 CPF 仓既有 `2.1.0-1.1.0` 制品，15 个对象身份匹配，不表示新构建或普遍 ABI 兼容。

[producer 历史工作流源码](https://github.com/qsxs/cpf-port-tooling/blob/4d01825448f83e87619888dade7e919562e8ecd4/.github/workflows/koin-producer.yml) 输入 `koin_sha=4165003410d767a5281441312f70d21dea4d6aab`；成功时上传验收通过的 staging，并另上传证据，由维护者核对后手动发布。重跑产生带新 run id/attempt 的版本，不覆盖已验版本。[本次 consumer 工作流源码](https://github.com/qsxs/cpf-port-tooling/blob/ed0e29a75c6f2a8a31af4a1c0ae68b8e170ffb0d/.github/workflows/koin-consumer.yml) 输入 `version=4.2.2-cpf11-preview-4165003410d7-40684515113-2`、`source_sha=4165003410d767a5281441312f70d21dea4d6aab`。Actions 分支选择器本次使用 `codex/initial-port-tooling`；重跑前核对实际 ref 指向并记录本次 `github.sha`，不能假定当前分支仍指向历史工作流 B。精确运行历史源码须选择实际指向该提交的可选 ref。

Producer [40684515113/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40684515113/attempts/1) 的 Native 包下载超时，[/2](https://github.com/qsxs/cpf-port-tooling/actions/runs/40684515113/attempts/2) 成功。Consumer [40689205374/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40689205374/attempts/1) 缺少 coroutines BOM 白名单，`e2926e62d51583c36a2c58c87bfe4c5bb6124a44` 修正；[40692875465/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40692875465/attempts/1) 匿名 HTTP 超时，[/2](https://github.com/qsxs/cpf-port-tooling/actions/runs/40692875465/attempts/2) 缺少 serialization BOM 白名单，`23e0202ca8c6f562781e6734cbc4ca61da6a83bb` 修正。[40695618284/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40695618284/attempts/1) 和 [/2](https://github.com/qsxs/cpf-port-tooling/actions/runs/40695618284/attempts/2) 的 Resolve 均成功，但 metadata 阶段下载官方 sysroot 超时；[/3](https://github.com/qsxs/cpf-port-tooling/actions/runs/40695618284/attempts/3) 在 Tasks 阶段失败，现有尾日志未包含根因；原始 runner stderr 未上传，无法判断原因，也不能归因网络。诊断提交 `ed0e29a75c6f2a8a31af4a1c0ae68b8e170ffb0d` 仅增加失败 stderr 的有界头部采集，已通过独立审查；[40703356336/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40703356336/attempts/1) 的 Resolve 成功后在 metadata 阶段下载 sysroot 超时，正常重试的 [/2](https://github.com/qsxs/cpf-port-tooling/actions/runs/40703356336/attempts/2) 使用该工作流提交和 Gradle 9.5.0，完成 Scope/ViewModel 探针的 common metadata、OHOS x64、arm64 真实编译。该次使用 K/N 标准按需下载，手工预填候选未应用；LLVM 与 sysroot 下载均至少发生一次连接超时，随后同次继续并完成。四模块 48 个公开对象与 staging 对齐，依赖边和三个解析配置已独立核对；Native Klib 完整文件 SHA 可与 staging 对齐。四个转换后的 metadata Klib 未上传本体，仅有 runner 路径、大小、SHA 和 metadataTrace，无法在本机独立重算其内部成员。

Gradle 8 消费、link、runtime、设备及 Android/iOS 回归未验证，App 引用未切换；历史运行证据不能代替本次新仓公开消费验收。

## Reorderable producer 与匿名 consumer

[Reorderable Fork source `85707894c99f8ce4c3fe10a84c870c71cee0b10b`](https://github.com/qsxs/Reorderable/commit/85707894c99f8ce4c3fe10a84c870c71cee0b10b) 保留上游 [v3.1.0](https://github.com/Calvin-LL/Reorderable/commit/66de5751227c440bcdbd63acc94999231ed67487) 的完整 9 份 common 原源、Apache-2.0 许可证和作者。[producer 40715768847/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40715768847/attempts/1) 使用工作流 B `8fd0a63cf246b2b8e90132b091506b49c9ebfb26`、共享工具锁 A `d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285`，完成 metadata、OHOS x64、arm64 生产；两个 ABI 各核验 43 个 Native metadata 名称及 4 个枚举 IR 签名。Runner 物理源码、插件和工具输入已清理，记录与来源锁匹配，但不能在本机重新哈希。

已发布根 GAV 为 `io.github.qsxs.cpf.reorderable:reorderable:3.1.0-cpf11-preview-85707894c99f-40715768847-1`；临时 Maven 根 `https://qsxs.github.io/cpf-maven/`（[根 POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/reorderable/reorderable/3.1.0-cpf11-preview-85707894c99f-40715768847-1/reorderable-3.1.0-cpf11-preview-85707894c99f-40715768847-1.pom)）。[Pages 制品提交 `3d5fe28dcc5b`](https://github.com/qsxs/cpf-maven/commit/3d5fe28dcc5b3a4cf326a8c413e649d7e0e2746a) 的 140 个文件、565,377 字节与 staging 匿名核验全部对齐；期间 15 次传输超时后重试，最终 140/140 匹配。

[consumer 40719398970/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40719398970/attempts/1) 的工作流 B 为 `2f30528fb9e0a90164d111788d701fd177897e63`。Gradle 9.5.0 的 `:compileCommonMainKotlinMetadata`、`:compileKotlinOhosX64`、`:compileKotlinOhosArm64` 已编译同一 1328B LazyList/LazyGrid 状态、item 及两种拖拽 handle 探针；12 个不同公开对象均首次 HTTP 成功并与 staging 对齐，三配置选择正确 root/leaf，Native Klib SHA 和 IR 已独立核对。Metadata 转换 Klib 原件未上传，不能在本机独立重哈希其内部成员。Gradle 8 消费、link、runtime、设备及 Android/iOS 回归未验，App 尚未切换。

[producer 历史工作流](https://github.com/qsxs/cpf-port-tooling/blob/8fd0a63cf246b2b8e90132b091506b49c9ebfb26/.github/workflows/reorderable-producer.yml) 输入完整 `reorderable_sha=85707894c99f8ce4c3fe10a84c870c71cee0b10b`；[consumer 历史工作流](https://github.com/qsxs/cpf-port-tooling/blob/2f30528fb9e0a90164d111788d701fd177897e63/.github/workflows/reorderable-consumer.yml) 输入已发布 version 与同一完整 source SHA。Actions 选择器使用分支或标签；重跑前须核对该 ref 的实际提交并记录 `github.sha`，不能假定当前分支仍指向历史 B。Producer 只交付 staging 和证据，Pages 须维护者核对后手动发布，不覆盖已有版本。

## ComposeCharts producer 与匿名 consumer（已验）

[上游 ComposeCharts 1.0.0](https://github.com/ehsannarmani/ComposeCharts/commit/8553b2bdbe209187fbba4fa3b567ce2fb978206a) 的 41 common 和 1 native 原源由 [Fork source `bce8769199ad`](https://github.com/qsxs/ComposeCharts/commit/bce8769199ad65d406d0843dd7cc8806c1437b30) 保留；配方从 Git blob 核对 sources JAR 后生成隔离源码，避免 Windows CRLF 工作树造成来源误判。上游 LICENSE 是 Apache-2.0，原 POM/模块发布配置声明 MIT；根据此前用户决定，CPF 私有 POM 写 Apache-2.0，保留原件，不推断双许可。

[producer 40800613406/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40800613406/attempts/1) 的工作流 B 为 `03ca69673f5875030198588b972a9ff21f35732e`，公共工具内容锁 A 为 `d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285`。Metadata 及双 ABI 生产已完成；每个 ABI 检查 604 个 metadata 名称及 4 个枚举的 16 条生成 IR 签名。Runner 物理输入及原编译输出未保留，不能本机重新哈希。

根 GAV 为 `io.github.qsxs.cpf.charts:compose-charts:1.0.0-cpf11-preview-bce8769199ad-40800613406-1`，临时 Maven 根 `https://qsxs.github.io/cpf-maven/`（[根 POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/charts/compose-charts/1.0.0-cpf11-preview-bce8769199ad-40800613406-1/compose-charts-1.0.0-cpf11-preview-bce8769199ad-40800613406-1.pom)）。[Pages 制品提交 `65b972781ab9`](https://github.com/qsxs/cpf-maven/commit/65b972781ab9f6dd23c613f6c8a04615236d118d) 的 170 文件、1,716,733 字节经修正批次匿名核对 170/170 匹配，批次零重试；此前一次本机 POM 请求超时，上一轮统计汇总无效。

[consumer 工作流源码](https://github.com/qsxs/cpf-port-tooling/blob/f06a5b40ce0e6e458ce42c6a9572663502c4ea24/.github/workflows/charts-consumer.yml) 的 B 为 `f06a5b40ce0e6e458ce42c6a9572663502c4ea24`。[40802580898/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40802580898/attempts/1) 核对 13 个公开对象并解析三配置后，在 metadata 准备阶段下载 sysroot 连续 10 次连接超时失败；[/2](https://github.com/qsxs/cpf-port-tooling/actions/runs/40802580898/attempts/2) 和 [/3](https://github.com/qsxs/cpf-port-tooling/actions/runs/40802580898/attempts/3) 同样在该阶段超时失败；[/4](https://github.com/qsxs/cpf-port-tooling/actions/runs/40802580898/attempts/4) 使用 Gradle 9.5.0 完成 metadata、OHOS x64 和 arm64 真实编译。该次标准按需下载在 sysroot 出现 Connect timed out 后继续完成，同 runner 重试提案未应用；该次 13 个不同公开 Maven 对象均首次 HTTP 200，大小与 SHA-256 与 staging 对齐；三配置选择正确 root/leaf，sources JAR 的 41 common+1 native 源及 metadata manifest 与 Git 输入匹配，992B ColumnChart/LineChart/PieChart 探针完成三目标编译，双 Native Klib 输入 SHA 对齐。Metadata JAR 的 43 个成员与匿名 HTTP 和 runner trace 记录匹配；转换后 Klib 及 runner 物理输入未上传，本机不能独立重哈其内部。Gradle 8、link、runtime、设备及 Android/iOS 回归未验证，App 未切换。历史 Popup 坐标和标签/提示裁切问题仍按用户决定延期。

[producer 历史工作流](https://github.com/qsxs/cpf-port-tooling/blob/03ca69673f5875030198588b972a9ff21f35732e/.github/workflows/charts-producer.yml) 输入 `charts_sha=bce8769199ad65d406d0843dd7cc8806c1437b30`；consumer 输入 `version=1.0.0-cpf11-preview-bce8769199ad-40800613406-1` 和 `source_sha=bce8769199ad65d406d0843dd7cc8806c1437b30`。Actions 选择器使用分支或标签，重跑须核对所选 ref 的实际提交并记录 `github.sha`；producer 只上传 staging 和证据，由维护者核对后手动发布。

## Calendar producer 与匿名 consumer（公开消费编译已验）

[上游 Calendar 2.10.1](https://github.com/kizitonwose/Calendar/commit/0e94f40b5849d92a6f1390b9e39a0d316c7d5408) 的 41 common 源、MIT 许可与作者由 [Fork source `03ea871e06df`](https://github.com/qsxs/Calendar/commit/03ea871e06df80e2bd96bb11f94c0b389c07be15) 保留，并沿用两份 OHOS actual 和 `calendar_icu.def`。旧 JAR 中两份资源生成源码不重复编译，Compose Resources 正式生成源码；上游没有 `composeResources` 资源资产。Prepare 使用 Git blob，避免 Windows CRLF 工作树来源误判。

[producer 40814095761/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40814095761/attempts/1) 使用工作流 B `88afbf38d426240bc0923539630a2fb262df695c` 与工具锁 A `d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285`，完成 metadata 和双 ABI 生产；每 ABI 包含主 Klib 与 ICU cinterop Klib，核对 17 个代表性 metadata 名称，并非完整 API 逐项或运行验证。Runner 物理输入及输出未保留，不能本机重新哈希。

根 GAV 为 `io.github.qsxs.cpf.calendar:compose-multiplatform:2.10.1-cpf11-preview-03ea871e06df-40814095761-1`，临时 Maven 根 `https://qsxs.github.io/cpf-maven/`（[根 POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/calendar/compose-multiplatform/2.10.1-cpf11-preview-03ea871e06df-40814095761-1/compose-multiplatform-2.10.1-cpf11-preview-03ea871e06df-40814095761-1.pom)）。[Pages 制品提交 `299a43ce93ad`](https://github.com/qsxs/cpf-maven/commit/299a43ce93ad6786940cb4a89362ae43812f759c) 的 150 文件、1,042,859 字节经修正批次匿名核对 150/150 匹配，批次零重试。CPF `.08` sysroot `26.0.0.38-01` 是外部 cinterop 构建输入，归档及所选头文件/双 ABI 库已核验；`libicu.so` 未打包，K/N 依赖仍按需下载。DevEco `26.0.0.105` 入口保留，但原库与候选库字节不同，完整 ABI/runtime 等价性未建立。

[此前 consumer 工作流源码](https://github.com/qsxs/cpf-port-tooling/blob/fc8690060ba0d989e51829a07c9201ede67949e4/.github/workflows/calendar-consumer.yml) 的 B 为 `fc8690060ba0d989e51829a07c9201ede67949e4`。[40815939032/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40815939032/attempts/1) 在 Resolve 下载 CPF Maven 的宿主依赖 `org.jetbrains:annotations:23.0.0` 时连接超时；[/2](https://github.com/qsxs/cpf-port-tooling/actions/runs/40815939032/attempts/2) 的 Resolve 成功，但 metadata 准备阶段下载 sysroot 连续 10 次连接超时失败；[/3](https://github.com/qsxs/cpf-port-tooling/actions/runs/40815939032/attempts/3) metadata 任务通过（独立证据复核待完成），NativeX64 因 `skiko-ohosx64-api` 与 `skiko-ohosx64` 的 `unique_name` 相同失败，arm64 未运行；用户批准按 producer 接线，脚本提交 [`04a3f59830287f6180648bf6665ea403d028ae7d`](https://github.com/qsxs/cpf-port-tooling/commit/04a3f59830287f6180648bf6665ea403d028ae7d) 声明并应用 Compose 插件 `1.12.0-0.1.0-11`，沿用 `rendererBackend=skia`；插件含 OHOS 依赖版本对齐及 Skia 模式下 Skiko api/fusionrenderer 请求替换为同 ABI 完整 Skiko 的规则；[新 consumer 40820357469/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40820357469/attempts/1) 的 Resolve 已将 x64/arm64 的 api/fusionrenderer 请求选为各自完整 Skiko `0.150.1-0.1.0-10`，随后 metadata 因 CPF Maven develop 的 Compose/serialization compiler `.08` POM 连接超时失败；[/2](https://github.com/qsxs/cpf-port-tooling/actions/runs/40820357469/attempts/2) 正常重试以 Gradle 9.5.0 完成月、周日历探针的 metadata、OHOS x64 和 arm64 真实编译。18 个不同匿名对象均首次请求成功并与 staging 对齐，解析到的外部 GAV 均匹配固定 pins；双 ABI 的 Skiko api/fusionrenderer 请求只选中各自完整 Skiko `0.150.1-0.1.0-10`。双 ABI 主 Klib 与 ICU cinterop Klib 的编译输入 SHA-256 均与 staging 一致，cinterop manifest 保留 `-licu`；metadata JAR 的 45 个成员与公开 HTTP 和 runner trace 一致，转换后的 Klib 与 runner 物理输入未上传，无法在本机独立重哈。Gradle 8、link、runtime、设备和 Android/iOS 回归未验，App 未切换，CAL-R1 仍延期。

[producer 历史工作流](https://github.com/qsxs/cpf-port-tooling/blob/88afbf38d426240bc0923539630a2fb262df695c/.github/workflows/calendar-producer.yml) 输入 `calendar_sha=03ea871e06df80e2bd96bb11f94c0b389c07be15`；consumer 输入 `version=2.10.1-cpf11-preview-03ea871e06df-40814095761-1` 和 `source_sha=03ea871e06df80e2bd96bb11f94c0b389c07be15`。Actions 选择器使用分支或标签，重跑须核对所选 ref 的实际提交并记录 `github.sha`；producer 成功时上传 staging 和证据，由维护者核对后手动发布。


## Lyricist 与 Lyricist-core

[Fork source `fad3d9091c75`](https://github.com/qsxs/lyricist/commit/fad3d9091c75927320da3511350202e681269b2a) 保留上游 Lyricist 1.8.0 两模块各一份完整 common 原源、MIT 许可与作者；`lyricist` 对 `lyricist-core` 为 `api`，coroutines 为 `implementation`，Compose runtime/ui 为 `compileOnly`；`lyricist-core` 的 coroutines 为 `implementation`，两模块保留 `explicitApi Strict`。

两个根 GAV 为 `io.github.qsxs.cpf.lyricist:lyricist:1.8.0-cpf11-preview-fad3d9091c75-40827525373-1` 和 `io.github.qsxs.cpf.lyricist:lyricist-core:1.8.0-cpf11-preview-fad3d9091c75-40827525373-1`；公开 Maven 根 `https://qsxs.github.io/cpf-maven/`（[lyricist POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/lyricist/lyricist/1.8.0-cpf11-preview-fad3d9091c75-40827525373-1/lyricist-1.8.0-cpf11-preview-fad3d9091c75-40827525373-1.pom)、[core POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/lyricist/lyricist-core/1.8.0-cpf11-preview-fad3d9091c75-40827525373-1/lyricist-core-1.8.0-cpf11-preview-fad3d9091c75-40827525373-1.pom)）。

[producer 40827525373/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40827525373/attempts/1) 使用工作流 `a2e3e537cfeffea4f9e63c70b190e46daddbd1ac`、共享工具锁 `d0cff88fd1ea2e4f08bb4409f1c802cca0c7f285` 完成 metadata 和 OHOS x64/arm64 生产及独立 staging 核验。Metadata 编译器库与 core 输出记录相符；Native 解析配置与 core 输出记录相符，但 Native 编译器 libraries、完整 compiler argv、taskDependencies 和 runner 物理输入未上传，不能在本机确认实际 Native 编译器输入或重哈这些路径。

[Pages 提交 `d4aeac15ad29`](https://github.com/qsxs/cpf-maven/commit/d4aeac15ad29f85497a733b133f12f2164322b44) 的 270 个文件、354,689 字节在修正匿名批次中与 staging 全部对齐，该批 270/270 首次请求成功；首轮将分隔符误计入响应 body，统计无效。 [consumer 40829692921/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40829692921/attempts/1) 使用工作流 `469293ce18774921a87627e756a617bff115b368` 和 Gradle 9.5.0，完成 `@LyricistStrings`、`rememberStrings`、语言 tag 和 `Lyricist.strings` 探针的 metadata、OHOS x64 与 arm64 真实编译；三个配置中 `lyricist` 通过 `api` 解析 `lyricist-core`，Compose runtime/ui 由 consumer 显式提供，不作为库的传递依赖。44 条公开 HTTP 记录与 staging 对齐，其中仅 38 条响应 body 随证据上传并可在本机复哈；四个 Native Klib 输入记录与 Pages/staging SHA-256 一致。两个 metadata trace 各有三个成员，但转换后的 metadata Klib 与 runner 物理输入未上传，无法本机独立重哈。

Gradle 8 消费、link、runtime、设备和 Android/iOS 回归未验证，App 引用尚未切换。Wheel 的 producer、Pages 及 Gradle 9.5 三目标公开消费编译已验；[consumer 40841841344/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40841841344/attempts/1) 完成业务探针编译，未获授权移除其 Lyricist 依赖。


## DateTime Wheel Picker

上游 Wheel 1.4.0 的完整 61 份 common 源包含 60 份 Git blob 与 1 份官方 sources JAR 的 KSP 生成 `Strings.kt`；33 语言、Apache-2.0 许可和作者保留，未重跑 Lyricist processor。Wheel 对 runtime、Material3、datetime 与 Lyricist 保持 `implementation`，Lyricist 对同版 core 为 `api`；所有 Wheel sourceSet 保留 `kotlin.time.ExperimentalTime` opt-in。

[producer 40839510773/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40839510773/attempts/1) 使用 source `18ea344423c94bff10c4bf7c43d1bbd408efafc9` 和 workflow `0862e8096aede7971366ae568f1e53a3dc108b3e`，完成 metadata、OHOS x64/arm64、Publish 和 Verify，staging 已独立核对。根 GAV 为 `io.github.qsxs.cpf.wheel:datetime-wheel-picker:1.4.0-cpf11-preview-18ea344423c9-40839510773-1`（[根 POM](https://qsxs.github.io/cpf-maven/io/github/qsxs/cpf/wheel/datetime-wheel-picker/1.4.0-cpf11-preview-18ea344423c9-40839510773-1/datetime-wheel-picker-1.4.0-cpf11-preview-18ea344423c9-40839510773-1.pom)）；公开 Maven 根为 `https://qsxs.github.io/cpf-maven/`。

[Pages 提交 `b826affc3704`](https://github.com/qsxs/cpf-maven/commit/b826affc370404ecedcd1b5fca418ad5eeae3940) 的 140 个文件、1,246,983 字节与 staging 匿名核对 140/140 一致，零重试。 [consumer 40841841344/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40841841344/attempts/1) 使用 workflow `0862e8096aede7971366ae568f1e53a3dc108b3e` 和 Gradle 9.5.0，仅直接依赖 Wheel 根，在 metadata、OHOS x64 和 arm64 中传递解析 Wheel→Lyricist→core，并实际编译 `WheelDatePicker`、`WheelDateTimePicker`、`timeFormatter` 与回调探针。66 条匿名 HTTP 记录与 staging 对齐；其中 57 条响应 body 随证据上传并可本机复哈，另 9 条仅保留 runner 记录。

Producer 未记录或上传完整 compiler argv 与 taskDependencies；consumer 转换后的 metadata Klib 和 runner 物理输入未上传，不能在本机独立重哈。Gradle 8 消费、link、runtime、设备及 Android/iOS 回归未验证，App 引用尚未切换；用户未授权移除 Lyricist 依赖。

## FileKit 0.16.0 OHOS（consumer 三目标编译已验）

[producer 40864370116/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40864370116/attempts/1) 使用 FileKit source `22683094fd5d30ef08441d073c797161804b9dc4` 和工作流 `e0116f36d402498b7a7fa2a6a37397ee5ec5b467`，完成 Metadata、OHOS x64/arm64、Publish 和 Verify；这些结果仅针对该次 producer。Metadata 的 LLVM 下载曾出现 EOF，重试后最终成功，不能将全部构建耗时归因于该下载问题。

两根 GAV 使用同一预览版本：

```text
io.github.qsxs.cpf.filekit:filekit-core:0.16.0-cpf11-preview-22683094fd5d-40864370116-1
io.github.qsxs.cpf.filekit:filekit-dialogs:0.16.0-cpf11-preview-22683094fd5d-40864370116-1
```

[Pages 源提交 `60752c680a23`](https://github.com/qsxs/cpf-maven/commit/60752c680a23322f8af23d9370677cb077011d31) 的 285 个文件、1,464,278 字节经匿名 HTTP 核对 285/285 与 staging 一致。dialogs 根同版 `arkts-sources@zip` 仅含 `FileKitShareFactory.ets`；上游与社区两份 MIT 许可均保留。

[consumer 40881058391/1](https://github.com/qsxs/cpf-port-tooling/actions/runs/40881058391/attempts/1) 已成功，使用 workflow `c4433b0c58150fafaa47696a6a72bc334e1d9d9b`、Gradle 8.11.1、JDK 17 和 Kotlin 2.4.20-0.1.0-08；source、version 与 producer fingerprint `9b6d8d85d7cb6b6ce547b55ae699f5a930433a87ce6e15b66bba96fecc6fb80c` 一致。Metadata、OHOS x64 和 arm64 三个任务实际执行成功；两个 ABI 分别选取对应平台的 core/dialogs KLIB，并核实 dialogs → core 传递边。49 次匿名请求均为 HTTP 200，其中归档的 36 份元数据可独立复核哈希；证据 ZIP 未包含编译输出二进制，不能独立重哈这些输出。

旧 P4 的完整 63 项矩阵、D019 内部短写计数、D022 原子回执及分享 drain、K3、其余 HEIC/图像矩阵和物理 ARM 等仍待验；P6 分享仍暂缓且非 PASS，OHOS 文件业务暂为 UTF-8，GBK 与共享 CSV 模板兼容延期。探针只覆盖 picker/readBytes、三参 init/session、saver、source/sink、两种压缩重载和 shareFile 调用的编译，不证明运行行为。consumer 收据中的 link、runtime、device、armDevice 和 ArkTS 编译均为 NOT_RUN。Android/iOS 平台及主工程 Gradle 门禁本次未验证；Android/iOS 和系统 SDK 不变，App 引用尚未切换。
