# CPF port tooling

固定版本 CPF/OHOS 库端口的最小 Python 标准库工具。提供 `physical/load/record/write/copy_exact` 与完整组件 Maven 快照；不导入应用或其他库配置。维护者已批准 Apache-2.0 公开，原来源、作者 Lihb 及授权说明见 `PROVENANCE.json`/`NOTICE`，许可证不因本次文档收口改变。

`mirror_cache(work, pins, cache_root=..., gradle_api=(9, 5, 0), tool_allowlist=[...])` 只镜像 pins/显式工具白名单内的完整组件，保留原 GMM/POM 字节、available-at 与 URL。缺件交给正常远端解析，不暴露半个组件。`write/copy_exact` 遇既有不同内容会失败；不下载或删除文件。Grid helper 仍锁 [`d063c7c70ffbc3f241d7e8bdd184add33dc9a009`](https://github.com/qsxs/cpf-port-tooling/commit/d063c7c70ffbc3f241d7e8bdd184add33dc9a009) 及逐文件 hash，和下面的工作流提交明确区分。

## Grid 已验交付

根坐标：`com.github.qsxs.gridlayout-compose:grid:2.8.0-cpf11-preview-ed3472803fdb-40432726650-1`，公开 Maven 根为 [Pages](https://qsxs.github.io/cpf-maven/)。115 文件/474253B 已逐字节核验；隔离 consumer metadata/双 Native 编译已过，link/runtime 与设备/Android/iOS 回归未执行。Grid 收口文档提交发布后暂停，不迁其他库或修改 App 引用。

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
