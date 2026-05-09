const state = {
  previewTimer: null,
  lastResult: null,
  editedCodebook: null,
  sourceName: null,
  sourceSize: null,
  dragDepth: 0,
};

const $ = (id) => document.getElementById(id);

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
    "option.dialog": "Dialog",
    "option.paragraph": "Paragraph",
    "option.line": "Line",
    "top.eyebrow": "GTFlow studio",
    "top.title": "Qualitative evidence into theory.",
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
    "progress.running": "Running analysis",
    "progress.runningCopy": "This can take a few minutes depending on provider latency.",
    "progress.starting": "Starting analysis",
    "progress.startingCopy": "The model pipeline is running locally through the Python server.",
    "progress.coding": "Coding segments",
    "progress.codingCopy": "Open coding and codebook generation are in progress.",
    "progress.complete": "Complete",
    "progress.completeCopy": "Artifacts are ready for review and export.",
    "results.eyebrow": "Analysis output",
    "results.coreCategory": "Core category",
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
    "gioia.download": "Download edited codebook",
    "data.segments": "Segments",
    "data.openCodes": "Open codes",
    "data.codebook": "Codebook",
    "table.empty": "No data yet.",
    "chart.empty": "No chart data yet.",
    "toast.previewFailed": "Preview failed",
    "toast.runFailed": "Run failed",
    "toast.batchApplied": "Batch alignment applied.",
    "toast.firstFile": "Loaded the first dropped file.",
    "toast.readFailed": "Could not read {name}.",
    "status.fileLoaded": "{name} loaded ({size}).",
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
    "option.dialog": "对话",
    "option.paragraph": "段落",
    "option.line": "行",
    "top.eyebrow": "GTFlow 工作室",
    "top.title": "从质性证据走向理论。",
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
    "progress.running": "正在分析",
    "progress.runningCopy": "耗时取决于服务商延迟。",
    "progress.starting": "启动分析",
    "progress.startingCopy": "模型管线正在通过本地 Python 服务运行。",
    "progress.coding": "编码分段",
    "progress.codingCopy": "正在进行开放编码和代码本生成。",
    "progress.complete": "完成",
    "progress.completeCopy": "产物已可审阅和导出。",
    "results.eyebrow": "分析输出",
    "results.coreCategory": "核心范畴",
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
    "gioia.download": "下载编辑后的代码本",
    "data.segments": "分段",
    "data.openCodes": "开放代码",
    "data.codebook": "代码本",
    "table.empty": "暂无数据。",
    "chart.empty": "暂无图表数据。",
    "toast.previewFailed": "预览失败",
    "toast.runFailed": "运行失败",
    "toast.batchApplied": "已应用批量对齐。",
    "toast.firstFile": "已加载拖入的第一个文件。",
    "toast.readFailed": "无法读取 {name}。",
    "status.fileLoaded": "{name} 已加载（{size}）。",
    "placeholder.apiKey": "使用环境变量或粘贴密钥",
    "placeholder.organization": "可选组织 ID",
    "placeholder.azureDeployment": "部署名称",
    "placeholder.optional": "可选",
    "placeholder.inputText": "在这里粘贴访谈摘录、田野笔记或上传文件内容。\n\n参与者 A：...\n参与者 B：...",
    "aria.workflow": "分析流程",
    "aria.dropZone": "选择或拖入来源文件",
    "aria.readiness": "就绪清单",
    "aria.resultViews": "结果视图",
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
    "option.dialog": "對話",
    "option.paragraph": "段落",
    "option.line": "行",
    "top.eyebrow": "GTFlow 工作室",
    "top.title": "從質性證據走向理論。",
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
    "progress.running": "正在分析",
    "progress.runningCopy": "耗時取決於服務商延遲。",
    "progress.starting": "啟動分析",
    "progress.startingCopy": "模型管線正在透過本地 Python 服務執行。",
    "progress.coding": "編碼分段",
    "progress.codingCopy": "正在進行開放編碼和代碼本生成。",
    "progress.complete": "完成",
    "progress.completeCopy": "產物已可審閱和匯出。",
    "results.eyebrow": "分析輸出",
    "results.coreCategory": "核心範疇",
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
    "gioia.download": "下載編輯後的代碼本",
    "data.segments": "分段",
    "data.openCodes": "開放代碼",
    "data.codebook": "代碼本",
    "table.empty": "暫無資料。",
    "chart.empty": "暫無圖表資料。",
    "toast.previewFailed": "預覽失敗",
    "toast.runFailed": "執行失敗",
    "toast.batchApplied": "已套用批次對齊。",
    "toast.firstFile": "已載入拖入的第一個檔案。",
    "toast.readFailed": "無法讀取 {name}。",
    "status.fileLoaded": "{name} 已載入（{size}）。",
    "placeholder.apiKey": "使用環境變數或貼上金鑰",
    "placeholder.organization": "可選組織 ID",
    "placeholder.azureDeployment": "部署名稱",
    "placeholder.optional": "可選",
    "placeholder.inputText": "在這裡貼上訪談摘錄、田野筆記或上傳檔案內容。\n\n參與者 A：...\n參與者 B：...",
    "aria.workflow": "分析流程",
    "aria.dropZone": "選擇或拖入來源檔案",
    "aria.readiness": "就緒清單",
    "aria.resultViews": "結果視圖",
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
  refreshLocalizedState();
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

