const state = {
  previewTimer: null,
  previewRequest: null,
  previewSequence: 0,
  lastResult: null,
  editedCodebook: null,
  sourceName: null,
  sourceSize: null,
  dragDepth: 0,
  csrfToken: null,
  csrfRequest: null,
  workflowState: "empty",
  lastReadiness: { input: false, provider: false, ready: false, segments: 0 },
  settingsOpen: false,
  settingsRestoreFocus: null,
  gioiaDirty: false,
  codebookHistory: [],
  lastProvider: null,
  lastAttemptFingerprint: null,
  lastSuccessfulFingerprint: null,
  activeJobId: null,
  resultJobId: null,
  bundleDownloadUrl: null,
  jobPollTimer: null,
  jobPollController: null,
};

const $ = (id) => document.getElementById(id);

const WORKFLOW_STATES = new Set([
  "empty",
  "configured",
  "ready",
  "queued",
  "running-stage",
  "succeeded",
  "failed",
  "edited",
  "exported",
]);

const ACTIVE_RUN_STATES = new Set(["queued", "running-stage"]);
const SETTINGS_STORAGE_KEY = "gtflow.ui.settings.v1";
const SAVED_SETTING_IDS = [
  "providerName",
  "model",
  "outputLanguage",
  "temperature",
  "maxTokens",
  "structuredOutput",
  "segmentationStrategy",
  "maxSegmentChars",
  "batchSize",
  "concurrentWorkers",
  "rateLimitRps",
  "timeoutSec",
  "streamThreshold",
  "streamOpenCoding",
  "maxPromptChars",
  "retryMax",
];

const LANGUAGE_OPTIONS = [
  { value: "English", label: "English", htmlLang: "en" },
  { value: "Chinese", label: "简体中文", htmlLang: "zh-CN" },
  { value: "Traditional Chinese", label: "繁體中文", htmlLang: "zh-Hant" },
  { value: "Japanese", label: "日本語", htmlLang: "ja" },
  { value: "French", label: "Français", htmlLang: "fr" },
  { value: "Spanish", label: "Español", htmlLang: "es" },
  { value: "German", label: "Deutsch", htmlLang: "de" },
  { value: "Korean", label: "한국어", htmlLang: "ko" },
];

