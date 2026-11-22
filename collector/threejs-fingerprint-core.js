'use strict';

/**
 * Offline static fingerprint engine for generated three.js / HTML artifacts.
 * It deliberately does not execute imported HTML. Results are evidence scores,
 * never a claimed provider identity without a labelled, held-out evaluation.
 */

const crypto = require('node:crypto');

const SAMPLE_SCHEMA = 'threejs-model-fingerprint-sample-v1';
const LIBRARY_SCHEMA = 'threejs-model-fingerprint-library-v1';
const FEATURE_SCHEMA = 'threejs-static-code-features-v1';
const ALLOWED_PROVIDERS = Object.freeze(['openai', 'anthropic', 'google', 'moonshotai', 'zai', 'spacexai', 'deepseek', 'minimax', 'meta', 'alibaba', 'v0']);
const PROVIDER_ALIASES = Object.freeze({
  openai: 'openai', gpt: 'openai',
  anthropic: 'anthropic', claude: 'anthropic',
  google: 'google', gemini: 'google',
  moonshotai: 'moonshotai', kimi: 'moonshotai',
  zai: 'zai', glm: 'zai', zhipu: 'zai',
  spacexai: 'spacexai', grok: 'spacexai', xai: 'spacexai',
  deepseek: 'deepseek',
  minimax: 'minimax',
  meta: 'meta', muse: 'meta',
  alibaba: 'alibaba', qwen: 'alibaba',
  v0: 'v0',
});
const MAX_ARTIFACT_BYTES = 5 * 1024 * 1024;
const MAX_EVIDENCE_BYTES = 10 * 1024 * 1024;
const EVIDENCE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.pdf']);
const DEFAULT_COVERAGE_GATE = Object.freeze({ minSamples: 12, minPrompts: 3, minSessions: 3 });
const DEFAULT_CALIBRATION_GATE = Object.freeze({ minHeldOutPredictions: 30, minExactTop1: 0.8 });
// Additive feature families. They deliberately describe source structure rather
// than claimed model names, numeric seeds, or runtime execution results.
const THREE_API_FAMILIES = Object.freeze({
  scene: new Set(['Scene', 'PerspectiveCamera', 'OrthographicCamera', 'WebGLRenderer', 'Color', 'Fog', 'FogExp2', 'Vector2', 'Vector3', 'Vector4', 'Group', 'Object3D', 'Mesh', 'InstancedMesh', 'Clock']),
  geometry: new Set(['BoxGeometry', 'PlaneGeometry', 'CircleGeometry', 'RingGeometry', 'ShapeGeometry', 'ExtrudeGeometry', 'TubeGeometry', 'LatheGeometry', 'SphereGeometry', 'IcosahedronGeometry', 'DodecahedronGeometry', 'OctahedronGeometry', 'TetrahedronGeometry', 'CylinderGeometry', 'ConeGeometry', 'CapsuleGeometry', 'TorusGeometry', 'TorusKnotGeometry', 'BufferGeometry', 'EdgesGeometry', 'WireframeGeometry']),
  material: new Set(['MeshStandardMaterial', 'MeshPhysicalMaterial', 'MeshPhongMaterial', 'MeshLambertMaterial', 'MeshBasicMaterial', 'PointsMaterial', 'LineBasicMaterial', 'ShaderMaterial', 'RawShaderMaterial']),
  light: new Set(['AmbientLight', 'DirectionalLight', 'PointLight', 'SpotLight', 'HemisphereLight', 'RectAreaLight']),
  interaction: new Set(['OrbitControls', 'TrackballControls', 'MapControls', 'Raycaster', 'DragControls']),
  asset: new Set(['TextureLoader', 'CubeTextureLoader', 'GLTFLoader', 'DRACOLoader', 'RGBELoader', 'FontLoader']),
  helper: new Set(['AxesHelper', 'GridHelper', 'DirectionalLightHelper', 'CameraHelper', 'BoxHelper']),
});
const THREE_API_NAMES = new Set(Object.values(THREE_API_FAMILIES).flatMap((items) => [...items]));

function sha256(value) {
  return crypto.createHash('sha256').update(String(value), 'utf8').digest('hex');
}