document.addEventListener("DOMContentLoaded", () => {
  setupLanguageOptions();
  bindControls();
  applyLanguage();
  updateProviderFields();
  updateSourceMeta();
  refreshPreview();
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
    if (node) node.addEventListener("input", schedulePreview);
  });
  $("providerName").addEventListener("change", updateProviderFields);
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
  $("downloadZip").addEventListener("click", downloadZip);
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !$("runButton").disabled) {
      event.preventDefault();
      runAnalysis();
    }
  });
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
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
  $("azureFields").classList.toggle("hidden", provider !== "azure_openai");
  $("openaiFields").classList.toggle("hidden", provider !== "openai_compatible");
  schedulePreview();
}

function schedulePreview() {
  updateSourceMeta();
  window.clearTimeout(state.previewTimer);
  state.previewTimer = window.setTimeout(refreshPreview, 250);
}

async function refreshPreview() {
  const payload = buildPayload();
  if (!payload.text.trim()) {
    renderPreview({ stats: { segments: 0, characters: 0, avg_chars: 0 }, segments: [], readiness: { ready: false, input: false, provider: providerLooksReady(), segments: 0 } });
    return;
  }
  try {
    const data = await postJson("/api/preview", payload);
    renderPreview(data);
  } catch (error) {
    showToast(error.message || t("toast.previewFailed"));
  }
}

function renderPreview(data) {
  const stats = data.stats || {};
  const readiness = data.readiness || {};
  updateSourceMeta(stats);
  $("metricSegments").textContent = stats.segments || 0;
  $("metricChars").textContent = stats.characters || 0;
  $("metricAvg").textContent = stats.avg_chars || 0;
  $("providerStep").classList.toggle("active", !!readiness.provider);
  $("runStep").classList.toggle("active", !!readiness.ready);
  $("runButton").disabled = !readiness.ready;
  document.body.classList.toggle("is-ready", !!readiness.ready);
  $("runHelp").textContent = runHelpText(readiness, stats);
  renderReadiness(readiness, stats);

  const list = $("previewList");
  const segments = data.segments || [];
  if (!segments.length) {
    list.className = "preview-list empty";
    list.textContent = t("preview.empty");
    return;
  }
  list.className = "preview-list";
  list.innerHTML = segments
    .slice(0, 30)
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
  if (provider === "azure_openai") {
    return hasModel && hasKey && $("azureEndpoint").value.trim() && $("azureDeployment").value.trim();
  }
  return hasModel && hasKey;
}

async function runAnalysis() {
  $("progressPanel").classList.remove("hidden");
  $("resultsPanel").classList.add("hidden");
  document.body.classList.add("is-running");
  setProgress(12, t("progress.starting"), t("progress.startingCopy"));
  $("runButton").disabled = true;
  $("runButton").textContent = t("button.running");
  try {
    setProgress(32, t("progress.coding"), t("progress.codingCopy"));
    const result = await postJson("/api/run", buildPayload());
    state.lastResult = result;
    state.editedCodebook = result.codebook;
    setProgress(100, t("progress.complete"), t("progress.completeCopy"));
    renderResults(result);
  } catch (error) {
    showToast(error.message || t("toast.runFailed"));
  } finally {
    document.body.classList.remove("is-running");
    $("runButton").disabled = false;
    $("runButton").textContent = t("button.run");
  }
}

function setProgress(value, title, copy) {
  $("progressBar").style.width = `${value}%`;
  $("progressTitle").textContent = title;
  $("progressCopy").textContent = copy;
}