const TRANSLATIONS = {
  English: {
    "brand.subtitle": "Grounded theory workspace",
    "section.connection": "Connection",
    "section.generation": "Generation",
    "section.costModel": "Cost model",
    "section.runSetup": "Run setup",
    "section.throughput": "Throughput",
    "section.advancedLimits": "Advanced limits",
    "label.provider": "Provider",
    "label.model": "Model",
    "label.apiKey": "API key",
    "label.baseUrl": "Base URL",
    "label.organization": "Organization",
    "label.useResponses": "Use Responses API when supported",
    "label.endpoint": "Endpoint",
    "label.deployment": "Deployment",
    "label.apiVersion": "API version",
    "label.outputLanguage": "Language",
    "label.temperature": "Temperature",
    "label.maxTokens": "Max tokens",
    "label.structuredOutput": "Structured JSON output",
    "label.priceIn": "Input $/1k",
    "label.priceOut": "Output $/1k",
    "label.segmentation": "Segmentation",
    "label.segmentSize": "Segment size",
    "label.batch": "Batch",
    "label.workers": "Workers",
    "label.rateSec": "Rate/sec",
    "label.timeoutSec": "Timeout sec",
    "label.streamAt": "Stream at",
    "label.streamOpenCoding": "Stream open coding for large runs",
    "label.promptChars": "Prompt chars",
    "label.retryAttempts": "Retry attempts",
    "label.sourceText": "Source text",
    "privacy.providerTransfer": "Running analysis sends source text and generated context to the selected provider. Preview is processed only by this local server and never includes your API key.",
    "privacy.sourceOnRun": "Source text is sent to the configured provider only after you choose Run analysis.",
    "privacy.hostRemote": "Run destination: {host} (remote). The API key is kept in memory for this session and is not saved by GTFlow.",
    "privacy.hostLocal": "Run destination: {host} (local service). Source text does not leave this device unless that service forwards it.",
    "privacy.hostMissing": "Enter a valid provider endpoint to see where run data will be sent.",
    "option.dialog": "Dialog",
    "option.paragraph": "Paragraph",
    "option.line": "Line",
    "top.eyebrow": "GTFlow studio",
    "top.title": "Qualitative evidence into theory.",
    "title.localWorkspace": "The interface and preview run on this device",
    "stage.source": "Source",
    "stage.sourceSub": "Paste or upload",
    "stage.provider": "Provider",
    "stage.providerSub": "Model and key",
    "stage.run": "Run",
    "stage.runSub": "Pipeline",
    "stage.review": "Review",
    "stage.reviewSub": "Gioia and contrasts",
    "stage.export": "Export",
    "stage.exportSub": "ZIP bundle",
    "source.title": "Source",
    "source.copy": "Paste text or load .txt, .md, .csv, or .jsonl.",
    "source.dropTitle": "Choose or drop source",
    "source.fileStatus": "Text stays editable after loading.",
    "source.dropOverlayTitle": "Drop file to load",
    "source.dropOverlayCopy": ".txt, .md, .csv, or .jsonl",
    "preview.title": "Preview",
    "preview.copy": "Segments and readiness update as you work.",
    "preview.empty": "No segments yet.",
    "preview.loading": "Updating preview…",
    "preview.showing": "Showing {shown} of {total}",
    "metric.segments": "Segments",
    "metric.characters": "Characters",
    "metric.avgChars": "Avg chars",
    "check.sourcePending": "Paste or upload source text.",
    "check.providerPending": "Add model and API settings.",
    "check.runPending": "Waiting for a complete setup.",
    "check.sourceReady": "{count} characters prepared.",
    "check.providerReady": "Provider settings look complete.",
    "check.runReady": "{count} segments ready for analysis.",
    "check.runBlocked": "Complete source and provider setup first.",
    "runHelp.initial": "Add source text and provider settings to begin.",
    "runHelp.ready": "Ready: {count} segments will be analyzed and exported as a ZIP.",
    "runHelp.missingSource": "source text",
    "runHelp.missingProvider": "provider settings",
    "runHelp.missing": "Add {items} to begin.",
    "runHelp.setupDetails": "setup details",
    "join.and": " and ",
    "button.clear": "Clear",
    "button.choose": "Choose",
    "button.run": "Run analysis",
    "button.running": "Running",
    "button.downloadZip": "Download ZIP",
    "button.settings": "Settings",
    "button.cancelRun": "Cancel",
    "button.cancelling": "Cancelling…",
    "progress.running": "Running analysis",
    "progress.runningCopy": "This can take a few minutes depending on provider latency.",
    "progress.starting": "Starting analysis",
    "progress.startingCopy": "GTFlow is preparing the local pipeline. Model requests go to the configured provider.",
    "progress.coding": "Coding segments",
    "progress.codingCopy": "Open coding and codebook generation are in progress.",
    "progress.complete": "Complete",
    "progress.completeCopy": "Artifacts are ready for review and export.",
    "progress.failed": "Analysis failed",
    "progress.failedCopy": "The previous successful result is still available. Review the settings and try again.",
    "progress.stageCopy": "Stage progress: {percent}%",
    "progress.cancelled": "Analysis cancelled",
    "progress.cancelledCopy": "No partial result was treated as complete. The previous successful result remains available.",
    "job.stage.queued": "Queued",
    "job.stage.starting": "Starting analysis",
    "job.stage.segmenting": "Segmenting source",
    "job.stage.open-coding": "Open coding",
    "job.stage.codebook": "Building codebook",
    "job.stage.axial-coding": "Axial coding",
    "job.stage.selective-coding": "Selective coding",
    "job.stage.validation": "Negative cases and saturation",
    "job.stage.finalizing": "Finalizing analysis",
    "job.stage.packaging": "Building audit bundle",
    "job.stage.complete": "Complete",
    "job.stage.cancelling": "Cancelling",
    "job.stage.cancelled": "Cancelled",
    "results.eyebrow": "Analysis output",
    "results.coreCategory": "Core category",
    "stat.segments": "Segments",
    "stat.open_codes": "Open codes",
    "stat.initial_codes": "Initial codes",
    "stat.codebook_entries": "Codebook entries",
    "stat.triples": "Triples",
    "tab.overview": "Overview",
    "tab.gioia": "Gioia",
    "tab.contrasts": "Contrasts",
    "tab.negatives": "Negatives",
    "tab.saturation": "Saturation",
    "tab.data": "Data",
    "overview.title": "Top codes",
    "overview.copy": "Most frequent codes in the current run.",
    "gioia.title": "Gioia alignment",
    "gioia.copy": "Edit theme and dimension alignment, then export the adjusted codebook.",
    "gioia.filter": "Code contains",
    "gioia.theme": "Set second-order theme",
    "gioia.dimension": "Set aggregate dimension",
    "gioia.apply": "Apply batch alignment",
    "gioia.save": "Save changes",
    "gioia.undo": "Undo",
    "gioia.dirty": "Unsaved edits. Save to rebuild the Gioia view, report, and ZIP bundle.",
    "gioia.saved": "Edits saved and export artifacts rebuilt.",
    "gioia.batchStaged": "Batch alignment staged. Review the table, then save changes.",
    "gioia.undone": "The previous alignment was restored.",
    "gioia.blankCode": "Every row needs a code before it can be saved.",
    "gioia.duplicateCode": "Code names must be unique: {code}",
    "gioia.column.code": "Code",
    "gioia.column.definition": "Definition",
    "gioia.column.theme": "Theme",
    "gioia.column.dimension": "Dimension",
    "gioia.column.aliases": "Aliases",
    "gioia.aria.code": "Code, row {row}",
    "gioia.aria.definition": "Definition, row {row}",
    "gioia.aria.theme": "Second-order theme, row {row}",
    "gioia.aria.dimension": "Aggregate dimension, row {row}",
    "gioia.aria.aliases": "Aliases, row {row}",
    "data.segments": "Segments",
    "data.openCodes": "Open codes",
    "data.codebook": "Codebook",
    "table.empty": "No data yet.",
    "chart.empty": "No chart data yet.",
    "toast.previewFailed": "Preview failed",
    "toast.runFailed": "Run failed",
    "toast.cancelRequested": "Cancellation requested.",
    "toast.batchApplied": "Batch alignment applied.",
    "toast.gioiaFailed": "Could not save Gioia edits.",
    "toast.firstFile": "Loaded the first dropped file.",
    "toast.readFailed": "Could not read {name}.",
    "status.fileLoaded": "{name} loaded ({size}).",
    "status.localWorkspace": "Local workspace",
    "phase.empty": "Empty",
    "phase.configured": "Configured",
    "phase.ready": "Ready",
    "phase.queued": "Queued",
    "phase.running-stage": "Running",
    "phase.succeeded": "Complete",
    "phase.failed": "Failed",
    "phase.edited": "Edited",
    "phase.exported": "Exported",
    "workflow.status": "Workflow state: {state}",
    "placeholder.apiKey": "Use env var or paste key",
    "placeholder.organization": "Optional org id",
    "placeholder.azureEndpoint": "https://resource.openai.azure.com",
    "placeholder.azureDeployment": "deployment name",
    "placeholder.optional": "Optional",
    "placeholder.inputText": "Paste interview excerpts, field notes, or uploaded file content here.\n\nParticipant A: ...\nParticipant B: ...",
    "aria.workflow": "Analysis workflow",
    "aria.dropZone": "Choose or drop a source file",
    "aria.readiness": "Readiness checklist",
    "aria.resultViews": "Result views",
    "aria.settings": "Analysis settings",
    "aria.closeSettings": "Close settings",
    "aria.skipWorkspace": "Skip to workspace",
    "aria.preview": "Segmentation preview",
  },
  Chinese: {
    "brand.subtitle": "扎根理论工作台",
    "section.connection": "连接",
    "section.generation": "生成",
    "section.costModel": "成本模型",
    "section.runSetup": "运行设置",
    "section.throughput": "吞吐",
    "section.advancedLimits": "高级限制",
    "label.provider": "服务商",
    "label.model": "模型",
    "label.apiKey": "API 密钥",
    "label.baseUrl": "基础 URL",
    "label.organization": "组织",
    "label.useResponses": "可用时使用 Responses API",
    "label.endpoint": "端点",
    "label.deployment": "部署",
    "label.apiVersion": "API 版本",
    "label.outputLanguage": "语言",
    "label.temperature": "温度",
    "label.maxTokens": "最大 tokens",
    "label.structuredOutput": "结构化 JSON 输出",
    "label.priceIn": "输入 $/1k",
    "label.priceOut": "输出 $/1k",
    "label.segmentation": "分段方式",
    "label.segmentSize": "分段大小",
    "label.batch": "批量",
    "label.workers": "并发",
    "label.rateSec": "速率/秒",
    "label.timeoutSec": "超时秒数",
    "label.streamAt": "流式阈值",
    "label.streamOpenCoding": "大规模运行时流式开放编码",
    "label.promptChars": "提示字符数",
    "label.retryAttempts": "重试次数",
    "label.sourceText": "来源文本",
    "privacy.providerTransfer": "运行分析时，来源文本和生成的上下文会发送给所选服务商。预览仅由本地服务器处理，且绝不会包含 API 密钥。",
    "privacy.sourceOnRun": "只有在选择“运行分析”后，来源文本才会发送到已配置的服务商。",
    "privacy.hostRemote": "运行目标：{host}（远程）。API 密钥仅保留在本次会话内存中，GTFlow 不会保存。",
    "privacy.hostLocal": "运行目标：{host}（本地服务）。除非该服务继续转发，否则来源文本不会离开本设备。",
    "privacy.hostMissing": "请输入有效的服务商端点，以确认运行数据将发送到哪里。",
    "option.dialog": "对话",
    "option.paragraph": "段落",
    "option.line": "行",
    "top.eyebrow": "GTFlow 工作室",
    "top.title": "从质性证据走向理论。",
    "title.localWorkspace": "界面和预览在本设备上运行",
    "stage.source": "来源",
    "stage.sourceSub": "粘贴或上传",
    "stage.provider": "服务商",
    "stage.providerSub": "模型与密钥",
    "stage.run": "运行",
    "stage.runSub": "管线",
    "stage.review": "审阅",
    "stage.reviewSub": "Gioia 与对比",
    "stage.export": "导出",
    "stage.exportSub": "ZIP 包",
    "source.title": "来源",
    "source.copy": "粘贴文本，或加载 .txt、.md、.csv、.jsonl。",
    "source.dropTitle": "选择或拖入来源",
    "source.fileStatus": "加载后文本仍可编辑。",
    "source.dropOverlayTitle": "松开以加载文件",
    "source.dropOverlayCopy": ".txt、.md、.csv 或 .jsonl",
    "preview.title": "预览",
    "preview.copy": "分段和就绪状态会随操作更新。",
    "preview.empty": "还没有分段。",
    "preview.loading": "正在更新预览…",
    "preview.showing": "显示 {shown}/{total}",
    "metric.segments": "分段",
    "metric.characters": "字符",
    "metric.avgChars": "平均字符",
    "check.sourcePending": "粘贴或上传来源文本。",
    "check.providerPending": "填写模型和 API 设置。",
    "check.runPending": "等待完整设置。",
    "check.sourceReady": "已准备 {count} 个字符。",
    "check.providerReady": "服务商设置看起来完整。",
    "check.runReady": "{count} 个分段已可分析。",
    "check.runBlocked": "请先完成来源和服务商设置。",
    "runHelp.initial": "添加来源文本和服务商设置后开始。",
    "runHelp.ready": "就绪：将分析 {count} 个分段并导出 ZIP。",
    "runHelp.missingSource": "来源文本",
    "runHelp.missingProvider": "服务商设置",
    "runHelp.missing": "添加{items}后开始。",
    "runHelp.setupDetails": "设置细节",
    "join.and": "和",
    "button.clear": "清空",
    "button.choose": "选择",
    "button.run": "运行分析",
    "button.running": "运行中",
    "button.downloadZip": "下载 ZIP",
    "button.settings": "设置",
    "button.cancelRun": "取消",
    "button.cancelling": "正在取消…",
    "progress.running": "正在分析",
    "progress.runningCopy": "耗时取决于服务商延迟。",
    "progress.starting": "启动分析",
    "progress.startingCopy": "GTFlow 正在准备本地管线；模型请求会发送到已配置的服务商。",
    "progress.coding": "编码分段",
    "progress.codingCopy": "正在进行开放编码和代码本生成。",
    "progress.complete": "完成",
    "progress.completeCopy": "产物已可审阅和导出。",
    "progress.failed": "分析失败",
    "progress.failedCopy": "上一次成功结果仍可查看。请检查设置后重试。",
    "progress.stageCopy": "阶段进度：{percent}%",
    "progress.cancelled": "分析已取消",
    "progress.cancelledCopy": "未将任何部分结果视为完成；上一次成功结果仍可查看。",
    "job.stage.queued": "排队中",
    "job.stage.starting": "正在启动分析",
    "job.stage.segmenting": "正在分段来源",
    "job.stage.open-coding": "开放编码",
    "job.stage.codebook": "构建代码本",
    "job.stage.axial-coding": "主轴编码",
    "job.stage.selective-coding": "选择性编码",
    "job.stage.validation": "负例与饱和度",
    "job.stage.finalizing": "正在收尾分析",
    "job.stage.packaging": "构建审计包",
    "job.stage.complete": "完成",
    "job.stage.cancelling": "正在取消",
    "job.stage.cancelled": "已取消",
    "results.eyebrow": "分析输出",
    "results.coreCategory": "核心范畴",
    "stat.segments": "分段",
    "stat.open_codes": "开放代码",
    "stat.initial_codes": "初始代码",
    "stat.codebook_entries": "代码本条目",
    "stat.triples": "主轴关系",
    "tab.overview": "概览",
    "tab.gioia": "Gioia",
    "tab.contrasts": "对比",
    "tab.negatives": "负例",
    "tab.saturation": "饱和度",
    "tab.data": "数据",
    "overview.title": "高频代码",
    "overview.copy": "当前运行中最常见的代码。",
    "gioia.title": "Gioia 对齐",
    "gioia.copy": "编辑主题和维度对齐，然后导出调整后的代码本。",
    "gioia.filter": "代码包含",
    "gioia.theme": "设置二阶主题",
    "gioia.dimension": "设置聚合维度",
    "gioia.apply": "应用批量对齐",
    "gioia.save": "保存修改",
    "gioia.undo": "撤销",
    "gioia.dirty": "存在未保存编辑。保存后将重新生成 Gioia 视图、报告和 ZIP 包。",
    "gioia.saved": "编辑已保存，导出产物已重新生成。",
    "gioia.batchStaged": "批量对齐已暂存。请检查表格，然后保存修改。",
    "gioia.undone": "已恢复上一版对齐。",
    "gioia.blankCode": "保存前，每一行都必须填写代码。",
    "gioia.duplicateCode": "代码名称不能重复：{code}",
    "gioia.column.code": "代码",
    "gioia.column.definition": "定义",
    "gioia.column.theme": "主题",
    "gioia.column.dimension": "维度",
    "gioia.column.aliases": "别名",
    "gioia.aria.code": "第 {row} 行代码",
    "gioia.aria.definition": "第 {row} 行定义",
    "gioia.aria.theme": "第 {row} 行二阶主题",
    "gioia.aria.dimension": "第 {row} 行聚合维度",
    "gioia.aria.aliases": "第 {row} 行别名",
    "data.segments": "分段",
    "data.openCodes": "开放代码",
    "data.codebook": "代码本",
    "table.empty": "暂无数据。",
    "chart.empty": "暂无图表数据。",
    "toast.previewFailed": "预览失败",
    "toast.runFailed": "运行失败",
    "toast.cancelRequested": "已请求取消。",
    "toast.batchApplied": "已应用批量对齐。",
    "toast.gioiaFailed": "无法保存 Gioia 编辑。",
    "toast.firstFile": "已加载拖入的第一个文件。",
    "toast.readFailed": "无法读取 {name}。",
    "status.fileLoaded": "{name} 已加载（{size}）。",
    "status.localWorkspace": "本地工作区",
    "phase.empty": "空白",
    "phase.configured": "已配置",
    "phase.ready": "已就绪",
    "phase.queued": "排队中",
    "phase.running-stage": "运行中",
    "phase.succeeded": "已完成",
    "phase.failed": "失败",
    "phase.edited": "已编辑",
    "phase.exported": "已导出",
    "workflow.status": "工作流状态：{state}",
    "placeholder.apiKey": "使用环境变量或粘贴密钥",
    "placeholder.organization": "可选组织 ID",
    "placeholder.azureDeployment": "部署名称",
    "placeholder.optional": "可选",
    "placeholder.inputText": "在这里粘贴访谈摘录、田野笔记或上传文件内容。\n\n参与者 A：...\n参与者 B：...",
    "aria.workflow": "分析流程",
    "aria.dropZone": "选择或拖入来源文件",
    "aria.readiness": "就绪清单",
    "aria.resultViews": "结果视图",
    "aria.settings": "分析设置",
    "aria.closeSettings": "关闭设置",
    "aria.skipWorkspace": "跳到工作区",
    "aria.preview": "分段预览",
  },
  "Traditional Chinese": {
    "brand.subtitle": "扎根理論工作台",
    "section.connection": "連線",
    "section.generation": "生成",
    "section.costModel": "成本模型",
    "section.runSetup": "執行設定",
    "section.throughput": "吞吐",
    "section.advancedLimits": "進階限制",
    "label.provider": "服務商",
    "label.model": "模型",
    "label.apiKey": "API 金鑰",
    "label.baseUrl": "基礎 URL",
    "label.organization": "組織",
    "label.useResponses": "可用時使用 Responses API",
    "label.endpoint": "端點",
    "label.deployment": "部署",
    "label.apiVersion": "API 版本",
    "label.outputLanguage": "語言",
    "label.temperature": "溫度",
    "label.maxTokens": "最大 tokens",
    "label.structuredOutput": "結構化 JSON 輸出",
    "label.priceIn": "輸入 $/1k",
    "label.priceOut": "輸出 $/1k",
    "label.segmentation": "分段方式",
    "label.segmentSize": "分段大小",
    "label.batch": "批次",
    "label.workers": "並發",
    "label.rateSec": "速率/秒",
    "label.timeoutSec": "逾時秒數",
    "label.streamAt": "串流閾值",
    "label.streamOpenCoding": "大規模執行時串流開放編碼",
    "label.promptChars": "提示字元數",
    "label.retryAttempts": "重試次數",
    "label.sourceText": "來源文字",
    "privacy.hostRemote": "執行目標：{host}（遠端）。API 金鑰只保留在本次工作階段記憶體中，GTFlow 不會儲存。",
    "privacy.hostLocal": "執行目標：{host}（本機服務）。除非該服務繼續轉送，否則來源文字不會離開本裝置。",
    "privacy.hostMissing": "請輸入有效的服務商端點，以確認執行資料將傳送到哪裡。",
    "privacy.sourceOnRun": "只有在選擇「執行分析」後，來源文字才會傳送到已設定的服務商。",
    "option.dialog": "對話",
    "option.paragraph": "段落",
    "option.line": "行",
    "top.eyebrow": "GTFlow 工作室",
    "top.title": "從質性證據走向理論。",
    "title.localWorkspace": "介面和預覽在本裝置上執行",
    "stage.source": "來源",
    "stage.sourceSub": "貼上或上傳",
    "stage.provider": "服務商",
    "stage.providerSub": "模型與金鑰",
    "stage.run": "執行",
    "stage.runSub": "管線",
    "stage.review": "審閱",
    "stage.reviewSub": "Gioia 與對比",
    "stage.export": "匯出",
    "stage.exportSub": "ZIP 套件",
    "source.title": "來源",
    "source.copy": "貼上文字，或載入 .txt、.md、.csv、.jsonl。",
    "source.dropTitle": "選擇或拖入來源",
    "source.fileStatus": "載入後文字仍可編輯。",
    "source.dropOverlayTitle": "放開以載入檔案",
    "source.dropOverlayCopy": ".txt、.md、.csv 或 .jsonl",
    "preview.title": "預覽",
    "preview.copy": "分段和就緒狀態會隨操作更新。",
    "preview.empty": "還沒有分段。",
    "preview.showing": "顯示 {shown}/{total}",
    "metric.segments": "分段",
    "metric.characters": "字元",
    "metric.avgChars": "平均字元",
    "check.sourcePending": "貼上或上傳來源文字。",
    "check.providerPending": "填寫模型和 API 設定。",
    "check.runPending": "等待完整設定。",
    "check.sourceReady": "已準備 {count} 個字元。",
    "check.providerReady": "服務商設定看起來完整。",
    "check.runReady": "{count} 個分段已可分析。",
    "check.runBlocked": "請先完成來源和服務商設定。",
    "runHelp.initial": "新增來源文字和服務商設定後開始。",
    "runHelp.ready": "就緒：將分析 {count} 個分段並匯出 ZIP。",
    "runHelp.missingSource": "來源文字",
    "runHelp.missingProvider": "服務商設定",
    "runHelp.missing": "新增{items}後開始。",
    "runHelp.setupDetails": "設定細節",
    "join.and": "和",
    "button.clear": "清空",
    "button.choose": "選擇",
    "button.run": "執行分析",
    "button.running": "執行中",
    "button.downloadZip": "下載 ZIP",
    "button.settings": "設定",
    "button.cancelRun": "取消",
    "button.cancelling": "正在取消…",
    "progress.running": "正在分析",
    "progress.runningCopy": "耗時取決於服務商延遲。",
    "progress.starting": "啟動分析",
    "progress.startingCopy": "GTFlow 正在準備本機管線；模型請求會傳送到已設定的服務商。",
    "progress.coding": "編碼分段",
    "progress.codingCopy": "正在進行開放編碼和代碼本生成。",
    "progress.complete": "完成",
    "progress.completeCopy": "產物已可審閱和匯出。",
    "progress.failed": "分析失敗",
    "progress.failedCopy": "上一次成功結果仍可檢視。請檢查設定後重試。",
    "progress.stageCopy": "階段進度：{percent}%",
    "progress.cancelled": "分析已取消",
    "progress.cancelledCopy": "未將任何部分結果視為完成；上一次成功結果仍可檢視。",
    "job.stage.queued": "排隊中",
    "job.stage.starting": "正在啟動分析",
    "job.stage.segmenting": "正在分段來源",
    "job.stage.open-coding": "開放編碼",
    "job.stage.codebook": "建立代碼本",
    "job.stage.axial-coding": "主軸編碼",
    "job.stage.selective-coding": "選擇性編碼",
    "job.stage.validation": "負例與飽和度",
    "job.stage.finalizing": "正在完成分析",
    "job.stage.packaging": "建立稽核套件",
    "job.stage.complete": "完成",
    "job.stage.cancelling": "正在取消",
    "job.stage.cancelled": "已取消",
    "results.eyebrow": "分析輸出",
    "results.coreCategory": "核心範疇",
    "stat.segments": "分段",
    "stat.open_codes": "開放代碼",
    "stat.initial_codes": "初始代碼",
    "stat.codebook_entries": "代碼本條目",
    "stat.triples": "主軸關係",
    "tab.overview": "概覽",
    "tab.gioia": "Gioia",
    "tab.contrasts": "對比",
    "tab.negatives": "負例",
    "tab.saturation": "飽和度",
    "tab.data": "資料",
    "overview.title": "高頻代碼",
    "overview.copy": "目前執行中最常見的代碼。",
    "gioia.title": "Gioia 對齊",
    "gioia.copy": "編輯主題和維度對齊，然後匯出調整後的代碼本。",
    "gioia.filter": "代碼包含",
    "gioia.theme": "設定二階主題",
    "gioia.dimension": "設定聚合維度",
    "gioia.apply": "套用批次對齊",
    "gioia.save": "儲存修改",
    "gioia.undo": "復原",
    "gioia.dirty": "有尚未儲存的編輯。儲存後將重新產生 Gioia 視圖、報告與 ZIP 套件。",
    "gioia.saved": "編輯已儲存，匯出產物已重新產生。",
    "gioia.batchStaged": "批次對齊已暫存。請檢查表格，然後儲存修改。",
    "gioia.undone": "已還原上一版對齊。",
    "gioia.blankCode": "儲存前，每一列都必須填寫代碼。",
    "gioia.duplicateCode": "代碼名稱不可重複：{code}",
    "gioia.column.code": "代碼",
    "gioia.column.definition": "定義",
    "gioia.column.theme": "主題",
    "gioia.column.dimension": "維度",
    "gioia.column.aliases": "別名",
    "gioia.aria.code": "第 {row} 列代碼",
    "gioia.aria.definition": "第 {row} 列定義",
    "gioia.aria.theme": "第 {row} 列二階主題",
    "gioia.aria.dimension": "第 {row} 列聚合維度",
    "gioia.aria.aliases": "第 {row} 列別名",
    "data.segments": "分段",
    "data.openCodes": "開放代碼",
    "data.codebook": "代碼本",
    "table.empty": "暫無資料。",
    "chart.empty": "暫無圖表資料。",
    "toast.previewFailed": "預覽失敗",
    "toast.runFailed": "執行失敗",
    "toast.cancelRequested": "已要求取消。",
    "toast.batchApplied": "已套用批次對齊。",
    "toast.firstFile": "已載入拖入的第一個檔案。",
    "toast.readFailed": "無法讀取 {name}。",
    "status.fileLoaded": "{name} 已載入（{size}）。",
    "phase.empty": "空白",
    "phase.configured": "已設定",
    "phase.ready": "已就緒",
    "phase.queued": "排隊中",
    "phase.running-stage": "執行中",
    "phase.succeeded": "已完成",
    "phase.failed": "失敗",
    "phase.edited": "已編輯",
    "phase.exported": "已匯出",
    "workflow.status": "工作流程狀態：{state}",
    "placeholder.apiKey": "使用環境變數或貼上金鑰",
    "placeholder.organization": "可選組織 ID",
    "placeholder.azureDeployment": "部署名稱",
    "placeholder.optional": "可選",
    "placeholder.inputText": "在這裡貼上訪談摘錄、田野筆記或上傳檔案內容。\n\n參與者 A：...\n參與者 B：...",
    "aria.workflow": "分析流程",
    "aria.dropZone": "選擇或拖入來源檔案",
    "aria.readiness": "就緒清單",
    "aria.resultViews": "結果視圖",
    "aria.settings": "分析設定",
    "aria.closeSettings": "關閉設定",
    "aria.skipWorkspace": "跳到工作區",
    "aria.preview": "分段預覽",
  },
  Japanese: {
    "join.and": "と",
    "label.outputLanguage": "言語",
    "section.connection": "接続",
    "section.runSetup": "実行設定",
    "top.title": "質的証拠を理論へ。",
    "source.title": "ソース",
    "source.copy": "テキストを貼り付けるか、.txt、.md、.csv、.jsonl を読み込みます。",
    "source.dropTitle": "ソースを選択またはドロップ",
    "source.fileStatus": "読み込み後もテキストは編集できます。",
    "preview.title": "プレビュー",
    "button.run": "分析を実行",
    "button.running": "実行中",
    "button.clear": "クリア",
    "button.choose": "選択",
    "stage.source": "ソース",
    "stage.provider": "プロバイダー",
    "stage.run": "実行",
    "stage.review": "確認",
    "stage.export": "エクスポート",
    "preview.empty": "まだセグメントはありません。",
    "runHelp.initial": "ソーステキストとプロバイダー設定を追加して開始します。",
  },
  French: {
    "join.and": " et ",
    "label.outputLanguage": "Langue",
    "section.connection": "Connexion",
    "section.runSetup": "Configuration",
    "top.title": "Des preuves qualitatives vers la théorie.",
    "source.title": "Source",
    "source.copy": "Collez du texte ou chargez .txt, .md, .csv ou .jsonl.",
    "source.dropTitle": "Choisir ou déposer la source",
    "source.fileStatus": "Le texte reste modifiable après le chargement.",
    "preview.title": "Aperçu",
    "button.run": "Lancer l’analyse",
    "button.running": "En cours",
    "button.clear": "Effacer",
    "button.choose": "Choisir",
    "stage.source": "Source",
    "stage.provider": "Fournisseur",
    "stage.run": "Exécuter",
    "stage.review": "Réviser",
    "stage.export": "Exporter",
    "preview.empty": "Aucun segment pour le moment.",
    "runHelp.initial": "Ajoutez le texte source et les paramètres du fournisseur pour commencer.",
  },
  Spanish: {
    "join.and": " y ",
    "label.outputLanguage": "Idioma",
    "section.connection": "Conexión",
    "section.runSetup": "Configuración",
    "top.title": "Evidencia cualitativa hacia teoría.",
    "source.title": "Fuente",
    "source.copy": "Pega texto o carga .txt, .md, .csv o .jsonl.",
    "source.dropTitle": "Elegir o soltar fuente",
    "source.fileStatus": "El texto sigue editable después de cargar.",
    "preview.title": "Vista previa",
    "button.run": "Ejecutar análisis",
    "button.running": "Ejecutando",
    "button.clear": "Borrar",
    "button.choose": "Elegir",
    "stage.source": "Fuente",
    "stage.provider": "Proveedor",
    "stage.run": "Ejecutar",
    "stage.review": "Revisar",
    "stage.export": "Exportar",
    "preview.empty": "Aún no hay segmentos.",
    "runHelp.initial": "Agrega texto fuente y configuración del proveedor para comenzar.",
  },
  German: {
    "join.and": " und ",
    "label.outputLanguage": "Sprache",
    "section.connection": "Verbindung",
    "section.runSetup": "Ausführung",
    "top.title": "Qualitative Evidenz wird Theorie.",
    "source.title": "Quelle",
    "source.copy": "Text einfügen oder .txt, .md, .csv oder .jsonl laden.",
    "source.dropTitle": "Quelle wählen oder ablegen",
    "source.fileStatus": "Der Text bleibt nach dem Laden bearbeitbar.",
    "preview.title": "Vorschau",
    "button.run": "Analyse starten",
    "button.running": "Läuft",
    "button.clear": "Leeren",
    "button.choose": "Wählen",
    "stage.source": "Quelle",
    "stage.provider": "Anbieter",
    "stage.run": "Start",
    "stage.review": "Prüfen",
    "stage.export": "Export",
    "preview.empty": "Noch keine Segmente.",
    "runHelp.initial": "Quelltext und Anbieter-Einstellungen hinzufügen, um zu beginnen.",
  },
  Korean: {
    "join.and": " 및 ",
    "label.outputLanguage": "언어",
    "section.connection": "연결",
    "section.runSetup": "실행 설정",
    "top.title": "질적 증거를 이론으로.",
    "source.title": "소스",
    "source.copy": "텍스트를 붙여넣거나 .txt, .md, .csv, .jsonl을 불러옵니다.",
    "source.dropTitle": "소스 선택 또는 놓기",
    "source.fileStatus": "불러온 뒤에도 텍스트를 편집할 수 있습니다.",
    "preview.title": "미리보기",
    "button.run": "분석 실행",
    "button.running": "실행 중",
    "button.clear": "지우기",
    "button.choose": "선택",
    "stage.source": "소스",
    "stage.provider": "제공자",
    "stage.run": "실행",
    "stage.review": "검토",
    "stage.export": "내보내기",
    "preview.empty": "아직 세그먼트가 없습니다.",
    "runHelp.initial": "소스 텍스트와 제공자 설정을 추가해 시작하세요.",
  },
};