function canonicalText(value) {
  return String(value || '').replace(/\r\n?/g, '\n').replace(/^\uFEFF/, '');
}

function normalizedProvider(value) {
  const key = String(value || '').trim().toLowerCase();
  const provider = PROVIDER_ALIASES[key] || '';
  if (!provider || !ALLOWED_PROVIDERS.includes(provider)) {
    throw new Error('仅允许 OpenAI、Anthropic、Google 三个来源；请使用精确可见的 provider 标签。');
  }
  return provider;
}

function normalizeModelId(value) {
  const model = String(value || '').trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9._:/-]{1,127}$/.test(model)) {
    throw new Error('模型 ID 必须是渠道实际显示的精确标识（2–128 个小写字母、数字、点、短横线、下划线、斜杠或冒号）。');
  }
  if (!/^(gpt|claude|gemini|kimi|glm|grok|deepseek|qwen|minimax|muse|llama|v0)[a-z0-9._:/-]*/.test(model)) {
    throw new Error('模型 ID 必须以已知模型族开头(gpt/claude/gemini/kimi/glm/grok/deepseek/qwen/minimax/muse/llama/v0)。');
  }
  return model;
}

function normalizeEffort(value) {
  const effort = String(value || '').trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9._-]{1,47}$/.test(effort)) {
    throw new Error('努力档 / thinking tier 必须由来源界面明确显示，且使用 2–48 个小写字母、数字、点、短横线或下划线。');
  }
  return effort;
}

function normalizeEvidenceAttachment(value) {
  const attachment = value && typeof value === 'object' ? value : {};
  const filename = String(attachment.filename || '').trim();
  const storedFile = String(attachment.storedFile || '').trim();
  const contentSha256 = String(attachment.contentSha256 || '').trim().toLowerCase();
  const byteLength = Number(attachment.byteLength);
  if (!filename || filename.length > 180 || /[\\/:\u0000]/.test(filename)) {
    throw new Error('必须附加有效的本地标签证据文件（截图、PDF 或导出的可复核文本），且文件名不能包含路径。');
  }
  if (!/^[a-f0-9]{64}$/.test(contentSha256) || !Number.isInteger(byteLength) || byteLength < 1 || byteLength > MAX_EVIDENCE_BYTES) {
    throw new Error('标签证据附件的哈希或大小无效。');
  }
  const stored = storedFile.match(/^([a-f0-9]{64})(\.[a-z0-9]{1,12})$/);
  if (!stored || stored[1] !== contentSha256 || !EVIDENCE_EXTENSIONS.has(stored[2])) {
    throw new Error('标签证据附件必须是与哈希绑定的 PNG/JPG/WEBP 或 PDF 本地副本。');
  }
  return { filename, storedFile, contentSha256, byteLength };
}

function normalizeApiReceiptHashChain(value) {
  if (value === undefined || value === null) return null;
  const chain = value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  const hashes = ['planSha256', 'candidateSha256', 'requestSha256', 'jobSha256', 'responseSha256', 'answerMarkdownSha256', 'reassessmentSha256', 'responseTextSha256'];
  if (!chain || chain.schema !== 'threejs-v0proxy-strict-import-hash-chain-v1'
    || !/^[a-z0-9][a-z0-9-]{2,95}$/.test(String(chain.taskId || ''))
    || !/^[a-f0-9]{64}$/.test(String(chain.importKey || '').toLowerCase())
    || hashes.some((name) => !/^[a-f0-9]{64}$/.test(String(chain[name] || '').toLowerCase()))) {
    throw new Error('API 最终回执哈希链不完整或格式无效。');
  }
  return {
    schema: chain.schema,
    taskId: String(chain.taskId),
    importKey: String(chain.importKey).toLowerCase(),
    ...Object.fromEntries(hashes.map((name) => [name, String(chain[name]).toLowerCase()])),
  };
}