function buildPayload() {
  return {
    text: $("inputText").value,
    source_name: state.sourceName,
    provider: {
      name: $("providerName").value,
      model: $("model").value,
      api_key: $("apiKey").value || null,
      base_url: $("baseUrl").value || null,
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
    },
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

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function renderResults(result, shouldScroll = true) {
  $("resultsPanel").classList.remove("hidden");
  document.body.classList.add("has-results");
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

function renderStats(stats) {
  $("statCards").innerHTML = Object.entries(stats)
    .map(([key, value]) => `<div class="metric"><span>${titleCase(key)}</span><b>${value}</b></div>`)
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
      <input id="gioiaFilter" placeholder="${escapeAttr(t("gioia.filter"))}" />
      <input id="gioiaTheme" placeholder="${escapeAttr(t("gioia.theme"))}" />
      <input id="gioiaDimension" placeholder="${escapeAttr(t("gioia.dimension"))}" />
    </div>
    <div class="button-row"><button id="applyGioia" class="secondary">${escapeHtml(t("gioia.apply"))}</button><button id="downloadCodebook" class="ghost">${escapeHtml(t("gioia.download"))}</button></div>
    <div class="table-wrap">${editableGioiaTable(rows)}</div>
  `;
  $("applyGioia").addEventListener("click", applyGioiaBatch);
  $("downloadCodebook").addEventListener("click", downloadEditedCodebook);
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
  return `<table id="gioiaTable"><thead><tr><th>Code</th><th>Definition</th><th>Theme</th><th>Dimension</th><th>Aliases</th></tr></thead><tbody>
    ${rows.map((row, idx) => `<tr data-old-code="${escapeHtml(row.old_code)}">
      <td><input data-field="code" data-row="${idx}" value="${escapeAttr(row.code)}" /></td>
      <td><input data-field="definition" data-row="${idx}" value="${escapeAttr(row.definition)}" /></td>
      <td><input data-field="second_order_theme" data-row="${idx}" value="${escapeAttr(row.second_order_theme)}" /></td>
      <td><input data-field="aggregate_dimension" data-row="${idx}" value="${escapeAttr(row.aggregate_dimension)}" /></td>
      <td><input data-field="aliases" data-row="${idx}" value="${escapeAttr(row.aliases)}" /></td>
    </tr>`).join("")}
  </tbody></table>`;
}

function applyGioiaBatch() {
  const filter = $("gioiaFilter").value.trim().toLowerCase();
  const theme = $("gioiaTheme").value.trim();
  const dimension = $("gioiaDimension").value.trim();
  document.querySelectorAll("#gioiaTable tbody tr").forEach((tr) => {
    const text = tr.innerText.toLowerCase();
    if (!filter || text.includes(filter)) {
      if (theme) tr.querySelector('[data-field="second_order_theme"]').value = theme;
      if (dimension) tr.querySelector('[data-field="aggregate_dimension"]').value = dimension;
    }
  });
  collectEditedCodebook();
  showToast(t("toast.batchApplied"));
}

function collectEditedCodebook() {
  const rows = Array.from(document.querySelectorAll("#gioiaTable tbody tr")).map((tr) => {
    const row = { old_code: tr.dataset.oldCode };
    tr.querySelectorAll("input").forEach((input) => (row[input.dataset.field] = input.value));
    return row;
  });
  const entries = [];
  const second = {};
  const aggregate = {};
  rows.forEach((row) => {
    if (!row.code) return;
    entries.push({ code: row.code, definition: row.definition || "", aliases: splitList(row.aliases), include: [], exclude: [], positive_examples: [], near_miss: [] });
    if (row.second_order_theme) {
      second[row.second_order_theme] = second[row.second_order_theme] || [];
      second[row.second_order_theme].push(row.code);
    }
    if (row.second_order_theme && row.aggregate_dimension) {
      aggregate[row.aggregate_dimension] = aggregate[row.aggregate_dimension] || [];
      if (!aggregate[row.aggregate_dimension].includes(row.second_order_theme)) aggregate[row.aggregate_dimension].push(row.second_order_theme);
    }
  });
  state.editedCodebook = { entries, second_order_themes: second, aggregate_dimensions: aggregate };
  return state.editedCodebook;
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

function activateTab(tab) {
  document.querySelectorAll(".tab").forEach((button) => {
    const isActive = button.dataset.tab === tab;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${tab}`));
}

function downloadZip() {
  if (!state.lastResult?.bundle_base64) return;
  downloadBase64(state.lastResult.bundle_base64, "gtflow_output.zip", "application/zip");
}

function downloadEditedCodebook() {
  const codebook = collectEditedCodebook();
  const blob = new Blob([JSON.stringify(codebook, null, 2)], { type: "application/json" });
  downloadBlob(blob, "codebook.edited.json");
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

function splitList(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
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

function showToast(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = message;
  document.body.appendChild(node);
  window.setTimeout(() => node.remove(), 4200);
}