function setupLanguageOptions() {
  const select = $("outputLanguage");
  if (!select) return;
  const selected = select.value || "English";
  select.innerHTML = LANGUAGE_OPTIONS
    .map((item) => `<option value="${item.value}">${item.label}</option>`)
    .join("");
  select.value = LANGUAGE_OPTIONS.some((item) => item.value === selected) ? selected : "English";
}

function currentLanguage() {
  return $("outputLanguage")?.value || "English";
}

function languageMeta(language = currentLanguage()) {
  return LANGUAGE_OPTIONS.find((item) => item.value === language) || LANGUAGE_OPTIONS[0];
}

function restoreNonSensitiveSettings() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(SETTINGS_STORAGE_KEY) || "{}");
    SAVED_SETTING_IDS.forEach((id) => {
      const node = $(id);
      if (!node || !Object.prototype.hasOwnProperty.call(saved, id)) return;
      if (node.type === "checkbox") node.checked = Boolean(saved[id]);
      else node.value = String(saved[id]);
    });
  } catch (_error) {
    // Storage can be disabled in hardened browser profiles; settings remain session-only.
  }
}

function persistNonSensitiveSettings() {
  try {
    const saved = {};
    SAVED_SETTING_IDS.forEach((id) => {
      const node = $(id);
      if (!node) return;
      saved[id] = node.type === "checkbox" ? node.checked : node.value;
    });
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(saved));
  } catch (_error) {
    // Failing to persist preferences must never block analysis.
  }
}