function strictLabel(provider, modelId, effortTier) {
  const normalized = normalizedProvider(provider);
  const model = normalizeModelId(modelId);
  const expectedPrefix = { openai: 'gpt', anthropic: 'claude', google: 'gemini', moonshotai: 'kimi', zai: 'glm', spacexai: 'grok', deepseek: 'deepseek', minimax: 'minimax', alibaba: 'qwen', v0: 'v0', meta: '' }[normalized];
  if (expectedPrefix && !model.startsWith(expectedPrefix)) {
    throw new Error(`来源与模型 ID 不一致：${normalized} 只能保存以 ${expectedPrefix} 开头的精确模型 ID。`);
  }
  return `${normalized}:${model}|${normalizeEffort(effortTier)}`;
}

function textWithoutFences(value) {
  const text = canonicalText(value).trim();
  const match = text.match(/^```(?:html|htm|javascript|js)?\s*\n([\s\S]*?)\n?```\s*$/i);
  return match ? match[1] : text;
}

function stripForStaticAnalysis(source) {
  let text = textWithoutFences(source);
  text = text.slice(0, MAX_ARTIFACT_BYTES);
  text = text.replace(/<!--[\s\S]*?-->/g, ' ');
  text = text.replace(/\/\*[\s\S]*?\*\//g, ' ');
  // Preserve URLs enough for token boundaries but remove line comments and string content.
  text = text.replace(/(^|[^:\\])\/\/[^\n\r]*/gm, '$1 ');
  text = text.replace(/(['"`])(?:\\.|(?!\1)[\s\S])*?\1/g, ' STR ');
  text = text.replace(/\b(?:gpt|claude|gemini)[a-z0-9._:/-]*\b/gi, ' MODEL_TOKEN ');
  text = text.replace(/\b\d+(?:\.\d+)?\b/g, ' NUM ');
  text = text.replace(/\s+/g, ' ').trim();
  return text;
}

function bump(map, key, amount = 1) {
  map[key] = (map[key] || 0) + amount;
}

function l2Normalize(vector) {
  const norm = Math.sqrt(Object.values(vector).reduce((sum, value) => sum + value * value, 0));
  if (!norm) return {};
  const result = {};
  for (const [key, value] of Object.entries(vector)) result[key] = Number((value / norm).toFixed(12));
  return result;
}

function prunedVector(vector, limit = 1400) {
  return Object.fromEntries(Object.entries(vector)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit));
}

function extractStaticFeatures(source) {
  const raw = canonicalText(source);
  const byteLength = Buffer.byteLength(raw, 'utf8');
  if (!raw.trim()) throw new Error('未收到 HTML / JavaScript 成果内容。');
  if (byteLength > MAX_ARTIFACT_BYTES) throw new Error(`成果文件超过 ${MAX_ARTIFACT_BYTES} bytes；请拆分或先人工确认。`);

  const canonical = stripForStaticAnalysis(raw);
  const vector = {};
  const count = (pattern) => (raw.match(pattern) || []).length;
  const summary = {
    byteLength,
    lines: raw.split('\n').length,
    scripts: count(/<script\b/gi),
    moduleScripts: count(/<script\b[^>]*\btype\s*=\s*["']module["']/gi),
    styles: count(/<style\b/gi),
    htmlTags: count(/<\/?[a-z][a-z0-9-]*/gi),
    threeApis: 0,
    geometryApis: 0,
    materialApis: 0,
    lightApis: 0,
    animationLoops: count(/requestAnimationFrame\s*\(/g) + count(/setAnimationLoop\s*\(/g),
    eventListeners: count(/addEventListener\s*\(/g),
    externalAssetReferences: count(/(?:https?:\/\/|\.gltf\b|\.glb\b|\.png\b|\.jpg\b|\.jpeg\b|\.webp\b|\.svg\b)/gi),
  };

  const htmlTags = raw.matchAll(/<\/?([a-z][a-z0-9-]*)\b/gi);
  for (const match of htmlTags) bump(vector, `html:${match[1].toLowerCase()}`);

  const apis = raw.matchAll(/\b(?:THREE\.)?([A-Z][A-Za-z0-9_]+)\s*\(/g);
  for (const match of apis) {
    const name = match[1];
    if (!THREE_API_NAMES.has(name)) continue;
    bump(vector, `api:${name}`);
    summary.threeApis += 1;
    for (const [family, names] of Object.entries(THREE_API_FAMILIES)) {
      if (names.has(name)) bump(vector, `api-family:${family}`);
    }
    if (THREE_API_FAMILIES.geometry.has(name)) summary.geometryApis += 1;
    if (THREE_API_FAMILIES.material.has(name)) summary.materialApis += 1;
    if (THREE_API_FAMILIES.light.has(name)) summary.lightApis += 1;
  }

  const calls = raw.matchAll(/\b([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*\(/g);
  for (const match of calls) {
    const property = match[2];
    if (/^(setSize|setPixelRatio|setAnimationLoop|add|remove|lookAt|render|update|appendChild|addEventListener|setAttribute|setClearColor|setFromCamera|intersectObjects|rotate[XYZ]|translate[XYZ]|scale|position|copy|clone|enableDamping|updateProjectionMatrix)$/.test(property)) {
      bump(vector, `call:${property}`);
    }
  }

  const cssProps = raw.matchAll(/(?:^|[;{])\s*([a-z-]{3,})\s*:/gmi);
  for (const match of cssProps) {
    const property = match[1].toLowerCase();
    if (/^(display|position|background|color|font-family|width|height|transform|border|box-shadow|grid-template-columns|align-items|justify-content|overflow|pointer-events|user-select|letter-spacing)$/.test(property)) {
      bump(vector, `css:${property}`);
    }
  }

  const directFeatures = [
    ['module:esm-import', /\bimport\s+(?:\*\s+as\s+)?[A-Za-z_$][\w$]*\s+from\s*["']https?:\/\//],
    ['renderer:antialias', /WebGLRenderer\s*\(\s*\{[^}]*\bantialias\s*:\s*true/i],
    ['renderer:alpha', /WebGLRenderer\s*\(\s*\{[^}]*\balpha\s*:\s*true/i],
    ['renderer:shadow-map', /\.shadowMap\.enabled\s*=\s*true/i],
    ['renderer:color-space', /\.(?:outputColorSpace|outputEncoding)\s*=/],
    ['renderer:tone-mapping', /\.toneMapping\s*=/],
    ['renderer:dpr-clamp', /Math\.min\s*\(\s*window\.devicePixelRatio/],
    ['material:wireframe', /\bwireframe\s*:\s*true/i],
    ['material:flat-shading', /\bflatShading\s*:\s*true/i],
    ['material:transparent', /\btransparent\s*:\s*true/i],
    ['material:metalness', /\bmetalness\s*:/i],
    ['material:roughness', /\broughness\s*:/i],
    ['object:cast-shadow', /\.castShadow\s*=\s*true/i],
    ['object:receive-shadow', /\.receiveShadow\s*=\s*true/i],
    ['animation:request-animation-frame', /requestAnimationFrame\s*\(/],
    ['animation:set-animation-loop', /setAnimationLoop\s*\(/],
    ['interaction:raycaster', /\bRaycaster\s*\(/],
    ['interaction:controls', /\b(?:OrbitControls|TrackballControls|MapControls|DragControls)\s*\(/],
    ['layout:resize-handler', /addEventListener\s*\(\s*["']resize["']/],
    ['layout:fixed-overlay', /\bposition\s*:\s*fixed/i],
    ['style:const', /\bconst\b/],
    ['style:arrow-function', /=>/],
    ['style:semicolon', /;/],
  ];
  for (const [key, pattern] of directFeatures) if (pattern.test(raw)) bump(vector, key);

  for (const match of raw.matchAll(/addEventListener\s*\(\s*["']([a-z-]{2,32})["']/gi)) bump(vector, `event:${match[1].toLowerCase()}`);

  const tokens = canonical.toLowerCase().match(/[a-z_$][a-z0-9_$.-]{1,48}/g) || [];
  const ignored = new Set(['const', 'let', 'var', 'function', 'return', 'true', 'false', 'null', 'undefined', 'str', 'num', 'model_token']);
  const kept = tokens.filter((token) => !ignored.has(token));
  for (const token of kept) bump(vector, `lex:${token}`);
  for (let index = 0; index + 1 < kept.length; index += 1) bump(vector, `pair:${kept[index]}|${kept[index + 1]}`);

  const normalized = prunedVector(l2Normalize(vector));
  return {
    schema: FEATURE_SCHEMA,
    contentSha256: sha256(canonical),
    byteLength,
    canonicalByteLength: Buffer.byteLength(canonical, 'utf8'),
    summary,
    vector: normalized,
  };
}

function validateEvidence(input) {
  const source = input && typeof input === 'object' ? input : {};
  const channel = String(source.channel || '').trim();
  const sessionKey = String(source.sessionKey || '').trim();
  const displayedModelId = normalizeModelId(source.displayedModelId);
  const displayedEffortTier = normalizeEffort(source.displayedEffortTier);
  const evidenceRef = String(source.evidenceRef || '').trim();
  if (!channel) throw new Error('必须记录样本来源渠道。');
  if (!sessionKey) throw new Error('必须记录独立会话 / 来源键；不能只用同一对话的重复输出训练。');
  if (!evidenceRef) throw new Error('必须提供可追溯证据说明或本地证据文件名；不要提交账号、Cookie 或令牌。');
  if (evidenceRef.length > 500 || /(?:password|passwd|cookie|token|authorization|bearer)\s*(?:=|:)/i.test(evidenceRef)) {
    throw new Error('证据说明疑似包含敏感凭据，已拒绝保存；请只写截图 / PDF / 界面证据说明。');
  }
  const evidenceAttachment = source.evidenceAttachment === undefined || source.evidenceAttachment === null
    ? null
    : normalizeEvidenceAttachment(source.evidenceAttachment);
  const apiReceiptHashChain = normalizeApiReceiptHashChain(source.apiReceiptHashChain);
  if (!evidenceAttachment && !apiReceiptHashChain) {
    throw new Error('必须附加本地截图/PDF 证据，或提供哈希绑定的 API 最终回执链。');
  }
  if (apiReceiptHashChain && channel !== 'v0proxy-v1-chat-final-receipt') {
    throw new Error('API 最终回执哈希链只能用于受控 v0proxy 直接文本采集渠道。');
  }
  if (source.labelConfirmed !== true) throw new Error('保存前必须人工确认来源界面显示的精确模型 ID 与 effort tier。');
  return { channel, sessionKey, displayedModelId, displayedEffortTier, evidenceRef, evidenceAttachment, apiReceiptHashChain, labelConfirmed: true };
}

function createSample(input) {
  const rawModelId = String(input?.modelId || '').trim();
  const rawEffortTier = String(input?.effortTier || '').trim();
  const rawDisplayedModelId = String(input?.source?.displayedModelId || '').trim();
  const rawDisplayedEffortTier = String(input?.source?.displayedEffortTier || '').trim();
  if (!rawModelId || rawModelId !== rawDisplayedModelId || !rawEffortTier || rawEffortTier !== rawDisplayedEffortTier) {
    throw new Error('保存被拒绝：训练标签与独立抄录的来源可见模型 ID / effort tier 原始文本不完全一致。');
  }
  const provider = normalizedProvider(input.provider);
  const modelId = normalizeModelId(input.modelId);
  const effortTier = normalizeEffort(input.effortTier);
  const evidence = validateEvidence(input.source);
  if (evidence.displayedModelId !== modelId || evidence.displayedEffortTier !== effortTier) {
    throw new Error('保存被拒绝：填写的训练标签与来源可见的模型 ID / effort tier 不完全一致。');
  }
  const probeId = String(input.probeId || '').trim();
  if (!/^[A-Z0-9][A-Z0-9._-]{2,63}$/i.test(probeId)) throw new Error('探针 ID 无效。');
  const promptSha256 = String(input.promptSha256 || '').trim().toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(promptSha256)) throw new Error('探针内容校验值无效；请从内置题库选择探针。');
  const feature = extractStaticFeatures(input.artifactText);
  const filename = String(input.filename || '').trim().slice(0, 180) || 'pasted-artifact.html';
  const label = strictLabel(provider, modelId, effortTier);
  const now = new Date().toISOString();
  const record = {
    schema: SAMPLE_SCHEMA,
    sampleId: `threejs-${Date.now().toString(36)}-${crypto.randomBytes(5).toString('hex')}`,
    createdAt: now,
    provider,
    modelId,
    effortTier,
    strictLabel: label,
    probeId,
    promptSha256,
    source: evidence,
    artifact: {
      filename,
      contentSha256: feature.contentSha256,
      byteLength: feature.byteLength,
      featureSchema: feature.schema,
      summary: feature.summary,
      vector: feature.vector,
    },
  };
  return { record, rawArtifact: canonicalText(input.artifactText), feature };
}

function validateRecord(record) {
  if (!record || typeof record !== 'object') throw new Error('样本记录不是对象。');
  if (record.schema !== SAMPLE_SCHEMA) throw new Error('样本 schema 不匹配。');
  const label = strictLabel(record.provider, record.modelId, record.effortTier);
  if (record.strictLabel !== label) throw new Error('样本严格标签被篡改或不一致。');
  const evidence = validateEvidence(record.source);
  if (evidence.displayedModelId !== record.modelId || evidence.displayedEffortTier !== record.effortTier) throw new Error('来源可见标签与训练标签不一致。');
  if (!record.artifact || record.artifact.featureSchema !== FEATURE_SCHEMA || !/^[a-f0-9]{64}$/.test(record.artifact.contentSha256 || '')) throw new Error('样本没有有效静态特征。');
  if (!record.artifact.vector || typeof record.artifact.vector !== 'object' || !Object.keys(record.artifact.vector).length) throw new Error('样本特征向量为空。');
  return true;
}

function duplicateStatus(records, record) {
  const sameArtifact = (records || []).filter((row) => row?.artifact?.contentSha256 === record.artifact.contentSha256 && row?.probeId === record.probeId);
  const exact = sameArtifact.find((row) => row.strictLabel === record.strictLabel);
  const conflicting = sameArtifact.find((row) => row.strictLabel !== record.strictLabel);
  return { exact: Boolean(exact), conflict: Boolean(conflicting), conflictLabel: conflicting?.strictLabel || '' };
}

function centroid(vectors) {
  const total = {};
  for (const vector of vectors) for (const [feature, value] of Object.entries(vector || {})) bump(total, feature, Number(value) || 0);
  const count = Math.max(1, vectors.length);
  for (const feature of Object.keys(total)) total[feature] /= count;
  return prunedVector(l2Normalize(total));
}

function coverageFor(records, gate = DEFAULT_COVERAGE_GATE) {
  const groups = new Map();
  for (const record of records || []) {
    try { validateRecord(record); } catch { continue; }
    const label = record.strictLabel;
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(record);
  }
  const labels = [];
  for (const [label, rows] of [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    const prompts = new Set(rows.map((row) => row.probeId));
    const sessions = new Set(rows.map((row) => `${row.source.channel}|${row.source.sessionKey}`));
    labels.push({
      strictLabel: label,
      provider: rows[0].provider,
      modelId: rows[0].modelId,
      effortTier: rows[0].effortTier,
      samples: rows.length,
      prompts: prompts.size,
      sessions: sessions.size,
      ready: rows.length >= gate.minSamples && prompts.size >= gate.minPrompts && sessions.size >= gate.minSessions,
      missing: [
        ...(rows.length < gate.minSamples ? [`samples ${rows.length}/${gate.minSamples}`] : []),
        ...(prompts.size < gate.minPrompts ? [`probes ${prompts.size}/${gate.minPrompts}`] : []),
        ...(sessions.size < gate.minSessions ? [`sessions ${sessions.size}/${gate.minSessions}`] : []),
      ],
    });
  }
  return { gate: { ...gate }, labels, totalRecords: (records || []).length, validRecords: labels.reduce((sum, item) => sum + item.samples, 0) };
}

function buildLibrary(records, options = {}) {
  const gate = { ...DEFAULT_COVERAGE_GATE, ...(options.coverageGate || {}) };
  const valid = [];
  const rejected = [];
  for (const row of records || []) {
    try { validateRecord(row); valid.push(row); } catch (error) { rejected.push({ sampleId: row?.sampleId || '', error: error.message }); }
  }
  const coverage = coverageFor(valid, gate);
  const groupByLabel = new Map();
  for (const row of valid) {
    if (!groupByLabel.has(row.strictLabel)) groupByLabel.set(row.strictLabel, []);
    groupByLabel.get(row.strictLabel).push(row);
  }
  const labels = {};
  for (const status of coverage.labels) {
    const rows = groupByLabel.get(status.strictLabel) || [];
    const perProbe = {};
    for (const row of rows) {
      if (!perProbe[row.probeId]) perProbe[row.probeId] = [];
      perProbe[row.probeId].push(row.artifact.vector);
    }
    labels[status.strictLabel] = {
      ...status,
      centroid: centroid(rows.map((row) => row.artifact.vector)),
      probes: Object.fromEntries(Object.entries(perProbe).map(([probeId, vectors]) => [probeId, { samples: vectors.length, centroid: centroid(vectors) }])),
    };
  }
  return {
    schema: LIBRARY_SCHEMA,
    createdAt: new Date().toISOString(),
    featureSchema: FEATURE_SCHEMA,
    providerAllowList: [...ALLOWED_PROVIDERS],
    coverageGate: gate,
    coverage,
    labels,
    rejected,
    calibration: { calibrated: false, reason: '需要独立会话留出集评测后才可设置可发布的决策阈值。' },
  };
}

function cosine(left, right) {
  let sum = 0;
  const [small, large] = Object.keys(left).length <= Object.keys(right).length ? [left, right] : [right, left];
  for (const [feature, value] of Object.entries(small)) sum += Number(value || 0) * Number(large[feature] || 0);
  return sum;
}

function predictArtifact(source, library, options = {}) {
  if (!library || library.schema !== LIBRARY_SCHEMA) throw new Error('请先建立兼容的指纹库。');
  const artifact = extractStaticFeatures(source);
  const probeId = String(options.probeId || '').trim();
  const candidates = Object.values(library.labels || {}).filter((label) => label.ready);
  const rankings = candidates.map((label) => {
    const generic = cosine(artifact.vector, label.centroid || {});
    const byProbe = probeId && label.probes?.[probeId]?.samples >= 2 ? cosine(artifact.vector, label.probes[probeId].centroid || {}) : null;
    const score = byProbe === null ? generic : (generic * 0.3 + byProbe * 0.7);
    return {
      strictLabel: label.strictLabel,
      provider: label.provider,
      modelId: label.modelId,
      effortTier: label.effortTier,
      score: Number(score.toFixed(6)),
      evidence: byProbe === null ? 'overall-prototype' : `probe-${probeId}-weighted`,
      coverage: { samples: label.samples, prompts: label.prompts, sessions: label.sessions },
    };
  }).sort((a, b) => b.score - a.score || a.strictLabel.localeCompare(b.strictLabel));
  const top = rankings[0] || null;
  const margin = top ? Number((top.score - (rankings[1]?.score || 0)).toFixed(6)) : 0;
  const calibration = library.calibration || { calibrated: false };
  let disposition = 'abstain';
  let reason = '没有达到覆盖门槛的模型标签。';
  if (top && calibration.calibrated) {
    const minSimilarity = Number(calibration.minSimilarity ?? 0);
    const minMargin = Number(calibration.minMargin ?? 0);
    if (top.score >= minSimilarity && margin >= minMargin) {
      disposition = 'candidate';
      reason = '通过经留出评测校准的相似度与间隔阈值；仍是代码风格候选，不是来源证明。';
    } else {
      reason = '低于校准阈值，按高精度策略拒识而非强行归类。';
    }
  } else if (top) {
    reason = '库尚未经过独立会话留出集校准；仅显示候选排序，不输出已识别结论。';
  }
  return { artifact, rankings: rankings.slice(0, 3), top, margin, disposition, reason, calibration };
}

function evaluateLibrary(records, options = {}) {
  const gate = { ...DEFAULT_COVERAGE_GATE, ...(options.coverageGate || {}) };
  const valid = (records || []).filter((row) => { try { return validateRecord(row); } catch { return false; } });
  const groups = new Map();
  for (const row of valid) {
    const key = `${row.source.channel}|${row.source.sessionKey}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  let attempted = 0;
  let resolved = 0;
  let exact = 0;
  const perLabel = {};
  const scorePairs = [];
  for (const [groupKey, heldOut] of groups) {
    const held = new Set(heldOut.map((row) => row.sampleId));
    const library = buildLibrary(valid.filter((row) => !held.has(row.sampleId)), { coverageGate: gate });
    for (const row of heldOut) {
      attempted += 1;
      const rankings = Object.values(library.labels || {}).filter((label) => label.ready).map((label) => {
        const generic = cosine(row.artifact.vector, label.centroid || {});
        const byProbe = label.probes?.[row.probeId]?.samples >= 2 ? cosine(row.artifact.vector, label.probes[row.probeId].centroid || {}) : null;
        const score = byProbe === null ? generic : generic * 0.3 + byProbe * 0.7;
        return { strictLabel: label.strictLabel, score };
      }).sort((a, b) => b.score - a.score || a.strictLabel.localeCompare(b.strictLabel));
      const top = rankings[0];
      if (!perLabel[row.strictLabel]) perLabel[row.strictLabel] = { attempted: 0, resolved: 0, exact: 0 };
      perLabel[row.strictLabel].attempted += 1;
      if (!top) continue;
      resolved += 1;
      perLabel[row.strictLabel].resolved += 1;
      const correct = top.strictLabel === row.strictLabel;
      if (correct) { exact += 1; perLabel[row.strictLabel].exact += 1; }
      scorePairs.push({ correct, topScore: top.score, margin: top.score - (rankings[1]?.score || 0) });
    }
  }
  const exactTop1 = resolved ? exact / resolved : 0;
  const minSimilarity = scorePairs.length ? Math.min(...scorePairs.filter((pair) => pair.correct).map((pair) => pair.topScore), 1) : 1;
  const minMargin = scorePairs.length ? Math.min(...scorePairs.filter((pair) => pair.correct).map((pair) => pair.margin), 1) : 1;
  const calibrationGate = { ...DEFAULT_CALIBRATION_GATE, ...(options.calibrationGate || {}) };
  const calibrated = resolved >= calibrationGate.minHeldOutPredictions && exactTop1 >= calibrationGate.minExactTop1;
  return {
    schema: 'threejs-fingerprint-evaluation-v1',
    createdAt: new Date().toISOString(),
    policy: 'strict_top1_exact_model_and_effort; session-grouped holdout; untrained labels do not count as hits',
    attempted,
    resolved,
    exact,
    exactTop1: Number(exactTop1.toFixed(6)),
    abstained: attempted - resolved,
    perLabel,
    calibration: {
      calibrated,
      minHeldOutPredictions: calibrationGate.minHeldOutPredictions,
      minExactTop1: calibrationGate.minExactTop1,
      minSimilarity: calibrated ? Number(Math.max(0, minSimilarity - 0.005).toFixed(6)) : null,
      minMargin: calibrated ? Number(Math.max(0, minMargin - 0.002).toFixed(6)) : null,
      reason: calibrated ? '根据会话分组留出集生成保守阈值。' : '未达到发布阈值；系统将继续拒识而不是声称高准确率。',
    },
  };
}

function applyEvaluation(library, evaluation) {
  if (!library || library.schema !== LIBRARY_SCHEMA) throw new Error('无效指纹库。');
  if (!evaluation || evaluation.schema !== 'threejs-fingerprint-evaluation-v1') throw new Error('无效评测报告。');
  return { ...library, calibration: { ...evaluation.calibration, evaluatedAt: evaluation.createdAt, exactTop1: evaluation.exactTop1, resolved: evaluation.resolved } };
}

module.exports = {
  SAMPLE_SCHEMA,
  LIBRARY_SCHEMA,
  FEATURE_SCHEMA,
  ALLOWED_PROVIDERS,
  DEFAULT_COVERAGE_GATE,
  DEFAULT_CALIBRATION_GATE,
  sha256,
  normalizedProvider,
  normalizeModelId,
  normalizeEffort,
  strictLabel,
  extractStaticFeatures,
  createSample,
  validateRecord,
  duplicateStatus,
  coverageFor,
  buildLibrary,
  predictArtifact,
  evaluateLibrary,
  applyEvaluation,
};