function usesSettingsDrawer() {
  return window.matchMedia("(max-width: 920px)").matches;
}

function setSettingsOpen(open, { restoreFocus = true } = {}) {
  const panel = $("settingsPanel");
  const backdrop = $("settingsBackdrop");
  const toggle = $("settingsToggle");
  const shouldOpen = usesSettingsDrawer() && Boolean(open);
  state.settingsOpen = shouldOpen;
  document.body.classList.toggle("settings-open", shouldOpen);
  toggle.setAttribute("aria-expanded", String(shouldOpen));
  backdrop.hidden = !shouldOpen;
  if (usesSettingsDrawer()) {
    panel.setAttribute("aria-hidden", String(!shouldOpen));
    if (shouldOpen) panel.removeAttribute("inert");
    else panel.setAttribute("inert", "");
  } else {
    panel.removeAttribute("aria-hidden");
    panel.removeAttribute("inert");
  }
  if (shouldOpen) {
    state.settingsRestoreFocus = document.activeElement;
    window.requestAnimationFrame(() => $("settingsClose").focus());
  } else if (restoreFocus && state.settingsRestoreFocus?.focus) {
    state.settingsRestoreFocus.focus();
    state.settingsRestoreFocus = null;
  }
}

function handleSettingsKeydown(event) {
  if (!state.settingsOpen) return;
  if (event.key === "Escape") {
    event.preventDefault();
    setSettingsOpen(false);
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = Array.from(
    $("settingsPanel").querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), summary, [tabindex="0"]')
  ).filter((node) => !node.closest("[hidden]") && node.getClientRects().length > 0);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function providerDestination() {
  const provider = $("providerName").value;
  let endpoint = "";
  if (provider === "azure_openai") endpoint = $("azureEndpoint").value.trim();
  else if (provider === "anthropic") endpoint = "https://api.anthropic.com";
  else if (provider === "ollama") endpoint = $("baseUrl").value.trim() || "http://localhost:11434/v1";
  else endpoint = $("baseUrl").value.trim() || "https://api.openai.com/v1";
  try {
    const url = new URL(endpoint);
    const hostname = url.hostname.toLowerCase();
    const local = hostname === "localhost" || hostname === "::1" || hostname.startsWith("127.");
    return { host: url.host, local };
  } catch (_error) {
    return null;
  }
}

function updateProviderNotice() {
  const destination = providerDestination();
  if (!destination) {
    $("providerHostNotice").textContent = t("privacy.hostMissing");
    return;
  }
  $("providerHostNotice").textContent = t(destination.local ? "privacy.hostLocal" : "privacy.hostRemote", {
    host: destination.host,
  });
}

function setupWorkflowState(readiness = state.lastReadiness) {
  if (readiness.ready) return "ready";
  if (readiness.input || readiness.provider) return "configured";
  return "empty";
}

function transitionWorkflow(next, readiness = state.lastReadiness) {
  if (!WORKFLOW_STATES.has(next)) throw new Error(`Unknown workflow state: ${next}`);
  state.workflowState = next;
  state.lastReadiness = { ...state.lastReadiness, ...(readiness || {}) };
  document.body.dataset.workflowState = next;
  const label = t(`phase.${next}`);
  $("phaseBadge").textContent = label;
  $("workflowStatus").textContent = t("workflow.status", { state: label });
  setWorkflowState(state.lastReadiness);
}

function t(key, values = {}) {
  const language = currentLanguage();
  const text = TRANSLATIONS[language]?.[key] ?? TRANSLATIONS.English[key] ?? key;
  return String(text).replace(/\{(\w+)\}/g, (_, name) => values[name] ?? "");
}

function applyLanguage() {
  const meta = languageMeta();
  document.documentElement.lang = meta.htmlLang;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel));
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.setAttribute("title", t(node.dataset.i18nTitle));
  });
  refreshLocalizedState();
  updateProviderNotice();
  transitionWorkflow(state.workflowState, state.lastReadiness);
}

function refreshLocalizedState() {
  if ($("inputText") && !$("inputText").value && !$("dropZone").classList.contains("has-file")) {
    $("fileStatus").textContent = t("source.fileStatus");
  } else if ($("dropZone")?.classList.contains("has-file") && state.sourceName) {
    $("fileStatus").textContent = t("status.fileLoaded", { name: state.sourceName, size: formatBytes(state.sourceSize || 0) });
  }
  const readyButtonText = document.body.classList.contains("is-running") ? "button.running" : "button.run";
  if ($("runButton")) $("runButton").textContent = t(readyButtonText);
  if ($("progressPanel") && $("progressPanel").classList.contains("hidden")) {
    $("progressTitle").textContent = t("progress.running");
    $("progressCopy").textContent = t("progress.runningCopy");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  restoreNonSensitiveSettings();
  setupLanguageOptions();
  bindControls();
  applyLanguage();
  updateProviderFields();
  updateSourceMeta();
  setSettingsOpen(false, { restoreFocus: false });
  transitionWorkflow("empty");
  try {
    await ensureCsrfToken();
    resumeStoredJob();
    refreshPreview();
  } catch (error) {
    showToast(error.message || "Could not establish a secure local session.");
  }
  document.body.dataset.ui = "ready";
});

function bindControls() {
  [
    "providerName",
    "model",
    "apiKey",
    "baseUrl",
    "organization",
    "useResponses",
    "azureEndpoint",
    "azureDeployment",
    "apiVersion",
    "outputLanguage",
    "temperature",
    "maxTokens",
    "structuredOutput",
    "priceIn",
    "priceOut",
    "segmentationStrategy",
    "maxSegmentChars",
    "batchSize",
    "concurrentWorkers",
    "rateLimitRps",
    "timeoutSec",
    "streamThreshold",
    "streamOpenCoding",
    "maxPromptChars",
    "retryMax",
  ].forEach((id) => {
    const node = $(id);
    if (node) node.addEventListener("input", () => {
      schedulePreview();
      if (SAVED_SETTING_IDS.includes(id)) persistNonSensitiveSettings();
      if (["providerName", "baseUrl", "azureEndpoint"].includes(id)) updateProviderNotice();
    });
  });
  $("providerName").addEventListener("change", () => {
    updateProviderFields();
    persistNonSensitiveSettings();
  });
  $("outputLanguage").addEventListener("change", () => {
    applyLanguage();
    if (state.lastResult) renderResults(state.lastResult, false);
    refreshPreview();
  });
  $("inputText").addEventListener("input", () => {
    updateSourceMeta();
    schedulePreview();
  });
  $("clearText").addEventListener("click", () => {
    $("inputText").value = "";
    state.sourceName = null;
    state.sourceSize = null;
    $("fileInput").value = "";
    $("dropZone").classList.remove("has-file");
    $("fileStatus").textContent = t("source.fileStatus");
    updateSourceMeta();
    refreshPreview();
  });
  $("dropZone").addEventListener("click", (event) => {
    if (event.target.closest("button")) return;
    $("fileInput").click();
  });
  $("dropZone").addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      $("fileInput").click();
    }
  });
  $("chooseFile").addEventListener("click", () => $("fileInput").click());
  $("fileInput").addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file) loadFile(file);
  });
  bindFileDrop();
  $("runButton").addEventListener("click", runAnalysis);
  $("cancelRun").addEventListener("click", cancelActiveRun);
  $("downloadZip").addEventListener("click", downloadZip);
  $("settingsToggle").addEventListener("click", () => setSettingsOpen(true));
  $("settingsClose").addEventListener("click", () => setSettingsOpen(false));
  $("settingsBackdrop").addEventListener("click", () => setSettingsOpen(false));
  $("settingsPanel").addEventListener("keydown", handleSettingsKeydown);
  window.addEventListener("resize", () => setSettingsOpen(state.settingsOpen, { restoreFocus: false }));
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !$("runButton").disabled) {
      event.preventDefault();
      runAnalysis();
    }
  });
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
    button.addEventListener("keydown", handleTabKeydown);
  });
}

function bindFileDrop() {
  const sourcePanel = $("sourcePanel");
  const dropZone = $("dropZone");
  const resetDrag = () => {
    state.dragDepth = 0;
    sourcePanel.classList.remove("dragging-file");
    dropZone.classList.remove("dragging");
  };

  ["dragenter", "dragover", "drop"].forEach((eventName) => {
    window.addEventListener(eventName, (event) => {
      if (!hasDraggedFiles(event)) return;
      event.preventDefault();
    });
  });

  window.addEventListener("dragleave", (event) => {
    if (event.relatedTarget !== null) return;
    resetDrag();
  });
  window.addEventListener("drop", resetDrag);

  sourcePanel.addEventListener("dragenter", (event) => {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
    state.dragDepth += 1;
    sourcePanel.classList.add("dragging-file");
    dropZone.classList.add("dragging");
  });

  sourcePanel.addEventListener("dragover", (event) => {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });

  sourcePanel.addEventListener("dragleave", (event) => {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
    state.dragDepth = Math.max(0, state.dragDepth - 1);
    if (state.dragDepth === 0) {
      sourcePanel.classList.remove("dragging-file");
      dropZone.classList.remove("dragging");
    }
  });

  sourcePanel.addEventListener("drop", (event) => {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
    const files = Array.from(event.dataTransfer?.files || []);
    resetDrag();
    if (files.length > 1) showToast(t("toast.firstFile"));
    const file = files[0];
    if (file) loadFile(file);
  });
}

function hasDraggedFiles(event) {
  return Array.from(event.dataTransfer?.types || []).includes("Files");
}

function loadFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    $("inputText").value = String(reader.result || "");
    state.sourceName = file.name;
    state.sourceSize = file.size;
    $("dropZone").classList.add("has-file");
    $("fileStatus").textContent = t("status.fileLoaded", { name: file.name, size: formatBytes(file.size) });
    updateSourceMeta();
    refreshPreview();
  };
  reader.onerror = () => showToast(t("toast.readFailed", { name: file.name }));
  reader.readAsText(file, "utf-8");
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function updateProviderFields() {
  const provider = $("providerName").value;
  const baseUrl = $("baseUrl");
  if (provider === "ollama" && (!baseUrl.value.trim() || baseUrl.value.trim() === "https://api.openai.com/v1")) {
    baseUrl.value = "http://localhost:11434/v1";
  } else if (provider === "openai_compatible" && baseUrl.value.trim() === "http://localhost:11434/v1") {
    baseUrl.value = "https://api.openai.com/v1";
  }
  $("azureFields").classList.toggle("hidden", provider !== "azure_openai");
  $("openaiFields").classList.toggle("hidden", !["openai_compatible", "ollama"].includes(provider));
  state.lastProvider = provider;
  updateProviderNotice();
  schedulePreview();
}

function resumeStoredJob() {
  try {
    const jobId = window.sessionStorage.getItem("gtflow.activeJobId") || "";
    if (!/^[A-Za-z0-9_-]{24,64}$/.test(jobId)) return;
    state.activeJobId = jobId;
    document.body.classList.add("is-running");
    $("progressPanel").classList.remove("hidden");
    $("progressPanel").setAttribute("aria-busy", "true");
    $("runButton").disabled = true;
    $("runButton").setAttribute("aria-busy", "true");
    $("cancelRun").hidden = false;
    transitionWorkflow("queued");
    setProgress(0, t("job.stage.queued"), t("progress.startingCopy"));
    scheduleJobPoll(0);
  } catch (_error) {
    // Session recovery is optional.
  }
}

function schedulePreview() {
  updateSourceMeta();
  window.clearTimeout(state.previewTimer);
  if (state.previewRequest) {
    state.previewRequest.abort();
    state.previewRequest = null;
  }
  const sequence = ++state.previewSequence;
  const chars = $("inputText").value.length;
  const delay = chars >= 200000 ? 700 : chars >= 20000 ? 450 : 250;
  state.previewTimer = window.setTimeout(() => refreshPreview(sequence), delay);
}

async function refreshPreview(sequence = null) {
  window.clearTimeout(state.previewTimer);
  if (sequence === null) {
    if (state.previewRequest) state.previewRequest.abort();
    sequence = ++state.previewSequence;
  } else if (sequence !== state.previewSequence) {
    return;
  }

  const payload = buildPayload({ includeCredential: false });
  payload.credential_configured = Boolean($("apiKey").value.trim());
  if (!payload.text.trim()) {
    if (sequence === state.previewSequence) {
      renderPreview({ stats: { segments: 0, characters: 0, avg_chars: 0 }, segments: [], readiness: { ready: false, input: false, provider: providerLooksReady(), segments: 0 } });
      $("previewPanel").setAttribute("aria-busy", "false");
    }
    return;
  }

  const controller = new AbortController();
  state.previewRequest = controller;
  $("previewPanel").setAttribute("aria-busy", "true");
  try {
    const data = await postJson("/api/preview", payload, { signal: controller.signal });
    if (sequence === state.previewSequence) renderPreview(data);
  } catch (error) {
    if (error.name !== "AbortError" && sequence === state.previewSequence) {
      showToast(error.message || t("toast.previewFailed"), { kind: "error" });
    }
  } finally {
    if (sequence === state.previewSequence && state.previewRequest === controller) {
      state.previewRequest = null;
      $("previewPanel").setAttribute("aria-busy", "false");
    }
  }
}

function renderPreview(data) {
  const stats = data.stats || {};
  const readiness = data.readiness || {};
  updateSourceMeta(stats);
  $("metricSegments").textContent = stats.segments || 0;
  $("metricChars").textContent = stats.characters || 0;
  $("metricAvg").textContent = stats.avg_chars || 0;
  state.lastReadiness = { ...state.lastReadiness, ...readiness };
  const fingerprint = analysisFingerprint();
  const resultStateIsCurrent = state.lastResult
    && state.lastSuccessfulFingerprint === fingerprint
    && ["succeeded", "edited", "exported"].includes(state.workflowState);
  const failedAttemptIsCurrent = state.workflowState === "failed" && state.lastAttemptFingerprint === fingerprint;
  if (ACTIVE_RUN_STATES.has(state.workflowState) || failedAttemptIsCurrent || resultStateIsCurrent) {
    setWorkflowState(readiness);
  } else {
    transitionWorkflow(setupWorkflowState(readiness), readiness);
  }
  $("runButton").disabled = Boolean(state.activeJobId) || !readiness.ready;
  document.body.classList.toggle("is-ready", !!readiness.ready);
  $("runHelp").textContent = runHelpText(readiness, stats);
  renderReadiness(readiness, stats);

  const list = $("previewList");
  const segments = data.segments || [];
  const total = Number(stats.segments || segments.length || 0);
  const visibleSegments = segments.slice(0, 30);
  $("previewCount").textContent = t("preview.showing", { shown: visibleSegments.length, total });
  if (!segments.length) {
    list.className = "preview-list empty";
    list.textContent = t("preview.empty");
    return;
  }
  list.className = "preview-list";
  list.innerHTML = visibleSegments
    .map((seg) => `<div class="segment-row"><b>${escapeHtml(seg.seg_id)} ${escapeHtml(seg.speaker || "")}</b><p>${escapeHtml((seg.text || "").slice(0, 220))}</p></div>`)
    .join("");
}

function renderReadiness(readiness, stats) {
  const segmentCount = stats.segments || readiness.segments || 0;
  setCheckState("inputCheck", !!readiness.input, readiness.input ? t("check.sourceReady", { count: stats.characters || 0 }) : t("check.sourcePending"));
  setCheckState("providerCheck", !!readiness.provider, readiness.provider ? t("check.providerReady") : t("check.providerPending"));
  setCheckState("runCheck", !!readiness.ready, readiness.ready ? t("check.runReady", { count: segmentCount }) : t("check.runBlocked"));
}

function setCheckState(id, ready, copy) {
  const node = $(id);
  if (!node) return;
  node.classList.toggle("ready", ready);
  const small = node.querySelector("small");
  if (small) small.textContent = copy;
}

function runHelpText(readiness, stats) {
  if (readiness.ready) {
    const count = stats.segments || readiness.segments || 0;
    return t("runHelp.ready", { count });
  }
  const missing = [];
  if (!readiness.input) missing.push(t("runHelp.missingSource"));
  if (!readiness.provider) missing.push(t("runHelp.missingProvider"));
  return t("runHelp.missing", { items: localizedJoin(missing) || t("runHelp.setupDetails") });
}

function localizedJoin(items) {
  return items.join(t("join.and"));
}

function updateSourceMeta(stats = null) {
  const text = $("inputText")?.value || "";
  return {
    sourceName: state.sourceName || "Manual input",
    chars: text.length,
    lines: text ? text.split(/\r\n|\r|\n/).length : 0,
    segments: stats && Number.isFinite(Number(stats.segments)) ? stats.segments || 0 : null,
  };
}

function providerLooksReady() {
  const provider = $("providerName").value;
  const hasModel = $("model").value.trim().length > 0;
  const hasKey = $("apiKey").value.trim().length > 0;
  if (provider === "ollama") return hasModel && Boolean(providerDestination()?.local);
  if (provider === "azure_openai") {
    return hasModel && hasKey && $("azureEndpoint").value.trim() && $("azureDeployment").value.trim();
  }
  return hasModel && hasKey;
}

async function runAnalysis() {
  if (state.activeJobId) return;
  $("progressPanel").classList.remove("hidden");
  if (state.lastResult) $("resultsPanel").classList.add("is-stale");
  state.lastAttemptFingerprint = analysisFingerprint();
  transitionWorkflow("queued", { input: true, provider: true, ready: true });
  document.body.classList.add("is-running");
  $("progressPanel").setAttribute("aria-busy", "true");
  $("runButton").setAttribute("aria-busy", "true");
  $("cancelRun").hidden = false;
  $("cancelRun").disabled = false;
  $("cancelRun").textContent = t("button.cancelRun");
  setProgress(0, t("job.stage.queued"), t("progress.startingCopy"));
  $("runButton").disabled = true;
  $("runButton").textContent = t("button.running");
  try {
    const job = await postJson("/api/jobs", buildPayload());
    state.activeJobId = job.job_id;
    try {
      window.sessionStorage.setItem("gtflow.activeJobId", job.job_id);
    } catch (_error) {
      // Session recovery is optional in hardened browser profiles.
    }
    handleJobUpdate(job);
    scheduleJobPoll();
  } catch (error) {
    transitionWorkflow("failed", { input: true, provider: true, ready: true });
    setProgress(0, t("progress.failed"), t("progress.failedCopy"));
    showToast(error.message || t("toast.runFailed"), { kind: "error" });
    finishActiveJob();
  }
}

function scheduleJobPoll(delay = 650) {
  window.clearTimeout(state.jobPollTimer);
  if (!state.activeJobId) return;
  state.jobPollTimer = window.setTimeout(pollActiveJob, delay);
}

async function pollActiveJob() {
  if (!state.activeJobId) return;
  const jobId = state.activeJobId;
  const controller = new AbortController();
  state.jobPollController = controller;
  try {
    const job = await getJson(`/api/jobs/${encodeURIComponent(jobId)}`, { signal: controller.signal });
    if (state.activeJobId !== jobId) return;
    handleJobUpdate(job);
    if (state.activeJobId) scheduleJobPoll();
  } catch (error) {
    if (error.name === "AbortError" || state.activeJobId !== jobId) return;
    transitionWorkflow("failed");
    setProgress(0, t("progress.failed"), t("progress.failedCopy"));
    showToast(error.message || t("toast.runFailed"), { kind: "error" });
    finishActiveJob();
  } finally {
    if (state.jobPollController === controller) state.jobPollController = null;
  }
}

function handleJobUpdate(job) {
  const status = job.status || "queued";
  const stage = job.stage || "queued";
  const stageLabel = t(`job.stage.${stage}`);
  if (status === "queued") {
    transitionWorkflow("queued");
    setProgress(job.progress || 0, stageLabel, t("progress.startingCopy"));
    return;
  }
  if (["running", "cancelling"].includes(status)) {
    transitionWorkflow("running-stage");
    const progress = Math.max(1, Number(job.progress) || 1);
    setProgress(progress, stageLabel, t("progress.stageCopy", { percent: progress }));
    const cancelling = status === "cancelling";
    $("cancelRun").disabled = cancelling || job.can_cancel === false;
    $("cancelRun").textContent = t(cancelling ? "button.cancelling" : "button.cancelRun");
    return;
  }
  if (status === "succeeded") {
    state.lastResult = job.result;
    state.lastSuccessfulFingerprint = state.lastAttemptFingerprint;
    state.editedCodebook = job.result?.codebook || null;
    state.resultJobId = job.job_id;
    state.bundleDownloadUrl = job.download_url || `/api/jobs/${encodeURIComponent(job.job_id)}/bundle`;
    state.gioiaDirty = false;
    state.codebookHistory = [];
    setProgress(100, t("progress.complete"), t("progress.completeCopy"));
    renderResults(job.result);
    finishActiveJob();
    return;
  }
  if (status === "cancelled") {
    transitionWorkflow("failed");
    setProgress(job.progress || 0, t("progress.cancelled"), t("progress.cancelledCopy"));
    finishActiveJob();
    return;
  }
  if (status === "failed") {
    transitionWorkflow("failed");
    setProgress(job.progress || 0, t("progress.failed"), t("progress.failedCopy"));
    showToast(job.error?.message || t("toast.runFailed"), { kind: "error" });
    finishActiveJob();
  }
}

async function cancelActiveRun() {
  if (!state.activeJobId) return;
  $("cancelRun").disabled = true;
  $("cancelRun").textContent = t("button.cancelling");
  try {
    const job = await deleteJson(`/api/jobs/${encodeURIComponent(state.activeJobId)}`);
    handleJobUpdate(job);
    showToast(t("toast.cancelRequested"));
  } catch (error) {
    $("cancelRun").disabled = false;
    $("cancelRun").textContent = t("button.cancelRun");
    showToast(error.message || t("toast.runFailed"), { kind: "error" });
  }
}

function finishActiveJob() {
  window.clearTimeout(state.jobPollTimer);
  state.jobPollTimer = null;
  if (state.jobPollController) state.jobPollController.abort();
  state.jobPollController = null;
  state.activeJobId = null;
  try {
    window.sessionStorage.removeItem("gtflow.activeJobId");
  } catch (_error) {
    // Session recovery is optional.
  }
  document.body.classList.remove("is-running");
  $("progressPanel").setAttribute("aria-busy", "false");
  $("runButton").removeAttribute("aria-busy");
  $("runButton").disabled = !state.lastReadiness.ready;
  $("runButton").textContent = t("button.run");
  $("cancelRun").hidden = true;
}

function setProgress(value, title, copy) {
  const indeterminate = value === null || value === undefined;
  const progress = indeterminate ? 0 : Math.max(0, Math.min(100, Number(value) || 0));
  $("progressTrack").classList.toggle("is-indeterminate", indeterminate);
  $("progressBar").style.width = indeterminate ? "36%" : `${progress}%`;
  if (indeterminate) $("progressTrack").removeAttribute("aria-valuenow");
  else $("progressTrack").setAttribute("aria-valuenow", String(progress));
  $("progressTitle").textContent = title;
  $("progressCopy").textContent = copy;
}

function buildPayload({ includeCredential = true } = {}) {
  const baseUrl = $("baseUrl").value.trim();
  const provider = {
    name: $("providerName").value,
    model: $("model").value,
    // Omitting the official default allows the server's trusted environment
    // credential to be used. Any custom endpoint requires a key entered here.
    base_url: baseUrl && baseUrl !== "https://api.openai.com/v1" ? baseUrl : null,
    organization: $("organization").value || null,
    use_responses_api: $("useResponses").checked,
    endpoint: $("azureEndpoint").value || null,
    api_version: $("apiVersion").value || null,
    deployment: $("azureDeployment").value || null,
    output_language: $("outputLanguage").value,
    structured: $("structuredOutput").checked,
    temperature: numberValue("temperature", 0.2),
    max_tokens: numberValue("maxTokens", 1024),
    price_input_per_1k: optionalNumberValue("priceIn"),
    price_output_per_1k: optionalNumberValue("priceOut"),
  };
  if (includeCredential) provider.api_key = $("apiKey").value || null;

  return {
    text: $("inputText").value,
    source_name: state.sourceName || "",
    provider,
    run: {
      segmentation_strategy: $("segmentationStrategy").value,
      max_segment_chars: numberValue("maxSegmentChars", 800),
      batch_size: numberValue("batchSize", 10),
      concurrent_workers: numberValue("concurrentWorkers", 6),
      rate_limit_rps: numberValue("rateLimitRps", 2),
      timeout_sec: numberValue("timeoutSec", 60),
      stream_open_coding: $("streamOpenCoding").checked,
      stream_open_coding_threshold: numberValue("streamThreshold", 2000),
      max_prompt_chars: numberValue("maxPromptChars", 200000),
      retry_max: numberValue("retryMax", 3),
    },
  };
}

function numberValue(id, fallback) {
  const value = Number($(id).value);
  return Number.isFinite(value) ? value : fallback;
}

function optionalNumberValue(id) {
  const raw = $(id).value.trim();
  if (!raw) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function analysisFingerprint() {
  return JSON.stringify(buildPayload({ includeCredential: false }));
}

async function ensureCsrfToken(force = false) {
  if (force) state.csrfToken = null;
  if (state.csrfToken) return state.csrfToken;
  if (!state.csrfRequest) {
    state.csrfRequest = fetch("/api/default-config", {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      credentials: "same-origin",
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not establish a secure local session.");
        const token = response.headers.get("X-GTFlow-CSRF");
        if (!token) throw new Error("The local server did not provide a CSRF token.");
        // Consume the response so the connection can be reused cleanly.
        await response.json();
        state.csrfToken = token;
        return token;
      })
      .finally(() => {
        state.csrfRequest = null;
      });
  }
  return state.csrfRequest;
}

async function postJson(url, payload, { signal, retryCsrf = true } = {}) {
  const csrfToken = await ensureCsrfToken();
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-GTFlow-CSRF": csrfToken,
    },
    credentials: "same-origin",
    body: JSON.stringify(payload),
    signal,
  });
  let data = {};
  try {
    data = await response.json();
  } catch (_error) {
    throw new Error(response.statusText || "The server returned an invalid response.");
  }
  const errorCode = typeof data.error === "object" ? data.error?.code : null;
  if (response.status === 403 && errorCode === "csrf_rejected" && retryCsrf) {
    await ensureCsrfToken(true);
    return postJson(url, payload, { signal, retryCsrf: false });
  }
  if (!response.ok) {
    const message = typeof data.error === "object" ? data.error?.message : data.error;
    throw new Error(message || response.statusText);
  }
  return data;
}

async function getJson(url, { signal } = {}) {
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
    credentials: "same-origin",
    signal,
  });
  let data = {};
  try {
    data = await response.json();
  } catch (_error) {
    throw new Error(response.statusText || "The server returned an invalid response.");
  }
  if (!response.ok) {
    const message = typeof data.error === "object" ? data.error?.message : data.error;
    throw new Error(message || response.statusText);
  }
  return data;
}

async function deleteJson(url, { retryCsrf = true } = {}) {
  const csrfToken = await ensureCsrfToken();
  const response = await fetch(url, {
    method: "DELETE",
    headers: { "X-GTFlow-CSRF": csrfToken },
    credentials: "same-origin",
  });
  let data = {};
  try {
    data = await response.json();
  } catch (_error) {
    throw new Error(response.statusText || "The server returned an invalid response.");
  }
  const errorCode = typeof data.error === "object" ? data.error?.code : null;
  if (response.status === 403 && errorCode === "csrf_rejected" && retryCsrf) {
    await ensureCsrfToken(true);
    return deleteJson(url, { retryCsrf: false });
  }
  if (!response.ok) {
    const message = typeof data.error === "object" ? data.error?.message : data.error;
    throw new Error(message || response.statusText);
  }
  return data;
}

function renderResults(result, shouldScroll = true) {
  $("resultsPanel").classList.remove("hidden");
  $("resultsPanel").classList.remove("is-stale");
  document.body.classList.add("has-results");
  transitionWorkflow("succeeded", { input: true, provider: true, ready: true });
  $("downloadZip").disabled = !(state.bundleDownloadUrl || result.bundle_base64);
  $("coreCategory").textContent = result.theory?.core_category || t("results.coreCategory");
  $("storyline").textContent = result.theory?.storyline || "";
  renderStats(result.stats || {});
  renderOverview(result);
  renderGioia(result);
  renderContrasts(result);
  renderNegatives(result);
  renderSaturation(result);
  renderData(result);
  if (shouldScroll) $("resultsPanel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function setWorkflowState(readiness = {}) {
  const inputReady = Boolean(readiness.input);
  const providerReady = Boolean(readiness.provider);
  const runReady = Boolean(readiness.ready);
  const phase = state.workflowState;
  const stages = ["sourceStep", "providerStep", "runStep", "reviewStep", "exportStep"];
  let current = "sourceStep";
  if (["queued", "running-stage", "failed", "ready"].includes(phase)) current = "runStep";
  else if (["succeeded", "edited"].includes(phase)) current = "reviewStep";
  else if (phase === "exported") current = "exportStep";
  else if (inputReady && !providerReady) current = "providerStep";
  else if (inputReady && providerReady) current = "runStep";
  const completed = {
    sourceStep: inputReady,
    providerStep: providerReady,
    runStep: ["succeeded", "edited", "exported"].includes(phase),
    reviewStep: ["edited", "exported"].includes(phase),
    exportStep: phase === "exported",
  };

  stages.forEach((id) => {
    const node = $(id);
    const isCurrent = id === current;
    const isFailed = id === "runStep" && phase === "failed";
    const isAvailable = (id === "runStep" && runReady) || ((id === "reviewStep" || id === "exportStep") && state.lastResult);
    node.classList.toggle("active", isCurrent);
    node.classList.toggle("is-available", Boolean(isAvailable));
    node.classList.toggle("is-complete", completed[id]);
    node.classList.toggle("is-failed", isFailed);
    if (isCurrent) node.setAttribute("aria-current", "step");
    else node.removeAttribute("aria-current");
  });
}

function renderStats(stats) {
  $("statCards").innerHTML = Object.entries(stats)
    .map(([key, value]) => {
      const translationKey = `stat.${key}`;
      const label = t(translationKey);
      return `<div class="metric"><span>${escapeHtml(label === translationKey ? titleCase(key) : label)}</span><b>${value}</b></div>`;
    })
    .join("");
}

function renderOverview(result) {
  const freqs = result.analytics?.code_frequencies || [];
  const max = Math.max(1, ...freqs.map((row) => row.count || 0));
  $("tab-overview").innerHTML = `
    <div class="panel-head compact"><div><h2>${escapeHtml(t("overview.title"))}</h2><p>${escapeHtml(t("overview.copy"))}</p></div></div>
    ${barList(freqs.slice(0, 16), "code", "count", max)}
  `;
}

function renderGioia(result) {
  const rows = codebookRows(state.editedCodebook || result.codebook);
  $("tab-gioia").innerHTML = `
    <div class="panel-head compact"><div><h2>${escapeHtml(t("gioia.title"))}</h2><p>${escapeHtml(t("gioia.copy"))}</p></div></div>
    <div class="edit-grid">
      <label><span>${escapeHtml(t("gioia.filter"))}</span><input id="gioiaFilter" /></label>
      <label><span>${escapeHtml(t("gioia.theme"))}</span><input id="gioiaTheme" /></label>
      <label><span>${escapeHtml(t("gioia.dimension"))}</span><input id="gioiaDimension" /></label>
    </div>
    <div class="button-row gioia-actions">
      <button id="applyGioia" class="secondary" type="button">${escapeHtml(t("gioia.apply"))}</button>
      <button id="saveGioia" class="primary" type="button" ${state.gioiaDirty ? "" : "disabled"}>${escapeHtml(t("gioia.save"))}</button>
      <button id="undoGioia" class="ghost" type="button" ${state.gioiaDirty || state.codebookHistory.length ? "" : "disabled"}>${escapeHtml(t("gioia.undo"))}</button>
    </div>
    <p id="gioiaStatus" class="hint ${state.gioiaDirty ? "is-dirty" : ""}" role="status" aria-live="polite">${state.gioiaDirty ? escapeHtml(t("gioia.dirty")) : ""}</p>
    <div class="table-wrap">${editableGioiaTable(rows)}</div>
  `;
  $("applyGioia").addEventListener("click", applyGioiaBatch);
  $("saveGioia").addEventListener("click", saveGioiaEdits);
  $("undoGioia").addEventListener("click", undoGioiaEdits);
  $("gioiaTable").addEventListener("input", markGioiaDirty);
}

function codebookRows(codebook) {
  const codeToTheme = {};
  const themeToDimension = {};
  Object.entries(codebook?.second_order_themes || {}).forEach(([theme, codes]) => (codes || []).forEach((code) => (codeToTheme[code] = theme)));
  Object.entries(codebook?.aggregate_dimensions || {}).forEach(([dimension, themes]) => (themes || []).forEach((theme) => (themeToDimension[theme] = dimension)));
  return (codebook?.entries || []).map((entry) => {
    const theme = codeToTheme[entry.code] || "";
    return {
      old_code: entry.code,
      code: entry.code,
      definition: entry.definition || "",
      second_order_theme: theme,
      aggregate_dimension: themeToDimension[theme] || "",
      aliases: (entry.aliases || []).join(", "),
    };
  });
}

function editableGioiaTable(rows) {
  return `<table id="gioiaTable"><thead><tr><th>${escapeHtml(t("gioia.column.code"))}</th><th>${escapeHtml(t("gioia.column.definition"))}</th><th>${escapeHtml(t("gioia.column.theme"))}</th><th>${escapeHtml(t("gioia.column.dimension"))}</th><th>${escapeHtml(t("gioia.column.aliases"))}</th></tr></thead><tbody>
    ${rows.map((row, idx) => `<tr data-old-code="${escapeHtml(row.old_code)}">
      <td><input aria-label="${escapeAttr(t("gioia.aria.code", { row: idx + 1 }))}" data-field="code" data-row="${idx}" value="${escapeAttr(row.code)}" /></td>
      <td><input aria-label="${escapeAttr(t("gioia.aria.definition", { row: idx + 1 }))}" data-field="definition" data-row="${idx}" value="${escapeAttr(row.definition)}" /></td>
      <td><input aria-label="${escapeAttr(t("gioia.aria.theme", { row: idx + 1 }))}" data-field="second_order_theme" data-row="${idx}" value="${escapeAttr(row.second_order_theme)}" /></td>
      <td><input aria-label="${escapeAttr(t("gioia.aria.dimension", { row: idx + 1 }))}" data-field="aggregate_dimension" data-row="${idx}" value="${escapeAttr(row.aggregate_dimension)}" /></td>
      <td><input aria-label="${escapeAttr(t("gioia.aria.aliases", { row: idx + 1 }))}" data-field="aliases" data-row="${idx}" value="${escapeAttr(row.aliases)}" /></td>
    </tr>`).join("")}
  </tbody></table>`;
}

function applyGioiaBatch() {
  const filter = $("gioiaFilter").value.trim().toLowerCase();
  const theme = $("gioiaTheme").value.trim();
  const dimension = $("gioiaDimension").value.trim();
  document.querySelectorAll("#gioiaTable tbody tr").forEach((tr) => {
    const text = Array.from(tr.querySelectorAll("input"), (input) => input.value).join(" ").toLowerCase();
    if (!filter || text.includes(filter)) {
      if (theme) tr.querySelector('[data-field="second_order_theme"]').value = theme;
      if (dimension) tr.querySelector('[data-field="aggregate_dimension"]').value = dimension;
    }
  });
  markGioiaDirty();
  $("gioiaStatus").textContent = t("gioia.batchStaged");
}

function markGioiaDirty() {
  state.gioiaDirty = true;
  transitionWorkflow("edited");
  const status = $("gioiaStatus");
  if (status) {
    status.classList.add("is-dirty");
    status.textContent = t("gioia.dirty");
  }
  if ($("saveGioia")) $("saveGioia").disabled = false;
  if ($("undoGioia")) $("undoGioia").disabled = false;
}

function collectGioiaRows() {
  return Array.from(document.querySelectorAll("#gioiaTable tbody tr")).map((tr) => {
    const row = { old_code: tr.dataset.oldCode };
    tr.querySelectorAll("input").forEach((input) => (row[input.dataset.field] = input.value));
    return row;
  });
}

function validateGioiaRows(rows) {
  const seen = new Set();
  for (const row of rows) {
    const code = String(row.code || "").trim();
    if (!code) throw new Error(t("gioia.blankCode"));
    const normalized = code.toLocaleLowerCase();
    if (seen.has(normalized)) throw new Error(t("gioia.duplicateCode", { code }));
    seen.add(normalized);
  }
}

async function persistGioiaEdits({ codebookOverride = null, rowsOverride = null, recordHistory = true } = {}) {
  const codebook = codebookOverride || state.editedCodebook || state.lastResult?.codebook;
  if (!codebook) return null;
  const rows = rowsOverride || collectGioiaRows();
  validateGioiaRows(rows);
  const response = await postJson("/api/align-codebook", {
    codebook,
    rows,
    job_id: state.resultJobId || null,
  });
  const edited = response.codebook || response;
  if (recordHistory) state.codebookHistory.push(structuredCloneSafe(codebook));
  state.editedCodebook = edited;
  if (response.result) state.lastResult = response.result;
  else if (state.lastResult) state.lastResult.codebook = edited;
  state.gioiaDirty = false;
  transitionWorkflow("edited");
  return edited;
}

async function saveGioiaEdits() {
  const button = $("saveGioia");
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  try {
    await persistGioiaEdits();
    renderGioia(state.lastResult || { codebook: state.editedCodebook });
    $("gioiaStatus").textContent = t("gioia.saved");
    showToast(t("gioia.saved"));
  } catch (error) {
    $("gioiaStatus").textContent = error.message || t("toast.gioiaFailed");
    showToast(error.message || t("toast.gioiaFailed"), { kind: "error" });
  } finally {
    if (button.isConnected) {
      button.disabled = !state.gioiaDirty;
      button.removeAttribute("aria-busy");
    }
  }
}

async function undoGioiaEdits() {
  try {
    if (state.gioiaDirty) {
      state.gioiaDirty = false;
      renderGioia(state.lastResult || { codebook: state.editedCodebook });
      $("gioiaStatus").textContent = t("gioia.undone");
      transitionWorkflow("succeeded");
      return;
    }
    const previous = state.codebookHistory.pop();
    if (!previous) return;
    await persistGioiaEdits({
      codebookOverride: previous,
      rowsOverride: codebookRows(previous),
      recordHistory: false,
    });
    renderGioia(state.lastResult || { codebook: state.editedCodebook });
    $("gioiaStatus").textContent = t("gioia.undone");
  } catch (error) {
    $("gioiaStatus").textContent = error.message || t("toast.gioiaFailed");
    showToast(error.message || t("toast.gioiaFailed"), { kind: "error" });
  }
}

function structuredCloneSafe(value) {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

function renderContrasts(result) {
  const rows = result.analytics?.participant_contrasts || [];
  $("tab-contrasts").innerHTML = table(rows, ["participant", "segments", "open_codes", "unique_codes", "top_codes"]);
}

function renderNegatives(result) {
  const rows = result.analytics?.negative_case_rows || [];
  const summary = result.analytics?.negative_cases?.by_conflict_type || [];
  const max = Math.max(1, ...summary.map((row) => row.count || 0));
  $("tab-negatives").innerHTML = `${barList(summary, "conflict_type", "count", max)}${table(rows, ["seg_id", "participant", "conflict_type", "boundary_condition", "explanation"])}`;
}

function renderSaturation(result) {
  const metrics = result.saturation_metrics?.window_metrics || [];
  const novelty = result.saturation_metrics?.novelty_curve || [];
  const max = Math.max(1, ...novelty.map((row) => row.cumulative_unique || 0));
  $("tab-saturation").innerHTML = `${barList(novelty.slice(0, 30), "index", "cumulative_unique", max)}${table(metrics, ["name", "window", "threshold", "saturation_seg_index"])}`;
}

function renderData(result) {
  $("tab-data").innerHTML = `
    <h2>${escapeHtml(t("data.segments"))}</h2>${table(result.segments || [], ["seg_id", "speaker", "text"])}
    <h2>${escapeHtml(t("data.openCodes"))}</h2>${table((result.open_items || []).map((item) => ({ seg_id: item.seg_id, codes: (item.initial_codes || []).map((c) => c.code).join(", "), memo: item.quick_memo || "" })), ["seg_id", "codes", "memo"])}
    <h2>${escapeHtml(t("data.codebook"))}</h2>${table((result.codebook?.entries || []).map((entry) => ({ code: entry.code, definition: entry.definition, aliases: (entry.aliases || []).join(", ") })), ["code", "definition", "aliases"])}
  `;
}

function table(rows, columns) {
  if (!rows.length) return `<div class="preview-list empty">${escapeHtml(t("table.empty"))}</div>`;
  return `<div class="table-wrap"><table><thead><tr>${columns.map((c) => `<th>${titleCase(c)}</th>`).join("")}</tr></thead><tbody>
    ${rows.map((row) => `<tr>${columns.map((c) => `<td>${escapeHtml(row[c] ?? "")}</td>`).join("")}</tr>`).join("")}
  </tbody></table></div>`;
}

function barList(rows, labelKey, valueKey, max) {
  if (!rows.length) return `<div class="preview-list empty">${escapeHtml(t("chart.empty"))}</div>`;
  return rows
    .map((row) => {
      const label = row[labelKey] ?? "";
      const value = row[valueKey] || 0;
      const width = Math.max(2, Math.round((value / max) * 100));
      return `<div class="bar-row"><span>${escapeHtml(label)}</span><div class="bar"><div style="width:${width}%"></div></div><b>${value}</b></div>`;
    })
    .join("");
}

function handleTabKeydown(event) {
  const tabs = Array.from(document.querySelectorAll('.tabs [role="tab"]'));
  const current = tabs.indexOf(event.currentTarget);
  if (current < 0) return;

  let next = current;
  if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
  else if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = tabs.length - 1;
  else return;

  event.preventDefault();
  activateTab(tabs[next].dataset.tab, { focus: true });
}

function activateTab(tab, { focus = false } = {}) {
  let activeButton = null;
  document.querySelectorAll(".tab").forEach((button) => {
    const isActive = button.dataset.tab === tab;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
    button.tabIndex = isActive ? 0 : -1;
    if (isActive) activeButton = button;
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    const isActive = panel.id === `tab-${tab}`;
    panel.classList.toggle("active", isActive);
    panel.hidden = !isActive;
  });
  if (focus && activeButton) activeButton.focus();
}

function downloadZip() {
  if (state.bundleDownloadUrl) {
    const link = document.createElement("a");
    link.href = state.bundleDownloadUrl;
    link.download = "gtflow_output.zip";
    document.body.appendChild(link);
    link.click();
    link.remove();
  } else if (state.lastResult?.bundle_base64) {
    downloadBase64(state.lastResult.bundle_base64, "gtflow_output.zip", "application/zip");
  } else {
    return;
  }
  transitionWorkflow("exported");
}

function downloadBase64(base64, filename, type) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  downloadBlob(new Blob([bytes], { type }), filename);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function titleCase(value) {
  return String(value).replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("\n", " ");
}

function showToast(message, { kind = "status" } = {}) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();
  const node = document.createElement("div");
  node.className = `toast ${kind === "error" ? "toast-error" : ""}`.trim();
  node.setAttribute("role", kind === "error" ? "alert" : "status");
  node.setAttribute("aria-live", kind === "error" ? "assertive" : "polite");
  node.textContent = message;
  document.body.appendChild(node);
  window.setTimeout(() => node.remove(), 4200);
}
