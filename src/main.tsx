import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  BrainCircuit,
  Check,
  ChevronDown,
  Download,
  FileSpreadsheet,
  FolderOpen,
  FolderPlus,
  Columns3,
  Gauge,
  House,
  LayoutGrid,
  MoreHorizontal,
  Link2,
  LogIn,
  LogOut,
  ImagePlus,
  KeyRound,
  Loader2,
  PackageSearch,
  Play,
  RefreshCw,
  Search,
  Settings,
  ShoppingBag,
  Trash2,
  Upload,
  UserRound,
  Coins,
  CalendarDays,
  Printer,
  Plus,
  Palette,
  X,
  ListChecks,
  AlertCircle,
  Ban,
  CircleStop,
  Clock,
} from "lucide-react";
import "./styles.css";
import {
  initUiTheme,
  normalizeUiThemePreference,
  showUiTheme,
  UI_THEME_PRESETS,
  type UiThemeId,
  type UiThemePreference,
} from "./uiTheme";

initUiTheme();

const API_BASE = "";
const ONBOARDING_COMPLETE_KEY = "eco_native_onboarding_complete";

type Marketplace = "shopee" | "tiktok_shop" | "kwai_shop" | "mercado_livre";
type AppTab = "dashboard" | "collect" | "products" | "costs" | "settings";
type ProductDetailSection = "listing" | "images" | "files" | "info";
type SettingsSection = "store" | "integrations" | "appearance" | "colors" | "production" | "backup";
type ProductStatus = "collected" | "in_edit" | "ready" | "exported";

type BlockedSourceUrl = {
  id: string;
  project_id: string;
  url: string;
  reason: string;
  label?: string | null;
  created_at: string;
};

type FilamentSpool = {
  id: string;
  store_profile_id: string;
  name: string;
  material: string;
  color?: string | null;
  spool_price_brl: number;
  spool_weight_g: number;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

type FilamentUsage = {
  filament_id: string;
  grams: number;
};

type ExtraProductionCost = {
  label: string;
  amount_brl: number;
};

type ProductionCost = {
  filament_id?: string | null;
  grams: number;
  print_time_minutes: number;
  other_costs_brl: number;
  filaments?: FilamentUsage[];
  extra_costs?: ExtraProductionCost[];
    notes: string;
};

type ProductionSettings = {
  store_profile_id: string;
  electricity_kwh_price_brl: number;
  printer_power_watts: number;
  printer_purchase_price_brl: number;
  printer_useful_life_hours: number;
  maintenance_cost_per_hour_brl: number;
  labor_cost_per_hour_brl: number;
  updated_at: string;
};

type Printer3D = {
  id: string;
  name: string;
  model?: string | null;
  notes?: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

type PrintPlate = {
  id: string;
  name: string;
  print_time_minutes: number;
  filament_grams: number;
  filament_id?: string | null;
  quantity: number;
  notes: string;
};

type ProductionCostBreakdown = {
  production_cost: ProductionCost;
  filament_lines: Array<{
    filament_id: string;
    name: string;
    material: string;
    color?: string | null;
    grams: number;
    cost_per_gram_brl: number;
    cost_brl: number;
  }>;
  filament_total_brl: number;
  energy_cost_brl: number;
  depreciation_cost_brl: number;
  maintenance_cost_brl: number;
  labor_cost_brl: number;
  other_costs_brl: number;
  extra_total_brl: number;
  production_subtotal_brl: number;
  ai_cost_usd: number;
  ai_cost_brl: number | null;
  total_brl: number | null;
  print_time_minutes: number;
  print_time_label: string;
  plate_count: number;
  cost_per_hour_brl: number | null;
};

type Listing = {
  title: string;
  description: string;
  category: string;
  price: string;
  stock: number;
  weight: string;
  parcel_size: string;
  keywords: string[];
};

type Asset = {
  id: string;
  product_id: string;
  kind: string;
  path: string;
  public_url?: string | null;
  created_at?: string;
};

type Product = {
  id: string;
  project_id: string;
  name: string;
  source_url?: string;
  status: ProductStatus;
  tags: string[];
  listing: Listing;
  assets: Asset[];
  metadata: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

type CostEvent = {
  id?: string;
  created_at?: string;
  provider?: string;
  action?: string;
  model?: string;
  cost_usd?: number;
  currency?: string;
  source?: string;
  units?: number;
  metadata?: Record<string, unknown>;
};

type Job = {
  id: string;
  type: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  project_id?: string;
  product_id?: string;
  progress: number;
  message: string;
  logs?: string[];
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

type ImageModelOption = {
  id: string;
  label: string;
  description: string;
  cost_usd: number;
};

type SettingsPayload = {
  integrations: {
    openrouter: boolean;
    openrouter_model?: string;
    kie_ai: boolean;
    kie_image_model?: string;
    image_models?: ImageModelOption[];
    codex_image_gen: boolean;
    codex_bin?: string | null;
    public_app_url: string;
  };
};

type SettingsSecrets = {
  openrouter_api_key?: string | null;
  openrouter_model?: string | null;
  kie_api_key?: string | null;
  kie_image_model?: string | null;
  codex_bin?: string | null;
  public_app_url?: string | null;
};

type RuntimeStatus = {
  online: boolean;
  requires_internet: boolean;
  exchange: {
    usd_brl?: number | null;
    fetched_at?: string | null;
    source?: string | null;
    cached?: boolean;
    stale?: boolean;
  };
};

type BackupRestoreSummary = {
  kind?: "full_app" | "legacy_store";
  store_profiles: number;
  ai_profiles: number;
  products: number;
  jobs: number;
  blocked_source_urls?: number;
  filament_spools?: number;
  production_settings?: number;
  printers_3d?: number;
  print_schedule_tasks?: number;
  files: number;
  env_restored?: boolean;
  store_profile_id?: string;
  store_profile_name?: string;
};

type MakerWorldLoginStatus = {
  pages?: { id: string; url: string }[];
  active_page_id?: string | null;
  open: boolean;
  url?: string | null;
  message: string;
  configured?: boolean;
  interactive_login_available?: boolean;
  remote_control?: boolean;
  width?: number;
  height?: number;
  loading?: boolean;
  challenge?: boolean;
  attention?: boolean;
  mode?: "login" | "collect";
};

type StoreProfile = {
  id: string;
  name: string;
  marketplace: Marketplace;
  niche: string;
  logo_path?: string | null;
  ui_theme?: UiThemePreference | null;
  ai_profile_id?: string | null;
  search_prompt: string;
  curation_prompt: string;
  listing_prompt: string;
  image_prompt: string;
  image_prompts: Record<string, string>;
  disabled_image_prompts: string[];
  color_variation_prompt: string;
  updated_at?: string;
};

type AuthStatus = {
  authenticated: boolean;
  setup_required: boolean;
  username?: string;
  is_admin?: boolean;
  store?: StoreProfile;
  legacy_stores?: Array<{ id: string; name: string }>;
  stores?: LoginStore[];
};

type LoginStore = { id: string; name: string; photo_version?: string | null; ui_theme?: UiThemePreference | null };

const LAST_LOGIN_STORE_KEY = "eco-native-last-login-store";

function readLastLoginStore(): string {
  try {
    return window.localStorage.getItem(LAST_LOGIN_STORE_KEY) || "";
  } catch {
    return "";
  }
}

function rememberLoginStore(storeId: string) {
  try {
    window.localStorage.setItem(LAST_LOGIN_STORE_KEY, storeId);
  } catch {
    // Only a convenience: the next visit just starts without a store selected.
  }
}

type AdminStoreUsage = {
  store: { id: string; name: string; marketplace: string };
  username?: string | null;
  enabled: boolean;
  quotas: Record<string, number | null | undefined>;
  usage: Record<string, number>;
};

type AdminUsage = {
  period: string;
  periods: string[];
  totals: Record<string, number>;
  stores: AdminStoreUsage[];
};

type ImageOptions = {
  studio_prompts: Array<{ id: string; name: string }>;
  colors: Array<{ id: string; description: string }>;
};

type BatchProgress = {
  label: string;
  total: number;
  done: number;
  current: string;
} | null;

type ConfirmDialog = {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  danger?: boolean;
  resolve: (confirmed: boolean) => void;
} | null;

type OnboardingPayload = {
  store_name: string;
  marketplace: Marketplace;
  niche: string;
  openrouter_api_key: string;
  openrouter_model: string;
  kie_api_key: string;
  kie_image_model: string;
  public_app_url: string;
};

type ProductFilters = {
  query: string;
  status: "all" | ProductStatus;
  characteristic:
    | "all"
    | "with_listing"
    | "without_listing"
    | "with_image"
    | "without_image"
    | "with_model"
    | "without_model"
    | "listed"
    | "not_listed"
    | "draft_listing"
    | "without_ai_images"
    | "file_issues";
  publication: ProductPublication;
};

// Whether a product is published is the user's call: a manual mark kept in
// metadata.listed, whatever was exported or sent to a marketplace.
type ProductPublication = "all" | "listed" | "not_listed";

type ProductPage = {
  items: Product[];
  next_cursor: string | null;
  total: number;
  with_title: number;
  store_total: number;
  listed_total: number;
  not_listed_total: number;
};

// One loaded window of the catalog: pages are appended as the list scrolls.
type ProductListState = {
  items: Product[];
  nextCursor: string | null;
  total: number;
  withTitle: number;
  storeTotal: number;
  // Counts for the publication tabs, under the other filters.
  listedTotal: number;
  notListedTotal: number;
  loading: boolean;
  loaded: boolean;
};

type CatalogStats = {
  total: number;
  // Board columns: published products count only under "listed".
  stages: Record<ProductStatus | "listed", number>;
  // Unpublished products still missing something, except file_issues.
  attention: {
    without_listing: number;
    draft_listing: number;
    without_ai_images: number;
    without_model: number;
    file_issues: number;
  };
  ai_cost_usd: number;
  ai_cost_products: number;
  ai_cost_by_provider: { openrouter: number; kie: number; other: number };
};

const PRODUCT_PAGE_SIZE = 40;
const MAX_PRODUCT_RELOAD = 200;
const EMPTY_PRODUCT_LIST: ProductListState = {
  items: [],
  nextCursor: null,
  total: 0,
  withTitle: 0,
  storeTotal: 0,
  listedTotal: 0,
  notListedTotal: 0,
  loading: false,
  loaded: false,
};

function productPagePath(filters: ProductFilters, limit: number, cursor?: string | null): string {
  const params = new URLSearchParams({ limit: String(limit) });
  const query = filters.query.trim();
  if (query) params.set("q", query);
  if (filters.status !== "all") params.set("status", filters.status);
  if (filters.characteristic !== "all") params.set("characteristic", filters.characteristic);
  if (filters.publication !== "all") params.set("publication", filters.publication);
  if (cursor) params.set("cursor", cursor);
  return `/api/products/page?${params.toString()}`;
}

function mergeJobs(current: Job[], changed: Job[]): Job[] {
  if (!changed.length) return current;
  const byId = new Map(changed.map((job) => [job.id, job]));
  const merged = current.map((job) => byId.get(job.id) ?? job);
  const known = new Set(current.map((job) => job.id));
  // New jobs go first, like the server's newest-first order.
  return [...changed.filter((job) => !known.has(job.id)), ...merged];
}

const JOB_TYPE_LABELS: Record<string, string> = {
  collect_products: "Coleta",
  generate_listing: "Anúncio com IA",
  generate_images: "Imagens com IA",
  regenerate_image: "Recriar imagem",
};

function jobActive(job: Job): boolean {
  return job.status === "queued" || job.status === "running";
}

function jobSubject(job: Job): string {
  const name = job.metadata?.product_name ?? job.metadata?.label;
  return typeof name === "string" ? name : "";
}

function jobTitle(job: Job): string {
  const kind = JOB_TYPE_LABELS[job.type] ?? job.type;
  const subject = jobSubject(job);
  return subject ? `${kind} · ${subject}` : kind;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...init,
  });
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new Event("eco-native-auth-required"));
    }
    throw new Error(await readApiError(response));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// A job continues on the server even if this page is closed. Polling preserves
// existing batch sequencing without holding a long HTTP request open.
async function submitJob(path: string, init: RequestInit, onProgress?: (job: Job) => void): Promise<Job> {
  let job = await api<Job>(path, init);
  onProgress?.(job);
  while (job.status === "queued" || job.status === "running") {
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
    try {
      job = await api<Job>(`/api/jobs/${job.id}`);
      onProgress?.(job);
    } catch (error) {
      throw new Error(`Não foi possível acompanhar a tarefa ${job.id}. Ela pode continuar no servidor; confira o histórico antes de repetir. ${error instanceof Error ? error.message : ""}`);
    }
  }
  return job;
}

async function apiUpload<T>(path: string, file: File, fields?: Record<string, string>): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  if (fields) {
    for (const [key, value] of Object.entries(fields)) {
      form.append(key, value);
    }
  }
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  return response.json() as Promise<T>;
}

function isModelAsset(asset: Asset): boolean {
  return asset.kind === "model_3mf" || asset.kind.startsWith("model_3mf_extra");
}

function modelAssetLabel(kind: string): string {
  if (kind === "model_3mf") return "Modelo principal";
  const match = kind.match(/^model_3mf_extra_(\d+)$/);
  if (match) return `Modelo adicional ${match[1]}`;
  return "Modelo 3D";
}

function fileBasename(path: string): string {
  return path.split(/[/\\]/).pop() || path;
}

function statusLabel(status: ProductStatus): string {
  const labels: Record<ProductStatus, string> = {
    collected: "Coletado",
    in_edit: "Em edição",
    ready: "Pronto",
    exported: "Exportado",
  };
  return labels[status];
}

function isJobResult(value: unknown): value is Job {
  return Boolean(value && typeof value === "object" && "status" in value && "message" in value);
}

// `width` asks the server for a cached WebP thumbnail (snapped to 160, 384 or 768 px).
function assetUrl(asset: Asset, version?: string, width?: number): string {
  const params = new URLSearchParams();
  if (version) params.set("v", version);
  if (width) params.set("w", String(width));
  const query = params.toString();
  return `${API_BASE}/api/assets/${asset.id}${query ? `?${query}` : ""}`;
}

function storePhotoUrl(profile?: StoreProfile): string | undefined {
  if (!profile?.logo_path) return undefined;
  return `${API_BASE}/api/store-profiles/${profile.id}/photo?v=${encodeURIComponent(profile.updated_at || profile.logo_path)}`;
}

function fixPortugueseText(value: string): string {
  if (!value) return value;

  let text = value;
  if (/Ã|Â(?![a-z])|â€/.test(text)) {
    try {
      text = decodeURIComponent(escape(text));
    } catch {
      // keep original when mojibake repair fails
    }
  }

  return text
    .replace(/\bVis\?o\b/g, "Visão")
    .replace(/\bCat\?logo\b/g, "Catálogo")
    .replace(/\bnao\b/g, "não")
    .replace(/\bNao\b/g, "Não")
    .replace(/\bpossivel\b/g, "possível")
    .replace(/\bPossivel\b/g, "Possível")
    .replace(/\bverificacao\b/g, "verificação")
    .replace(/\bVerificacao\b/g, "Verificação")
    .replace(/\bserao\b/g, "serão")
    .replace(/\bSerao\b/g, "Serão")
    .replace(/\bpaginas\b/g, "páginas")
    .replace(/\bPaginas\b/g, "Páginas")
    .replace(/\bpagina\b/g, "página")
    .replace(/\bPagina\b/g, "Página")
    .replace(/\bextracao\b/g, "extração")
    .replace(/\bExtracao\b/g, "Extração")
    .replace(/\btendencias\b/g, "tendências")
    .replace(/\bTendencias\b/g, "Tendências")
    .replace(/\bvariacoes\b/g, "variações")
    .replace(/\bVariacoes\b/g, "Variações")
    .replace(/\bvariacao\b/g, "variação")
    .replace(/\bVariacao\b/g, "Variação")
    .replace(/\bVariaÃ§Ã£o\b/g, "Variação")
    .replace(/\bacao\b/g, "ação")
    .replace(/\bAcao\b/g, "Ação")
    .replace(/\banuncio\b/g, "anúncio")
    .replace(/\bAnuncio\b/g, "Anúncio")
    .replace(/\brevisao\b/g, "revisão")
    .replace(/\bRevisao\b/g, "Revisão")
    .replace(/\bdescricao\b/g, "descrição")
    .replace(/\bDescricao\b/g, "Descrição")
    .replace(/\banalise\b/g, "análise")
    .replace(/\bAnalise\b/g, "Análise")
    .replace(/\bestudio\b/g, "estúdio")
    .replace(/\bEstudio\b/g, "Estúdio")
    .replace(/\bconfiguracao\b/g, "configuração")
    .replace(/\bConfiguracao\b/g, "Configuração")
    .replace(/\bexecucao\b/g, "execução")
    .replace(/\bExecucao\b/g, "Execução")
    .replace(/\bversao\b/g, "versão")
    .replace(/\bVersao\b/g, "Versão")
    .replace(/\bsuportada\b/g, "suportada")
    .replace(/\bFaca\b/g, "Faça");
}

function displayText(value: string): string {
  return fixPortugueseText(value);
}

async function readApiError(response: Response): Promise<string> {
  const raw = await response.text();
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown };
    const detail = parsed.detail;
    if (typeof detail === "string") return fixPortugueseText(detail);
    if (Array.isArray(detail)) {
      return fixPortugueseText(
        detail
          .map((item) => {
            if (typeof item === "string") return item;
            if (item && typeof item === "object" && "msg" in item) return String((item as { msg?: string }).msg || item);
            return String(item);
          })
          .join("; "),
      );
    }
  } catch {
    // response body is not JSON
  }
  return fixPortugueseText(raw);
}

const PREVIOUS_VERSION_PREFIX = "previous_";

// Earlier versions of regenerated images; only the "Versões anteriores" gallery lists them.
function isPreviousVersion(asset: Asset): boolean {
  return asset.kind.startsWith(PREVIOUS_VERSION_PREFIX);
}

function isImageAsset(asset: Asset): boolean {
  if (isPreviousVersion(asset)) return false;
  return asset.kind.includes("image") || /\.(png|jpe?g|webp)$/i.test(asset.path);
}

function assetLabel(asset: Asset): string {
  const previous = isPreviousVersion(asset);
  const kind = previous ? asset.kind.slice(PREVIOUS_VERSION_PREFIX.length) : asset.kind;
  const label = kind.replace(/^generated_/, "IA ").replace(/^color_/, "Cor ").replace(/_/g, " ");
  return previous ? `${label} (anterior)` : label;
}

function getCoverAsset(product: Product): Asset | undefined {
  return product.assets.find((asset) => asset.kind === "cover_image" && isImageAsset(asset))
    ?? product.assets.find(isImageAsset);
}

function getImageAssets(product: Product): Asset[] {
  return product.assets.filter(isImageAsset);
}

// Once studio images exist the product is shown by the first one, as in its gallery.
function getMainImageAsset(product: Product): Asset | undefined {
  const generated = product.assets.filter((asset) => asset.kind.startsWith("generated_"));
  return generated.find((asset) => asset.kind === "generated_studio_classic") ?? generated[0] ?? getCoverAsset(product);
}

function productThumbnailUrl(product?: Product, width = 160): string | undefined {
  const asset = product ? getMainImageAsset(product) : undefined;
  // Replacing the cover keeps its asset id, so the product's update time busts the browser cache.
  return asset && product ? assetUrl(asset, product.updated_at, width) : undefined;
}

function hasListingContent(product?: Product): boolean {
  return Boolean(product?.listing.title || product?.listing.description);
}

function hasBaseImages(product?: Product): boolean {
  return Boolean(product?.assets.some((asset) => asset.kind.startsWith("generated_")));
}

function existingColorVariations(product: Product | undefined, colorIds: string[]): string[] {
  if (!product) return [];
  const existing = new Set(product.assets.filter((asset) => asset.kind.startsWith("color_")).map((asset) => asset.kind.replace(/^color_/, "")));
  return colorIds.filter((colorId) => existing.has(colorId));
}

function productCostEvents(product: Product): CostEvent[] {
  return Array.isArray(product.metadata.cost_events) ? (product.metadata.cost_events as CostEvent[]) : [];
}

function productSku(product?: Product): string {
  return String(product?.metadata?.sku || "");
}

function productColorSkus(product?: Product): Record<string, string> {
  const value = product?.metadata?.color_skus;
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, string> : {};
}

function productColorLabels(product?: Product): Record<string, string> {
  const value = product?.metadata?.color_labels;
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, string> : {};
}

type ManualVariation = { id: string; attribute: string; value: string; sku: string };

function productManualVariations(product?: Product): ManualVariation[] {
  const value = product?.metadata?.manual_variations;
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is ManualVariation =>
    Boolean(item) && typeof item === "object" && typeof (item as ManualVariation).id === "string");
}

function productListed(product?: Product): boolean {
  return Boolean(product?.metadata?.listed);
}

function productFileWarnings(product?: Product): string[] {
  const value = product?.metadata?.file_warnings;
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function productFileWarningLabel(product: Product): string | null {
  const warnings = productFileWarnings(product);
  if (!warnings.length) return null;
  if (warnings.includes("empty_folder")) return "Pasta do produto vazia no disco";
  if (warnings.some((warning) => warning.startsWith("missing_"))) return "Arquivos locais ausentes";
  if (warnings.includes("remote_only")) return "Somente imagem remota disponível";
  return "Arquivos locais inconsistentes";
}

type PipelineBadge = {
  key: string;
  label: string;
  state: "done" | "partial" | "pending";
  detail: string;
};

function productPipelineBadges(product: Product): PipelineBadge[] {
  const listing = product.listing;
  const hasFullListing = Boolean(listing.title && listing.description);
  const hasPartialListing = hasListingContent(product) && !hasFullListing;
  const baseImages = product.assets.filter((asset) => asset.kind.startsWith("generated_")).length;
  const colorImages = product.assets.filter((asset) => asset.kind.startsWith("color_")).length;
  const studioImages = baseImages + colorImages;
  const cover = getCoverAsset(product);
  const models = product.assets.filter(isModelAsset).length;
  const fileWarning = productFileWarningLabel(product);

  let publicationDetail = "Aguardando";
  let publicationState: PipelineBadge["state"] = "pending";
  if (product.status === "exported") {
    publicationDetail = "Exportado";
    publicationState = "done";
  } else if (product.status === "ready") {
    publicationDetail = "Pronto";
    publicationState = "done";
  } else if (hasFullListing || product.status === "in_edit") {
    publicationDetail = "Em edição";
    publicationState = "partial";
  }

  return [
    {
      key: "listing",
      label: "Anúncio",
      state: hasFullListing ? "done" : hasPartialListing ? "partial" : "pending",
      detail: hasFullListing ? "Completo" : hasPartialListing ? "Rascunho" : "Pendente",
    },
    {
      key: "photos",
      label: "Fotos",
      state: studioImages > 0 ? "done" : cover ? "partial" : "pending",
      detail: studioImages > 0 ? `${studioImages} IA` : cover ? "Só capa" : "Sem foto",
    },
    {
      key: "model",
      label: "3D",
      state: models > 0 ? "done" : "pending",
      detail: models > 0 ? `${models} arquivo${models > 1 ? "s" : ""}` : "Sem modelo",
    },
    ...(fileWarning ? [{
      key: "files",
      label: "Arquivos",
      state: "partial" as const,
      detail: fileWarning,
    }] : []),
    {
      key: "stage",
      label: "Etapa",
      state: publicationState,
      detail: publicationDetail,
    },
  ];
}

function productCardSubtitle(product: Product): string {
  const parts: string[] = [];
  const sku = productSku(product);
  if (sku) parts.push(sku);
  if (product.listing.title) parts.push(product.listing.title);
  if (product.listing.price) {
    const numeric = Number(String(product.listing.price).replace(",", "."));
    parts.push(Number.isFinite(numeric) && numeric > 0 ? formatBrl(numeric) : `R$ ${product.listing.price}`);
  }
  return parts.join(" · ");
}

function productCostTotal(product: Product): number {
  const stored = Number(product.metadata.cost_total_usd);
  if (Number.isFinite(stored) && stored > 0) return stored;
  return productCostEvents(product).reduce((sum, event) => sum + Number(event.cost_usd || 0), 0);
}

function defaultProductionCost(): ProductionCost {
  return {
    filament_id: null,
    grams: 0,
    print_time_minutes: 0,
    other_costs_brl: 0,
    notes: "",
  };
}

function defaultProductionSettings(storeProfileId: string): ProductionSettings {
  return {
    store_profile_id: storeProfileId,
    electricity_kwh_price_brl: 0.85,
    printer_power_watts: 200,
    printer_purchase_price_brl: 0,
    printer_useful_life_hours: 5000,
    maintenance_cost_per_hour_brl: 0,
    labor_cost_per_hour_brl: 0,
    updated_at: "",
  };
}

function readProductionCost(product?: Product): ProductionCost {
  const raw = product?.metadata?.production_cost;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return defaultProductionCost();
  const value = raw as Partial<ProductionCost> & { filaments?: FilamentUsage[]; extra_costs?: ExtraProductionCost[] };
  let filamentId = value.filament_id ? String(value.filament_id) : null;
  let grams = Number(value.grams || 0);
  if (!filamentId && Array.isArray(value.filaments) && value.filaments[0]) {
    filamentId = String(value.filaments[0].filament_id || "");
    grams = Number(value.filaments[0].grams || 0);
  }
  let otherCosts = Number(value.other_costs_brl || 0);
  if (otherCosts <= 0 && Array.isArray(value.extra_costs)) {
    otherCosts = value.extra_costs.reduce((sum, item) => sum + Number(item.amount_brl || 0), 0);
  }
  return {
    filament_id: filamentId,
    grams,
    print_time_minutes: Number(value.print_time_minutes || 0),
    other_costs_brl: otherCosts,
    notes: String(value.notes || ""),
  };
}

function resolveProductionCostFromProduct(product: Product, otherCostsOverride?: number): ProductionCost {
  const stored = readProductionCost(product);
  const other_costs_brl = otherCostsOverride ?? stored.other_costs_brl;
  const plates = readPrintPlates(product);
  if (!plates.length) {
    return { ...stored, other_costs_brl };
  }

  const totals = plateTotals(plates);
  const gramsByFilament = new Map<string, number>();
  for (const plate of plates) {
    if (!plate.filament_id || plate.filament_grams <= 0) continue;
    const add = plate.filament_grams * plate.quantity;
    gramsByFilament.set(plate.filament_id, (gramsByFilament.get(plate.filament_id) || 0) + add);
  }
  const filaments: FilamentUsage[] = [...gramsByFilament.entries()].map(([filament_id, grams]) => ({
    filament_id,
    grams: Math.round(grams * 100) / 100,
  }));
  const single = filaments.length === 1 ? filaments[0] : null;
  return {
    filament_id: single?.filament_id ?? null,
    grams: single?.grams ?? 0,
    print_time_minutes: totals.total_print_time_minutes,
    other_costs_brl,
    notes: stored.notes,
    filaments,
  };
}

function energyCostBrl(printTimeMinutes: number, settings: ProductionSettings): number {
  if (printTimeMinutes <= 0 || settings.printer_power_watts <= 0 || settings.electricity_kwh_price_brl <= 0) return 0;
  const hours = printTimeMinutes / 60;
  const kwh = hours * (settings.printer_power_watts / 1000);
  return Math.round(kwh * settings.electricity_kwh_price_brl * 100) / 100;
}

function hourlyCostBrl(printTimeMinutes: number, hourlyRate: number): number {
  if (printTimeMinutes <= 0 || hourlyRate <= 0) return 0;
  return Math.round((printTimeMinutes / 60) * hourlyRate * 100) / 100;
}

function depreciationCostBrl(printTimeMinutes: number, settings: ProductionSettings): number {
  if (settings.printer_purchase_price_brl <= 0 || settings.printer_useful_life_hours <= 0) return 0;
  const hourlyRate = settings.printer_purchase_price_brl / settings.printer_useful_life_hours;
  return hourlyCostBrl(printTimeMinutes, hourlyRate);
}

function maintenanceCostBrl(printTimeMinutes: number, settings: ProductionSettings): number {
  return hourlyCostBrl(printTimeMinutes, settings.maintenance_cost_per_hour_brl);
}

function laborCostBrl(printTimeMinutes: number, settings: ProductionSettings): number {
  return hourlyCostBrl(printTimeMinutes, settings.labor_cost_per_hour_brl);
}

function filamentCostPerGram(spool: FilamentSpool): number {
  if (spool.spool_weight_g <= 0) return 0;
  return spool.spool_price_brl / spool.spool_weight_g;
}

function formatPrintMinutes(minutes: number): string {
  if (!minutes || minutes <= 0) return "—";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours) return `${hours}h ${rest}min`;
  return `${rest}min`;
}

function computeProductionBreakdown(
  product: Product,
  filaments: FilamentSpool[],
  settings: ProductionSettings,
  usdBrl: number | null,
  otherCostsOverride?: number,
): ProductionCostBreakdown {
  const production_cost = resolveProductionCostFromProduct(product, otherCostsOverride);
  const filamentMap = new Map(filaments.map((item) => [item.id, item]));
  const filament_lines: ProductionCostBreakdown["filament_lines"] = [];
  let filament_total_brl = 0;

  if (production_cost.filament_id && production_cost.grams > 0) {
    const spool = filamentMap.get(production_cost.filament_id);
    if (spool) {
      const cost_per_gram_brl = filamentCostPerGram(spool);
      const cost_brl = Math.round(production_cost.grams * cost_per_gram_brl * 100) / 100;
      filament_lines.push({
        filament_id: spool.id,
        name: spool.name,
        material: spool.material,
        color: spool.color,
        grams: production_cost.grams,
        cost_per_gram_brl: Math.round(cost_per_gram_brl * 10000) / 10000,
        cost_brl,
      });
      filament_total_brl = cost_brl;
    }
  } else if (production_cost.filaments?.length) {
    for (const usage of production_cost.filaments) {
      const spool = filamentMap.get(usage.filament_id);
      if (!spool || usage.grams <= 0) continue;
      const cost_per_gram_brl = filamentCostPerGram(spool);
      const cost_brl = Math.round(usage.grams * cost_per_gram_brl * 100) / 100;
      filament_lines.push({
        filament_id: spool.id,
        name: spool.name,
        material: spool.material,
        color: spool.color,
        grams: usage.grams,
        cost_per_gram_brl: Math.round(cost_per_gram_brl * 10000) / 10000,
        cost_brl,
      });
      filament_total_brl += cost_brl;
    }
    filament_total_brl = Math.round(filament_total_brl * 100) / 100;
  }

  const energy_cost_brl = energyCostBrl(production_cost.print_time_minutes, settings);
  const depreciation_cost_brl = depreciationCostBrl(production_cost.print_time_minutes, settings);
  const maintenance_cost_brl = maintenanceCostBrl(production_cost.print_time_minutes, settings);
  const labor_cost_brl = laborCostBrl(production_cost.print_time_minutes, settings);
  const other_costs_brl = Math.round(production_cost.other_costs_brl * 100) / 100;
  const production_subtotal_brl = Math.round(
    (filament_total_brl + energy_cost_brl + depreciation_cost_brl + maintenance_cost_brl + labor_cost_brl + other_costs_brl) * 100,
  ) / 100;
  const ai_cost_usd = productCostTotal(product);
  const ai_cost_brl = usdBrl && usdBrl > 0 ? Math.round(ai_cost_usd * usdBrl * 100) / 100 : null;
  const total_brl = ai_cost_brl !== null
    ? Math.round((production_subtotal_brl + ai_cost_brl) * 100) / 100
    : null;
  const print_time_minutes = production_cost.print_time_minutes;
  const cost_per_hour_brl = print_time_minutes > 0
    ? Math.round((production_subtotal_brl / (print_time_minutes / 60)) * 100) / 100
    : null;

  return {
    production_cost,
    filament_lines,
    filament_total_brl,
    energy_cost_brl,
    depreciation_cost_brl,
    maintenance_cost_brl,
    labor_cost_brl,
    other_costs_brl,
    extra_total_brl: other_costs_brl,
    production_subtotal_brl,
    ai_cost_usd,
    ai_cost_brl,
    total_brl,
    print_time_minutes,
    print_time_label: formatPrintMinutes(print_time_minutes),
    plate_count: readPrintPlates(product).length,
    cost_per_hour_brl,
  };
}

function productionCostPayloadFromDraft(draft: ProductionCost): ProductionCost {
  return {
    filament_id: draft.filament_id || null,
    grams: Number(draft.grams || 0),
    print_time_minutes: Number(draft.print_time_minutes || 0),
    other_costs_brl: Number(draft.other_costs_brl || 0),
    notes: draft.notes || "",
    filaments: draft.filament_id
      ? [{ filament_id: draft.filament_id, grams: Number(draft.grams || 0) }]
      : [],
    extra_costs: [],
  };
}

function formatFilamentSummary(breakdown: ProductionCostBreakdown): string {
  if (!breakdown.filament_lines.length) return "—";
  if (breakdown.filament_lines.length === 1) return breakdown.filament_lines[0].name;
  return `${breakdown.filament_lines.length} filamentos`;
}

function totalFilamentGrams(breakdown: ProductionCostBreakdown, product: Product): number {
  if (breakdown.filament_lines.length) {
    return Math.round(breakdown.filament_lines.reduce((sum, line) => sum + line.grams, 0) * 100) / 100;
  }
  const plates = readPrintPlates(product);
  if (!plates.length) return 0;
  return plateTotals(plates).total_filament_grams;
}

function todayDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function defaultPrintPlate(index = 1): PrintPlate {
  return {
    id: crypto.randomUUID().replace(/-/g, ""),
    name: `Placa ${index}`,
    print_time_minutes: 0,
    filament_grams: 0,
    filament_id: null,
    quantity: 1,
    notes: "",
  };
}

function readPrintPlates(product?: Product): PrintPlate[] {
  const raw = product?.metadata?.print_plates;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
    .map((item) => ({
      id: String(item.id || crypto.randomUUID().replace(/-/g, "")),
      name: String(item.name || "Placa"),
      print_time_minutes: Number(item.print_time_minutes || 0),
      filament_grams: Number(item.filament_grams || 0),
      filament_id: item.filament_id ? String(item.filament_id) : null,
      quantity: Math.max(1, Number(item.quantity || 1)),
      notes: String(item.notes || ""),
    }));
}

function printPlatesEqual(left: PrintPlate[], right: PrintPlate[]): boolean {
  if (left.length !== right.length) return false;
  return left.every((plate, index) => {
    const other = right[index];
    return (
      plate.id === other.id
      && plate.name === other.name
      && plate.print_time_minutes === other.print_time_minutes
      && plate.filament_grams === other.filament_grams
      && (plate.filament_id || null) === (other.filament_id || null)
      && plate.quantity === other.quantity
      && plate.notes === other.notes
    );
  });
}

type AutosaveStatus = "saved" | "pending" | "saving" | "error";

type ListingSnapshot = { productId: string; listing: Listing; name: string };

type IntegrationDrafts = {
  openrouter_api_key: string;
  openrouter_model: string;
  kie_api_key: string;
  kie_image_model: string;
  use_codex_image_gen: boolean;
  codex_bin: string;
  public_app_url: string;
};

type ProductionDrafts = {
  settings: {
    electricity_kwh_price_brl: number;
    printer_power_watts: number;
    printer_purchase_price_brl: number;
    printer_useful_life_hours: number;
    maintenance_cost_per_hour_brl: number;
    labor_cost_per_hour_brl: number;
  };
  filaments: FilamentSpool[];
};

// New filament rows get a temporary id until the server creates them.
const DRAFT_FILAMENT_PREFIX = "draft-";

function parseDecimal(value: string): number {
  return Number(value.replace(",", ".")) || 0;
}

function listingsEqual(left: Listing, right: Listing): boolean {
  return left.title === right.title
    && left.description === right.description
    && left.category === right.category
    && left.price === right.price
    && left.stock === right.stock
    && left.weight === right.weight
    && left.parcel_size === right.parcel_size
    && left.keywords.join("\n") === right.keywords.join("\n");
}

function listingFingerprint(listing?: Listing | null): string {
  if (!listing) return "";
  return JSON.stringify(listing);
}

function storeProfilesEqual(left: StoreProfile, right: StoreProfile): boolean {
  return left.name === right.name
    && left.marketplace === right.marketplace
    && left.niche === right.niche
    && left.search_prompt === right.search_prompt
    && left.curation_prompt === right.curation_prompt
    && left.listing_prompt === right.listing_prompt
    && left.image_prompt === right.image_prompt
    && left.color_variation_prompt === right.color_variation_prompt
    && JSON.stringify(left.disabled_image_prompts || []) === JSON.stringify(right.disabled_image_prompts || [])
    && JSON.stringify(left.image_prompts || {}) === JSON.stringify(right.image_prompts || {});
}

function imageColorsEqual(left: ImageOptions["colors"], right: ImageOptions["colors"]): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function normalizeFilamentDraft(item: FilamentSpool) {
  return {
    id: item.id,
    name: item.name.trim(),
    material: item.material.trim() || "PLA",
    color: item.color || "",
    spool_price_brl: Number(item.spool_price_brl) || 0,
    spool_weight_g: Number(item.spool_weight_g) || 1000,
    notes: item.notes || "",
  };
}

function filamentDraftsEqual(drafts: FilamentSpool[], saved: FilamentSpool[]): boolean {
  const normalize = (items: FilamentSpool[]) =>
    items.filter((item) => item.name.trim()).map(normalizeFilamentDraft);
  return JSON.stringify(normalize(drafts)) === JSON.stringify(normalize(saved));
}

function normalizePrinterDraft(item: Printer3D) {
  return {
    id: item.id,
    name: item.name.trim(),
    model: item.model || "",
    notes: item.notes || "",
    active: item.active,
  };
}

function printerDraftsEqual(drafts: Printer3D[], saved: Printer3D[]): boolean {
  const normalize = (items: Printer3D[]) =>
    items.filter((item) => item.name.trim()).map(normalizePrinterDraft);
  return JSON.stringify(normalize(drafts)) === JSON.stringify(normalize(saved));
}

function productionSettingsDraftEqual(
  electricityPrice: string,
  printerPower: string,
  printerPurchasePrice: string,
  printerUsefulLifeHours: string,
  maintenanceCostPerHour: string,
  laborCostPerHour: string,
  settings: ProductionSettings | null,
): boolean {
  const fallback = defaultProductionSettings("");
  const target = settings ?? fallback;
  const parse = (value: string) => Number(value.replace(",", ".")) || 0;
  return parse(electricityPrice) === Number(target.electricity_kwh_price_brl)
    && parse(printerPower) === Number(target.printer_power_watts)
    && parse(printerPurchasePrice) === Number(target.printer_purchase_price_brl)
    && parse(printerUsefulLifeHours) === Number(target.printer_useful_life_hours)
    && parse(maintenanceCostPerHour) === Number(target.maintenance_cost_per_hour_brl)
    && parse(laborCostPerHour) === Number(target.labor_cost_per_hour_brl);
}

type AutosaveEntry<T> = { scope: string; key: string; snapshot: T };

const AUTOSAVE_RETRY_DELAYS_MS = [2000, 5000, 10000, 20000, 30000];

// Saves a draft once typing pauses. Each save receives the draft it is for, so
// edits are never lost when the user switches to another item, closes the
// editor or leaves the page: whatever is still pending is saved right away.
// Saves run one at a time; a failed save is retried until it succeeds or a
// newer draft of the same item replaces it.
function useAutosave<T>({
  enabled = true,
  scope,
  isDirty,
  snapshot,
  save,
  debounceMs = 1200,
}: {
  enabled?: boolean;
  scope: string;
  isDirty: boolean;
  snapshot: T;
  save: (snapshot: T) => Promise<unknown>;
  debounceMs?: number;
}): AutosaveStatus {
  const [status, setStatus] = useState<AutosaveStatus>("saved");
  const saveRef = useRef(save);
  saveRef.current = save;
  const pendingRef = useRef<AutosaveEntry<T> | null>(null);
  const queueRef = useRef<Promise<void>>(Promise.resolve());
  const inFlightRef = useRef(0);
  const mountedRef = useRef(true);
  const key = enabled && isDirty ? JSON.stringify(snapshot) : "";

  const persist = useCallback((entry: AutosaveEntry<T>) => {
    const run = async () => {
      for (let attempt = 0; ; attempt += 1) {
        // A newer draft of the same item already contains these edits.
        const newer = pendingRef.current;
        if (attempt > 0 && newer && newer.scope === entry.scope) return;
        inFlightRef.current += 1;
        if (mountedRef.current) setStatus("saving");
        try {
          await saveRef.current(entry.snapshot);
          inFlightRef.current -= 1;
          if (mountedRef.current) setStatus(pendingRef.current ? "pending" : "saved");
          return;
        } catch {
          inFlightRef.current -= 1;
          // One blip retries quietly; repeated failures are shown.
          if (mountedRef.current && attempt > 0) setStatus("error");
          const delay = AUTOSAVE_RETRY_DELAYS_MS[Math.min(attempt, AUTOSAVE_RETRY_DELAYS_MS.length - 1)];
          await new Promise((resolve) => window.setTimeout(resolve, delay));
        }
      }
    };
    queueRef.current = queueRef.current.then(run, run);
    return queueRef.current;
  }, []);

  const flush = useCallback(() => {
    const entry = pendingRef.current;
    if (!entry) return;
    pendingRef.current = null;
    void persist(entry);
  }, [persist]);

  useEffect(() => {
    const previous = pendingRef.current;
    // The user moved to something else: save what they left behind now.
    if (previous && (!enabled || previous.scope !== scope)) flush();
    if (!key) {
      pendingRef.current = null;
      if (inFlightRef.current === 0) setStatus((current) => (current === "error" ? current : "saved"));
      return undefined;
    }
    const entry: AutosaveEntry<T> = { scope, key, snapshot };
    pendingRef.current = entry;
    setStatus((current) => (current === "saving" ? current : "pending"));
    const timer = window.setTimeout(() => {
      if (pendingRef.current === entry) flush();
    }, debounceMs);
    return () => window.clearTimeout(timer);
    // `snapshot` is represented by `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, scope, key, debounceMs, flush]);

  useEffect(() => {
    mountedRef.current = true;
    const onHide = () => {
      if (document.visibilityState === "hidden") flush();
    };
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!pendingRef.current && inFlightRef.current === 0) return;
      flush();
      // Asks the browser to confirm leaving while the save is still running.
      event.preventDefault();
      event.returnValue = "";
    };
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      document.removeEventListener("visibilitychange", onHide);
      window.removeEventListener("beforeunload", onBeforeUnload);
      mountedRef.current = false;
      flush();
    };
  }, [flush]);

  return status;
}

function AutosaveIndicator({ status }: { status: AutosaveStatus }) {
  if (status === "error") {
    return <span className="autosave-indicator error">Não foi possível salvar. Tentando de novo...</span>;
  }
  if (status === "saved") {
    return (
      <span className="autosave-indicator saved">
        <Check size={13} /> Salvo
      </span>
    );
  }
  return <span className="autosave-indicator pending">Salvando...</span>;
}

function plateTotals(plates: PrintPlate[]) {
  return {
    plate_count: plates.length,
    total_print_time_minutes: plates.reduce((sum, plate) => sum + plate.print_time_minutes * plate.quantity, 0),
    total_filament_grams: Math.round(plates.reduce((sum, plate) => sum + plate.filament_grams * plate.quantity, 0) * 100) / 100,
  };
}

// Keeps the text being typed ("12," or "a, ") while the parsed value goes up;
// a different value from outside replaces the text.
function useParsedText<T>(value: T, format: (value: T) => string, parse: (text: string) => T) {
  const [text, setText] = useState(() => format(value));
  useEffect(() => {
    setText((current) => (format(parse(current)) === format(value) ? current : format(value)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [format(value)]);
  return [text, setText] as const;
}

function DecimalInput({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  const [text, setText] = useParsedText(value, (number) => (number ? String(number).replace(".", ",") : ""), parseDecimal);
  return (
    <input
      inputMode="decimal"
      value={text}
      onChange={(event) => {
        setText(event.target.value);
        onChange(parseDecimal(event.target.value));
      }}
    />
  );
}

function parseKeywords(text: string): string[] {
  return text.split(",").map((keyword) => keyword.trim()).filter(Boolean);
}

function KeywordsInput({ value, onChange }: { value: string[]; onChange: (value: string[]) => void }) {
  const [text, setText] = useParsedText(value, (keywords) => keywords.join(", "), parseKeywords);
  return (
    <input
      value={text}
      onChange={(event) => {
        setText(event.target.value);
        onChange(parseKeywords(event.target.value));
      }}
      placeholder="Separe por vírgula"
    />
  );
}

function formatUsd(value: number): string {
  if (!value) return "US$ 0,0000";
  return `US$ ${value.toLocaleString("pt-BR", { minimumFractionDigits: 4, maximumFractionDigits: 6 })}`;
}

function formatBrl(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function parseListingPrice(value: string): number | null {
  const parsed = Number(String(value || "").trim().replace(",", "."));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function ListingProductionHint({
  product,
  listingPrice,
  filaments,
  productionSettings,
  storeProfileId,
}: {
  product: Product;
  listingPrice: string;
  filaments: FilamentSpool[];
  productionSettings: ProductionSettings | null;
  storeProfileId?: string;
}) {
  const settings = productionSettings ?? defaultProductionSettings(storeProfileId || "");
  const breakdown = computeProductionBreakdown(product, filaments, settings, null);
  const plates = readPrintPlates(product);
  const productionCost = breakdown.production_subtotal_brl;

  if (!plates.length) {
    return (
      <small className="listing-production-hint">
        Custo de produção: cadastre placas em Impressão
      </small>
    );
  }

  const price = parseListingPrice(listingPrice);
  const margin = price !== null ? Math.round((price - productionCost) * 100) / 100 : null;
  const marginPct = price !== null && price > 0 && margin !== null
    ? Math.round((margin / price) * 100)
    : null;
  const marginClass = margin !== null && margin < 0 ? "negative" : margin !== null && margin > 0 ? "positive" : "";

  return (
    <small className={`listing-production-hint ${marginClass}`.trim()}>
      Produção {formatBrl(productionCost)}
      {margin !== null && marginPct !== null ? ` · margem ${formatBrl(margin)} (${marginPct}%)` : ""}
    </small>
  );
}

type ShopeeTemplateStatus = { configured: boolean; uploaded_at?: string };

// Opens the browser's file picker. Call it straight from a click handler:
// browsers block pickers that are not tied to a user gesture.
function pickFile(accept: string): Promise<File | null> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.addEventListener("change", () => resolve(input.files?.[0] ?? null), { once: true });
    input.addEventListener("cancel", () => resolve(null), { once: true });
    input.click();
  });
}

function filenameFromDisposition(disposition: string | null, fallback: string): string {
  const utf8Match = disposition?.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1]);
  const plainMatch = disposition?.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] || fallback;
}

function collectJobCost(job: Job): { cost: number; requests: number; source: "job" | "logs" | "none" } {
  const metadataCost = Number(job.metadata?.ai_cost_total_usd);
  const metadataRequests = Number(job.metadata?.ai_request_count);
  if (Number.isFinite(metadataCost) && metadataCost > 0) {
    return {
      cost: metadataCost,
      requests: Number.isFinite(metadataRequests) ? metadataRequests : 0,
      source: "job",
    };
  }
  const costs = (job.logs || [])
    .map((line) => line.match(/OpenRouter\s+\$([0-9.]+)/i)?.[1])
    .filter(Boolean)
    .map((value) => Number(value));
  const total = costs.reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0);
  if (total > 0) return { cost: total, requests: costs.length, source: "logs" };
  return { cost: 0, requests: Number.isFinite(metadataRequests) ? metadataRequests : 0, source: "none" };
}

function collectJobCreatedCount(job: Job): number {
  const metadataCreated = Number(job.metadata?.created_products);
  if (Number.isFinite(metadataCreated)) return metadataCreated;
  const message = displayText(job.message);
  const manualMatch = message.match(/^(\d+)\s+produto\(s\)\s+extraido/i);
  if (manualMatch) return Number(manualMatch[1]);
  const approvedMatch = message.match(/^(\d+)\s+aprovados/i);
  if (approvedMatch) return Number(approvedMatch[1]);
  return 0;
}

function collectJobsSummary(jobs: Job[]): { totalCost: number; totalJobs: number; totalProducts: number } {
  return jobs.reduce(
    (summary, job) => ({
      totalCost: summary.totalCost + collectJobCost(job).cost,
      totalJobs: summary.totalJobs + 1,
      totalProducts: summary.totalProducts + collectJobCreatedCount(job),
    }),
    { totalCost: 0, totalJobs: 0, totalProducts: 0 },
  );
}

function summarizeCostEvents(events: CostEvent[]): { openRouter: number; kie: number; other: number } {
  return events.reduce(
    (summary, event) => {
      const provider = String(event.provider || "").toLowerCase();
      const value = Number(event.cost_usd || 0);
      if (provider.includes("openrouter")) return { ...summary, openRouter: summary.openRouter + value };
      if (provider.includes("kie")) return { ...summary, kie: summary.kie + value };
      return { ...summary, other: summary.other + value };
    },
    { openRouter: 0, kie: 0, other: 0 },
  );
}

function filterProducts(products: Product[], filters: ProductFilters): Product[] {
  const query = filters.query.trim().toLowerCase();
  return products.filter((product) => {
    const hasListing = Boolean(product.listing.title || product.listing.description);
    const hasImage = product.assets.some(isImageAsset);
    const hasModel = product.assets.some(isModelAsset);
    const listed = productListed(product);
    if (filters.status !== "all" && product.status !== filters.status) return false;
    if (filters.publication !== "all" && listed !== (filters.publication === "listed")) return false;
    if (query) {
      const searchable = [
        product.name,
        product.source_url || "",
        product.status,
        product.tags.join(" "),
        product.listing.title,
        product.listing.category,
        product.listing.keywords.join(" "),
        productSku(product),
        Object.values(productColorSkus(product)).join(" "),
        productListed(product) ? "a venda à venda vendido publicado" : "nao publicado não publicado nao esta a venda não está à venda",
      ].join(" ").toLowerCase();
      if (!searchable.includes(query)) return false;
    }
    switch (filters.characteristic) {
      case "with_listing":
        return hasListing;
      case "without_listing":
        return !hasListing;
      case "with_image":
        return hasImage;
      case "without_image":
        return !hasImage;
      case "with_model":
        return hasModel;
      case "without_model":
        return !hasModel;
      case "listed":
        return listed;
      case "not_listed":
        return !listed;
      case "draft_listing":
        return hasListing && !(product.listing.title && product.listing.description);
      case "without_ai_images":
        return !product.assets.some((asset) => asset.kind.startsWith("generated_") || asset.kind.startsWith("color_"));
      case "file_issues":
        return productFileWarnings(product).length > 0;
      default:
        return true;
    }
  });
}

const tabInfo: Record<AppTab, { title: string; eyebrow: string }> = {
  dashboard: {
    eyebrow: "Visão geral",
    title: "Dashboard",
  },
  collect: {
    eyebrow: "MakerWorld scraper",
    title: "Coleta",
  },
  products: {
    eyebrow: "Catálogo e IA",
    title: "Produtos",
  },
  costs: {
    eyebrow: "Produção",
    title: "Custos",
  },
  settings: {
    eyebrow: "Configuração",
    title: "Ajustes",
  },
}

function App({ auth, onLogout }: { auth: AuthStatus; onLogout: () => Promise<void> }) {
  const [productList, setProductList] = useState<ProductListState>(EMPTY_PRODUCT_LIST);
  // Full products fetched by id (open details, recently changed). The list
  // holds lighter summaries, so details win when both have the product.
  const [productDetails, setProductDetails] = useState<Record<string, Product>>({});
  const [catalogStats, setCatalogStats] = useState<CatalogStats | null>(null);
  // Bumped whenever the list reloads or loses a product, so the board view,
  // which pages each column itself, reloads with it.
  const [catalogRevision, setCatalogRevision] = useState(0);
  // The costs table edits every product of the store, so it loads the whole
  // catalog itself, and only while that tab is open.
  const [costProducts, setCostProducts] = useState<Product[] | null>(null);
  const [shopeeTemplate, setShopeeTemplate] = useState<ShopeeTemplateStatus | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [storeProfiles, setStoreProfiles] = useState<StoreProfile[]>([]);
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [activeTab, setActiveTab] = useState<AppTab>("dashboard");
  const [selectedProductId, setSelectedProductId] = useState<string>("");
  const [keyword, setKeyword] = useState("organizador cozinha");
  const [manualUrl, setManualUrl] = useState("");
  const [collectLimit, setCollectLimit] = useState(8);
  const [collectScrolls, setCollectScrolls] = useState(8);
  const [activeStoreProfileId, setActiveStoreProfileId] = useState("");
  const [storeProfileDraft, setStoreProfileDraft] = useState<StoreProfile | null>(null);
  const [openRouterApiKeyDraft, setOpenRouterApiKeyDraft] = useState("");
  const [openRouterModelDraft, setOpenRouterModelDraft] = useState("qwen/qwen3.5-flash-02-23");
  const [kieApiKeyDraft, setKieApiKeyDraft] = useState("");
  const [kieImageModelDraft, setKieImageModelDraft] = useState("qwen/image-edit");
  const [useCodexImageGenDraft, setUseCodexImageGenDraft] = useState(false);
  const [codexBinDraft, setCodexBinDraft] = useState("");
  const [publicAppUrlDraft, setPublicAppUrlDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [listingDraft, setListingDraft] = useState<Listing | null>(null);
  const [productNameDraft, setProductNameDraft] = useState("");
  // Which product the listing drafts belong to; for one render after a product
  // switch they still hold the previous product's text.
  const [listingDraftOwner, setListingDraftOwner] = useState("");
  const [makerWorldLogin, setMakerWorldLogin] = useState<MakerWorldLoginStatus | null>(null);
  const [makerWorldViewerOpen, setMakerWorldViewerOpen] = useState(false);
  const [collectRunning, setCollectRunning] = useState(false);
  const [collectAttention, setCollectAttention] = useState("");
  const [collectJobId, setCollectJobId] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [productFilters, setProductFilters] = useState<ProductFilters>({ query: "", status: "all", characteristic: "all", publication: "all" });
  const [imageOptions, setImageOptions] = useState<ImageOptions>({ studio_prompts: [], colors: [] });
  const [selectedColorVariations, setSelectedColorVariations] = useState<string[]>([]);
  const [batchProgress, setBatchProgress] = useState<BatchProgress>(null);
  const [jobsPanelOpen, setJobsPanelOpen] = useState(false);
  // Jobs seen waiting or running; the poller reports them when they end.
  const activeJobIdsRef = useRef(new Set<string>());
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialog>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [blockedSourceUrls, setBlockedSourceUrls] = useState<BlockedSourceUrl[]>([]);
  const [filaments, setFilaments] = useState<FilamentSpool[]>([]);
  const [productionSettings, setProductionSettings] = useState<ProductionSettings | null>(null);

  const activeStoreProfile = storeProfiles.find((profile) => profile.id === activeStoreProfileId) ?? storeProfiles[0];
  const storeTheme = (activeStoreProfile ?? auth.store)?.ui_theme;
  const storeThemeKey = JSON.stringify(storeTheme ?? null);
  // Each store keeps its own colours, whichever browser it signs in from.
  useEffect(() => showUiTheme(storeTheme), [storeThemeKey]);
  // The server only returns this store's jobs.
  const storeJobs = jobs;
  const [debouncedProductQuery, setDebouncedProductQuery] = useState(productFilters.query);
  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedProductQuery(productFilters.query), 300);
    return () => window.clearTimeout(timeout);
  }, [productFilters.query]);
  const listFilters = useMemo<ProductFilters>(
    () => ({
      query: debouncedProductQuery,
      status: productFilters.status,
      characteristic: productFilters.characteristic,
      publication: productFilters.publication,
    }),
    [debouncedProductQuery, productFilters.status, productFilters.characteristic, productFilters.publication],
  );

  // Refs let long-lived callbacks (job polling, batch actions) see the latest
  // list and filters without being recreated.
  const productListRef = useRef(productList);
  productListRef.current = productList;
  const listFiltersRef = useRef(listFilters);
  const selectedProductIdRef = useRef(selectedProductId);
  selectedProductIdRef.current = selectedProductId;
  const productListRequestRef = useRef(0);
  const statsTimerRef = useRef<number | null>(null);

  const listedProducts = productList.items;
  const selectedProduct = (selectedProductId
    ? productDetails[selectedProductId] ?? listedProducts.find((product) => product.id === selectedProductId)
    : undefined) ?? listedProducts[0];

  function findProduct(productId: string): Product | undefined {
    return productDetails[productId]
      ?? productList.items.find((product) => product.id === productId)
      ?? costProducts?.find((product) => product.id === productId);
  }

  async function refreshStats() {
    const stats = await api<CatalogStats>("/api/products/stats");
    setCatalogStats(stats);
    return stats;
  }

  function scheduleStatsRefresh() {
    if (statsTimerRef.current !== null) window.clearTimeout(statsTimerRef.current);
    statsTimerRef.current = window.setTimeout(() => {
      statsTimerRef.current = null;
      refreshStats().catch(() => undefined);
    }, 800);
  }

  // Reloads the list from the top. With keepLoaded it fetches as many items as
  // are already on screen (up to MAX_PRODUCT_RELOAD), so the scroll position holds.
  async function reloadProductList(keepLoaded = true) {
    const request = ++productListRequestRef.current;
    const loadedCount = productListRef.current.items.length;
    const limit = keepLoaded ? Math.min(MAX_PRODUCT_RELOAD, Math.max(PRODUCT_PAGE_SIZE, loadedCount)) : PRODUCT_PAGE_SIZE;
    setCatalogRevision((revision) => revision + 1);
    setProductList((current) => ({ ...current, loading: true }));
    try {
      const page = await api<ProductPage>(productPagePath(listFiltersRef.current, limit));
      if (request !== productListRequestRef.current) return;
      setProductList({
        items: page.items,
        nextCursor: page.next_cursor,
        total: page.total,
        withTitle: page.with_title,
        storeTotal: page.store_total,
        listedTotal: page.listed_total,
        notListedTotal: page.not_listed_total,
        loading: false,
        loaded: true,
      });
    } catch (error) {
      if (request === productListRequestRef.current) setProductList((current) => ({ ...current, loading: false }));
      throw error;
    }
  }

  async function loadMoreProducts() {
    const current = productListRef.current;
    if (current.loading || !current.nextCursor) return;
    const request = productListRequestRef.current;
    setProductList((state) => ({ ...state, loading: true }));
    try {
      const page = await api<ProductPage>(productPagePath(listFiltersRef.current, PRODUCT_PAGE_SIZE, current.nextCursor));
      // A reload started meanwhile owns the list now.
      if (request !== productListRequestRef.current) return;
      setProductList((state) => {
        const known = new Set(state.items.map((product) => product.id));
        return {
          ...state,
          items: [...state.items, ...page.items.filter((product) => !known.has(product.id))],
          nextCursor: page.next_cursor,
          total: page.total,
          withTitle: page.with_title,
          storeTotal: page.store_total,
          listedTotal: page.listed_total,
          notListedTotal: page.not_listed_total,
          loading: false,
        };
      });
    } catch (error) {
      if (request === productListRequestRef.current) setProductList((state) => ({ ...state, loading: false }));
      setNotice(error instanceof Error ? error.message : "Não foi possível carregar mais produtos");
    }
  }

  useEffect(() => {
    listFiltersRef.current = listFilters;
    // A selection may include products the new filter hides; batch actions
    // should only ever touch products the user can see.
    setSelectedProductIds([]);
    reloadProductList(false).catch((error) => setNotice(error.message));
  }, [listFilters, activeStoreProfileId]);

  async function refresh() {
    const [nextStats, nextJobs, nextSettings, nextStoreProfiles, nextImageOptions, nextRuntimeStatus] = await Promise.all([
      api<CatalogStats>("/api/products/stats"),
      api<Job[]>("/api/jobs"),
      api<SettingsPayload>("/api/settings"),
      api<StoreProfile[]>("/api/store-profiles"),
      api<ImageOptions>("/api/image-options"),
      api<RuntimeStatus>("/api/runtime/status"),
    ]);
    setCatalogStats(nextStats);
    setJobs(nextJobs);
    setStoreProfiles(nextStoreProfiles);
    const nextStore = nextStoreProfiles.find((profile) => profile.id === activeStoreProfileId) ?? nextStoreProfiles[0];
    if (nextStore && !activeStoreProfileId) setActiveStoreProfileId(nextStore.id);
    if (nextStore && (!storeProfileDraft || nextStore.id === activeStoreProfileId)) setStoreProfileDraft(nextStore);
    setSettings(nextSettings);
    setRuntimeStatus(nextRuntimeStatus);
    setImageOptions(nextImageOptions);
    setOpenRouterModelDraft(nextSettings.integrations.openrouter_model || "qwen/qwen3.5-flash-02-23");
    setKieImageModelDraft(nextSettings.integrations.kie_image_model || "qwen/image-edit");
    setUseCodexImageGenDraft(Boolean(nextSettings.integrations.codex_image_gen));
    setCodexBinDraft(nextSettings.integrations.codex_bin || "");
    setPublicAppUrlDraft(nextSettings.integrations.public_app_url || "");
    const isCleanDefaultWorkspace =
      (nextStoreProfiles.length === 0 || (nextStoreProfiles.length === 1 && nextStoreProfiles[0]?.name === "Loja principal")) &&
      nextStats.total === 0;
    if (isCleanDefaultWorkspace && window.localStorage.getItem(ONBOARDING_COMPLETE_KEY) !== "true") {
      setOnboardingOpen(true);
    }
    api<MakerWorldLoginStatus>("/api/jobs/makerworld-login")
      .then((status) => {
        setMakerWorldLogin(status);
      })
      .catch(() => undefined);
  }

  async function refreshCatalog() {
    const [nextJobs] = await Promise.all([
      api<Job[]>("/api/jobs"),
      reloadProductList(true),
      refreshStats(),
    ]);
    setJobs(nextJobs);
  }

  // Fetches one product again and patches it wherever it is shown.
  async function refreshProduct(productId: string) {
    try {
      patchProduct(await api<Product>(`/api/products/${productId}`));
    } catch {
      /* Deleted or no longer in this store; the next reload drops it. */
    }
  }

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const active = activeJobIdsRef.current;
    let since = "";
    let polls = 0;
    async function poll() {
      try {
        // Only jobs changed since the last poll; a full list now and then also
        // drops jobs deleted on the server.
        const full = !since || polls % 24 === 0;
        const changed = await api<Job[]>(full ? "/api/jobs" : `/api/jobs?since=${encodeURIComponent(since)}`);
        if (cancelled) return;
        polls += 1;
        for (const job of changed) {
          if (job.updated_at && job.updated_at > since) since = job.updated_at;
        }
        setJobs((current) => (full ? changed : mergeJobs(current, changed)));
        const finished = changed.filter((job) => active.has(job.id) && !jobActive(job));
        for (const job of changed) {
          if (jobActive(job)) active.add(job.id);
          else active.delete(job.id);
        }
        // Collections report through their own screen.
        const reported = finished.filter((job) => job.type !== "collect_products");
        if (reported.length === 1) {
          const [job] = reported;
          setNotice(job.status === "completed" ? `Pronto: ${jobTitle(job)}.` : `Falhou: ${jobTitle(job)}. ${job.message}`);
        } else if (reported.length > 1) {
          const failed = reported.filter((job) => job.status === "failed").length;
          setNotice(`${reported.length} tarefas terminaram${failed ? `, ${failed} com falha` : ""}. Veja em Tarefas.`);
        }
        if (finished.length) {
          // Product jobs refresh just their product; collections add new
          // products, so those reload the list.
          const productIds = [...new Set(finished.map((job) => job.product_id).filter((id): id is string => Boolean(id)))];
          const reloadList = finished.some((job) => !job.product_id);
          await Promise.all([
            ...productIds.map(refreshProduct),
            reloadList ? reloadProductList(true) : Promise.resolve(),
            refreshStats(),
          ]);
        }
      } catch { /* Other API calls handle authentication and user-facing errors. */ }
      if (!cancelled) timer = setTimeout(poll, 2500);
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, []);

  useEffect(() => {
    if (!detailsOpen || !selectedProductId) return;
    void refreshProduct(selectedProductId);
  }, [detailsOpen, selectedProductId]);

  useEffect(() => {
    if (activeTab !== "costs") return undefined;
    let cancelled = false;
    api<Product[]>("/api/products")
      .then((items) => {
        if (!cancelled) setCostProducts(items);
      })
      .catch((error) => setNotice(error instanceof Error ? error.message : "Não foi possível carregar os custos"));
    return () => {
      cancelled = true;
    };
  }, [activeTab, activeStoreProfileId]);

  // `insert` is for a product just created here: it goes to the top of the
  // list. Otherwise only products already shown are updated, and one that no
  // longer matches the filters leaves the list (its open details stay).
  function patchProduct(updated: Product, insert = false) {
    const stillMatches = filterProducts([updated], listFiltersRef.current).length > 0;
    if (!stillMatches && !insert) setSelectedProductIds((current) => current.filter((id) => id !== updated.id));
    setProductList((current) => {
      const previous = current.items.find((product) => product.id === updated.id);
      if (!previous) {
        if (!insert) return current;
        const listed = productListed(updated);
        return {
          ...current,
          items: [updated, ...current.items],
          total: current.total + 1,
          storeTotal: current.storeTotal + 1,
          withTitle: current.withTitle + (updated.listing.title ? 1 : 0),
          listedTotal: current.listedTotal + (listed ? 1 : 0),
          notListedTotal: current.notListedTotal + (listed ? 0 : 1),
        };
      }
      // Publishing moves a product between the tabs, so their counts follow.
      const shift = Number(productListed(updated)) - Number(productListed(previous));
      const counts = {
        listedTotal: Math.max(0, current.listedTotal + shift),
        notListedTotal: Math.max(0, current.notListedTotal - shift),
      };
      if (!stillMatches) {
        return {
          ...current,
          ...counts,
          items: current.items.filter((product) => product.id !== updated.id),
          total: Math.max(0, current.total - 1),
        };
      }
      return { ...current, ...counts, items: current.items.map((product) => (product.id === updated.id ? updated : product)) };
    });
    // Every change is kept here, so views holding their own copies (the
    // board columns) show the latest version.
    setProductDetails((current) => ({ ...current, [updated.id]: updated }));
    setCostProducts((current) =>
      current?.some((product) => product.id === updated.id)
        ? current.map((product) => (product.id === updated.id ? updated : product))
        : current,
    );
    scheduleStatsRefresh();
  }

  async function saveStoreTheme(theme: UiThemePreference) {
    const profileId = activeStoreProfile?.id;
    if (!profileId) return;
    try {
      patchStoreProfile(await api<StoreProfile>(`/api/store-profiles/${profileId}/theme`, {
        method: "PUT",
        body: JSON.stringify(theme),
      }));
    } catch (error) {
      setNotice(error instanceof Error ? `Não foi possível salvar o tema da loja. ${error.message}` : "Não foi possível salvar o tema da loja.");
    }
  }

  function patchStoreProfile(updated: StoreProfile) {
    setStoreProfiles((current) => {
      const exists = current.some((profile) => profile.id === updated.id);
      if (!exists) return [...current, updated];
      return current.map((profile) => (profile.id === updated.id ? updated : profile));
    });
    if (updated.id === activeStoreProfileId || updated.id === storeProfileDraft?.id) {
      setStoreProfileDraft(updated);
    }
  }

  function removeProductFromState(productId: string) {
    setProductList((current) => {
      const removed = current.items.find((product) => product.id === productId);
      if (!removed) return current;
      const listed = productListed(removed);
      return {
        ...current,
        items: current.items.filter((product) => product.id !== productId),
        total: Math.max(0, current.total - 1),
        storeTotal: Math.max(0, current.storeTotal - 1),
        listedTotal: Math.max(0, current.listedTotal - (listed ? 1 : 0)),
        notListedTotal: Math.max(0, current.notListedTotal - (listed ? 0 : 1)),
      };
    });
    setProductDetails((current) => {
      if (!current[productId]) return current;
      const next = { ...current };
      delete next[productId];
      return next;
    });
    setCostProducts((current) => current?.filter((product) => product.id !== productId) ?? current);
    setCatalogRevision((revision) => revision + 1);
    scheduleStatsRefresh();
    setSelectedProductIds((current) => current.filter((id) => id !== productId));
    if (selectedProductId === productId) {
      setSelectedProductId("");
      setDetailsOpen(false);
    }
  }

  type RefreshMode = false | "catalog" | "all";

  type ActionOptions = {
    refresh?: RefreshMode;
    blockUi?: boolean;
    notifySuccess?: boolean;
  };

  async function applyRefresh(mode: RefreshMode) {
    if (mode === "all") await Promise.all([refresh(), reloadProductList(true)]);
    else if (mode === "catalog") await refreshCatalog();
  }

  useEffect(() => {
    refresh().catch((error) => setNotice(error.message));
  }, []);

  useEffect(() => {
    function refreshRuntimeStatus() {
      api<RuntimeStatus>("/api/runtime/status")
        .then(setRuntimeStatus)
        .catch(() => setRuntimeStatus((current) => current ? { ...current, online: false } : null));
    }
    window.addEventListener("online", refreshRuntimeStatus);
    window.addEventListener("offline", refreshRuntimeStatus);
    const interval = window.setInterval(refreshRuntimeStatus, 5 * 60 * 1000);
    return () => {
      window.removeEventListener("online", refreshRuntimeStatus);
      window.removeEventListener("offline", refreshRuntimeStatus);
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!notice || busy) return undefined;
    const timeout = window.setTimeout(() => setNotice(""), 4500);
    return () => window.clearTimeout(timeout);
  }, [notice, busy]);

  // The server copy the drafts were last synced with. A newer server copy of
  // the same product (an autosave reply, a finished job) only replaces fields
  // the user has not edited since, so typing during a save is never undone.
  const listingBaseRef = useRef<{ productId: string; listing: string; name: string } | null>(null);
  useEffect(() => {
    if (!selectedProduct) {
      listingBaseRef.current = null;
      setListingDraft(null);
      setProductNameDraft("");
      setListingDraftOwner("");
      return;
    }
    const base = listingBaseRef.current;
    const serverListing = selectedProduct.listing;
    if (base && base.productId === selectedProduct.id) {
      setListingDraft((current) => (current && listingFingerprint(current) !== base.listing ? current : serverListing));
      setProductNameDraft((current) => (current !== base.name ? current : selectedProduct.name));
    } else {
      setListingDraft(serverListing);
      setProductNameDraft(selectedProduct.name);
      setListingDraftOwner(selectedProduct.id);
    }
    listingBaseRef.current = {
      productId: selectedProduct.id,
      listing: listingFingerprint(serverListing),
      name: selectedProduct.name,
    };
  }, [selectedProduct?.id, selectedProduct?.name, listingFingerprint(selectedProduct?.listing)]);

  useEffect(() => {
    if (!activeStoreProfile?.id) {
      setBlockedSourceUrls([]);
      return undefined;
    }
    let cancelled = false;
    api<BlockedSourceUrl[]>("/api/blocked-urls")
      .then((entries) => {
        if (!cancelled) setBlockedSourceUrls(entries);
      })
      .catch(() => {
        if (!cancelled) setBlockedSourceUrls([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeStoreProfile?.id, catalogStats?.total]);

  useEffect(() => {
    if (!activeStoreProfile?.id) {
      setFilaments([]);
      return undefined;
    }
    let cancelled = false;
    api<FilamentSpool[]>(`/api/store-profiles/${activeStoreProfile.id}/filaments`)
      .then((entries) => {
        if (!cancelled) setFilaments(entries);
      })
      .catch(() => {
        if (!cancelled) setFilaments([]);
      });
    api<ProductionSettings>(`/api/store-profiles/${activeStoreProfile.id}/production-settings`)
      .then((settings) => {
        if (!cancelled) setProductionSettings(settings);
      })
      .catch(() => {
        if (!cancelled) setProductionSettings(defaultProductionSettings(activeStoreProfile.id));
      });
    return () => {
      cancelled = true;
    };
  }, [activeStoreProfile?.id, catalogStats?.total]);

  async function removeBlockedUrl(entryId: string) {
    try {
      setBusy(true);
      await api(`/api/blocked-urls/${entryId}`, { method: "DELETE" });
      setBlockedSourceUrls((current) => current.filter((entry) => entry.id !== entryId));
      setNotice("URL removida da lista de bloqueio. Ela pode ser coletada novamente.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Erro ao remover URL bloqueada");
    } finally {
      setBusy(false);
    }
  }

  async function saveFilament(payload: {
    id?: string;
    name: string;
    material: string;
    color: string;
    spool_price_brl: number;
    spool_weight_g: number;
    notes: string;
  }) {
    if (!activeStoreProfile?.id) return;
    const storeProfileId = activeStoreProfile.id;
    if (payload.id) {
      const updated = await api<FilamentSpool>(`/api/store-profiles/${storeProfileId}/filaments/${payload.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: payload.name,
          material: payload.material,
          color: payload.color || null,
          spool_price_brl: payload.spool_price_brl,
          spool_weight_g: payload.spool_weight_g,
          notes: payload.notes || null,
        }),
      });
      setFilaments((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      return updated;
    }
    const created = await api<FilamentSpool>(`/api/store-profiles/${storeProfileId}/filaments`, {
      method: "POST",
      body: JSON.stringify({
        name: payload.name,
        material: payload.material,
        color: payload.color || null,
        spool_price_brl: payload.spool_price_brl,
        spool_weight_g: payload.spool_weight_g,
        notes: payload.notes || null,
      }),
    });
    setFilaments((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name, "pt-BR")));
    return created;
  }

  async function deleteFilament(filamentId: string) {
    if (!activeStoreProfile?.id) return;
    await api(`/api/store-profiles/${activeStoreProfile.id}/filaments/${filamentId}`, { method: "DELETE" });
    setFilaments((current) => current.filter((item) => item.id !== filamentId));
  }

  async function saveProductionSettings(payload: {
    electricity_kwh_price_brl: number;
    printer_power_watts: number;
    printer_purchase_price_brl: number;
    printer_useful_life_hours: number;
    maintenance_cost_per_hour_brl: number;
    labor_cost_per_hour_brl: number;
  }) {
    if (!activeStoreProfile?.id) return;
    const updated = await api<ProductionSettings>(`/api/store-profiles/${activeStoreProfile.id}/production-settings`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    setProductionSettings(updated);
  }

  const saveProductionCostsBatch = useCallback(async (entries: Array<{ productId: string; productionCost: ProductionCost }>) => {
    if (!entries.length) return;
    await api<{ updated: number; product_ids: string[] }>("/api/products/production-costs/batch", {
      method: "PUT",
      body: JSON.stringify({
        items: entries.map(({ productId, productionCost }) => ({
          product_id: productId,
          production_cost: productionCostPayloadFromDraft(productionCost),
        })),
      }),
    });
  }, []);

  const syncProductionCostsInProducts = useCallback((
    entries: Array<{ productId: string; productionCost: ProductionCost }>,
  ) => {
    if (!entries.length) return;
    const updates = new Map(entries.map((entry) => [entry.productId, entry.productionCost]));
    function apply(product: Product): Product {
      const draft = updates.get(product.id);
      if (!draft) return product;
      return {
        ...product,
        metadata: {
          ...product.metadata,
          production_cost: productionCostPayloadFromDraft(draft),
        },
      };
    }
    setCostProducts((current) => current?.map(apply) ?? current);
    setProductList((current) => ({ ...current, items: current.items.map(apply) }));
    setProductDetails((current) => Object.fromEntries(Object.entries(current).map(([id, product]) => [id, apply(product)])));
  }, []);

  async function runAction<T>(label: string, action: () => Promise<T>): Promise<T | undefined>;
  async function runAction<T>(
    label: string,
    action: () => Promise<T>,
    options: ActionOptions,
  ): Promise<T | undefined>;
  async function runAction<T>(
    label: string,
    action: () => Promise<T>,
    options: ActionOptions = {},
  ): Promise<T | undefined> {
    const refreshMode: RefreshMode = options.refresh ?? "all";
    const blockUi = options.blockUi ?? refreshMode === "all";
    const notifySuccess = options.notifySuccess ?? blockUi;
    try {
      if (blockUi) {
        setBusy(true);
        setNotice(`${label}...`);
      }
      const result = await action();
      await applyRefresh(refreshMode);
      if (isJobResult(result) && result.status === "cancelled") {
        setNotice(result.message);
        return result;
      }
      if (isJobResult(result) && result.status === "failed") {
        const detail = result.logs?.length ? result.logs[result.logs.length - 1] : result.message;
        throw new Error(detail || "A tarefa falhou.");
      }
      if (notifySuccess && label.trim()) {
        setNotice(`${label} concluído.`);
      }
      return result;
    } catch (error) {
      if (error instanceof Error && error.message === "__cancelled__") {
        if (blockUi) setNotice("Ação cancelada.");
        return undefined;
      }
      setNotice(error instanceof Error ? error.message : "Erro inesperado");
      return undefined;
    } finally {
      if (blockUi) setBusy(false);
    }
  }

  function runFluidAction<T>(label: string, action: () => Promise<T>) {
    return runAction(label, action, { refresh: false, blockUi: false, notifySuccess: false });
  }

  function askConfirm({
    cancelLabel = "Cancelar",
    confirmLabel = "Continuar",
    danger = false,
    message,
    title,
  }: {
    cancelLabel?: string;
    confirmLabel?: string;
    danger?: boolean;
    message: string;
    title: string;
  }): Promise<boolean> {
    return new Promise((resolve) => {
      setConfirmDialog({ cancelLabel, confirmLabel, danger, message, resolve, title });
    });
  }

  function closeConfirmDialog(confirmed: boolean) {
    if (!confirmDialog) return;
    confirmDialog.resolve(confirmed);
    setConfirmDialog(null);
  }

  function confirmRegeneration(message: string): Promise<boolean> {
    return askConfirm({
      title: "Confirmar nova geração",
      message,
      confirmLabel: "Gerar mesmo assim",
    });
  }

  async function confirmDangerousDelete(message: string): Promise<boolean> {
    const first = await askConfirm({
      title: "Apagar produto",
      message,
      confirmLabel: "Continuar",
      danger: true,
    });
    if (!first) return false;
    return askConfirm({
      title: "Confirmar exclusão",
      message: "Confirme novamente. Esta exclusão não poderá ser desfeita.",
      confirmLabel: "Apagar definitivamente",
      danger: true,
    });
  }

  function collectProducts() {
    return runCollect("Coletando produtos", {
      store_profile_id: activeStoreProfile?.id ?? null,
      keyword,
      urls: [],
      limit: collectLimit,
      scrolls: collectScrolls,
      visible_browser: true,
      skip_ai_curation: true,
    });
  }

  function extractSelectedLinks() {
    const urls = manualUrl
      .split(/\s|,|\n/)
      .map((url) => url.trim())
      .filter(Boolean);
    if (!urls.length) {
      setNotice("Cole ao menos um link MakerWorld para extrair.");
      return Promise.resolve();
    }
    return runCollect("Extraindo links selecionados", {
      store_profile_id: activeStoreProfile?.id ?? null,
      keyword: "",
      urls,
      limit: urls.length,
      scrolls: collectScrolls,
      visible_browser: true,
      skip_ai_curation: true,
    });
  }

  // The collect browser is shown in the remote panel so the user can solve MakerWorld checks.
  function runCollect(label: string, body: Record<string, unknown>) {
    return runAction(label, async () => {
      if (makerWorldLogin?.open && makerWorldLogin.mode !== "collect") {
        // The login window holds the store's browser profile that the collect needs.
        setMakerWorldLogin(await api<MakerWorldLoginStatus>("/api/jobs/makerworld-login/close", { method: "POST" }));
      }
      let attention = "";
      setNotice(`${label}... Você pode usar o resto do app enquanto isso.`);
      setCollectAttention("");
      setCollectRunning(true);
      setMakerWorldViewerOpen(true);
      try {
        return await submitJob("/api/jobs/collect", { method: "POST", body: JSON.stringify(body) }, (job) => {
          setCollectJobId(job.id);
          const next = typeof job.metadata?.attention === "string" ? job.metadata.attention : "";
          if (next === attention) return;
          attention = next;
          setCollectAttention(next);
          if (next) setMakerWorldViewerOpen(true);
          setNotice(next || `${label}...`);
        });
      } finally {
        setCollectAttention("");
        setCollectJobId("");
        setCollectRunning(false);
        setMakerWorldViewerOpen(false);
      }
    }, { refresh: "catalog", blockUi: false, notifySuccess: true });
  }

  function stopCollect(jobId: string) {
    return runAction("Parando a coleta", async () => {
      setNotice("Parando a coleta... Os produtos já coletados ficam salvos.");
      const job = await api<Job>(`/api/jobs/${jobId}/stop`, { method: "POST" });
      setJobs((current) => mergeJobs(current, [job]));
    }, { refresh: false, blockUi: false, notifySuccess: false });
  }

  function openMakerWorldLogin() {
    return runAction("Abrindo login MakerWorld", async () => {
      const result = await api<MakerWorldLoginStatus>("/api/jobs/makerworld-login", {
        method: "POST",
      });
      setMakerWorldLogin(result);
      setMakerWorldViewerOpen(true);
      return result;
    });
  }

  function closeMakerWorldLogin() {
    return runAction("Fechando navegador MakerWorld", async () => {
      const result = await api<MakerWorldLoginStatus>("/api/jobs/makerworld-login/close", {
        method: "POST",
      });
      setMakerWorldLogin(result);
      setMakerWorldViewerOpen(false);
      return result;
    });
  }

  // Autosave: throws on failure so the caller retries. The secret drafts stay
  // filled while the editor is open (it clears them on close), so a pause in
  // the middle of typing a key never empties the field.
  async function saveOpenRouterSettings(draft: IntegrationDrafts) {
    const updated = await api<SettingsPayload>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify(draft),
    });
    setSettings(updated);
  }

  function clearIntegrationSecretDrafts() {
    setOpenRouterApiKeyDraft("");
    setKieApiKeyDraft("");
  }

  function finishOnboarding(payload: OnboardingPayload) {
    return runFluidAction("Salvando configuração inicial", async () => {
      const profileId = activeStoreProfile?.id ?? storeProfiles[0]?.id;
      if (profileId) {
        const baseProfile = activeStoreProfile ?? storeProfiles[0];
        const updatedProfile = await api<StoreProfile>(`/api/store-profiles/${profileId}`, {
          method: "PATCH",
          body: JSON.stringify({
            ...baseProfile,
            name: payload.store_name.trim() || baseProfile.name,
            marketplace: payload.marketplace,
            niche: payload.niche.trim() || baseProfile.niche,
          }),
        });
        patchStoreProfile(updatedProfile);
        setActiveStoreProfileId(updatedProfile.id);
      }

      const integrationPayload: Record<string, string> = {
        openrouter_model: payload.openrouter_model.trim() || "qwen/qwen3.5-flash-02-23",
        kie_image_model: payload.kie_image_model.trim() || "qwen/image-edit",
      };
      if (payload.openrouter_api_key.trim()) integrationPayload.openrouter_api_key = payload.openrouter_api_key.trim();
      if (payload.kie_api_key.trim()) integrationPayload.kie_api_key = payload.kie_api_key.trim();
      if (payload.public_app_url.trim()) integrationPayload.public_app_url = payload.public_app_url.trim();
      const updatedSettings = await api<SettingsPayload>("/api/settings", {
        method: "PATCH",
        body: JSON.stringify(integrationPayload),
      });
      setSettings(updatedSettings);
      window.localStorage.setItem(ONBOARDING_COMPLETE_KEY, "true");
      setOnboardingOpen(false);
      setNotice("Configuração inicial salva.");
      return updatedSettings;
    });
  }

  function skipOnboarding() {
    window.localStorage.setItem(ONBOARDING_COMPLETE_KEY, "true");
    setOnboardingOpen(false);
  }

  function selectStoreProfile(profileId: string) {
    setActiveStoreProfileId(profileId);
    const profile = storeProfiles.find((item) => item.id === profileId);
    if (profile) setStoreProfileDraft(profile);
    setSelectedProductId("");
    setSelectedProductIds([]);
    setDetailsOpen(false);
  }

  // Autosave: throws on failure so the caller retries.
  async function saveStoreProfile(draft: StoreProfile) {
    const updated = await api<StoreProfile>(`/api/store-profiles/${draft.id}`, {
      method: "PATCH",
      body: JSON.stringify(draft),
    });
    setStoreProfiles((current) => current.map((profile) => (profile.id === updated.id ? updated : profile)));
    // Typing that happened during the save stays in the draft.
    setStoreProfileDraft((current) =>
      current && current.id === updated.id && JSON.stringify(current) === JSON.stringify(draft) ? updated : current);
  }

  function createStoreProfile(credentials: { name: string; username: string; password: string }) {
    return runFluidAction("Criando perfil de loja", async () => {
      const created = await api<StoreProfile>("/api/store-profiles", {
        method: "POST",
        body: JSON.stringify({
          name: credentials.name,
          username: credentials.username,
          password: credentials.password,
          marketplace: storeProfileDraft?.marketplace || "shopee",
          niche: storeProfileDraft?.niche || "Utilidades para casa",
          ai_profile_id: storeProfileDraft?.ai_profile_id || null,
          search_prompt: storeProfileDraft?.search_prompt || "",
          curation_prompt: storeProfileDraft?.curation_prompt || "",
          listing_prompt: storeProfileDraft?.listing_prompt || "",
          image_prompt: storeProfileDraft?.image_prompt || "",
          image_prompts: storeProfileDraft?.image_prompts || {},
          disabled_image_prompts: storeProfileDraft?.disabled_image_prompts || [],
          color_variation_prompt: storeProfileDraft?.color_variation_prompt || "",
        }),
      });
      setNotice(`Loja ${created.name} criada. Ela já pode entrar com o login próprio.`);
      return created;
    });
  }

  function uploadStoreProfilePhoto(profileId: string, file: File) {
    return runFluidAction("Salvando foto da loja", async () => {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(new Error("Não foi possível ler a imagem."));
        reader.readAsDataURL(file);
      });
      const updated = await api<StoreProfile>(`/api/store-profiles/${profileId}/photo`, {
        method: "POST",
        body: JSON.stringify({ data_url: dataUrl }),
      });
      patchStoreProfile(updated);
      setActiveStoreProfileId(updated.id);
      setNotice("Foto da loja salva.");
      return updated;
    });
  }

  // Autosave: throws on failure so the caller retries.
  async function saveImageColorOptions(colors: ImageOptions["colors"]) {
    const updated = await api<ImageOptions>("/api/image-options", {
      method: "PUT",
      body: JSON.stringify({ colors }),
    });
    setImageOptions(updated);
  }

  function downloadAppBackup() {
    return runAction("Gerando backup completo", async () => {
      const response = await fetch(`${API_BASE}/api/backups/download`);
      if (!response.ok) throw new Error(await readApiError(response));
      const blob = await response.blob();
      const fallback = `eco-native-backup-${todayDateString()}.zip`;
      const filename = filenameFromDisposition(response.headers.get("content-disposition"), fallback);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setNotice(`Backup gerado: ${filename}`);
      return { filename };
    });
  }

  function restoreAppBackup(file: File) {
    return runAction("Restaurando backup completo", async () => {
      const response = await fetch(`${API_BASE}/api/backups/restore`, {
        method: "POST",
        headers: { "Content-Type": "application/zip" },
        body: await file.arrayBuffer(),
      });
      if (!response.ok) throw new Error(await readApiError(response));
      const summary = await response.json() as BackupRestoreSummary;
      await refresh();
      if (summary.store_profile_id) {
        setActiveStoreProfileId(summary.store_profile_id);
      } else {
        const nextProfiles = await api<StoreProfile[]>("/api/store-profiles");
        if (nextProfiles[0]) setActiveStoreProfileId(nextProfiles[0].id);
      }
      setSelectedProductId("");
      setSelectedProductIds([]);
      setDetailsOpen(false);
      const restoredParts = [
        `${summary.products} produto(s)`,
        `${summary.store_profiles} loja(s)`,
        summary.filament_spools ? `${summary.filament_spools} filamento(s)` : null,
        `${summary.files} arquivo(s)`,
        summary.env_restored ? "integrações (.env)" : null,
      ].filter(Boolean).join(", ");
      setNotice(`Backup restaurado: ${restoredParts}.`);
      return summary;
    }, { refresh: "all", blockUi: true, notifySuccess: true });
  }

  const activeJobCount = storeJobs.filter(jobActive).length;
  const closeJobsPanel = useCallback(() => setJobsPanelOpen(false), []);

  async function openProductFromJob(productId: string) {
    setJobsPanelOpen(false);
    // Loads it even when the current list or filters do not include it.
    await refreshProduct(productId);
    setActiveTab("products");
    setSelectedProductId(productId);
    setDetailsOpen(true);
  }

  // Queues a job and returns at once: the poller refreshes the product and
  // reports the result, so the rest of the app stays usable meanwhile.
  async function enqueueJob(path: string, body: Record<string, unknown>): Promise<Job> {
    const job = await api<Job>(path, { method: "POST", body: JSON.stringify(body) });
    setJobs((current) => mergeJobs(current, [job]));
    if (jobActive(job)) activeJobIdsRef.current.add(job.id);
    return job;
  }

  function noticeQueued(job: Job) {
    setNotice(`Na fila: ${jobTitle(job)}. Você pode continuar usando o app; acompanhe em Tarefas.`);
    return job;
  }

  function generateListing(productId = selectedProduct?.id) {
    if (!productId) return Promise.resolve();
    if (!settings?.integrations.openrouter) {
      setNotice("Configure OPENROUTER_API_KEY em Ajustes para gerar anúncios com IA.");
      return Promise.resolve();
    }
    return runAction("Gerando anúncio", () =>
      (async () => {
        const product = findProduct(productId);
        if (
          hasListingContent(product)
          && !(await confirmRegeneration(`"${product?.name ?? "Este produto"}" já possui descrição/anúncio gerado. Gerar novamente pode substituir o texto atual e somar novo custo de IA. Deseja continuar?`))
        ) {
          throw new Error("__cancelled__");
        }
        return noticeQueued(await enqueueJob("/api/jobs/listing", { product_id: productId }));
      })(),
    { refresh: false, blockUi: false, notifySuccess: false });
  }

  // Kie.ai downloads the source image from a link the app serves; Codex reads the file.
  function publicAppUrlMissing() {
    if (settings?.integrations.codex_image_gen || settings?.integrations.public_app_url) return false;
    setNotice("Configure o endereço público do app em Ajustes → Integrações para o Kie.ai baixar as imagens.");
    return true;
  }

  function generateImages(productId = selectedProduct?.id) {
    if (!productId) return Promise.resolve();
    if (!settings?.integrations.kie_ai) {
      setNotice("Configure KIE_API_KEY em Ajustes para gerar imagens com Kie.ai.");
      return Promise.resolve();
    }
    if (publicAppUrlMissing()) return Promise.resolve();
    return runAction("Gerando imagens base", () =>
      (async () => {
        const product = findProduct(productId);
        const name = product?.name ?? "Este produto";
        const disabled = new Set(activeStoreProfile?.disabled_image_prompts ?? []);
        const existing = new Set(
          (product?.assets ?? []).filter((asset) => asset.kind.startsWith("generated_")).map((asset) => asset.kind.slice("generated_".length)),
        );
        const missing = imageOptions.studio_prompts.filter((style) => !disabled.has(style.id) && !existing.has(style.id));
        let regenerate = false;
        if (existing.size && missing.length) {
          // Finishing an interrupted batch only pays for the styles still missing.
          if (!(await confirmRegeneration(`"${name}" ainda não tem imagem para ${missing.length} estilo(s): ${missing.map((style) => style.name).join(", ")}. Gerar só esses? Para refazer uma imagem existente, use o botão IA na miniatura.`))) {
            throw new Error("__cancelled__");
          }
        } else if (existing.size) {
          if (!(await confirmRegeneration(`"${name}" já possui imagens base geradas. Gerar novamente cria uma nova versão de cada imagem, com novo custo de IA. As imagens atuais continuam salvas em “Versões anteriores”, na aba Imagens. Deseja continuar?`))) {
            throw new Error("__cancelled__");
          }
          regenerate = true;
        }
        return noticeQueued(await enqueueJob("/api/jobs/images", {
          product_id: productId,
          color_variations: [],
          generate_base_images: true,
          regenerate,
        }));
      })(),
    { refresh: false, blockUi: false, notifySuccess: false });
  }

  function generateColorVariations(productId = selectedProduct?.id, colorVariations = selectedColorVariations) {
    if (!productId || !colorVariations.length) return Promise.resolve();
    if (!settings?.integrations.kie_ai) {
      setNotice("Configure KIE_API_KEY em Ajustes para gerar variações de cor com Kie.ai.");
      return Promise.resolve();
    }
    if (publicAppUrlMissing()) return Promise.resolve();
    return runAction("Gerando variações de cor", () =>
      (async () => {
        const product = findProduct(productId);
        const alreadyGenerated = existingColorVariations(product, colorVariations);
        if (
          alreadyGenerated.length
          && !(await confirmRegeneration(`Este produto já possui variação(ões) para: ${alreadyGenerated.join(", ")}. Gerar novamente cria uma nova versão dessas cores, com novo custo de IA. As atuais continuam salvas em “Versões anteriores”, na aba Imagens. Deseja continuar?`))
        ) {
          throw new Error("__cancelled__");
        }
        return noticeQueued(await enqueueJob("/api/jobs/images", {
          product_id: productId,
          color_variations: colorVariations,
          generate_base_images: false,
          regenerate: alreadyGenerated.length > 0,
        }));
      })(),
    { refresh: false, blockUi: false, notifySuccess: false });
  }

  function regenerateImage(productId: string, promptKey: string, extraPrompt: string) {
    if (!settings?.integrations.kie_ai) {
      setNotice("Configure KIE_API_KEY em Ajustes para recriar imagens com Kie.ai.");
      return Promise.resolve();
    }
    if (publicAppUrlMissing()) return Promise.resolve();
    return runAction("Recriando imagem", async () =>
      noticeQueued(await enqueueJob("/api/jobs/image-regenerate", {
        product_id: productId,
        prompt_key: promptKey,
        extra_prompt: extraPrompt,
      })),
    { refresh: false, blockUi: false, notifySuccess: false });
  }

  // Autosave: throws on failure so the caller retries.
  async function saveListing(draft: ListingSnapshot) {
    const product = findProduct(draft.productId);
    if (!product) return;
    const payload: { listing: Listing; status?: ProductStatus; name?: string } = {
      listing: draft.listing,
      status: draft.listing.title && draft.listing.description ? "in_edit" : product.status,
    };
    const name = draft.name.trim();
    if (name && name !== product.name) payload.name = name;
    const updated = await api<Product>(`/api/products/${draft.productId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    patchProduct(updated);
  }

  function approveProduct() {
    if (!selectedProduct || !listingDraft) return Promise.resolve();
    const payload: { listing: Listing; status: ProductStatus; name?: string } = {
      listing: listingDraft,
      status: "ready",
    };
    if (productNameDraft.trim() && productNameDraft.trim() !== selectedProduct.name) {
      payload.name = productNameDraft.trim();
    }
    return runFluidAction("Aprovando produto", async () => {
      const updated = await api<Product>(`/api/products/${selectedProduct.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      patchProduct(updated);
      setNotice("Produto aprovado.");
      return updated;
    });
  }

  function uploadCoverImage(productId: string, file: File) {
    return runAction("Atualizando capa do produto", async () => {
      const updated = await apiUpload<Product>(`/api/products/${productId}/cover-image`, file);
      patchProduct(updated);
      return updated;
    }, { refresh: false, blockUi: true, notifySuccess: true });
  }

  function uploadModelFile(productId: string, file: File) {
    return runAction("Enviando arquivo 3D", async () => {
      const updated = await apiUpload<Product>(`/api/products/${productId}/model-files`, file);
      patchProduct(updated);
      return updated;
    }, { refresh: false, blockUi: true, notifySuccess: true });
  }

  function uploadStyleImage(productId: string, promptKey: string, file: File) {
    return runAction("Enviando imagem do estilo", async () => {
      const updated = await apiUpload<Product>(`/api/products/${productId}/style-image/${promptKey}`, file);
      patchProduct(updated);
      return updated;
    }, { refresh: false, blockUi: true, notifySuccess: true });
  }

  function uploadColorImageManual(productId: string, name: string, file: File) {
    return runAction("Enviando variação de cor", async () => {
      const updated = await apiUpload<Product>(`/api/products/${productId}/color-image`, file, { name });
      patchProduct(updated);
      return updated;
    }, { refresh: false, blockUi: true, notifySuccess: true });
  }

  function createVariation(productId: string, attribute: string, value: string) {
    return runFluidAction("Criando variação", async () => {
      const updated = await api<Product>(`/api/products/${productId}/variations`, {
        method: "POST",
        body: JSON.stringify({ attribute, value }),
      });
      patchProduct(updated);
      setNotice("Variação criada.");
      return updated;
    });
  }

  function uploadVariationImage(productId: string, slug: string, file: File) {
    return runAction("Enviando foto da variação", async () => {
      const updated = await apiUpload<Product>(`/api/products/${productId}/variations/${slug}/image`, file);
      patchProduct(updated);
      return updated;
    }, { refresh: false, blockUi: true, notifySuccess: true });
  }

  function deleteVariation(productId: string, slug: string) {
    return runFluidAction("Removendo variação", async () => {
      const updated = await api<Product>(`/api/products/${productId}/variations/${slug}`, { method: "DELETE" });
      patchProduct(updated);
      setNotice("Variação removida.");
      return updated;
    });
  }

  function deleteModelAsset(productId: string, assetId: string) {
    return runFluidAction("Removendo arquivo 3D", async () => {
      const updated = await api<Product>(`/api/products/${productId}/assets/${assetId}`, { method: "DELETE" });
      patchProduct(updated);
      setNotice("Arquivo 3D removido.");
      return updated;
    });
  }

  function deleteColorAsset(productId: string, assetId: string) {
    return runFluidAction("Removendo variação de cor", async () => {
      const updated = await api<Product>(`/api/products/${productId}/assets/${assetId}`, { method: "DELETE" });
      patchProduct(updated);
      setNotice("Variação de cor removida.");
      return updated;
    });
  }

  function updateProductListed(productId: string, listed: boolean) {
    return runFluidAction(listed ? "Marcando como publicado" : "Marcando como não publicado", async () => {
      const updated = await api<Product>(`/api/products/${productId}`, {
        method: "PATCH",
        body: JSON.stringify({
          metadata: {
            listed,
            listed_at: listed ? new Date().toISOString() : null,
          },
        }),
      });
      patchProduct(updated);
      return updated;
    });
  }

  // A board column is a status, or "listed" for the user's publication mark.
  // Leaving the published column clears the mark.
  function moveProductToColumn(product: Product, column: BoardColumnKey) {
    const productId = product.id;
    const wasListed = productListed(product);
    const body = column === "listed"
      ? { metadata: { listed: true, listed_at: new Date().toISOString() } }
      : { status: column, ...(wasListed ? { metadata: { listed: false, listed_at: null } } : {}) };
    return runFluidAction("Movendo produto", async () => {
      const updated = await api<Product>(`/api/products/${productId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      patchProduct(updated);
      return updated;
    });
  }

  async function deleteProduct(productId = selectedProduct?.id) {
    if (!productId) return Promise.resolve();
    const product = findProduct(productId);
    if (!(await confirmDangerousDelete(`Apagar o produto "${product?.name ?? productId}"?`))) return Promise.resolve();
    return runFluidAction("Apagando produto", async () => {
      await api<{ status: string; product_id: string }>(`/api/products/${productId}`, {
        method: "DELETE",
      });
      removeProductFromState(productId);
      setNotice("Produto apagado.");
    });
  }

  async function createManualProduct(name: string, sourceUrl?: string) {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setNotice("Informe o nome do produto.");
      return undefined;
    }
    return runFluidAction("Criando produto", async () => {
      const created = await api<Product>("/api/products", {
        method: "POST",
        body: JSON.stringify({
          name: trimmedName,
          source_url: sourceUrl?.trim() || null,
        }),
      });
      patchProduct(created, true);
      setSelectedProductId(created.id);
      setDetailsOpen(true);
      setNotice(`Produto "${created.name}" criado.`);
      return created;
    });
  }

  async function downloadProductFiles(productId = selectedProduct?.id) {
    if (!productId) return;
    setBusy(true);
    setNotice("Preparando arquivos do produto...");
    try {
      const response = await fetch(`${API_BASE}/api/products/${productId}/download-files`, { credentials: "same-origin" });
      if (!response.ok) throw new Error(await readApiError(response));
      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
      const filename = encodedName ? decodeURIComponent(encodedName) : plainName || "arquivos-do-produto.zip";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setNotice("Download dos arquivos iniciado.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Não foi possível baixar os arquivos");
    } finally {
      setBusy(false);
    }
  }

  async function runBatchProductAction(
    label: string,
    productIds: string[],
    action: (productId: string) => Promise<Job>,
    kind?: "listing" | "images",
  ) {
    if (!productIds.length) {
      setNotice("Selecione pelo menos um produto.");
      return;
    }
    if (kind === "listing") {
      const withExisting = productIds
        .map((id) => findProduct(id))
        .filter((product): product is Product => Boolean(product && hasListingContent(product)));
      if (
        withExisting.length
        && !(await confirmRegeneration(`${withExisting.length} produto(s) selecionado(s) já possuem descrição/anúncio. Gerar em lote pode substituir textos existentes e somar novos custos de IA. Deseja continuar?`))
      ) {
        return;
      }
    }
    if (kind === "images") {
      const withExisting = productIds
        .map((id) => findProduct(id))
        .filter((product): product is Product => Boolean(product && hasBaseImages(product)));
      if (
        withExisting.length
        && !(await confirmRegeneration(`${withExisting.length} produto(s) selecionado(s) já possuem imagens base. O sistema reutiliza arquivos existentes quando possível; para recriar imagens específicas, use o botão IA nas miniaturas. Deseja continuar?`))
      ) {
        return;
      }
    }
    // Only queues the jobs (a few quick requests); the Tasks panel follows them.
    const total = productIds.length;
    let queued = 0;
    const errors: string[] = [];
    try {
      for (const [index, productId] of productIds.entries()) {
        const current = findProduct(productId)?.name ?? productId;
        setBatchProgress({ label: `${label}: colocando na fila`, total, done: index, current });
        try {
          await action(productId);
          queued += 1;
        } catch (error) {
          errors.push(`${current}: ${error instanceof Error ? error.message : "erro inesperado"}`);
        }
      }
      if (errors.length) {
        const extra = errors.length > 1 ? ` (+${errors.length - 1} outro(s))` : "";
        setNotice(`${queued} de ${total} tarefa(s) na fila. Não entraram: ${errors[0]}${extra}`);
      } else {
        setNotice(`${label}: ${total} tarefa(s) na fila. Você pode continuar usando o app; acompanhe em Tarefas.`);
      }
    } finally {
      setBatchProgress(null);
    }
  }

  function generateListingsBatch(productIds = selectedProductIds) {
    if (!settings?.integrations.openrouter) {
      setNotice("Configure OPENROUTER_API_KEY em Ajustes para gerar anúncios com IA.");
      return Promise.resolve();
    }
    return runBatchProductAction(
      "Gerando anúncios em lote",
      productIds,
      (productId) => enqueueJob("/api/jobs/listing", { product_id: productId }),
      "listing",
    );
  }

  function generateImagesBatch(productIds = selectedProductIds) {
    if (!settings?.integrations.kie_ai) {
      setNotice("Configure KIE_API_KEY em Ajustes para gerar imagens com Kie.ai.");
      return Promise.resolve();
    }
    if (publicAppUrlMissing()) return Promise.resolve();
    return runBatchProductAction(
      "Gerando imagens base em lote",
      productIds,
      (productId) =>
        enqueueJob("/api/jobs/images", { product_id: productId, color_variations: [], generate_base_images: true }),
      "images",
    );
  }

  async function deleteProductsBatch(productIds = selectedProductIds) {
    if (!productIds.length) {
      setNotice("Selecione pelo menos um produto para apagar.");
      return;
    }
    if (!(await confirmDangerousDelete(`Apagar ${productIds.length} produto(s) selecionado(s)?`))) return;
    try {
      setBusy(true);
      setNotice(`Apagando ${productIds.length} produto(s)...`);
      // One request for the whole batch; the screen updates once.
      await api<{ status: string; product_ids: string[] }>("/api/products/delete-batch", {
        method: "POST",
        body: JSON.stringify({ product_ids: productIds }),
      });
      productIds.forEach(removeProductFromState);
      setSelectedProductIds([]);
      setNotice(`${productIds.length} produto(s) apagado(s).`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Erro ao apagar produtos");
    } finally {
      setBusy(false);
    }
  }

  async function setListedBatch(productIds: string[], listed: boolean) {
    if (!productIds.length) {
      setNotice("Selecione pelo menos um produto.");
      return;
    }
    const pendingIds = productIds.filter((id) => productListed(findProduct(id)) !== listed);
    if (!pendingIds.length) {
      setNotice(listed ? "Os selecionados já estão publicados." : "Os selecionados já estão como não publicados.");
      return;
    }
    const label = listed ? "publicado(s)" : "não publicado(s)";
    try {
      setBusy(true);
      setNotice(`Marcando ${pendingIds.length} produto(s) como ${label}...`);
      const listedAt = listed ? new Date().toISOString() : null;
      for (const productId of pendingIds) {
        const updated = await api<Product>(`/api/products/${productId}`, {
          method: "PATCH",
          body: JSON.stringify({ metadata: { listed, listed_at: listedAt } }),
        });
        patchProduct(updated);
      }
      setNotice(`${pendingIds.length} produto(s) marcado(s) como ${label}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Erro ao atualizar a publicação");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!activeStoreProfile?.id) return;
    api<ShopeeTemplateStatus>("/api/exports/shopee-template")
      .then(setShopeeTemplate)
      .catch(() => setShopeeTemplate(null));
  }, [activeStoreProfile?.id]);

  function readyExportIds(productIds: string[]): string[] | null {
    if (!productIds.length) {
      setNotice("Selecione pelo menos um produto pronto para exportar.");
      return null;
    }
    const readySelectedIds = productIds.filter((id) => {
      const product = findProduct(id);
      return Boolean(product?.listing.title && product?.listing.description);
    });
    if (!readySelectedIds.length) {
      setNotice("Selecione produtos com anúncio gerado antes de exportar.");
      return null;
    }
    return readySelectedIds;
  }

  // Posts the export, downloads the returned file and refreshes the exported
  // products, whose status changes to "exportado".
  async function downloadExport(path: string, productIds: string[], fallbackName: string) {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        marketplace: activeStoreProfile?.marketplace ?? "shopee",
        product_ids: productIds,
      }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    const blob = await response.blob();
    const filename = filenameFromDisposition(response.headers.get("content-disposition"), fallbackName);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    const result = {
      filename,
      count: Number(response.headers.get("X-Eco-Export-Count")) || productIds.length,
      marketplace: response.headers.get("X-Eco-Export-Marketplace") || activeStoreProfile?.marketplace || "shopee",
    };
    void Promise.all(productIds.map(refreshProduct));
    return result;
  }

  async function uploadShopeeTemplate(file: File) {
    const status = await apiUpload<ShopeeTemplateStatus>("/api/exports/shopee-template", file);
    setShopeeTemplate(status);
    return status;
  }

  function replaceShopeeTemplate() {
    const picked = pickFile(".xlsx");
    return runAction("Salvando template da Shopee", async () => {
      const file = await picked;
      if (!file) throw new Error("__cancelled__");
      return uploadShopeeTemplate(file);
    }, { refresh: false, blockUi: true, notifySuccess: true });
  }

  // Fills the store's own Shopee mass-upload template. Without one yet, the
  // file picker opens right away and the export continues after the upload.
  function exportShopeeSheet(productIds = selectedProductIds) {
    if (!listedProducts.length) return Promise.resolve();
    const readySelectedIds = readyExportIds(productIds);
    if (!readySelectedIds) return Promise.resolve();
    const picked = shopeeTemplate?.configured ? null : pickFile(".xlsx");
    if (picked) setNotice("Escolha o template de envio em massa baixado da Shopee (.xlsx).");
    return runAction("Gerando planilha da Shopee", async () => {
      if (picked) {
        const file = await picked;
        if (!file) throw new Error("__cancelled__");
        await uploadShopeeTemplate(file);
      }
      return downloadExport("/api/exports/shopee-xlsx", readySelectedIds, `shopee-envio-em-massa-${todayDateString()}.xlsx`);
    }, { refresh: false, blockUi: true, notifySuccess: true });
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <StorePicker
          activeStore={activeStoreProfile}
          stores={storeProfiles}
          onChange={selectStoreProfile}
        />
        <nav className="app-tabs">
          <TabButton active={activeTab === "dashboard"} icon={<BarChart3 size={18} />} onClick={() => setActiveTab("dashboard")}>
            Dashboard
          </TabButton>
          <TabButton active={activeTab === "collect"} icon={<PackageSearch size={18} />} onClick={() => setActiveTab("collect")}>
            Coleta
          </TabButton>
          <TabButton active={activeTab === "products"} icon={<ShoppingBag size={18} />} onClick={() => setActiveTab("products")}>
            Produtos
          </TabButton>
          <TabButton active={activeTab === "costs"} icon={<Coins size={18} />} onClick={() => setActiveTab("costs")}>
            Custos
          </TabButton>
        </nav>
        <nav className="sidebar-footer" aria-label="Ajustes">
          <button className={`tab-button jobs-button${jobsPanelOpen ? " active" : ""}`} onClick={() => setJobsPanelOpen(true)}>
            <ListChecks size={18} /> Tarefas
            {activeJobCount > 0 && (
              <span className="jobs-badge" aria-label={`${activeJobCount} em andamento`}>
                <Loader2 size={12} className="spin" /> {activeJobCount}
              </span>
            )}
          </button>
          <TabButton active={activeTab === "settings"} icon={<Settings size={18} />} onClick={() => setActiveTab("settings")}>
            Ajustes
          </TabButton>
          <button className="tab-button logout-button" onClick={() => void onLogout()}>
            <LogOut size={18} /> Sair ({auth.username})
          </button>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{tabInfo[activeTab].eyebrow}</p>
            <h1>{tabInfo[activeTab].title}</h1>
          </div>
        </header>

        {activeTab === "dashboard" && (
          <DashboardTab
            stats={catalogStats}
            runtimeStatus={runtimeStatus}
            onOpenProducts={(filters) => {
              setProductFilters({ query: "", ...filters });
              setActiveTab("products");
            }}
            onOpenCollect={() => setActiveTab("collect")}
          />
        )}

        {activeTab === "collect" && (
          <CollectTab
            activeStoreProfile={activeStoreProfile}
            busy={busy || collectRunning}
            jobs={storeJobs}
            keyword={keyword}
            limit={collectLimit}
            loginStatus={makerWorldLogin}
            manualUrl={manualUrl}
            productCount={catalogStats?.total ?? 0}
            scrolls={collectScrolls}
            onCollect={collectProducts}
            onExtractSelectedLinks={extractSelectedLinks}
            onCloseLogin={closeMakerWorldLogin}
            onKeywordChange={setKeyword}
            onLimitChange={setCollectLimit}
            onOpenLogin={openMakerWorldLogin}
            onManualUrlChange={setManualUrl}
            onScrollsChange={setCollectScrolls}
            blockedSourceUrls={blockedSourceUrls}
            onRemoveBlockedUrl={removeBlockedUrl}
          />
        )}

        {activeTab === "products" && (
          <ProductsTab
            batchProgress={batchProgress}
            busy={busy}
            imageOptions={imageOptions}
            jobs={storeJobs}
            listingDraft={listingDraft}
            listingDraftOwner={listingDraftOwner}
            productNameDraft={productNameDraft}
            filters={productFilters}
            boardFilters={listFilters}
            catalogRevision={catalogRevision}
            freshProducts={productDetails}
            onMoveProduct={moveProductToColumn}
            products={listedProducts}
            matchedProductCount={productList.total}
            listedCount={productList.listedTotal}
            notListedCount={productList.notListedTotal}
            hasMoreProducts={Boolean(productList.nextCursor)}
            productsLoading={productList.loading}
            productsLoaded={productList.loaded}
            onLoadMoreProducts={() => void loadMoreProducts()}
            selectedProduct={selectedProduct}
            selectedProductIds={selectedProductIds}
            selectedColorVariations={selectedColorVariations}
            onCreateManualProduct={createManualProduct}
            onApproveProduct={approveProduct}
            onBatchGenerateImages={generateImagesBatch}
            onBatchGenerateListings={generateListingsBatch}
            onBatchDeleteProducts={deleteProductsBatch}
            onBatchSetListed={setListedBatch}
            onDeleteProduct={deleteProduct}
            onFiltersChange={setProductFilters}
            onGenerateColorVariations={generateColorVariations}
            onGenerateImages={generateImages}
            onGenerateListing={generateListing}
            onRegenerateImage={regenerateImage}
            onExportShopeeSheet={exportShopeeSheet}
            onReplaceShopeeTemplate={replaceShopeeTemplate}
            shopeeTemplate={shopeeTemplate}
            onDownloadProductFiles={downloadProductFiles}
            onDeleteModelAsset={deleteModelAsset}
            onListingDraftChange={setListingDraft}
            onProductNameDraftChange={setProductNameDraft}
            onSaveListing={saveListing}
            onUploadCoverImage={uploadCoverImage}
            onUploadModelFile={uploadModelFile}
            onUploadStyleImage={uploadStyleImage}
            onUploadColorImageManual={uploadColorImageManual}
            onCreateVariation={createVariation}
            onUploadVariationImage={uploadVariationImage}
            onDeleteVariation={deleteVariation}
            onDeleteColorAsset={deleteColorAsset}
            onUpdateProductListed={updateProductListed}
            filaments={filaments}
            productionSettings={productionSettings}
            activeStoreProfile={activeStoreProfile}
            onSelectedProductIdsChange={setSelectedProductIds}
            onSelectedColorVariationsChange={setSelectedColorVariations}
            detailsOpen={detailsOpen}
            onCloseDetails={() => setDetailsOpen(false)}
            onOpenDetails={(id) => {
              setSelectedProductId(id);
              setDetailsOpen(true);
            }}
            onSelectProduct={setSelectedProductId}
          />
        )}

        {activeTab === "costs" && (
          <CostsTab
            activeStoreProfile={activeStoreProfile}
            busy={busy}
            filaments={filaments}
            productionSettings={productionSettings}
            products={costProducts ?? []}
            productsLoading={costProducts === null}
            runtimeStatus={runtimeStatus}
            onSaveAllProductionCosts={saveProductionCostsBatch}
            onProductionCostsSaved={syncProductionCostsInProducts}
          />
        )}

        {activeTab === "settings" && (
          <SettingsTab
            isAdmin={Boolean(auth.is_admin)}
            uiTheme={normalizeUiThemePreference(storeTheme)}
            onSaveUiTheme={saveStoreTheme}
            storeProfileDraft={storeProfileDraft}
            storeProfiles={storeProfiles}
            imageOptions={imageOptions}
            openRouterApiKeyDraft={openRouterApiKeyDraft}
            openRouterModelDraft={openRouterModelDraft}
            kieApiKeyDraft={kieApiKeyDraft}
            kieImageModelDraft={kieImageModelDraft}
            useCodexImageGenDraft={useCodexImageGenDraft}
            codexBinDraft={codexBinDraft}
            publicAppUrlDraft={publicAppUrlDraft}
            settings={settings}
            onOpenRouterApiKeyChange={setOpenRouterApiKeyDraft}
            onOpenRouterModelChange={setOpenRouterModelDraft}
            onKieApiKeyChange={setKieApiKeyDraft}
            onKieImageModelChange={setKieImageModelDraft}
            onUseCodexImageGenChange={setUseCodexImageGenDraft}
            onCodexBinChange={setCodexBinDraft}
            onPublicAppUrlChange={setPublicAppUrlDraft}
            onSaveOpenRouterSettings={saveOpenRouterSettings}
            onClearIntegrationSecrets={clearIntegrationSecretDrafts}
            onStoreProfileDraftChange={setStoreProfileDraft}
            onCreateStoreProfile={createStoreProfile}
            onDownloadAppBackup={downloadAppBackup}
            onSaveStoreProfile={saveStoreProfile}
            onSaveImageColorOptions={saveImageColorOptions}
            onSelectedStoreProfileChange={selectStoreProfile}
            onRestoreAppBackup={restoreAppBackup}
            onUploadStoreProfilePhoto={uploadStoreProfilePhoto}
            filaments={filaments}
            productionSettings={productionSettings}
            onDeleteFilament={deleteFilament}
            onSaveFilament={saveFilament}
            onSaveProductionSettings={saveProductionSettings}
            onWrapAction={runAction}
          />
        )}
      </section>
      {onboardingOpen && (
        <OnboardingModal
          busy={busy}
          storeProfile={activeStoreProfile}
          openRouterModel={openRouterModelDraft}
          kieImageModel={kieImageModelDraft}
          imageModels={settings?.integrations.image_models ?? []}
          onFinish={finishOnboarding}
          onSkip={skipOnboarding}
        />
      )}
      {(collectAttention || notice) && (
        <div className={busy ? "toast-notice busy-toast" : "toast-notice"} role="status" aria-live="polite">
          {busy && <Loader2 className="spin" size={16} />}
          <span>{displayText(collectAttention || notice)}</span>
          {collectRunning && !makerWorldViewerOpen && (
            <button className="toast-action" onClick={() => setMakerWorldViewerOpen(true)}>
              {collectAttention ? "Validar no MakerWorld" : "Ver navegador da coleta"}
            </button>
          )}
          {!busy && !collectAttention && (
            <button aria-label="Fechar aviso" onClick={() => setNotice("")}>
              ×
            </button>
          )}
        </div>
      )}
      {confirmDialog && (
        <ConfirmModal dialog={confirmDialog} onClose={closeConfirmDialog} />
      )}
      {jobsPanelOpen && (
        <JobsPanel
          jobs={storeJobs}
          collectViewerAvailable={collectRunning}
          onClose={closeJobsPanel}
          onOpenProduct={(productId) => void openProductFromJob(productId)}
          onStopCollect={(jobId) => void stopCollect(jobId)}
          onOpenCollectViewer={() => {
            setJobsPanelOpen(false);
            setMakerWorldViewerOpen(true);
          }}
        />
      )}
      {makerWorldViewerOpen && (
        <MakerWorldRemoteBrowser
          status={makerWorldLogin}
          collect={collectRunning}
          onStopCollect={collectJobId ? () => void stopCollect(collectJobId) : undefined}
          onCloseViewer={() => setMakerWorldViewerOpen(false)}
          onFinish={() => void closeMakerWorldLogin()}
        />
      )}
    </main>
  );
}

type DragPoint = [number, number, number];

function MakerWorldRemoteBrowser({
  status,
  collect,
  onStopCollect,
  onCloseViewer,
  onFinish,
}: {
  status: MakerWorldLoginStatus | null;
  collect: boolean;
  onStopCollect?: () => void;
  onCloseViewer: () => void;
  onFinish: () => void;
}) {
  const [frameNonce, setFrameNonce] = useState(0);
  const [frameReady, setFrameReady] = useState(false);
  const [liveStatus, setLiveStatus] = useState(status);
  const [inputError, setInputError] = useState("");
  const frameRef = useRef<HTMLImageElement>(null);
  const liveStatusRef = useRef(status);
  const sendChain = useRef<Promise<void>>(Promise.resolve());
  const pendingPath = useRef<DragPoint[]>([]);
  const pendingWheel = useRef<{ x: number; y: number } | null>(null);
  const drag = useRef<{ start: { x: number; y: number }; button: string; moved: boolean; lastTime: number } | null>(null);
  const viewportWidth = liveStatus?.width || 1280;
  const viewportHeight = liveStatus?.height || 720;
  const collectMode = collect || liveStatus?.mode === "collect";

  useEffect(() => {
    let cancelled = false;
    let timer: number;
    async function refresh() {
      try {
        const next = await api<MakerWorldLoginStatus>("/api/jobs/makerworld-login");
        if (!cancelled) {
          liveStatusRef.current = next;
          setLiveStatus(next);
          setFrameNonce((value) => value + 1);
        }
      } catch (error) {
        if (!cancelled) setInputError(String(error));
      } finally {
        if (!cancelled) timer = window.setTimeout(refresh, 550);
      }
    }
    void refresh();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, []);

  // One request at a time: parallel requests can reach the server out of order,
  // scrambling typed text and drag paths. A function payload is built when its turn comes.
  function sendInput(payload: Record<string, unknown> | (() => Record<string, unknown> | null)) {
    sendChain.current = sendChain.current.then(async () => {
      const body = typeof payload === "function" ? payload() : payload;
      if (!body) return;
      try {
        await api<void>("/api/jobs/makerworld-login/input", {
          method: "POST",
          body: JSON.stringify({ page_id: liveStatusRef.current?.active_page_id, ...body }),
        });
        setInputError("");
      } catch (error) {
        setInputError(String(error));
      }
    });
  }

  function sendPendingPath() {
    sendInput(() => {
      const path = pendingPath.current.splice(0, 120);
      if (pendingPath.current.length) sendPendingPath();
      return path.length ? { type: "move", path } : null;
    });
  }

  function sendWheel(deltaX: number, deltaY: number) {
    if (pendingWheel.current) {
      pendingWheel.current.x += deltaX;
      pendingWheel.current.y += deltaY;
      return;
    }
    pendingWheel.current = { x: deltaX, y: deltaY };
    sendInput(() => {
      const wheel = pendingWheel.current;
      pendingWheel.current = null;
      if (!wheel) return null;
      const limit = (value: number) => Math.max(-5000, Math.min(5000, value));
      return { type: "wheel", delta_x: limit(wheel.x), delta_y: limit(wheel.y) };
    });
  }

  function point(event: React.MouseEvent<HTMLDivElement>) {
    // Measure the drawn frame itself so layout changes cannot shift clicks away from what the user sees.
    const rect = (frameRef.current ?? event.currentTarget).getBoundingClientRect();
    const scale = Math.min(rect.width / viewportWidth, rect.height / viewportHeight);
    const renderedWidth = viewportWidth * scale;
    const renderedHeight = viewportHeight * scale;
    const offsetX = (rect.width - renderedWidth) / 2;
    const offsetY = (rect.height - renderedHeight) / 2;
    return {
      x: Math.max(0, Math.min(viewportWidth, (event.clientX - rect.left - offsetX) / scale)),
      y: Math.max(0, Math.min(viewportHeight, (event.clientY - rect.top - offsetY) / scale)),
    };
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button > 2) return;
    event.currentTarget.focus();
    event.currentTarget.setPointerCapture(event.pointerId);
    const button = event.button === 2 ? "right" : event.button === 1 ? "middle" : "left";
    drag.current = { start: point(event), button, moved: false, lastTime: event.timeStamp };
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const current = drag.current;
    if (!current) return;
    const next = point(event);
    if (!current.moved) {
      // Small jitter still counts as a click; beyond it the gesture is a drag (slider puzzles).
      if (Math.hypot(next.x - current.start.x, next.y - current.start.y) < 4) return;
      current.moved = true;
      sendInput({ type: "down", button: current.button, ...current.start });
    }
    const delay = Math.max(0, Math.min(1000, Math.round(event.timeStamp - current.lastTime)));
    current.lastTime = event.timeStamp;
    if (pendingPath.current.push([next.x, next.y, delay]) === 1) sendPendingPath();
  }

  function handlePointerUp(event: React.PointerEvent<HTMLDivElement>) {
    const current = drag.current;
    drag.current = null;
    if (!current) return;
    sendInput({ type: current.moved ? "up" : "click", button: current.button, ...point(event) });
  }

  function handleKey(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.ctrlKey || event.metaKey || event.altKey) {
      const modifiers = [event.ctrlKey ? "Control" : "", event.altKey ? "Alt" : "", event.metaKey ? "Meta" : ""].filter(Boolean);
      sendInput({ type: "key", key: [...modifiers, event.key].join("+") });
    } else if (event.key.length === 1) {
      sendInput({ type: "text", text: event.key });
    } else if (["Backspace", "Delete", "Enter", "Tab", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"].includes(event.key)) {
      sendInput({ type: "key", key: event.key });
    } else {
      return;
    }
    event.preventDefault();
  }

  return (
    <div className="remote-browser-backdrop" role="presentation">
      <section className="remote-browser-dialog" role="dialog" aria-modal="true" aria-label="Navegador MakerWorld remoto">
        <header className="remote-browser-toolbar">
          <div>
            <strong>{collectMode ? "MakerWorld · navegador da coleta" : "MakerWorld · navegador local"}</strong>
            <span>
              {liveStatus?.loading && <Loader2 className="spin" size={12} aria-label="Carregando página" />}
              {liveStatus?.url || liveStatus?.message || "Iniciando Chromium no PC..."}
            </span>
            {!!liveStatus?.pages?.length && (
              <label>Janela: <select
                aria-label="Janela do navegador"
                value={liveStatus.active_page_id || ""}
                onChange={(event) => sendInput({ type: "select_page", page_id: event.target.value })}
              >
                {liveStatus.pages.map((page, index) => (
                  <option key={page.id} value={page.id}>{index + 1} · {page.url || "Abrindo..."}</option>
                ))}
              </select></label>
            )}
          </div>
          <div className="remote-browser-actions">
            {/* The collect job drives its own navigation; only the login browser gets these controls. */}
            {!collectMode && (
              <>
                <button className="primary ghost" title="Voltar" aria-label="Voltar" onClick={() => sendInput({ type: "navigate", action: "back" })}>
                  <ArrowLeft size={16} />
                </button>
                <button className="primary ghost" title="Recarregar" aria-label="Recarregar" onClick={() => sendInput({ type: "navigate", action: "reload" })}>
                  <RefreshCw size={16} />
                </button>
                <button className="primary ghost" title="Página inicial do MakerWorld" aria-label="Página inicial do MakerWorld" onClick={() => sendInput({ type: "navigate", action: "home" })}>
                  <House size={16} />
                </button>
                <button className="primary ghost" title="Abre a página de login da Bambu Lab, que volta ao MakerWorld após entrar" onClick={() => sendInput({ type: "navigate", action: "login" })}>
                  <LogIn size={16} /> Tela de login
                </button>
              </>
            )}
            {collectMode && onStopCollect && (
              <button className="primary ghost" title="Encerra a coleta; os produtos já coletados ficam salvos" onClick={onStopCollect}>
                <CircleStop size={16} /> Parar coleta
              </button>
            )}
            <button className="primary ghost" onClick={onCloseViewer}>Ocultar</button>
            {!collectMode && <button className="primary" onClick={onFinish}>Concluir e salvar sessão</button>}
          </div>
        </header>
        <div
          className="remote-browser-viewport"
          tabIndex={0}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={() => { drag.current = null; }}
          onContextMenu={(event) => event.preventDefault()}
          onWheel={(event) => sendWheel(event.deltaX, event.deltaY)}
          onKeyDown={handleKey}
          onPaste={(event) => {
            event.preventDefault();
            sendInput({ type: "text", text: event.clipboardData.getData("text") });
          }}
        >
          {!frameReady && (
            <div className="remote-browser-loading">
              <Loader2 className="spin" size={28} /> {collectMode ? "Aguardando o navegador da coleta..." : "Aguardando imagem do navegador..."}
            </div>
          )}
          <img
            ref={frameRef}
            src={`${API_BASE}/api/jobs/makerworld-login/frame?t=${frameNonce}`}
            alt="Tela interativa do MakerWorld"
            draggable={false}
            onLoad={() => setFrameReady(true)}
          />
        </div>
        <footer className={liveStatus?.challenge || liveStatus?.attention ? "remote-browser-help attention" : "remote-browser-help"}>
          {inputError || liveStatus?.message} · Novas janelas aparecem automaticamente. Use “Janela” para alternar entre elas.
        </footer>
      </section>
    </div>
  );
}

function formatElapsed(fromIso?: string, toIso?: string): string {
  if (!fromIso) return "";
  const start = Date.parse(fromIso);
  const end = toIso ? Date.parse(toIso) : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return "";
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}min`;
  return `${Math.floor(hours / 24)} dia(s)`;
}

const JOB_STATUS_LABELS: Record<Job["status"], string> = {
  queued: "Na fila",
  running: "Rodando",
  completed: "Concluída",
  failed: "Falhou",
  cancelled: "Interrompida",
};

type JobsFilter = "all" | "active" | "failed";

function JobsPanel({
  jobs,
  collectViewerAvailable,
  onClose,
  onOpenProduct,
  onStopCollect,
  onOpenCollectViewer,
}: {
  jobs: Job[];
  collectViewerAvailable: boolean;
  onClose: () => void;
  onOpenProduct: (productId: string) => void;
  onStopCollect: (jobId: string) => void;
  onOpenCollectViewer: () => void;
}) {
  const [filter, setFilter] = useState<JobsFilter>("all");
  const [, setTick] = useState(0);
  // Keeps the elapsed times moving between polls.
  useEffect(() => {
    const timer = window.setInterval(() => setTick((tick) => tick + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const active = jobs.filter(jobActive);
  const failed = jobs.filter((job) => job.status === "failed");
  // Running first, then waiting in submission order, then the rest newest first.
  const ordered = [
    ...active.filter((job) => job.status === "running"),
    ...active.filter((job) => job.status === "queued").reverse(),
    ...jobs.filter((job) => !jobActive(job)),
  ];
  const visible = ordered
    .filter((job) => filter === "all" || (filter === "active" ? jobActive(job) : job.status === "failed"))
    .slice(0, 80);

  return (
    <div className="jobs-backdrop" role="presentation" onClick={onClose}>
      <aside className="jobs-panel" role="dialog" aria-modal="true" aria-labelledby="jobs-title" onClick={(event) => event.stopPropagation()}>
        <header className="jobs-panel-header">
          <div>
            <p className="eyebrow">Fila de trabalho</p>
            <h2 id="jobs-title">Tarefas</h2>
          </div>
          <button className="icon-button" aria-label="Fechar tarefas" onClick={onClose}>
            <X size={18} />
          </button>
        </header>
        <p className="jobs-panel-note">
          As tarefas continuam no servidor mesmo se você fechar esta página. Coletas, imagens e textos rodam em paralelo.
        </p>
        <div className="jobs-filter" role="tablist" aria-label="Filtrar tarefas">
          {([
            ["all", `Todas (${jobs.length})`],
            ["active", `Em andamento (${active.length})`],
            ["failed", `Falhas (${failed.length})`],
          ] as Array<[JobsFilter, string]>).map(([key, label]) => (
            <button key={key} role="tab" aria-selected={filter === key} className={filter === key ? "active" : ""} onClick={() => setFilter(key)}>
              {label}
            </button>
          ))}
        </div>
        <ul className="jobs-list">
          {visible.length === 0 && (
            <li className="jobs-empty">
              {filter === "active" ? "Nada rodando agora." : filter === "failed" ? "Nenhuma falha." : "Nenhuma tarefa ainda."}
            </li>
          )}
          {visible.map((job) => {
            const running = job.status === "running";
            const lastLog = job.logs?.length ? job.logs[job.logs.length - 1] : "";
            const elapsed = jobActive(job)
              ? formatElapsed(job.created_at)
              : formatElapsed(job.created_at, job.updated_at);
            return (
              <li key={job.id} className={`jobs-item ${job.status}`}>
                <span className="jobs-item-icon" aria-hidden="true">
                  {job.status === "running" && <Loader2 size={16} className="spin" />}
                  {job.status === "queued" && <Clock size={16} />}
                  {job.status === "completed" && <Check size={16} />}
                  {job.status === "failed" && <AlertCircle size={16} />}
                  {job.status === "cancelled" && <Ban size={16} />}
                </span>
                <div className="jobs-item-body">
                  <div className="jobs-item-title">
                    <strong>{JOB_TYPE_LABELS[job.type] ?? job.type}</strong>
                    <span className={`jobs-status ${job.status}`}>
                      {JOB_STATUS_LABELS[job.status]}{running && job.progress ? ` · ${job.progress}%` : ""}
                    </span>
                  </div>
                  {jobSubject(job) && <span className="jobs-item-subject">{jobSubject(job)}</span>}
                  <span className="jobs-item-message" title={job.status === "failed" ? lastLog : undefined}>
                    {displayText(job.message)}
                  </span>
                  {running && (
                    <div className="jobs-progress" aria-hidden="true">
                      <span style={{ width: `${Math.max(4, Math.min(100, job.progress || 0))}%` }} />
                    </div>
                  )}
                  <div className="jobs-item-footer">
                    <small>{jobActive(job) ? `há ${elapsed}` : `levou ${elapsed}`}</small>
                    {job.product_id && (
                      <button className="link-button" onClick={() => onOpenProduct(job.product_id!)}>
                        Abrir produto
                      </button>
                    )}
                    {job.type === "collect_products" && running && collectViewerAvailable && (
                      <button className="link-button" onClick={onOpenCollectViewer}>
                        Ver navegador
                      </button>
                    )}
                    {job.type === "collect_products" && jobActive(job) && (
                      <button className="link-button" title="Os produtos já coletados ficam salvos" onClick={() => onStopCollect(job.id)}>
                        {running ? "Parar coleta" : "Cancelar"}
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </aside>
    </div>
  );
}

function ConfirmModal({
  dialog,
  onClose,
}: {
  dialog: NonNullable<ConfirmDialog>;
  onClose: (confirmed: boolean) => void;
}) {
  return (
    <div className="confirm-backdrop" role="presentation" onClick={() => onClose(false)}>
      <div className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onClick={(event) => event.stopPropagation()}>
        <div>
          <p className="eyebrow">{dialog.danger ? "Ação sensível" : "Confirmação"}</p>
          <h2 id="confirm-title">{dialog.title}</h2>
        </div>
        <p>{dialog.message}</p>
        <div className="confirm-actions">
          <button className="primary ghost" onClick={() => onClose(false)}>
            {dialog.cancelLabel}
          </button>
          <button className={dialog.danger ? "danger-button confirm-danger" : "primary"} onClick={() => onClose(true)}>
            {dialog.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// Only models the backend knows how to call can be chosen: each one needs its own request format.
function ImageModelSelect({
  value,
  models,
  onChange,
}: {
  value: string;
  models: ImageModelOption[];
  onChange: (value: string) => void;
}) {
  const selected = models.find((model) => model.id === value);
  return (
    <>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {!selected && value && <option value={value}>{models.length ? `${value} (não suportado)` : value}</option>}
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.label} · ~US$ {model.cost_usd.toLocaleString("pt-BR", { minimumFractionDigits: 2 })} por imagem
          </option>
        ))}
      </select>
      {selected && <small>{selected.description}</small>}
    </>
  );
}

function OnboardingModal({
  busy,
  kieImageModel,
  imageModels,
  openRouterModel,
  storeProfile,
  onFinish,
  onSkip,
}: {
  busy: boolean;
  kieImageModel: string;
  imageModels: ImageModelOption[];
  openRouterModel: string;
  storeProfile?: StoreProfile;
  onFinish: (payload: OnboardingPayload) => Promise<unknown>;
  onSkip: () => void;
}) {
  const [storeName, setStoreName] = useState(storeProfile?.name ?? "Luma Store");
  const [marketplace, setMarketplace] = useState<Marketplace>(storeProfile?.marketplace ?? "shopee");
  const [niche, setNiche] = useState(storeProfile?.niche ?? "Utilidades para casa e organização");
  const [openRouterKey, setOpenRouterKey] = useState("");
  const [openRouterModelValue, setOpenRouterModelValue] = useState(openRouterModel || "qwen/qwen3.5-flash-02-23");
  const [kieKey, setKieKey] = useState("");
  const [kieImageModelValue, setKieImageModelValue] = useState(kieImageModel || "qwen/image-edit");
  const [publicAppUrl, setPublicAppUrl] = useState(window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" ? "" : window.location.origin);

  useEffect(() => {
    if (!storeProfile) return;
    setStoreName(storeProfile.name);
    setMarketplace(storeProfile.marketplace);
    setNiche(storeProfile.niche);
  }, [storeProfile?.id]);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFinish({
      store_name: storeName,
      marketplace,
      niche,
      openrouter_api_key: openRouterKey,
      openrouter_model: openRouterModelValue,
      kie_api_key: kieKey,
      kie_image_model: kieImageModelValue,
      public_app_url: publicAppUrl,
    });
  }

  return (
    <div className="onboarding-backdrop" role="presentation">
      <form className="onboarding-dialog" role="dialog" aria-modal="true" aria-labelledby="onboarding-title" onSubmit={submit}>
        <div className="onboarding-hero">
          <span className="brand-mark">
            <img src="./eco-logo.png" alt="" />
          </span>
          <div>
            <p className="eyebrow">Primeira configuração</p>
            <h2 id="onboarding-title">Bem-vindo ao ECO Native Studio</h2>
            <p>Configure a loja e as integrações principais para começar com o fluxo de coleta, produtos e IA pronto para uso.</p>
          </div>
        </div>

        <div className="onboarding-grid">
          <section className="onboarding-section">
            <div className="panel-title compact">
              <ShoppingBag size={18} />
              <h3>Loja</h3>
            </div>
            <label>
              Nome da loja
              <input value={storeName} onChange={(event) => setStoreName(event.target.value)} required />
            </label>
            <label>
              Marketplace principal
              <select value={marketplace} onChange={(event) => setMarketplace(event.target.value as Marketplace)}>
                <option value="shopee">Shopee</option>
                <option value="tiktok_shop">TikTok Shop</option>
                <option value="kwai_shop">Kwai Shop</option>
                <option value="mercado_livre">Mercado Livre</option>
              </select>
            </label>
            <label>
              Nicho ou foco da loja
              <input value={niche} onChange={(event) => setNiche(event.target.value)} />
            </label>
          </section>

          <section className="onboarding-section">
            <div className="panel-title compact">
              <BrainCircuit size={18} />
              <h3>IA</h3>
            </div>
            <label>
              Chave OpenRouter
              <input type="password" value={openRouterKey} onChange={(event) => setOpenRouterKey(event.target.value)} placeholder="opcional agora" />
            </label>
            <label>
              Modelo OpenRouter
              <input value={openRouterModelValue} onChange={(event) => setOpenRouterModelValue(event.target.value)} />
            </label>
            <label>
              Chave Kie
              <input type="password" value={kieKey} onChange={(event) => setKieKey(event.target.value)} placeholder="opcional agora" />
            </label>
            <label>
              Modelo de imagem Kie
              <ImageModelSelect value={kieImageModelValue} models={imageModels} onChange={setKieImageModelValue} />
            </label>
          </section>

          <section className="onboarding-section">
            <div className="panel-title compact">
              <FolderOpen size={18} />
              <h3>Arquivos e exportação</h3>
            </div>
            <label>
              Endereço público do app
              <input value={publicAppUrl} onChange={(event) => setPublicAppUrl(event.target.value)} placeholder="https://eco.seudominio.com" />
              <small>O Kie.ai e a planilha da Shopee baixam as imagens por links neste endereço.</small>
            </label>
          </section>
        </div>

        <div className="onboarding-footer">
          <button type="button" className="primary ghost" disabled={busy} onClick={onSkip}>
            Configurar depois
          </button>
          <button type="submit" className="primary" disabled={busy}>
            {busy ? <Loader2 className="spin" size={18} /> : <Check size={18} />} Começar
          </button>
        </div>
      </form>
    </div>
  );
}

type DashboardFilters = Pick<ProductFilters, "status" | "characteristic" | "publication">;

const DASHBOARD_ATTENTION: { key: keyof CatalogStats["attention"]; label: string; hint: string; filters: DashboardFilters }[] = [
  {
    key: "draft_listing",
    label: "Anúncio em rascunho",
    hint: "Falta título ou descrição",
    filters: { status: "all", characteristic: "draft_listing", publication: "not_listed" },
  },
  {
    key: "without_listing",
    label: "Sem anúncio",
    hint: "Ainda não tem texto gerado",
    filters: { status: "all", characteristic: "without_listing", publication: "not_listed" },
  },
  {
    key: "without_ai_images",
    label: "Sem fotos de IA",
    hint: "Só a capa original do MakerWorld",
    filters: { status: "all", characteristic: "without_ai_images", publication: "not_listed" },
  },
  {
    key: "without_model",
    label: "Sem arquivo 3D",
    hint: "Nenhum 3MF baixado",
    filters: { status: "all", characteristic: "without_model", publication: "not_listed" },
  },
  {
    key: "file_issues",
    label: "Problema nos arquivos",
    hint: "Pasta vazia ou arquivo ausente no disco",
    filters: { status: "all", characteristic: "file_issues", publication: "all" },
  },
];

function DashboardTab({
  stats,
  runtimeStatus,
  onOpenProducts,
  onOpenCollect,
}: {
  stats: CatalogStats | null;
  runtimeStatus: RuntimeStatus | null;
  onOpenProducts: (filters: DashboardFilters) => void;
  onOpenCollect: () => void;
}) {
  // Counted on the server, so the dashboard never needs the whole catalog.
  if (!stats) {
    return (
      <section className="dashboard-page">
        <div className="panel compact-empty">
          <Loader2 className="spin" size={18} />
          <span>Carregando números da loja…</span>
        </div>
      </section>
    );
  }

  if (!stats.total) {
    return (
      <section className="dashboard-page">
        <div className="panel compact-empty dashboard-empty">
          <strong>Nenhum produto nesta loja ainda</strong>
          <span>Comece coletando produtos do MakerWorld.</span>
          <button type="button" className="primary" onClick={onOpenCollect}>
            <PackageSearch size={16} /> Ir para Coleta
          </button>
        </div>
      </section>
    );
  }

  // Same columns, in the same order, as the products board.
  const stages = BOARD_COLUMNS.map((column) => ({
    key: column.key,
    label: column.label,
    filters: { status: column.status, characteristic: "all", publication: column.publication } as DashboardFilters,
  }));
  const readyToPublish = stats.stages.ready;
  const attention = DASHBOARD_ATTENTION.filter((item) => stats.attention[item.key] > 0);
  const totalCost = stats.ai_cost_usd;
  const averageCost = stats.ai_cost_products ? totalCost / stats.ai_cost_products : 0;
  const costByProvider = stats.ai_cost_by_provider;
  const maxCost = Math.max(costByProvider.openrouter, costByProvider.kie, costByProvider.other, 0.000001);
  const usdBrl = Number(runtimeStatus?.exchange.usd_brl);
  const toBrl = (value: number) => (Number.isFinite(usdBrl) && usdBrl > 0 ? formatBrl(value * usdBrl) : null);

  return (
    <section className="dashboard-page">
      <div className="panel">
        <div className="panel-title">
          <Columns3 size={18} />
          <h2>Produtos por etapa</h2>
          <span className="dashboard-panel-meta">{stats.total} no total</span>
        </div>
        <div className="dashboard-funnel-bar" aria-hidden="true">
          {stages.map((stage) => (
            stats.stages[stage.key] > 0 && (
              <span
                key={stage.key}
                className={`stage-${stage.key}`}
                style={{ flexGrow: stats.stages[stage.key] }}
              />
            )
          ))}
        </div>
        <div className="dashboard-stages">
          {stages.map((stage) => {
            const count = stats.stages[stage.key];
            return (
              <button
                key={stage.key}
                type="button"
                className={`dashboard-stage stage-${stage.key}`}
                onClick={() => onOpenProducts(stage.filters)}
              >
                <span className="dashboard-stage-label"><i aria-hidden="true" />{stage.label}</span>
                <strong>{count}</strong>
                <small>{Math.round((count / stats.total) * 100)}%</small>
              </button>
            );
          })}
        </div>
      </div>

      <div className="dashboard-panels">
        <div className="panel">
          <div className="panel-title">
            <ListChecks size={18} />
            <h2>O que fazer agora</h2>
          </div>
          <div className="dashboard-todo">
            {readyToPublish > 0 && (
              <button
                type="button"
                className="dashboard-todo-row highlight"
                onClick={() => onOpenProducts({ status: "ready", characteristic: "all", publication: "not_listed" })}
              >
                <BadgeCheck size={18} />
                <span>
                  <strong>Prontos para publicar</strong>
                  <small>Na etapa Pronto, ainda não exportados nem publicados</small>
                </span>
                <b>{readyToPublish}</b>
                <ArrowRight size={16} />
              </button>
            )}
            {attention.map((item) => (
              <button
                key={item.key}
                type="button"
                className={item.key === "file_issues" ? "dashboard-todo-row warning" : "dashboard-todo-row"}
                onClick={() => onOpenProducts(item.filters)}
              >
                <AlertCircle size={18} />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.hint}</small>
                </span>
                <b>{stats.attention[item.key]}</b>
                <ArrowRight size={16} />
              </button>
            ))}
            {!readyToPublish && !attention.length && (
              <div className="compact-empty">
                <strong>Nada pendente</strong>
                <span>Todos os produtos não publicados têm anúncio, fotos e 3D.</span>
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">
            <BrainCircuit size={18} />
            <h2>Custo de IA</h2>
          </div>
          <div className="dashboard-cost-figures">
            <div>
              <span>Total</span>
              <strong>{formatUsd(totalCost)}</strong>
              {toBrl(totalCost) && <small>{toBrl(totalCost)}{runtimeStatus?.exchange.stale ? " · câmbio em cache" : ""}</small>}
            </div>
            <div>
              <span>Média por produto</span>
              <strong>{formatUsd(averageCost)}</strong>
              {toBrl(averageCost) && <small>{toBrl(averageCost)}</small>}
            </div>
          </div>
          <div className="cost-bars">
            <CostBar label="Texto (OpenRouter)" value={costByProvider.openrouter} max={maxCost} />
            <CostBar label="Imagem (Kie)" value={costByProvider.kie} max={maxCost} />
            {costByProvider.other > 0 && <CostBar label="Outros" value={costByProvider.other} max={maxCost} />}
          </div>
        </div>
      </div>
    </section>
  );
}

function CostBar({ label, max, value }: { label: string; max: number; value: number }) {
  const percent = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="cost-bar-row">
      <div>
        <strong>{label}</strong>
        <span>{formatUsd(value)}</span>
      </div>
      <div className="chart-bar-track cost-track">
        <span style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
      </div>
    </div>
  );
}

function TabButton({
  active,
  children,
  icon,
  onClick,
}: {
  active: boolean;
  children: React.ReactNode;
  icon: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button className={active ? "tab-button active" : "tab-button"} onClick={onClick}>
      {icon}
      {children}
    </button>
  );
}

function StorePicker({
  activeStore,
  stores,
  onChange,
}: {
  activeStore?: StoreProfile;
  stores: StoreProfile[];
  onChange: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement | null>(null);
  const initial = (activeStore?.name || "L").trim().slice(0, 1).toUpperCase();
  const photoUrl = storePhotoUrl(activeStore);

  useEffect(() => {
    if (!open) return;
    function handleDocumentClick(event: MouseEvent) {
      if (!pickerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleDocumentClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleDocumentClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div className="store-profile-switcher" ref={pickerRef}>
      <div className="store-avatar" aria-hidden="true">
        {photoUrl ? <img src={photoUrl} alt="" /> : activeStore ? initial : <UserRound size={18} />}
      </div>
      <div className="store-picker-control">
        <button className="store-picker-button" type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
          <span>{activeStore?.name ?? "Selecionar loja"}</span>
          <ChevronDown size={16} aria-hidden="true" />
        </button>
        {open && (
          <div className="store-picker-menu" role="listbox">
            {stores.map((store) => {
              const selected = store.id === activeStore?.id;
              const storeInitial = store.name.trim().slice(0, 1).toUpperCase();
              const storePhoto = storePhotoUrl(store);
              return (
                <button
                  className={selected ? "store-picker-option active" : "store-picker-option"}
                  key={store.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => {
                    onChange(store.id);
                    setOpen(false);
                  }}
                >
                  <span className="store-picker-option-avatar">{storePhoto ? <img src={storePhoto} alt="" /> : storeInitial}</span>
                  <span>{store.name}</span>
                  {selected && <Check size={15} aria-hidden="true" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function CollectTab({
  activeStoreProfile,
  busy,
  jobs,
  keyword,
  limit,
  loginStatus,
  manualUrl,
  productCount,
  scrolls,
  onCollect,
  onCloseLogin,
  onExtractSelectedLinks,
  onKeywordChange,
  onLimitChange,
  onOpenLogin,
  onManualUrlChange,
  onScrollsChange,
  blockedSourceUrls,
  onRemoveBlockedUrl,
}: {
  activeStoreProfile?: StoreProfile;
  busy: boolean;
  jobs: Job[];
  keyword: string;
  limit: number;
  loginStatus: MakerWorldLoginStatus | null;
  manualUrl: string;
  productCount: number;
  scrolls: number;
  onCollect: () => void;
  onCloseLogin: () => void;
  onExtractSelectedLinks: () => void;
  onKeywordChange: (value: string) => void;
  onLimitChange: (value: number) => void;
  onOpenLogin: () => void;
  onManualUrlChange: (value: string) => void;
  onScrollsChange: (value: number) => void;
  blockedSourceUrls: BlockedSourceUrl[];
  onRemoveBlockedUrl: (entryId: string) => void;
}) {
  const allCollectJobs = jobs.filter((job) => job.type === "collect_products");
  const collectJobs = allCollectJobs.slice(0, 4);
  const collectSummary = collectJobsSummary(allCollectJobs);

  return (
    <section className="tab-layout collect-layout">
      <div className="panel primary-work-panel">
        <div className="panel-title">
          <PackageSearch size={18} />
          <h2>Coletar produtos</h2>
        </div>

        <p className="settings-note collect-catalog-note">
          Os produtos coletados entram direto no catálogo da loja ({productCount} produto(s), {blockedSourceUrls.length} URL(s) bloqueada(s)).
        </p>

        <div className="form-grid">
          <label>
            Palavra-chave
            <input value={keyword} onChange={(event) => onKeywordChange(event.target.value)} />
          </label>
          <label>
            Limite
            <input
              min="1"
              max="100"
              type="number"
              value={limit}
              onChange={(event) => onLimitChange(Number(event.target.value))}
            />
          </label>
          <label>
            Rolagens
            <input
              min="1"
              max="60"
              type="number"
              value={scrolls}
              onChange={(event) => onScrollsChange(Number(event.target.value))}
            />
          </label>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={true}
            disabled
          />
          Navegador com interface no servidor (controle pelo painel)
        </label>

        <div className="action-row">
          <button className="primary login-button" onClick={onOpenLogin} disabled={busy}>
            <LogIn size={18} /> Configurar login MakerWorld
          </button>
          <button className="primary ghost" onClick={onCloseLogin} disabled={busy || !loginStatus?.open}>
            Fechar navegador
          </button>
          <button className="primary dark" onClick={onCollect} disabled={busy}>
            <Play size={18} /> Iniciar coleta
          </button>
        </div>

        <p className="session-note">O navegador roda e permanece visível no PC servidor. O login pode ser controlado pela janela remota deste app.</p>

        <div className="manual-links-section">
          <div className="manual-links-heading">
            <div>
              <div className="subsection-title">Links para extrair produtos selecionados</div>
              <small>Use quando você já escolheu os produtos no MakerWorld. Este fluxo captura e envia direto para Produtos.</small>
            </div>
            <Link2 size={18} />
          </div>
          <textarea
            value={manualUrl}
            onChange={(event) => onManualUrlChange(event.target.value)}
            placeholder="Cole links especificos aqui, um por linha"
          />
          <div className="option-row">
            <small>{manualUrl.split(/\s|,|\n/).filter((url) => url.trim()).length} link(s) na lista</small>
            <button className="primary" onClick={onExtractSelectedLinks} disabled={busy || !manualUrl.trim()}>
              <Link2 size={16} /> Extrair links selecionados
            </button>
          </div>
        </div>

        <div className="blocked-urls-section">
          <div className="manual-links-heading">
            <div>
              <div className="subsection-title">Lista de bloqueio ({blockedSourceUrls.length})</div>
              <small>
                URLs de produtos apagados ficam aqui para evitar recoleta acidental. Remova uma entrada para permitir coletar de novo.
              </small>
            </div>
          </div>
          {blockedSourceUrls.length ? (
            <div className="blocked-url-list">
              {blockedSourceUrls.slice(0, 8).map((entry) => (
                <div className="blocked-url-item" key={entry.id}>
                  <div className="blocked-url-copy">
                    <strong>{entry.label || "Produto removido"}</strong>
                    <small>{entry.url}</small>
                  </div>
                  <button className="primary ghost compact-button" disabled={busy} onClick={() => onRemoveBlockedUrl(entry.id)}>
                    Liberar
                  </button>
                </div>
              ))}
              {blockedSourceUrls.length > 8 && (
                <small className="blocked-url-more">+ {blockedSourceUrls.length - 8} URL(s) bloqueada(s)</small>
              )}
            </div>
          ) : (
            <p className="settings-note">Nenhuma URL bloqueada nesta loja.</p>
          )}
        </div>
      </div>

      <div className="panel side-panel">
        <div className="panel-title">
          <PackageSearch size={18} />
          <h2>Últimas coletas</h2>
        </div>
        <div className="collect-summary-strip">
          <div>
            <span>Curadoria</span>
            <strong>Manual</strong>
          </div>
          <div>
            <span>Coletas</span>
            <strong>{collectSummary.totalJobs}</strong>
          </div>
          <div>
            <span>Produtos</span>
            <strong>{collectSummary.totalProducts}</strong>
          </div>
        </div>

        {loginStatus?.message && <p className="session-note">{displayText(loginStatus.message)}</p>}
        {loginStatus?.url && <p className="session-url">{loginStatus.url}</p>}
        <div className="mini-job-list">
          {collectJobs.length > 0 ? (
            collectJobs.map((job) => {
              const cost = collectJobCost(job);
              return (
              <div className="mini-job" key={job.id}>
                <span>
                  <strong>{jobActive(job) ? "Em andamento" : JOB_STATUS_LABELS[job.status]}</strong>
                  <small>{displayText(job.message)}</small>
                  <small>
                    {collectJobCreatedCount(job)} produto(s) coletado(s)
                    {cost.cost ? ` · IA ${formatUsd(cost.cost)}` : ""}
                    {cost.source === "logs" ? " · estimado por logs" : ""}
                  </small>
                </span>
                <progress max={100} value={job.progress} />
              </div>
              );
            })
          ) : (
            <div className="empty-state compact-empty">
              <strong>Nenhuma coleta ainda</strong>
              <span>As execuções recentes aparecerão aqui com os produtos coletados.</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

const THUMB_PREVIEW_LAYOUT = {
  costs: {
    previewClass: "costs-thumb-preview",
    captionClass: "costs-thumb-preview-caption",
    width: 236,
    height: 248,
    imageWidth: 384,
    delayMs: 500,
  },
  products: {
    previewClass: "product-thumb-preview",
    captionClass: "product-thumb-preview-caption",
    width: 380,
    height: 400,
    imageWidth: 768,
    delayMs: 500,
  },
} as const;

type ThumbPreviewVariant = keyof typeof THUMB_PREVIEW_LAYOUT;

function useProductThumbPreview(product: Product, variant: ThumbPreviewVariant) {
  const layout = THUMB_PREVIEW_LAYOUT[variant];
  const thumbnailUrl = productThumbnailUrl(product);
  const previewUrl = productThumbnailUrl(product, layout.imageWidth);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewPos, setPreviewPos] = useState({ top: 0, left: 0 });
  const hoverTimerRef = useRef<number | null>(null);
  const anchorRef = useRef<HTMLElement>(null);

  useEffect(() => () => {
    if (hoverTimerRef.current !== null) {
      window.clearTimeout(hoverTimerRef.current);
    }
  }, []);

  function clearHoverTimer() {
    if (hoverTimerRef.current !== null) {
      window.clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  }

  function openPreview() {
    const anchor = anchorRef.current;
    if (!anchor || !thumbnailUrl) return;
    const rect = anchor.getBoundingClientRect();
    const gap = 10;
    let left = rect.right + gap;
    if (left + layout.width > window.innerWidth - 8) {
      left = rect.left - layout.width - gap;
    }
    left = Math.max(8, left);
    let top = rect.top + rect.height / 2 - layout.height / 2;
    top = Math.max(8, Math.min(top, window.innerHeight - layout.height - 8));
    setPreviewPos({ top, left });
    setPreviewOpen(true);
  }

  function handleMouseEnter() {
    if (!thumbnailUrl) return;
    clearHoverTimer();
    hoverTimerRef.current = window.setTimeout(openPreview, layout.delayMs);
  }

  function handleMouseLeave() {
    clearHoverTimer();
    setPreviewOpen(false);
  }

  return {
    anchorRef,
    thumbnailUrl,
    previewUrl,
    handleMouseEnter,
    handleMouseLeave,
    layout,
    previewOpen,
    previewPos,
  };
}

function ProductThumbPreviewPortal({
  imageUrl,
  layout,
  open,
  position,
  productName,
}: {
  imageUrl: string;
  layout: (typeof THUMB_PREVIEW_LAYOUT)[ThumbPreviewVariant];
  open: boolean;
  position: { top: number; left: number };
  productName: string;
}) {
  if (!open) return null;
  return createPortal(
    <div className={layout.previewClass} style={{ top: position.top, left: position.left }}>
      <img src={imageUrl} alt={productName} />
      <span className={layout.captionClass} title={productName}>{productName}</span>
    </div>,
    document.body,
  );
}

const PUBLICATION_TABS: { value: ProductPublication; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "not_listed", label: "Não publicados" },
  { value: "listed", label: "Publicados" },
];

// One-tap filters for what still needs work; each is a status or a
// characteristic, and only one applies at a time.
const PRODUCT_QUICK_FILTERS: {
  key: string;
  label: string;
  status: ProductFilters["status"];
  characteristic: ProductFilters["characteristic"];
}[] = [
  { key: "without_listing", label: "Sem anúncio", status: "all", characteristic: "without_listing" },
  { key: "draft_listing", label: "Rascunho", status: "all", characteristic: "draft_listing" },
  { key: "without_ai_images", label: "Sem fotos IA", status: "all", characteristic: "without_ai_images" },
  { key: "without_model", label: "Sem 3D", status: "all", characteristic: "without_model" },
  { key: "file_issues", label: "Arquivos com problema", status: "all", characteristic: "file_issues" },
  { key: "ready", label: "Prontos", status: "ready", characteristic: "all" },
  { key: "exported", label: "Exportados", status: "exported", characteristic: "all" },
];

type ActionMenuItem = {
  key: string;
  label: string;
  icon?: React.ReactNode;
  title?: string;
  danger?: boolean;
  onClick: () => void;
};

function ActionMenu({
  label,
  trigger,
  items,
  disabled,
  placement = "down",
}: {
  label: string;
  trigger?: React.ReactNode;
  items: ActionMenuItem[];
  disabled?: boolean;
  placement?: "down" | "up";
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function handleDocumentClick(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleDocumentClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleDocumentClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div className={`action-menu ${placement}`} ref={menuRef}>
      <button
        type="button"
        className={trigger ? "action-menu-trigger" : "action-menu-trigger icon-only"}
        onClick={() => setOpen((value) => !value)}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        title={trigger ? undefined : label}
        disabled={disabled}
      >
        {trigger ?? <MoreHorizontal size={18} />}
      </button>
      {open && (
        <div className="action-menu-list" role="menu">
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              role="menuitem"
              className={item.danger ? "danger" : ""}
              title={item.title}
              onClick={() => {
                setOpen(false);
                item.onClick();
              }}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

type ProductViewMode = "grid" | "board";
const PRODUCT_VIEW_MODE_KEY = "eco_native_products_view";

function readProductViewMode(): ProductViewMode {
  try {
    return window.localStorage.getItem(PRODUCT_VIEW_MODE_KEY) === "board" ? "board" : "grid";
  } catch {
    return "grid";
  }
}

type BoardColumnKey = ProductStatus | "listed";

// Unpublished products sit in their status column; published ones, whatever
// their status, in the last column.
const BOARD_COLUMNS: { key: BoardColumnKey; label: string; status: ProductFilters["status"]; publication: ProductPublication }[] = [
  { key: "collected", label: "Coletado", status: "collected", publication: "not_listed" },
  { key: "in_edit", label: "Em edição", status: "in_edit", publication: "not_listed" },
  { key: "ready", label: "Pronto", status: "ready", publication: "not_listed" },
  { key: "exported", label: "Exportado", status: "exported", publication: "not_listed" },
  { key: "listed", label: "Publicado", status: "all", publication: "listed" },
];

function productBoardColumn(product: Product): BoardColumnKey {
  return productListed(product) ? "listed" : product.status;
}

type BoardColumnState = {
  items: Product[];
  nextCursor: string | null;
  total: number;
  loading: boolean;
};

// Card callbacks take the product, so one stable object serves every card
// and memoized cards skip re-rendering when the page around them changes.
type ProductCardHandlers = {
  open: (productId: string) => void;
  toggleSelected: (productId: string) => void;
  toggleListed: (product: Product) => void;
  generateListing: (productId: string) => void;
  generateImages: (productId: string) => void;
  remove: (productId: string) => void;
};

// Returns an object whose functions never change but always call the latest
// version of `handlers`.
function useStableHandlers<T extends Record<string, (...args: never[]) => unknown>>(handlers: T): T {
  const ref = useRef(handlers);
  ref.current = handlers;
  return useMemo(() => {
    const stable = {} as Record<string, (...args: unknown[]) => unknown>;
    for (const key of Object.keys(handlers)) {
      stable[key] = (...args: unknown[]) => (ref.current[key] as (...args: unknown[]) => unknown)(...args);
    }
    return stable as unknown as T;
  }, []);
}

// Calls onLoadMore when it scrolls into view (inside `root` when given).
// The observer is recreated whenever `rerunKey` changes, so a sentinel that
// is still visible after a page arrives keeps loading until the space is filled.
function LoadMoreSentinel({
  enabled,
  onLoadMore,
  rerunKey,
  root,
  className,
  children,
}: {
  enabled: boolean;
  onLoadMore: () => void;
  rerunKey: number;
  root?: React.RefObject<HTMLElement | null>;
  className: string;
  children: React.ReactNode;
}) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const callbackRef = useRef(onLoadMore);
  callbackRef.current = onLoadMore;

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!enabled || !sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) callbackRef.current();
      },
      { root: root?.current ?? null, rootMargin: "400px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [enabled, rerunKey]);

  return <div className={className} ref={sentinelRef}>{children}</div>;
}

const ProductTile = React.memo(function ProductTile({
  product,
  busy,
  selected,
  active,
  handlers,
}: {
  product: Product;
  busy: boolean;
  selected: boolean;
  active: boolean;
  handlers: ProductCardHandlers;
}) {
  const listed = productListed(product);
  const imageUrl = productThumbnailUrl(product, 384);
  const subtitle = productCardSubtitle(product);
  const badges = productPipelineBadges(product);
  const stage = badges.find((badge) => badge.key === "stage");
  const steps = badges.filter((badge) => badge.key !== "stage");
  const open = () => handlers.open(product.id);
  const className = ["product-tile", listed ? "published" : "", selected ? "selected" : "", active ? "active" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <article className={className}>
      <div className="product-tile-media">
        <button className="product-tile-image" onClick={open} aria-label={`Abrir ${product.name}`}>
          {imageUrl ? <img src={imageUrl} alt="" loading="lazy" decoding="async" /> : <ShoppingBag size={28} />}
        </button>
        <label className="product-tile-check" aria-label={`Selecionar ${product.name}`}>
          <input type="checkbox" checked={selected} onChange={() => handlers.toggleSelected(product.id)} disabled={busy} />
        </label>
        <div className="product-tile-menu">
          <ActionMenu
            label={`Ações de ${product.name}`}
            disabled={busy}
            items={[
              { key: "listing", label: "Gerar anúncio", icon: <BrainCircuit size={15} />, onClick: () => handlers.generateListing(product.id) },
              { key: "images", label: "Gerar imagens", icon: <ImagePlus size={15} />, onClick: () => handlers.generateImages(product.id) },
              { key: "delete", label: "Apagar produto", icon: <Trash2 size={15} />, danger: true, onClick: () => handlers.remove(product.id) },
            ]}
          />
        </div>
        {stage && stage.detail !== "Aguardando" && <span className={`product-tile-stage ${stage.state}`}>{stage.detail}</span>}
      </div>
      <button className="product-tile-body" onClick={open}>
        <strong title={product.name}>{product.name}</strong>
        <span className={subtitle ? "product-tile-subtitle" : "product-tile-subtitle muted"}>
          {subtitle || "Sem anúncio gerado ainda"}
        </span>
      </button>
      <div className="product-tile-steps">
        {steps.map((badge) => (
          <span className={`product-tile-step ${badge.state}`} key={badge.key} title={`${badge.label}: ${badge.detail}`}>
            <span className="product-tile-step-dot" aria-hidden="true" />
            {badge.label}
          </span>
        ))}
      </div>
      <button
        className={listed ? "publish-toggle on" : "publish-toggle"}
        onClick={() => handlers.toggleListed(product)}
        disabled={busy}
        aria-pressed={listed}
        title={listed ? "Clique para marcar como não publicado" : "Clique quando o produto estiver publicado"}
      >
        {listed ? <><Check size={15} /> Publicado</> : "Marcar como publicado"}
      </button>
    </article>
  );
});

type BoardHandlers = {
  dragStart: (productId: string) => void;
  dragEnd: () => void;
  move: (product: Product, target: BoardColumnKey) => void;
};

function ProductBoard({
  active,
  filters,
  revision,
  freshProducts,
  busy,
  selectedProductIds,
  activeProductId,
  onMoveProduct,
  handlers,
}: {
  active: boolean;
  filters: ProductFilters;
  revision: number;
  freshProducts: Record<string, Product>;
  busy: boolean;
  selectedProductIds: string[];
  activeProductId?: string;
  onMoveProduct: (product: Product, column: BoardColumnKey) => Promise<unknown>;
  handlers: ProductCardHandlers;
}) {
  const [columns, setColumns] = useState<Partial<Record<BoardColumnKey, BoardColumnState>>>({});
  // Drops show at once; the server's answer then replaces them.
  const [pendingMoves, setPendingMoves] = useState<Record<string, BoardColumnKey>>({});
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<BoardColumnKey | null>(null);
  const columnsRef = useRef(columns);
  columnsRef.current = columns;
  const requestRef = useRef(0);
  const loadedRevisionRef = useRef<number | null>(null);

  function columnPath(column: (typeof BOARD_COLUMNS)[number], limit: number, cursor?: string | null) {
    return productPagePath({ ...filters, status: column.status, publication: column.publication }, limit, cursor);
  }

  // Reloads every column, keeping as many items as each already shows. While
  // the board is hidden, changes wait until it is shown again.
  useEffect(() => {
    if (!active || loadedRevisionRef.current === revision) return;
    loadedRevisionRef.current = revision;
    const request = ++requestRef.current;
    const loaded = columnsRef.current;
    setColumns((current) => {
      const next = { ...current };
      for (const column of BOARD_COLUMNS) next[column.key] = { ...(current[column.key] ?? { items: [], nextCursor: null, total: 0 }), loading: true };
      return next;
    });
    Promise.all(BOARD_COLUMNS.map(async (column) => {
      const limit = Math.min(MAX_PRODUCT_RELOAD, Math.max(PRODUCT_PAGE_SIZE, loaded[column.key]?.items.length ?? 0));
      const page = await api<ProductPage>(columnPath(column, limit));
      return [column.key, { items: page.items, nextCursor: page.next_cursor, total: page.total, loading: false }] as const;
    }))
      .then((pages) => {
        if (request !== requestRef.current) return;
        setColumns(Object.fromEntries(pages));
        setPendingMoves({});
      })
      .catch(() => {
        if (request !== requestRef.current) return;
        loadedRevisionRef.current = null;
        setColumns((current) => Object.fromEntries(
          Object.entries(current).map(([key, state]) => [key, { ...state, loading: false }]),
        ));
      });
  }, [revision, active]);

  async function loadMore(column: (typeof BOARD_COLUMNS)[number]) {
    const state = columnsRef.current[column.key];
    if (!state?.nextCursor || state.loading) return;
    const request = requestRef.current;
    const loadingState = { ...state, loading: true };
    // The ref is updated now so a second observer callback cannot fire the
    // same page before React re-renders.
    columnsRef.current = { ...columnsRef.current, [column.key]: loadingState };
    setColumns((current) => ({ ...current, [column.key]: loadingState }));
    try {
      const page = await api<ProductPage>(columnPath(column, PRODUCT_PAGE_SIZE, state.nextCursor));
      if (request !== requestRef.current) return;
      setColumns((current) => {
        const previous = current[column.key] ?? state;
        const known = new Set(previous.items.map((product) => product.id));
        return {
          ...current,
          [column.key]: {
            items: [...previous.items, ...page.items.filter((product) => !known.has(product.id))],
            nextCursor: page.next_cursor,
            total: page.total,
            loading: false,
          },
        };
      });
    } catch {
      setColumns((current) => ({ ...current, [column.key]: { ...state, loading: false } }));
    }
  }

  // Products are placed by their latest version, so a change made anywhere
  // (a drop, the details panel, a finished job) moves the card; the column
  // counts shift by the cards that moved in or out.
  const placed = useMemo(() => {
    const byColumn = Object.fromEntries(BOARD_COLUMNS.map((column) => [column.key, [] as Product[]])) as Record<BoardColumnKey, Product[]>;
    const delta = Object.fromEntries(BOARD_COLUMNS.map((column) => [column.key, 0])) as Record<BoardColumnKey, number>;
    const seen = new Set<string>();
    for (const column of BOARD_COLUMNS) {
      for (const item of columns[column.key]?.items ?? []) {
        if (seen.has(item.id)) continue;
        seen.add(item.id);
        const product = freshProducts[item.id] ?? item;
        const target = pendingMoves[item.id] ?? productBoardColumn(product);
        byColumn[target].push(product);
        if (target !== column.key) {
          delta[target] += 1;
          delta[column.key] -= 1;
        }
      }
    }
    for (const list of Object.values(byColumn)) {
      list.sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "") || b.id.localeCompare(a.id));
    }
    return { byColumn, delta };
  }, [columns, freshProducts, pendingMoves]);

  function moveProduct(product: Product, target: BoardColumnKey) {
    const current = pendingMoves[product.id] ?? productBoardColumn(product);
    if (current === target) return;
    setPendingMoves((moves) => ({ ...moves, [product.id]: target }));
    void onMoveProduct(product, target).finally(() => {
      setPendingMoves((moves) => {
        const next = { ...moves };
        delete next[product.id];
        return next;
      });
    });
  }

  const boardHandlers = useStableHandlers<BoardHandlers>({
    dragStart: (productId) => setDraggingId(productId),
    dragEnd: () => {
      setDraggingId(null);
      setDropTarget(null);
    },
    move: moveProduct,
  });

  function handleDrop(event: React.DragEvent, target: BoardColumnKey) {
    event.preventDefault();
    setDropTarget(null);
    const productId = event.dataTransfer.getData("text/plain");
    setDraggingId(null);
    const product = Object.values(placed.byColumn).flat().find((item) => item.id === productId);
    if (product) moveProduct(product, target);
  }

  return (
    <div className="product-board">
      {BOARD_COLUMNS.map((column) => {
        const state = columns[column.key];
        const items = placed.byColumn[column.key];
        return (
          <BoardColumn
            key={column.key}
            column={column}
            state={state}
            items={items}
            total={Math.max(items.length, (state?.total ?? 0) + placed.delta[column.key])}
            dropTarget={dropTarget === column.key}
            onDragOver={(event) => {
              if (!draggingId) return;
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
              if (dropTarget !== column.key) setDropTarget(column.key);
            }}
            onDragLeave={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDropTarget(null);
            }}
            onDrop={(event) => handleDrop(event, column.key)}
            onLoadMore={() => void loadMore(column)}
          >
            {items.map((product) => (
              <BoardCard
                key={product.id}
                product={product}
                column={column.key}
                busy={busy}
                pending={Boolean(pendingMoves[product.id])}
                selected={selectedProductIds.includes(product.id)}
                active={product.id === activeProductId}
                dragging={draggingId === product.id}
                handlers={handlers}
                boardHandlers={boardHandlers}
              />
            ))}
          </BoardColumn>
        );
      })}
    </div>
  );
}

function BoardColumn({
  column,
  state,
  items,
  total,
  dropTarget,
  onDragOver,
  onDragLeave,
  onDrop,
  onLoadMore,
  children,
}: {
  column: (typeof BOARD_COLUMNS)[number];
  state?: BoardColumnState;
  items: Product[];
  total: number;
  dropTarget: boolean;
  onDragOver: (event: React.DragEvent) => void;
  onDragLeave: (event: React.DragEvent) => void;
  onDrop: (event: React.DragEvent) => void;
  onLoadMore: () => void;
  children: React.ReactNode;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  return (
    <section
      className={[
        "board-column",
        column.key === "listed" ? "published" : "",
        dropTarget ? "drop-target" : "",
      ].filter(Boolean).join(" ")}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      aria-label={column.label}
    >
      <header className="board-column-head">
        {column.key === "listed" && <Check size={15} />}
        <h3>{column.label}</h3>
        <span className="board-column-count">{state ? total : "…"}</span>
      </header>
      <div className="board-column-list" ref={listRef}>
        {children}
        {state && !state.loading && !items.length && (
          <p className="board-column-empty">
            {column.key === "listed" ? "Arraste para cá o que você já publicou" : "Nenhum produto"}
          </p>
        )}
        {state?.nextCursor && (
          <LoadMoreSentinel
            className="board-load-more"
            enabled={!state.loading}
            onLoadMore={onLoadMore}
            rerunKey={state.items.length}
            root={listRef}
          >
            {state.loading ? "Carregando..." : `Role para ver mais (${items.length} de ${total})`}
          </LoadMoreSentinel>
        )}
        {!state && <p className="board-column-empty">Carregando...</p>}
      </div>
    </section>
  );
}

const BoardCard = React.memo(function BoardCard({
  product,
  column,
  busy,
  pending,
  selected,
  active,
  dragging,
  handlers,
  boardHandlers,
}: {
  product: Product;
  column: BoardColumnKey;
  busy: boolean;
  pending: boolean;
  selected: boolean;
  active: boolean;
  dragging: boolean;
  handlers: ProductCardHandlers;
  boardHandlers: BoardHandlers;
}) {
  const imageUrl = productThumbnailUrl(product);
  const steps = productPipelineBadges(product).filter((badge) => badge.key !== "stage");
  const open = () => handlers.open(product.id);
  const className = [
    "board-card",
    selected ? "selected" : "",
    active ? "active" : "",
    dragging ? "dragging" : "",
    pending ? "pending" : "",
  ].filter(Boolean).join(" ");

  return (
    <article
      className={className}
      draggable={!busy}
      onDragStart={(event) => {
        event.dataTransfer.setData("text/plain", product.id);
        event.dataTransfer.effectAllowed = "move";
        boardHandlers.dragStart(product.id);
      }}
      onDragEnd={boardHandlers.dragEnd}
    >
      <div className="board-card-thumb">
        <button onClick={open} aria-label={`Abrir ${product.name}`} tabIndex={-1}>
          {imageUrl ? <img src={imageUrl} alt="" loading="lazy" decoding="async" draggable={false} /> : <ShoppingBag size={20} />}
        </button>
        <label className="product-tile-check" aria-label={`Selecionar ${product.name}`}>
          <input type="checkbox" checked={selected} onChange={() => handlers.toggleSelected(product.id)} disabled={busy} />
        </label>
      </div>
      <button className="board-card-body" onClick={open}>
        <strong title={product.name}>{product.name}</strong>
        <span className="board-card-sku">{productSku(product) || "Sem SKU"}</span>
        <span className="product-tile-steps">
          {steps.map((badge) => (
            <span className={`product-tile-step ${badge.state}`} key={badge.key} title={`${badge.label}: ${badge.detail}`}>
              <span className="product-tile-step-dot" aria-hidden="true" />
              {badge.label}
            </span>
          ))}
        </span>
      </button>
      <div className="product-tile-menu board-card-menu">
        <ActionMenu
          label={`Ações de ${product.name}`}
          disabled={busy}
          items={[
            ...BOARD_COLUMNS.filter((target) => target.key !== column).map((target) => ({
              key: `move-${target.key}`,
              label: `Mover para ${target.label}`,
              icon: target.key === "listed" ? <Check size={15} /> : <ArrowRight size={15} />,
              onClick: () => boardHandlers.move(product, target.key),
            })),
            { key: "listing", label: "Gerar anúncio", icon: <BrainCircuit size={15} />, onClick: () => handlers.generateListing(product.id) },
            { key: "images", label: "Gerar imagens", icon: <ImagePlus size={15} />, onClick: () => handlers.generateImages(product.id) },
            { key: "delete", label: "Apagar produto", icon: <Trash2 size={15} />, danger: true, onClick: () => handlers.remove(product.id) },
          ]}
        />
      </div>
    </article>
  );
});

function CostsProductCell({ product }: { product: Product }) {
  const sku = productSku(product) || "—";
  const {
    anchorRef,
    thumbnailUrl,
    previewUrl,
    handleMouseEnter,
    handleMouseLeave,
    layout,
    previewOpen,
    previewPos,
  } = useProductThumbPreview(product, "costs");

  return (
    <>
      <div
        ref={anchorRef as React.RefObject<HTMLDivElement>}
        className="costs-product-cell-inner"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        title={product.name}
      >
        <div className="costs-product-thumb" aria-hidden="true">
          {thumbnailUrl ? (
            <img src={thumbnailUrl} alt="" loading="lazy" decoding="async" />
          ) : (
            <span className="costs-product-thumb-fallback">
              <ShoppingBag size={18} />
            </span>
          )}
        </div>
        <code className="costs-product-sku">{sku}</code>
      </div>
      {previewUrl && (
        <ProductThumbPreviewPortal
          imageUrl={previewUrl}
          layout={layout}
          open={previewOpen}
          position={previewPos}
          productName={product.name}
        />
      )}
    </>
  );
}

const COSTS_TABLE_ROW_BATCH = 28;
const COSTS_TABLE_SCROLL_THRESHOLD = 160;

function CostsTab({
  activeStoreProfile,
  busy,
  filaments,
  productionSettings,
  products,
  productsLoading,
  runtimeStatus,
  onSaveAllProductionCosts,
  onProductionCostsSaved,
}: {
  activeStoreProfile?: StoreProfile;
  busy: boolean;
  filaments: FilamentSpool[];
  productionSettings: ProductionSettings | null;
  products: Product[];
  productsLoading: boolean;
  runtimeStatus: RuntimeStatus | null;
  onSaveAllProductionCosts: (entries: Array<{ productId: string; productionCost: ProductionCost }>) => Promise<void>;
  onProductionCostsSaved: (entries: Array<{ productId: string; productionCost: ProductionCost }>) => void;
}) {
  const settings = productionSettings ?? defaultProductionSettings(activeStoreProfile?.id || "");
  const usdBrl = Number(runtimeStatus?.exchange.usd_brl);
  const exchangeReady = Number.isFinite(usdBrl) && usdBrl > 0;
  const [otherCostsRows, setOtherCostsRows] = useState<Record<string, number>>({});
  const [savedOtherCostsRows, setSavedOtherCostsRows] = useState<Record<string, number>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [saveStatus, setSaveStatus] = useState<"saved" | "pending" | "saving" | "error">("saved");
  const [renderedRowCount, setRenderedRowCount] = useState(COSTS_TABLE_ROW_BATCH);
  const tableScrollRef = useRef<HTMLDivElement>(null);
  const otherCostsRowsRef = useRef(otherCostsRows);
  const savedOtherCostsRowsRef = useRef(savedOtherCostsRows);
  const savingRef = useRef(false);
  otherCostsRowsRef.current = otherCostsRows;
  savedOtherCostsRowsRef.current = savedOtherCostsRows;

  const filteredProducts = useMemo(
    () => filterProducts(products, { query: searchQuery, status: "all", characteristic: "all", publication: "all" }),
    [products, searchQuery],
  );

  function readOtherCosts(product: Product): number {
    return readProductionCost(product).other_costs_brl;
  }

  function dirtyEntriesFromState() {
    return products
      .map((product) => {
        const draft = otherCostsRowsRef.current[product.id] ?? readOtherCosts(product);
        const saved = savedOtherCostsRowsRef.current[product.id] ?? readOtherCosts(product);
        return draft === saved
          ? null
          : {
            productId: product.id,
            productionCost: productionCostPayloadFromDraft({
              ...readProductionCost(product),
              other_costs_brl: draft,
            }),
          };
      })
      .filter((entry): entry is { productId: string; productionCost: ProductionCost } => Boolean(entry));
  }

  useEffect(() => {
    const nextRows: Record<string, number> = {};
    const nextSaved: Record<string, number> = {};
    products.forEach((product) => {
      const fromProduct = readOtherCosts(product);
      const draft = otherCostsRowsRef.current[product.id] ?? fromProduct;
      const previousSaved = savedOtherCostsRowsRef.current[product.id] ?? fromProduct;
      const isDirty = draft !== previousSaved;
      nextSaved[product.id] = fromProduct;
      nextRows[product.id] = isDirty ? draft : fromProduct;
    });
    savedOtherCostsRowsRef.current = nextSaved;
    otherCostsRowsRef.current = nextRows;
    setSavedOtherCostsRows(nextSaved);
    setOtherCostsRows(nextRows);
  }, [products]);

  useEffect(() => {
    const pending = dirtyEntriesFromState();
    if (!pending.length) {
      setSaveStatus((current) => (current === "saving" ? current : "saved"));
      return;
    }
    setSaveStatus("pending");
    const timer = window.setTimeout(async () => {
      if (savingRef.current) return;
      const entries = dirtyEntriesFromState();
      if (!entries.length) return;
      savingRef.current = true;
      setSaveStatus("saving");
      try {
        await onSaveAllProductionCosts(entries);
        onProductionCostsSaved(entries);
        const nextSaved = { ...savedOtherCostsRowsRef.current };
        entries.forEach(({ productId, productionCost }) => {
          nextSaved[productId] = productionCost.other_costs_brl;
        });
        savedOtherCostsRowsRef.current = nextSaved;
        setSavedOtherCostsRows(nextSaved);
        const stillDirty = products.some((product) => {
          const draft = otherCostsRowsRef.current[product.id] ?? readOtherCosts(product);
          const saved = nextSaved[product.id] ?? readOtherCosts(product);
          return draft !== saved;
        });
        setSaveStatus(stillDirty ? "pending" : "saved");
      } catch {
        setSaveStatus("error");
      } finally {
        savingRef.current = false;
      }
    }, 800);
    return () => window.clearTimeout(timer);
  }, [otherCostsRows, savedOtherCostsRows, products, onSaveAllProductionCosts, onProductionCostsSaved]);

  function updateOtherCosts(productId: string, other_costs_brl: number) {
    setOtherCostsRows((current) => ({
      ...current,
      [productId]: other_costs_brl,
    }));
  }

  const tableRows = filteredProducts.map((product) => {
    const otherDraft = otherCostsRows[product.id] ?? readOtherCosts(product);
    const savedOther = savedOtherCostsRows[product.id] ?? readOtherCosts(product);
    const isDirty = otherDraft !== savedOther;
    const plates = readPrintPlates(product);
    const breakdown = computeProductionBreakdown(
      product,
      filaments,
      settings,
      exchangeReady ? usdBrl : null,
      otherDraft,
    );
    return {
      product,
      plates,
      breakdown,
      otherDraft,
      isDirty,
      totalGrams: totalFilamentGrams(breakdown, product),
    };
  });
  const visibleTableRows = tableRows.slice(0, renderedRowCount);
  const hasMoreRows = renderedRowCount < tableRows.length;

  useEffect(() => {
    setRenderedRowCount(COSTS_TABLE_ROW_BATCH);
    tableScrollRef.current?.scrollTo({ top: 0 });
  }, [searchQuery, products]);

  useEffect(() => {
    const container = tableScrollRef.current;
    if (!container || !hasMoreRows) return;

    function maybeLoadMore() {
      const node = tableScrollRef.current;
      if (!node) return;
      const nearBottom = node.scrollTop + node.clientHeight >= node.scrollHeight - COSTS_TABLE_SCROLL_THRESHOLD;
      if (nearBottom) {
        setRenderedRowCount((count) => Math.min(tableRows.length, count + COSTS_TABLE_ROW_BATCH));
      }
    }

    maybeLoadMore();
    container.addEventListener("scroll", maybeLoadMore, { passive: true });
    return () => container.removeEventListener("scroll", maybeLoadMore);
  }, [hasMoreRows, renderedRowCount, tableRows.length]);

  useEffect(() => {
    const el = tableScrollRef.current;
    if (!el || !hasMoreRows) return;
    if (el.scrollHeight <= el.clientHeight + 1) {
      setRenderedRowCount((count) => Math.min(tableRows.length, count + COSTS_TABLE_ROW_BATCH));
    }
  }, [hasMoreRows, renderedRowCount, tableRows.length, visibleTableRows.length]);

  const totals = tableRows.reduce(
    (acc, row) => ({
      filament: acc.filament + row.breakdown.filament_total_brl,
      energy: acc.energy + row.breakdown.energy_cost_brl,
      depreciation: acc.depreciation + row.breakdown.depreciation_cost_brl,
      maintenance: acc.maintenance + row.breakdown.maintenance_cost_brl,
      labor: acc.labor + row.breakdown.labor_cost_brl,
      other: acc.other + row.breakdown.other_costs_brl,
      production: acc.production + row.breakdown.production_subtotal_brl,
      ai: acc.ai + (row.breakdown.ai_cost_brl || 0),
      total: acc.total + (row.breakdown.total_brl || 0),
    }),
    { filament: 0, energy: 0, depreciation: 0, maintenance: 0, labor: 0, other: 0, production: 0, ai: 0, total: 0 },
  );

  return (
    <section className="costs-page">
      <div className="panel costs-table-panel">
        <div className="panel-title">
          <Coins size={18} />
          <h2>Custos de produção</h2>
        </div>
        <p className="settings-note section-intro">
          Filamento, gramas e tempo vêm das placas em Produtos → Impressão. Depreciação, manutenção e mão de obra usam as tarifas de Ajustes → Produção. Ajuste aqui apenas outros custos (embalagem, extras).
        </p>
        {!filaments.length && (
          <p className="settings-note">Cadastre filamentos em Ajustes → Produção para calcular o custo de material.</p>
        )}
        {settings.printer_purchase_price_brl <= 0 && (
          <p className="settings-note">Depreciação zerada: informe o valor da impressora em Ajustes → Produção.</p>
        )}
        {!exchangeReady && (
          <p className="settings-note">Câmbio indisponível: coluna IA pode aparecer só em dólar.</p>
        )}
        <div className="costs-filters">
          <label>
            <span className="costs-search-label"><Search size={14} /> Buscar</span>
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="SKU, nome, tag, categoria..."
            />
          </label>
          {searchQuery.trim() && (
            <button className="quiet-button filter-reset" type="button" onClick={() => setSearchQuery("")}>
              Limpar
            </button>
          )}
          <span className="costs-filter-meta">
            {filteredProducts.length === products.length
              ? `${products.length} produto(s)`
              : `${filteredProducts.length} de ${products.length} produto(s)`}
            {hasMoreRows ? ` · exibindo ${visibleTableRows.length}` : ""}
          </span>
        </div>
        <div className="costs-toolbar">
          <AutosaveIndicator status={saveStatus} />
        </div>
        <div className="costs-table-scroll" ref={tableScrollRef}>
          <table className="costs-table costs-table-detailed">
            <colgroup>
              <col className="col-product" />
              <col className="col-plates" />
              <col className="col-time" />
              <col className="col-grams" />
              <col className="col-filament" />
              <col className="col-money" />
              <col className="col-money" />
              <col className="col-money" />
              <col className="col-money" />
              <col className="col-money" />
              <col className="col-money" />
              <col className="col-money" />
              <col className="col-money" />
              <col className="col-money" />
              <col className="col-money" />
            </colgroup>
            <thead>
              <tr>
                <th>Produto</th>
                <th>Placas</th>
                <th>Tempo</th>
                <th>Gramas</th>
                <th>Filamento</th>
                <th>Mat. R$</th>
                <th>Energ. R$</th>
                <th>Deprec. R$</th>
                <th>Manut. R$</th>
                <th>M.O. R$</th>
                <th>Outros R$</th>
                <th>IA</th>
                <th>Produção R$</th>
                <th>R$/h</th>
                <th>Total R$</th>
              </tr>
            </thead>
            <tbody>
              {visibleTableRows.map(({ product, plates, breakdown, otherDraft, isDirty, totalGrams }) => (
                <tr key={product.id} className={isDirty ? "costs-row-dirty" : undefined}>
                  <td className="costs-product-cell">
                    <CostsProductCell product={product} />
                    {!plates.length && (
                      <small className="costs-plates-hint">Sem placas — cadastre em Produtos → Impressão</small>
                    )}
                  </td>
                  <td className="costs-readonly costs-num">
                    {breakdown.plate_count > 0 ? breakdown.plate_count : "—"}
                  </td>
                  <td className="costs-readonly">
                    {breakdown.print_time_label}
                  </td>
                  <td className="costs-readonly costs-num">
                    {totalGrams > 0 ? `${totalGrams} g` : "—"}
                  </td>
                  <td className="costs-readonly">
                    {formatFilamentSummary(breakdown)}
                  </td>
                  <td className="costs-readonly costs-num">
                    {formatBrl(breakdown.filament_total_brl)}
                  </td>
                  <td className="costs-readonly costs-num">
                    {formatBrl(breakdown.energy_cost_brl)}
                  </td>
                  <td className="costs-readonly costs-num">
                    {formatBrl(breakdown.depreciation_cost_brl)}
                  </td>
                  <td className="costs-readonly costs-num">
                    {formatBrl(breakdown.maintenance_cost_brl)}
                  </td>
                  <td className="costs-readonly costs-num">
                    {formatBrl(breakdown.labor_cost_brl)}
                  </td>
                  <td className="costs-input-num">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={otherDraft || ""}
                      onChange={(event) => updateOtherCosts(product.id, Number(event.target.value) || 0)}
                      disabled={busy}
                    />
                  </td>
                  <td className="costs-readonly costs-num">
                    {breakdown.ai_cost_brl !== null ? formatBrl(breakdown.ai_cost_brl) : formatUsd(breakdown.ai_cost_usd)}
                  </td>
                  <td className="costs-readonly costs-num">
                    {formatBrl(breakdown.production_subtotal_brl)}
                  </td>
                  <td className="costs-readonly costs-num">
                    {breakdown.cost_per_hour_brl !== null ? formatBrl(breakdown.cost_per_hour_brl) : "—"}
                  </td>
                  <td className="costs-readonly costs-num costs-total-cell">
                    <strong>{breakdown.total_brl !== null ? formatBrl(breakdown.total_brl) : "—"}</strong>
                  </td>
                </tr>
              ))}
              {hasMoreRows && (
                <tr className="costs-table-load-more">
                  <td colSpan={15}>
                    Role para carregar mais produtos ({visibleTableRows.length} de {tableRows.length})
                  </td>
                </tr>
              )}
            </tbody>
            <tfoot>
              <tr>
                <th colSpan={5}>Totais ({tableRows.length} produto(s))</th>
                <th className="costs-num">{formatBrl(Math.round(totals.filament * 100) / 100)}</th>
                <th className="costs-num">{formatBrl(Math.round(totals.energy * 100) / 100)}</th>
                <th className="costs-num">{formatBrl(Math.round(totals.depreciation * 100) / 100)}</th>
                <th className="costs-num">{formatBrl(Math.round(totals.maintenance * 100) / 100)}</th>
                <th className="costs-num">{formatBrl(Math.round(totals.labor * 100) / 100)}</th>
                <th className="costs-num">{formatBrl(Math.round(totals.other * 100) / 100)}</th>
                <th className="costs-num">{formatBrl(Math.round(totals.ai * 100) / 100)}</th>
                <th className="costs-num">{formatBrl(Math.round(totals.production * 100) / 100)}</th>
                <th />
                <th className="costs-num">{formatBrl(Math.round(totals.total * 100) / 100)}</th>
              </tr>
            </tfoot>
          </table>
          {!products.length && (
            <p className="empty table-empty">{productsLoading ? "Carregando produtos..." : "Nenhum produto nesta loja."}</p>
          )}
          {products.length > 0 && !filteredProducts.length && (
            <p className="empty table-empty">Nenhum produto corresponde à busca.</p>
          )}
        </div>
      </div>
    </section>
  );
}

function ProductsTab({
  batchProgress,
  busy,
  detailsOpen,
  filters,
  boardFilters,
  catalogRevision,
  freshProducts,
  onMoveProduct,
  imageOptions,
  jobs,
  listingDraft,
  listingDraftOwner,
  productNameDraft,
  products,
  selectedProduct,
  selectedProductIds,
  selectedColorVariations,
  matchedProductCount,
  listedCount,
  notListedCount,
  hasMoreProducts,
  productsLoading,
  productsLoaded,
  onLoadMoreProducts,
  onCreateManualProduct,
  onApproveProduct,
  onBatchGenerateImages,
  onBatchGenerateListings,
  onBatchDeleteProducts,
  onBatchSetListed,
  onCloseDetails,
  onDeleteModelAsset,
  onDeleteProduct,
  onFiltersChange,
  onGenerateColorVariations,
  onGenerateImages,
  onGenerateListing,
  onExportShopeeSheet,
  onReplaceShopeeTemplate,
  shopeeTemplate,
  onListingDraftChange,
  onOpenDetails,
  onDownloadProductFiles,
  onProductNameDraftChange,
  onRegenerateImage,
  onSaveListing,
  onUpdateProductListed,
  onUploadCoverImage,
  onUploadModelFile,
  onUploadStyleImage,
  onUploadColorImageManual,
  onCreateVariation,
  onUploadVariationImage,
  onDeleteVariation,
  onDeleteColorAsset,
  filaments,
  productionSettings,
  activeStoreProfile,
  onSelectedProductIdsChange,
  onSelectedColorVariationsChange,
  onSelectProduct,
}: {
  batchProgress: BatchProgress;
  busy: boolean;
  detailsOpen: boolean;
  filters: ProductFilters;
  boardFilters: ProductFilters;
  catalogRevision: number;
  freshProducts: Record<string, Product>;
  onMoveProduct: (product: Product, column: BoardColumnKey) => Promise<unknown>;
  imageOptions: ImageOptions;
  jobs: Job[];
  listingDraft: Listing | null;
  listingDraftOwner: string;
  productNameDraft: string;
  products: Product[];
  selectedProduct?: Product;
  selectedProductIds: string[];
  selectedColorVariations: string[];
  matchedProductCount: number;
  listedCount: number;
  notListedCount: number;
  hasMoreProducts: boolean;
  productsLoading: boolean;
  productsLoaded: boolean;
  onLoadMoreProducts: () => void;
  onCreateManualProduct: (name: string, sourceUrl?: string) => Promise<Product | undefined>;
  onApproveProduct: () => void;
  onBatchGenerateImages: (ids?: string[]) => void;
  onBatchGenerateListings: (ids?: string[]) => void;
  onBatchDeleteProducts: (ids?: string[]) => void;
  onBatchSetListed: (ids: string[], listed: boolean) => void;
  onCloseDetails: () => void;
  onDeleteModelAsset: (productId: string, assetId: string) => void;
  onDeleteProduct: (id?: string) => void;
  onFiltersChange: (filters: ProductFilters) => void;
  onGenerateColorVariations: (id?: string, colorVariations?: string[]) => void;
  onGenerateImages: (id?: string) => void;
  onGenerateListing: (id?: string) => void;
  onExportShopeeSheet: (ids?: string[]) => void;
  onReplaceShopeeTemplate: () => void;
  shopeeTemplate: ShopeeTemplateStatus | null;
  onListingDraftChange: (listing: Listing) => void;
  onOpenDetails: (id: string) => void;
  onDownloadProductFiles: (id?: string) => void;
  onProductNameDraftChange: (value: string) => void;
  onRegenerateImage: (productId: string, promptKey: string, extraPrompt: string) => void;
  onSaveListing: (draft: ListingSnapshot) => Promise<unknown>;
  onUpdateProductListed: (productId: string, listed: boolean) => void;
  onUploadCoverImage: (productId: string, file: File) => void;
  onUploadModelFile: (productId: string, file: File) => void;
  onUploadStyleImage: (productId: string, promptKey: string, file: File) => void;
  onUploadColorImageManual: (productId: string, name: string, file: File) => void;
  onCreateVariation: (productId: string, attribute: string, value: string) => Promise<unknown> | void;
  onUploadVariationImage: (productId: string, slug: string, file: File) => void;
  onDeleteVariation: (productId: string, slug: string) => void;
  onDeleteColorAsset: (productId: string, assetId: string) => void;
  filaments: FilamentSpool[];
  productionSettings: ProductionSettings | null;
  activeStoreProfile?: StoreProfile;
  onSelectedProductIdsChange: (ids: string[]) => void;
  onSelectedColorVariationsChange: (ids: string[]) => void;
  onSelectProduct: (id: string) => void;
}) {
  const [fullscreenAsset, setFullscreenAsset] = useState<Asset | null>(null);
  const [viewMode, setViewMode] = useState<ProductViewMode>(readProductViewMode);
  // Both views stay mounted once shown, so switching only flips visibility.
  const [boardMounted, setBoardMounted] = useState(viewMode === "board");
  const [imageExtraPrompts, setImageExtraPrompts] = useState<Record<string, string>>({});
  const [costDetailsOpen, setCostDetailsOpen] = useState(false);
  const [colorDialogOpen, setColorDialogOpen] = useState(false);
  const [manualProductDialogOpen, setManualProductDialogOpen] = useState(false);
  const [manualProductName, setManualProductName] = useState("");
  const [manualProductSourceUrl, setManualProductSourceUrl] = useState("");
  const [detailSection, setDetailSection] = useState<ProductDetailSection>("listing");
  const modelFileInputRef = useRef<HTMLInputElement>(null);
  const visibleCount = products.length;
  const visibleProductIds = products.map((product) => product.id);
  const allSelected = visibleProductIds.length > 0 && visibleProductIds.every((id) => selectedProductIds.includes(id));
  const progressValue = batchProgress ? Math.round((batchProgress.done / Math.max(batchProgress.total, 1)) * 100) : 0;
  const progressLabel = batchProgress ? `${batchProgress.label}: ${batchProgress.done}/${batchProgress.total}` : "";
  const boardView = viewMode === "board";
  // On the board, columns already split by status and publication, so only
  // the characteristic filters still apply.
  const quickFilters = boardView ? PRODUCT_QUICK_FILTERS.filter((filter) => filter.status === "all") : PRODUCT_QUICK_FILTERS;
  const activeQuickFilter = quickFilters.find((filter) =>
    filter.status === filters.status && filter.characteristic === filters.characteristic);
  const hasNarrowingFilters = filters.status !== "all" || filters.characteristic !== "all" || Boolean(filters.query.trim());
  const selectedCostEvents = selectedProduct ? productCostEvents(selectedProduct) : [];
  const selectedCostSummary = summarizeCostEvents(selectedCostEvents);

  useEffect(() => {
    setCostDetailsOpen(false);
    setDetailSection("listing");
  }, [selectedProduct?.id]);

  const selectedProductJobs = selectedProduct
    ? jobs.filter((job) => job.product_id === selectedProduct.id && jobActive(job))
    : [];
  const listingJob = selectedProductJobs.find((job) => job.type === "generate_listing");
  const imagesJob = selectedProductJobs.find((job) => job.type === "generate_images");

  const listingDraftReady = Boolean(selectedProduct && listingDraft && listingDraftOwner === selectedProduct.id);
  const listingDirty = Boolean(
    listingDraftReady
    && selectedProduct
    && listingDraft
    && (
      !listingsEqual(listingDraft, selectedProduct.listing)
      || productNameDraft.trim() !== selectedProduct.name
    ),
  );

  const listingAutosaveStatus = useAutosave<ListingSnapshot | null>({
    enabled: listingDraftReady,
    scope: listingDraftOwner,
    isDirty: listingDirty,
    snapshot: selectedProduct && listingDraft
      ? { productId: selectedProduct.id, listing: listingDraft, name: productNameDraft }
      : null,
    save: async (draft) => {
      if (draft) await onSaveListing(draft);
    },
  });


  function updateDraft<K extends keyof Listing>(key: K, value: Listing[K]) {
    if (!listingDraft) return;
    onListingDraftChange({ ...listingDraft, [key]: value });
  }

  function toggleProductSelection(productId: string) {
    if (selectedProductIds.includes(productId)) {
      onSelectedProductIdsChange(selectedProductIds.filter((id) => id !== productId));
      return;
    }
    onSelectedProductIdsChange([...selectedProductIds, productId]);
  }

  function toggleAllProducts() {
    if (allSelected) {
      onSelectedProductIdsChange(selectedProductIds.filter((id) => !visibleProductIds.includes(id)));
      return;
    }
    onSelectedProductIdsChange(Array.from(new Set([...selectedProductIds, ...visibleProductIds])));
  }

  function updateFilters(update: Partial<ProductFilters>) {
    onFiltersChange({ ...filters, ...update });
  }

  function changeViewMode(mode: ProductViewMode) {
    setViewMode(mode);
    if (mode === "board") setBoardMounted(true);
    try {
      window.localStorage.setItem(PRODUCT_VIEW_MODE_KEY, mode);
    } catch {
      /* The choice just won't be remembered. */
    }
    // Columns are statuses and publication, so those filters step aside.
    if (mode === "board" && (filters.status !== "all" || filters.publication !== "all")) {
      updateFilters({ status: "all", publication: "all", characteristic: activeQuickFilter?.status === "all" ? filters.characteristic : "all" });
    }
  }

  const cardHandlers = useStableHandlers<ProductCardHandlers>({
    open: onOpenDetails,
    toggleSelected: toggleProductSelection,
    toggleListed: (product) => onUpdateProductListed(product.id, !productListed(product)),
    generateListing: (productId) => {
      onSelectProduct(productId);
      onGenerateListing(productId);
    },
    generateImages: (productId) => {
      onSelectProduct(productId);
      onGenerateImages(productId);
    },
    remove: onDeleteProduct,
  });

  function toggleColorVariation(colorId: string) {
    if (selectedColorVariations.includes(colorId)) {
      onSelectedColorVariationsChange(selectedColorVariations.filter((id) => id !== colorId));
      return;
    }
    onSelectedColorVariationsChange([...selectedColorVariations, colorId]);
  }

  function generateSelectedColorVariations() {
    onGenerateColorVariations(undefined, selectedColorVariations);
    setColorDialogOpen(false);
  }

  function updateImageExtraPrompt(promptKey: string, value: string) {
    setImageExtraPrompts((current) => ({ ...current, [promptKey]: value }));
  }

  function openManualProductDialog() {
    setManualProductName("");
    setManualProductSourceUrl("");
    setManualProductDialogOpen(true);
  }

  async function submitManualProduct() {
    const created = await onCreateManualProduct(manualProductName, manualProductSourceUrl);
    if (created) setManualProductDialogOpen(false);
  }

  function handleModelFileSelected(file?: File) {
    if (!file || !selectedProduct) return;
    onUploadModelFile(selectedProduct.id, file);
  }

  const modelAssets = selectedProduct ? selectedProduct.assets.filter(isModelAsset) : [];
  const imageAssets = selectedProduct ? selectedProduct.assets.filter((asset) => !isModelAsset(asset)) : [];

  return (
    <section className="products-page">
      <div className="panel products-table-panel">
        <div className="panel-title">
          <ShoppingBag size={18} />
          <h2>Produtos</h2>
          <div className="panel-title-actions">
            <button
              className="primary panel-title-action"
              onClick={openManualProductDialog}
              disabled={busy}
            >
              <Plus size={16} /> Novo produto
            </button>
            <ActionMenu
              label="Mais opções"
              disabled={busy}
              items={[
                {
                  key: "shopee-template",
                  label: shopeeTemplate?.configured ? "Trocar template da Shopee" : "Enviar template da Shopee",
                  icon: <Upload size={15} />,
                  title: shopeeTemplate?.uploaded_at
                    ? `Template atual enviado em ${new Date(shopeeTemplate.uploaded_at).toLocaleString("pt-BR")}.`
                    : "Template de envio em massa baixado da Shopee",
                  onClick: onReplaceShopeeTemplate,
                },
              ]}
            />
          </div>
        </div>

        <div className="catalog-toolbar">
          <div className="view-toggle" role="group" aria-label="Visualização">
            <button
              className={boardView ? "" : "active"}
              aria-pressed={!boardView}
              onClick={() => changeViewMode("grid")}
              title="Grade"
            >
              <LayoutGrid size={16} /> Grade
            </button>
            <button
              className={boardView ? "active" : ""}
              aria-pressed={boardView}
              onClick={() => changeViewMode("board")}
              title="Quadro por etapa"
            >
              <Columns3 size={16} /> Quadro
            </button>
          </div>
          {!boardView && <div className="publication-tabs" role="tablist" aria-label="Publicação">
            {PUBLICATION_TABS.map((tab) => {
              const count = tab.value === "listed"
                ? listedCount
                : tab.value === "not_listed"
                  ? notListedCount
                  : listedCount + notListedCount;
              return (
                <button
                  key={tab.value}
                  className={filters.publication === tab.value ? "active" : ""}
                  role="tab"
                  aria-selected={filters.publication === tab.value}
                  onClick={() => updateFilters({ publication: tab.value })}
                >
                  {tab.label}
                  <span className="publication-tab-count">{productsLoaded ? count : "…"}</span>
                </button>
              );
            })}
          </div>}
          <label className="catalog-search">
            <Search size={16} />
            <input
              value={filters.query}
              onChange={(event) => updateFilters({ query: event.target.value })}
              placeholder="Buscar por nome, SKU, tag, categoria..."
              aria-label="Buscar produtos"
            />
            {filters.query && (
              <button className="catalog-search-clear" onClick={() => updateFilters({ query: "" })} aria-label="Limpar busca">
                <X size={14} />
              </button>
            )}
          </label>
        </div>

        <div className="catalog-subbar">
          <div className="catalog-chips">
            {quickFilters.map((filter) => {
              const active = activeQuickFilter?.key === filter.key;
              return (
                <button
                  key={filter.key}
                  className={active ? "catalog-chip active" : "catalog-chip"}
                  aria-pressed={active}
                  onClick={() => updateFilters(active
                    ? { status: "all", characteristic: "all" }
                    : { status: filter.status, characteristic: filter.characteristic })}
                >
                  {filter.label}
                </button>
              );
            })}
            {hasNarrowingFilters && (
              <button
                className="catalog-chip-reset"
                onClick={() => updateFilters({ query: "", status: "all", characteristic: "all" })}
              >
                Limpar filtros
              </button>
            )}
          </div>
          {!boardView && <label className="checkbox-row catalog-select-all">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAllProducts}
              disabled={!products.length || busy}
            />
            Selecionar {visibleCount < matchedProductCount ? `os ${visibleCount} carregados` : "todos"}
          </label>}
        </div>

        {batchProgress && (
          <div className="analysis-progress">
            <div>
              <strong>Progresso da ação em lote</strong>
              <span>{progressLabel}</span>
              {batchProgress.current && <small>{batchProgress.current}</small>}
            </div>
            <progress max={100} value={progressValue} />
          </div>
        )}

        {boardMounted && (
          <div hidden={!boardView}>
            <ProductBoard
              active={boardView}
              filters={boardFilters}
              revision={catalogRevision}
              freshProducts={freshProducts}
              busy={busy}
              selectedProductIds={selectedProductIds}
              activeProductId={detailsOpen ? selectedProduct?.id : undefined}
              onMoveProduct={onMoveProduct}
              handlers={cardHandlers}
            />
          </div>
        )}
        <div hidden={boardView}>
          <div className="product-grid">
            {products.map((product) => (
              <ProductTile
                key={product.id}
                product={product}
                busy={busy}
                selected={selectedProductIds.includes(product.id)}
                active={product.id === selectedProduct?.id && detailsOpen}
                handlers={cardHandlers}
              />
            ))}
            {!products.length && (
              <p className="empty table-empty">
                {!productsLoaded
                  ? "Carregando produtos..."
                  : filters.publication === "listed" && !hasNarrowingFilters
                    ? "Nenhum produto publicado ainda. Marque um produto como publicado no card ou em lote."
                    : "Nenhum produto encontrado com os filtros atuais."}
              </p>
            )}
          </div>
          {hasMoreProducts && (
            <LoadMoreSentinel
              className="product-list-load-more"
              enabled={!boardView && !productsLoading}
              onLoadMore={onLoadMoreProducts}
              rerunKey={products.length}
            >
              {productsLoading ? "Carregando mais produtos..." : `Role para carregar mais (${visibleCount} de ${matchedProductCount})`}
            </LoadMoreSentinel>
          )}
        </div>

        {selectedProductIds.length > 0 && (
          <div className="selection-bar" role="toolbar" aria-label="Ações para os selecionados">
            <div className="selection-bar-count">
              <strong>{selectedProductIds.length}</strong> selecionado(s)
              <button className="selection-bar-clear" onClick={() => onSelectedProductIdsChange([])} aria-label="Limpar seleção">
                <X size={14} />
              </button>
            </div>
            <div className="selection-bar-actions">
              <button onClick={() => onBatchGenerateListings()} disabled={busy}>
                <BrainCircuit size={15} /> Gerar anúncios
              </button>
              <button onClick={() => onBatchGenerateImages()} disabled={busy}>
                <ImagePlus size={15} /> Gerar imagens
              </button>
              <button onClick={() => onBatchSetListed(selectedProductIds, true)} disabled={busy}>
                <Check size={15} /> Marcar publicado
              </button>
              <button onClick={() => onBatchSetListed(selectedProductIds, false)} disabled={busy}>
                Marcar não publicado
              </button>
              <ActionMenu
                label="Exportar"
                trigger={<><Download size={15} /> Exportar <ChevronDown size={14} /></>}
                placement="up"
                disabled={busy}
                items={[
                  {
                    key: "shopee",
                    label: "Planilha Shopee",
                    icon: <FileSpreadsheet size={15} />,
                    title: shopeeTemplate?.configured
                      ? "Preenche o template de envio em massa da sua loja"
                      : "Na primeira vez, escolha o template de envio em massa baixado da Shopee",
                    onClick: () => onExportShopeeSheet(selectedProductIds),
                  },
                ]}
              />
              <button className="selection-bar-danger" onClick={() => onBatchDeleteProducts()} disabled={busy}>
                <Trash2 size={15} /> Apagar
              </button>
            </div>
          </div>
        )}
      </div>

      {detailsOpen && (
        <div className="details-backdrop">
          <div className="panel product-detail-panel details-panel">
            <div className="panel-title details-title">
              <div>
                <ShoppingBag size={18} />
                <h2>{selectedProduct?.name ?? "Detalhes do produto"}</h2>
              </div>
              <button className="close-button" onClick={onCloseDetails}>Fechar</button>
            </div>
        {selectedProduct ? (
          <>
            <div className="product-detail-header">
              <div className="product-detail-meta">
                <p className="eyebrow">{statusLabel(selectedProduct.status)}</p>
                <div className="sku-line">
                  <span>SKU</span>
                  <code>{productSku(selectedProduct) || "Será gerado na próxima ação"}</code>
                </div>
                <div className="product-source-actions">
                  {selectedProduct.source_url ? (
                    <a href={selectedProduct.source_url} target="_blank" rel="noreferrer">
                      Abrir link do produto
                    </a>
                  ) : (
                    <span>Produto sem link de origem</span>
                  )}
                  <button onClick={() => onDownloadProductFiles(selectedProduct.id)} disabled={busy}>
                    <Download size={14} /> Baixar arquivos (.zip)
                  </button>
                </div>
              </div>
              <div className="compact-actions">
                <AutosaveIndicator status={listingAutosaveStatus} />
                <button onClick={() => onGenerateListing()} disabled={busy || Boolean(listingJob)}>
                  {listingJob
                    ? <><Loader2 size={16} className="spin" /> {listingJob.status === "queued" ? "Anúncio na fila" : "Gerando anúncio"}</>
                    : <><BrainCircuit size={16} /> Gerar anúncio</>}
                </button>
                <button onClick={() => onGenerateImages()} disabled={busy || Boolean(imagesJob)}>
                  {imagesJob
                    ? <><Loader2 size={16} className="spin" /> {imagesJob.status === "queued" ? "Imagens na fila" : "Gerando imagens"}</>
                    : <><ImagePlus size={16} /> Imagens base</>}
                </button>
                <button onClick={onApproveProduct} disabled={busy || !listingDraft?.title || !listingDraft?.description}>
                  <BadgeCheck size={16} /> Aprovar
                </button>
              </div>
            </div>

            <div className="detail-tabs" role="tablist" aria-label="Seções do produto">
              <button
                className={detailSection === "listing" ? "active" : ""}
                onClick={() => setDetailSection("listing")}
                role="tab"
                aria-selected={detailSection === "listing"}
              >
                <BrainCircuit size={15} /> Anúncio
              </button>
              <button
                className={detailSection === "images" ? "active" : ""}
                onClick={() => setDetailSection("images")}
                role="tab"
                aria-selected={detailSection === "images"}
              >
                <ImagePlus size={15} /> Imagens
              </button>
              <button
                className={detailSection === "files" ? "active" : ""}
                onClick={() => setDetailSection("files")}
                role="tab"
                aria-selected={detailSection === "files"}
              >
                <PackageSearch size={15} /> Arquivos 3D
              </button>
              <button
                className={detailSection === "info" ? "active" : ""}
                onClick={() => setDetailSection("info")}
                role="tab"
                aria-selected={detailSection === "info"}
              >
                <BarChart3 size={15} /> Info
              </button>
            </div>

            {detailSection === "listing" && listingDraft && (
              <div className="detail-section">
                <p className="settings-note section-intro">
                  Edite o conteúdo comercial do anúncio. As alterações são salvas automaticamente. Aprove quando estiver pronto para exportar.
                </p>
                <div className="listing-editor">
                  <label className="full-span">
                    Nome do produto
                    <input value={productNameDraft} onChange={(event) => onProductNameDraftChange(event.target.value)} />
                  </label>
                  <label className="full-span">
                    Título do anúncio
                    <input value={listingDraft.title} onChange={(event) => updateDraft("title", event.target.value)} />
                  </label>
                  <label>
                    Categoria
                    <input value={listingDraft.category} onChange={(event) => updateDraft("category", event.target.value)} />
                  </label>
                  <label>
                    Preço (R$)
                    <input value={listingDraft.price} onChange={(event) => updateDraft("price", event.target.value)} />
                    <ListingProductionHint
                      product={selectedProduct}
                      listingPrice={listingDraft.price}
                      filaments={filaments}
                      productionSettings={productionSettings}
                      storeProfileId={activeStoreProfile?.id}
                    />
                  </label>
                  <label>
                    Estoque
                    <input
                      type="number"
                      min="0"
                      value={listingDraft.stock}
                      onChange={(event) => updateDraft("stock", Number(event.target.value))}
                    />
                  </label>
                  <label>
                    Peso (kg)
                    <input value={listingDraft.weight} onChange={(event) => updateDraft("weight", event.target.value)} />
                  </label>
                  <label className="full-span">
                    Dimensões do pacote
                    <input
                      value={listingDraft.parcel_size}
                      onChange={(event) => updateDraft("parcel_size", event.target.value)}
                      placeholder="L:10 W:10 H:10"
                    />
                  </label>
                  <label className="full-span">
                    Descrição
                    <textarea value={listingDraft.description} onChange={(event) => updateDraft("description", event.target.value)} />
                  </label>
                  <label className="full-span">
                    Palavras-chave
                    <KeywordsInput value={listingDraft.keywords} onChange={(keywords) => updateDraft("keywords", keywords)} />
                  </label>
                </div>
                {(listingDraft.keywords.length > 0 || selectedProduct.tags.length > 0) && (
                  <div className="chips">
                    {(listingDraft.keywords.length ? listingDraft.keywords : selectedProduct.tags).map((tag) => (
                      <span key={tag}>{tag}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {detailSection === "images" && (
              <div className="detail-section">
                <ProductImageGallery
                  busy={busy}
                  extraPrompts={imageExtraPrompts}
                  product={selectedProduct}
                  studioPrompts={imageOptions.studio_prompts}
                  onExtraPromptChange={updateImageExtraPrompt}
                  onOpenImage={setFullscreenAsset}
                  onRegenerateImage={onRegenerateImage}
                  onUploadCoverImage={onUploadCoverImage}
                  onUploadStyleImage={onUploadStyleImage}
                  onDeleteColorAsset={onDeleteColorAsset}
                />
                <div className="image-generation-options">
                  <div className="subsection-title">Variações de cor</div>
                  <div className="option-row">
                    <small>Gere cores por IA a partir da imagem base, ou adicione uma cor manualmente enviando a foto.</small>
                    <button
                      className="primary compact-primary"
                      onClick={() => setColorDialogOpen(true)}
                      disabled={busy || !imageOptions.colors.length}
                    >
                      <ImagePlus size={16} /> Gerar variações de cor
                    </button>
                  </div>
                  <ManualColorAdder
                    busy={busy}
                    onAdd={(name, file) => onUploadColorImageManual(selectedProduct.id, name, file)}
                  />
                </div>
                <VariationsManager
                  busy={busy}
                  product={selectedProduct}
                  imageVersion={selectedProduct.updated_at}
                  onCreate={(attribute, value) => onCreateVariation(selectedProduct.id, attribute, value)}
                  onUploadImage={(slug, file) => onUploadVariationImage(selectedProduct.id, slug, file)}
                  onDelete={(slug) => onDeleteVariation(selectedProduct.id, slug)}
                  onOpenImage={setFullscreenAsset}
                />
              </div>
            )}

            {detailSection === "files" && (
              <div className="detail-section">
                <p className="settings-note section-intro">
                  Gerencie os arquivos 3D do produto. O primeiro arquivo enviado vira o modelo principal; os demais ficam como adicionais.
                </p>
                <div className="model-files-toolbar">
                  <input
                    ref={modelFileInputRef}
                    accept=".3mf,.stl"
                    type="file"
                    hidden
                    onChange={(event) => {
                      handleModelFileSelected(event.target.files?.[0]);
                      event.currentTarget.value = "";
                    }}
                  />
                  <button className="primary" onClick={() => modelFileInputRef.current?.click()} disabled={busy}>
                    <Upload size={16} /> Adicionar arquivo 3D
                  </button>
                  <small>Formatos aceitos: .3mf e .stl (até 50 MB)</small>
                </div>
                <div className="model-files-list">
                  {modelAssets.map((asset) => (
                    <div className="model-file-row" key={asset.id}>
                      <div>
                        <strong>{modelAssetLabel(asset.kind)}</strong>
                        <code>{fileBasename(asset.path)}</code>
                      </div>
                      <div className="model-file-actions">
                        <a href={assetUrl(asset)} download={fileBasename(asset.path)}>
                          Baixar
                        </a>
                        <button
                          className="danger-button compact-danger"
                          onClick={() => onDeleteModelAsset(selectedProduct.id, asset.id)}
                          disabled={busy}
                        >
                          <Trash2 size={14} /> Remover
                        </button>
                      </div>
                    </div>
                  ))}
                  {!modelAssets.length && (
                    <p className="empty">Nenhum arquivo 3D ainda. Faça upload manual ou colete o produto no MakerWorld.</p>
                  )}
                  {typeof selectedProduct.metadata.model_download_error === "string" && selectedProduct.metadata.model_download_error && (
                    <p className="asset-error">Erro na coleta automática: {selectedProduct.metadata.model_download_error}</p>
                  )}
                </div>
                {imageAssets.length > 0 && (
                  <div className="asset-list compact-asset-list">
                    <h4>Outros arquivos</h4>
                    {imageAssets.map((asset) => (
                      <div className="asset-row" key={asset.id}>
                        <strong>{assetLabel(asset)}</strong>
                        <code>{fileBasename(asset.path)}</code>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {detailSection === "info" && (
              <div className="detail-section">
                <label className="listed-toggle info-listed-toggle">
                  <input
                    type="checkbox"
                    checked={productListed(selectedProduct)}
                    onChange={(event) => onUpdateProductListed(selectedProduct.id, event.target.checked)}
                    disabled={busy}
                  />
                  <span>Produto publicado</span>
                </label>
                <div className="image-generation-options">
                  <div className="subsection-title">Custo de criação (IA)</div>
                  <div className="cost-summary">
                    <div>
                      <strong>{formatUsd(productCostTotal(selectedProduct))}</strong>
                      <span>
                        {selectedCostEvents.length} registro(s) — Texto {formatUsd(selectedCostSummary.openRouter)} — Imagens {formatUsd(selectedCostSummary.kie)}
                      </span>
                    </div>
                    <button className="quiet-button" onClick={() => setCostDetailsOpen((open) => !open)} disabled={!selectedCostEvents.length}>
                      {costDetailsOpen ? "Recolher" : "Expandir"}
                    </button>
                  </div>
                  {costDetailsOpen && selectedCostEvents.length > 0 && (
                    <div className="cost-events">
                      {selectedCostEvents.map((event, index) => (
                        <div className="cost-event" key={event.id || `${event.provider}-${event.action}-${index}`}>
                          <div>
                            <strong>{displayText(event.action || "Ação IA")}</strong>
                            <small>
                              {displayText(event.provider || "IA")} · {displayText(event.model || "modelo")} · {displayText(event.source || "estimado")}
                            </small>
                          </div>
                          <span>{formatUsd(Number(event.cost_usd || 0))}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="empty">Selecione um produto capturado para gerar descrições, imagens e informações comerciais.</p>
        )}
          </div>
        </div>
      )}
      {fullscreenAsset && (
        <div className="image-fullscreen-backdrop" onClick={() => setFullscreenAsset(null)}>
          <div className="image-fullscreen-viewer" onClick={(event) => event.stopPropagation()}>
            <button className="close-button fullscreen-close" onClick={() => setFullscreenAsset(null)}>Fechar</button>
            <img src={assetUrl(fullscreenAsset, selectedProduct?.updated_at)} alt="" />
            <span>{assetLabel(fullscreenAsset)}</span>
          </div>
        </div>
      )}
      {colorDialogOpen && (
        <div className="profile-editor-backdrop" role="presentation" onClick={() => setColorDialogOpen(false)}>
          <div className="color-dialog" role="dialog" aria-modal="true" aria-labelledby="color-dialog-title" onClick={(event) => event.stopPropagation()}>
            <div className="profile-editor-header">
              <div>
                <p className="eyebrow">Kie/Qwen</p>
                <h2 id="color-dialog-title">Gerar variações de cor</h2>
              </div>
              <button className="primary ghost" onClick={() => setColorDialogOpen(false)}>
                Fechar
              </button>
            </div>
            <p className="settings-note">
              Selecione uma ou mais cores. Cada cor vai gerar uma imagem própria e um SKU derivado do SKU principal do produto.
            </p>
            <div className="color-options color-dialog-options">
              {imageOptions.colors.map((color) => (
                <label className="color-option" key={color.id}>
                  <input
                    type="checkbox"
                    checked={selectedColorVariations.includes(color.id)}
                    onChange={() => toggleColorVariation(color.id)}
                    disabled={busy}
                  />
                  <span>
                    <strong>{color.id.replace(/_/g, " ")}</strong>
                    <small>{color.description}</small>
                  </span>
                </label>
              ))}
            </div>
            <div className="profile-editor-footer">
              <button className="primary ghost" onClick={() => onSelectedColorVariationsChange([])} disabled={busy || !selectedColorVariations.length}>
                Limpar seleção
              </button>
              <button className="primary" onClick={generateSelectedColorVariations} disabled={busy || !selectedColorVariations.length}>
                <ImagePlus size={18} /> Gerar {selectedColorVariations.length || ""} cor(es)
              </button>
            </div>
          </div>
        </div>
      )}
      {manualProductDialogOpen && (
        <div className="confirm-backdrop" role="presentation" onClick={() => setManualProductDialogOpen(false)}>
          <div className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="manual-product-title" onClick={(event) => event.stopPropagation()}>
            <div>
              <p className="eyebrow">Produto manual</p>
              <h2 id="manual-product-title">Adicionar produto</h2>
              <p className="settings-note">Crie um produto sem coleta automática. Você pode enviar o 3MF e completar o anúncio depois.</p>
            </div>
            <div className="form-grid">
              <label className="full-span">
                Nome
                <input
                  value={manualProductName}
                  onChange={(event) => setManualProductName(event.target.value)}
                  placeholder="Ex.: Organizador de gaveta modular"
                  autoFocus
                />
              </label>
              <label className="full-span">
                Link de origem (opcional)
                <input
                  value={manualProductSourceUrl}
                  onChange={(event) => setManualProductSourceUrl(event.target.value)}
                  placeholder="https://..."
                />
              </label>
            </div>
            <div className="confirm-actions">
              <button className="quiet-button" onClick={() => setManualProductDialogOpen(false)} disabled={busy}>
                Cancelar
              </button>
              <button className="primary" onClick={() => void submitManualProduct()} disabled={busy || !manualProductName.trim()}>
                <Plus size={16} /> Criar produto
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function ProductImageGallery({
  busy,
  extraPrompts,
  product,
  studioPrompts,
  onExtraPromptChange,
  onOpenImage,
  onRegenerateImage,
  onUploadCoverImage,
  onUploadStyleImage,
  onDeleteColorAsset,
}: {
  busy: boolean;
  extraPrompts: Record<string, string>;
  product: Product;
  studioPrompts: Array<{ id: string; name: string }>;
  onExtraPromptChange: (promptKey: string, value: string) => void;
  onOpenImage: (asset: Asset) => void;
  onRegenerateImage: (productId: string, promptKey: string, extraPrompt: string) => void;
  onUploadCoverImage: (productId: string, file: File) => void;
  onUploadStyleImage: (productId: string, promptKey: string, file: File) => void;
  onDeleteColorAsset: (productId: string, assetId: string) => void;
}) {
  const coverFileInputRef = useRef<HTMLInputElement>(null);
  const images = getImageAssets(product);
  const capturedImages = images.filter((asset) => asset.kind === "cover_image");
  const baseImages = images.filter((asset) => asset.kind.startsWith("generated_"));
  const colorImages = images.filter((asset) => asset.kind.startsWith("color_"));
  const mainImage = getMainImageAsset(product);
  const previousImages = product.assets
    .filter(isPreviousVersion)
    .sort((left, right) => (right.created_at ?? "").localeCompare(left.created_at ?? ""));
  const colorSkus = productColorSkus(product);
  const colorLabels = productColorLabels(product);
  const imageVersion = product.updated_at;

  function handleCoverFileSelected(file?: File) {
    if (!file) return;
    onUploadCoverImage(product.id, file);
  }

  return (
    <div className="product-gallery">
      <div className="gallery-main">
        {mainImage ? (
          <button className="gallery-main-button" onClick={() => onOpenImage(mainImage)}>
            <img src={assetUrl(mainImage, imageVersion)} alt="" />
          </button>
        ) : (
          <div className="gallery-placeholder">
            <ImagePlus size={24} />
            <span>Nenhuma imagem salva ainda</span>
          </div>
        )}
      </div>
      <div className="gallery-groups">
        <div className="gallery-group">
          <div className="gallery-group-head">
            <div className="gallery-group-title">Capturada</div>
            <button
              className="gallery-cover-upload"
              disabled={busy}
              onClick={() => coverFileInputRef.current?.click()}
              title="Substituir a foto de capa capturada"
            >
              <Upload size={14} /> Trocar capa
            </button>
            <input
              ref={coverFileInputRef}
              accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
              hidden
              type="file"
              onChange={(event) => {
                handleCoverFileSelected(event.target.files?.[0]);
                event.currentTarget.value = "";
              }}
            />
          </div>
          <GalleryGroup
            assets={capturedImages}
            bare
            emptyText="Envie uma capa ou colete o produto no MakerWorld."
            imageVersion={imageVersion}
            onOpenImage={onOpenImage}
            title=""
          />
          <small className="gallery-cover-note">
            A IA recebe a capa por um link público do próprio app.
          </small>
        </div>
        <BaseStyleGallery
          assets={baseImages}
          busy={busy}
          extraPrompts={extraPrompts}
          imageVersion={imageVersion}
          productId={product.id}
          styles={studioPrompts}
          onExtraPromptChange={onExtraPromptChange}
          onOpenImage={onOpenImage}
          onRegenerateImage={onRegenerateImage}
          onUploadStyleImage={onUploadStyleImage}
        />
        <GalleryGroup
          allowRegenerate
          assets={colorImages}
          busy={busy}
          emptyText="Escolha cores e use Gerar cores."
          extraPrompts={extraPrompts}
          imageVersion={imageVersion}
          productId={product.id}
          skuByKey={colorSkus}
          labelByKey={colorLabels}
          title="Variações de cor"
          onDeleteAsset={(assetId) => onDeleteColorAsset(product.id, assetId)}
          onExtraPromptChange={onExtraPromptChange}
          onOpenImage={onOpenImage}
          onRegenerateImage={onRegenerateImage}
        />
        {previousImages.length > 0 && (
          <GalleryGroup
            assets={previousImages}
            emptyText=""
            imageVersion={imageVersion}
            labelFor={previousVersionLabel}
            title={`Versões anteriores (${previousImages.length})`}
            onOpenImage={onOpenImage}
          />
        )}
      </div>
    </div>
  );
}

function previousVersionLabel(asset: Asset): string {
  const label = assetLabel(asset).replace(/ \(anterior\)$/, "");
  if (!asset.created_at) return label;
  const created = new Date(asset.created_at).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  return `${label} · ${created}`;
}

function BaseStyleGallery({
  assets,
  busy,
  extraPrompts,
  imageVersion,
  productId,
  styles,
  onExtraPromptChange,
  onOpenImage,
  onRegenerateImage,
  onUploadStyleImage,
}: {
  assets: Asset[];
  busy: boolean;
  extraPrompts: Record<string, string>;
  imageVersion?: string;
  productId: string;
  styles: Array<{ id: string; name: string }>;
  onExtraPromptChange: (promptKey: string, value: string) => void;
  onOpenImage: (asset: Asset) => void;
  onRegenerateImage: (productId: string, promptKey: string, extraPrompt: string) => void;
  onUploadStyleImage: (productId: string, promptKey: string, file: File) => void;
}) {
  const [activeRegenerateKey, setActiveRegenerateKey] = useState("");
  const slots = styles.length
    ? styles
    : assets.map((asset) => {
        const id = asset.kind.replace(/^generated_/, "");
        return { id, name: id.replace(/_/g, " ") };
      });

  return (
    <div className="gallery-group">
      <div className="gallery-group-title">Imagens base IA</div>
      <div className="gallery-strip">
        {slots.map((style) => {
          const asset = assets.find((item) => item.kind === `generated_${style.id}`);
          const regenerateOpen = activeRegenerateKey === style.id;
          return (
            <div className="gallery-thumb" key={style.id}>
              <div className="thumb-image-frame">
                {asset ? (
                  <button className="thumb-open" onClick={() => onOpenImage(asset)}>
                    <img src={assetUrl(asset, imageVersion, 384)} alt="" loading="lazy" decoding="async" />
                  </button>
                ) : (
                  <div className="thumb-empty">
                    <ImagePlus size={20} />
                  </div>
                )}
                <label className="thumb-upload" title="Enviar imagem manual">
                  <Upload size={12} />
                  <input
                    type="file"
                    hidden
                    accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                    disabled={busy}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) onUploadStyleImage(productId, style.id, file);
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
                <button
                  aria-expanded={regenerateOpen}
                  aria-label={`Abrir geração por IA para ${style.name}`}
                  className="thumb-ai-toggle"
                  disabled={busy}
                  onClick={() => setActiveRegenerateKey(regenerateOpen ? "" : style.id)}
                  title="IA: gerar ou recriar imagem"
                >
                  IA
                </button>
              </div>
              <span>{style.name}</span>
              {regenerateOpen && (
                <div className="thumb-regenerate">
                  <input
                    value={extraPrompts[style.id] || ""}
                    onChange={(event) => onExtraPromptChange(style.id, event.target.value)}
                    placeholder="Prompt extra"
                    disabled={busy}
                  />
                  <button
                    title={asset ? "Recriar esta imagem" : "Gerar esta imagem"}
                    onClick={() => onRegenerateImage(productId, style.id, extraPrompts[style.id] || "")}
                    disabled={busy}
                  >
                    {asset ? "Recriar" : "Gerar"}
                  </button>
                </div>
              )}
            </div>
          );
        })}
        {!slots.length && (
          <div className="gallery-note">Configure os estilos de imagem em Ajustes para liberar os slots.</div>
        )}
      </div>
    </div>
  );
}

function ManualColorAdder({
  busy,
  onAdd,
}: {
  busy: boolean;
  onAdd: (name: string, file: File) => void;
}) {
  const [name, setName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFile(file?: File) {
    if (!file) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    onAdd(trimmed, file);
    setName("");
  }

  const ready = Boolean(name.trim());

  return (
    <div className="manual-variation-add">
      <input
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Nome da cor (ex.: Azul Bebê)"
        disabled={busy}
      />
      <button
        className="compact-primary"
        disabled={busy || !ready}
        onClick={() => fileInputRef.current?.click()}
        title={ready ? "Enviar foto da cor" : "Informe o nome da cor primeiro"}
      >
        <Upload size={14} /> Adicionar cor (foto)
      </button>
      <input
        ref={fileInputRef}
        accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
        hidden
        type="file"
        onChange={(event) => {
          handleFile(event.target.files?.[0]);
          event.currentTarget.value = "";
        }}
      />
    </div>
  );
}

function VariationsManager({
  busy,
  product,
  imageVersion,
  onCreate,
  onUploadImage,
  onDelete,
  onOpenImage,
}: {
  busy: boolean;
  product: Product;
  imageVersion?: string;
  onCreate: (attribute: string, value: string) => void;
  onUploadImage: (slug: string, file: File) => void;
  onDelete: (slug: string) => void;
  onOpenImage: (asset: Asset) => void;
}) {
  const [attribute, setAttribute] = useState("Tamanho");
  const [value, setValue] = useState("");
  const variations = productManualVariations(product);

  const canCreate = Boolean(attribute.trim() && value.trim());

  function handleCreate() {
    if (!canCreate) return;
    onCreate(attribute.trim(), value.trim());
    setValue("");
  }

  return (
    <div className="image-generation-options variations-manager">
      <div className="subsection-title">Variações (Tamanho ou outras)</div>
      <small>Crie variações manuais com o nome que quiser e envie uma foto para cada uma.</small>
      <div className="variation-create-row">
        <input
          value={attribute}
          onChange={(event) => setAttribute(event.target.value)}
          placeholder="Tipo (ex.: Tamanho)"
          disabled={busy}
        />
        <input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Valor (ex.: G)"
          disabled={busy}
          onKeyDown={(event) => {
            if (event.key === "Enter") handleCreate();
          }}
        />
        <button className="compact-primary" disabled={busy || !canCreate} onClick={handleCreate}>
          <Plus size={14} /> Adicionar variação
        </button>
      </div>
      <div className="gallery-strip">
        {variations.map((variation) => {
          const asset = product.assets.find((item) => item.kind === `variation_${variation.id}`);
          return (
            <div className="gallery-thumb" key={variation.id}>
              <div className="thumb-image-frame">
                {asset ? (
                  <button className="thumb-open" onClick={() => onOpenImage(asset)}>
                    <img src={assetUrl(asset, imageVersion, 384)} alt="" loading="lazy" decoding="async" />
                  </button>
                ) : (
                  <div className="thumb-empty">
                    <ImagePlus size={20} />
                  </div>
                )}
                <label className="thumb-upload" title="Enviar foto da variação">
                  <Upload size={12} />
                  <input
                    type="file"
                    hidden
                    accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                    disabled={busy}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) onUploadImage(variation.id, file);
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
                <button
                  aria-label={`Remover ${variation.attribute} ${variation.value}`}
                  className="thumb-delete"
                  disabled={busy}
                  onClick={() => onDelete(variation.id)}
                  title="Remover variação"
                >
                  <Trash2 size={12} />
                </button>
              </div>
              <span>{variation.attribute}: {variation.value}</span>
              {variation.sku && <code className="thumb-sku">{variation.sku}</code>}
            </div>
          );
        })}
        {!variations.length && (
          <div className="gallery-note">Nenhuma variação manual ainda. Crie uma acima.</div>
        )}
      </div>
    </div>
  );
}

function GalleryGroup({
  allowRegenerate = false,
  assets,
  bare = false,
  busy = false,
  emptyText,
  extraPrompts = {},
  imageVersion,
  productId,
  skuByKey = {},
  labelByKey = {},
  labelFor,
  onDeleteAsset,
  onExtraPromptChange,
  onOpenImage,
  onRegenerateImage,
  title,
}: {
  allowRegenerate?: boolean;
  assets: Asset[];
  bare?: boolean;
  busy?: boolean;
  emptyText: string;
  extraPrompts?: Record<string, string>;
  imageVersion?: string;
  productId?: string;
  skuByKey?: Record<string, string>;
  labelByKey?: Record<string, string>;
  labelFor?: (asset: Asset) => string;
  onDeleteAsset?: (assetId: string) => void;
  onExtraPromptChange?: (promptKey: string, value: string) => void;
  onOpenImage: (asset: Asset) => void;
  onRegenerateImage?: (productId: string, promptKey: string, extraPrompt: string) => void;
  title: string;
}) {
  const [activeRegenerateKey, setActiveRegenerateKey] = useState("");

  const content = (
    <>
      {title ? <div className="gallery-group-title">{title}</div> : null}
      <div className="gallery-strip">
        {assets.map((asset) => {
          const promptKey = asset.kind.replace(/^generated_/, "");
          const slugKey = asset.kind.replace(/^color_/, "");
          const label = labelFor?.(asset)
            || labelByKey[slugKey]
            || asset.kind.replace(/^generated_/, "").replace(/^color_/, "").replace(/_/g, " ");
          const sku = skuByKey[slugKey];
          const regenerateOpen = activeRegenerateKey === promptKey;

          return (
            <div className="gallery-thumb" key={asset.id}>
              <div className="thumb-image-frame">
                <button className="thumb-open" onClick={() => onOpenImage(asset)}>
                  <img src={assetUrl(asset, imageVersion, 384)} alt="" loading="lazy" decoding="async" />
                </button>
                {allowRegenerate && productId && onRegenerateImage && onExtraPromptChange && (
                  <button
                    aria-expanded={regenerateOpen}
                    aria-label={`Abrir recriação por IA para ${label}`}
                    className="thumb-ai-toggle"
                    disabled={busy}
                    onClick={() => setActiveRegenerateKey(regenerateOpen ? "" : promptKey)}
                    title="IA: recriar imagem"
                  >
                    IA
                  </button>
                )}
                {onDeleteAsset && (
                  <button
                    aria-label={`Remover ${label}`}
                    className="thumb-delete"
                    disabled={busy}
                    onClick={() => onDeleteAsset(asset.id)}
                    title="Remover variação"
                  >
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
              <span>{label}</span>
              {sku && <code className="thumb-sku">{sku}</code>}
              {allowRegenerate && productId && onRegenerateImage && onExtraPromptChange && regenerateOpen && (
                <div className="thumb-regenerate">
                  <input
                    value={extraPrompts[promptKey] || ""}
                    onChange={(event) => onExtraPromptChange(promptKey, event.target.value)}
                    placeholder="Prompt extra"
                    disabled={busy}
                  />
                  <button
                    title="Recriar esta imagem"
                    onClick={() => onRegenerateImage(productId, promptKey, extraPrompts[promptKey] || "")}
                    disabled={busy}
                  >
                    Recriar
                  </button>
                </div>
              )}
            </div>
          );
        })}
        {!assets.length && <div className="gallery-note">{emptyText}</div>}
      </div>
    </>
  );

  if (bare) return content;
  return <div className="gallery-group">{content}</div>;
}

function SettingsTab({
  isAdmin,
  uiTheme,
  onSaveUiTheme,
  imageOptions,
  openRouterApiKeyDraft,
  openRouterModelDraft,
  kieApiKeyDraft,
  kieImageModelDraft,
  useCodexImageGenDraft,
  codexBinDraft,
  publicAppUrlDraft,
  settings,
  storeProfileDraft,
  storeProfiles,
  onCreateStoreProfile,
  onDownloadAppBackup,
  onOpenRouterApiKeyChange,
  onOpenRouterModelChange,
  onKieApiKeyChange,
  onKieImageModelChange,
  onUseCodexImageGenChange,
  onCodexBinChange,
  onPublicAppUrlChange,
  onSaveOpenRouterSettings,
  onClearIntegrationSecrets,
  onSaveStoreProfile,
  onSaveImageColorOptions,
  onSelectedStoreProfileChange,
  onRestoreAppBackup,
  onStoreProfileDraftChange,
  onUploadStoreProfilePhoto,
  filaments,
  productionSettings,
  onDeleteFilament,
  onSaveFilament,
  onSaveProductionSettings,
  onWrapAction,
}: {
  isAdmin: boolean;
  uiTheme: UiThemePreference;
  onSaveUiTheme: (theme: UiThemePreference) => Promise<void>;
  imageOptions: ImageOptions;
  openRouterApiKeyDraft: string;
  openRouterModelDraft: string;
  kieApiKeyDraft: string;
  kieImageModelDraft: string;
  useCodexImageGenDraft: boolean;
  codexBinDraft: string;
  publicAppUrlDraft: string;
  settings: SettingsPayload | null;
  storeProfileDraft: StoreProfile | null;
  storeProfiles: StoreProfile[];
  onCreateStoreProfile: (credentials: { name: string; username: string; password: string }) => Promise<unknown> | void;
  onDownloadAppBackup: () => Promise<unknown> | void;
  onOpenRouterApiKeyChange: (value: string) => void;
  onOpenRouterModelChange: (value: string) => void;
  onKieApiKeyChange: (value: string) => void;
  onKieImageModelChange: (value: string) => void;
  onUseCodexImageGenChange: (value: boolean) => void;
  onCodexBinChange: (value: string) => void;
  onPublicAppUrlChange: (value: string) => void;
  onSaveOpenRouterSettings: (draft: IntegrationDrafts) => Promise<unknown>;
  onClearIntegrationSecrets: () => void;
  onSaveStoreProfile: (draft: StoreProfile) => Promise<unknown>;
  onSaveImageColorOptions: (colors: ImageOptions["colors"]) => Promise<unknown>;
  onSelectedStoreProfileChange: (value: string) => void;
  onRestoreAppBackup: (file: File) => Promise<unknown> | void;
  onStoreProfileDraftChange: (value: StoreProfile) => void;
  onUploadStoreProfilePhoto: (profileId: string, file: File) => Promise<unknown> | void;
  filaments: FilamentSpool[];
  productionSettings: ProductionSettings | null;
  onDeleteFilament: (filamentId: string) => Promise<unknown>;
  onSaveFilament: (payload: {
    id?: string;
    name: string;
    material: string;
    color: string;
    spool_price_brl: number;
    spool_weight_g: number;
    notes: string;
  }) => Promise<FilamentSpool | undefined>;
  onSaveProductionSettings: (payload: {
    electricity_kwh_price_brl: number;
    printer_power_watts: number;
    printer_purchase_price_brl: number;
    printer_useful_life_hours: number;
    maintenance_cost_per_hour_brl: number;
    labor_cost_per_hour_brl: number;
  }) => Promise<unknown>;
  onWrapAction: <T,>(label: string, action: () => Promise<T>) => Promise<T | undefined>;
}) {
  const [profileEditorOpen, setProfileEditorOpen] = useState(false);
  const [newStoreOpen, setNewStoreOpen] = useState(false);
  const [newStoreName, setNewStoreName] = useState("");
  const [newStoreUsername, setNewStoreUsername] = useState("");
  const [newStorePassword, setNewStorePassword] = useState("");
  const [integrationEditorOpen, setIntegrationEditorOpen] = useState(false);
  const [integrationSecretsVisible, setIntegrationSecretsVisible] = useState(false);
  const [loadingIntegrationSecrets, setLoadingIntegrationSecrets] = useState(false);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("store");
  const [colorDrafts, setColorDrafts] = useState<ImageOptions["colors"]>(imageOptions.colors);
  const [filamentDrafts, setFilamentDrafts] = useState<FilamentSpool[]>(filaments);
  const [electricityPrice, setElectricityPrice] = useState("0.85");
  const [printerPower, setPrinterPower] = useState("200");
  const [printerPurchasePrice, setPrinterPurchasePrice] = useState("0");
  const [printerUsefulLifeHours, setPrinterUsefulLifeHours] = useState("5000");
  const [maintenanceCostPerHour, setMaintenanceCostPerHour] = useState("0");
  const [laborCostPerHour, setLaborCostPerHour] = useState("0");
  const uiThemePreference = uiTheme;
  const [customAccentDraft, setCustomAccentDraft] = useState(
    () => uiTheme.accent ?? UI_THEME_PRESETS[0].tokens.greenDark,
  );

  // The colour picker fires on every move; only the colour it stops on is saved.
  const themeSaveTimer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(themeSaveTimer.current), []);
  function queueThemeSave(next: UiThemePreference) {
    window.clearTimeout(themeSaveTimer.current);
    themeSaveTimer.current = window.setTimeout(() => void onSaveUiTheme(next), 400);
  }

  function selectUiTheme(id: UiThemeId) {
    const next = normalizeUiThemePreference(id === "custom"
      ? { id: "custom", accent: customAccentDraft }
      : { id: id as Exclude<UiThemeId, "custom"> });
    showUiTheme(next);
    queueThemeSave(next);
  }

  function applyCustomAccent(accent: string) {
    setCustomAccentDraft(accent);
    const next = normalizeUiThemePreference({ id: "custom", accent });
    if (next.id !== "custom") return;  // Not a colour yet (still typing).
    showUiTheme(next);
    queueThemeSave(next);
  }

  // A newer server copy (usually an autosave reply) only replaces drafts the
  // user has not edited since the previous copy, so typing is never undone.
  const filamentBaseRef = useRef(filaments);
  // Temporary row id -> id the server gave it, and back (rows keep their React key).
  const createdFilamentIdsRef = useRef<Record<string, string>>({});
  const filamentRowKeysRef = useRef<Record<string, string>>({});
  useEffect(() => {
    const base = filamentBaseRef.current;
    filamentBaseRef.current = filaments;
    setFilamentDrafts((current) => {
      const resolved = current.map((item) => {
        const createdId = createdFilamentIdsRef.current[item.id];
        return createdId ? { ...item, id: createdId } : item;
      });
      return filamentDraftsEqual(resolved, base) ? filaments : resolved;
    });
  }, [filaments]);

  const productionBaseRef = useRef<ProductionSettings | null>(null);
  useEffect(() => {
    if (!productionSettings) return;
    const base = productionBaseRef.current;
    productionBaseRef.current = productionSettings;
    const sync = (
      setter: React.Dispatch<React.SetStateAction<string>>,
      key: keyof ProductionDrafts["settings"],
      fallback: number,
    ) => setter((current) =>
      base && parseDecimal(current) !== Number(base[key] ?? fallback) ? current : String(productionSettings[key] ?? fallback));
    sync(setElectricityPrice, "electricity_kwh_price_brl", 0);
    sync(setPrinterPower, "printer_power_watts", 0);
    sync(setPrinterPurchasePrice, "printer_purchase_price_brl", 0);
    sync(setPrinterUsefulLifeHours, "printer_useful_life_hours", 5000);
    sync(setMaintenanceCostPerHour, "maintenance_cost_per_hour_brl", 0);
    sync(setLaborCostPerHour, "labor_cost_per_hour_brl", 0);
  }, [productionSettings]);

  const colorBaseRef = useRef(imageOptions.colors);
  useEffect(() => {
    const base = colorBaseRef.current;
    colorBaseRef.current = imageOptions.colors;
    setColorDrafts((current) => (imageColorsEqual(current, base) ? imageOptions.colors : current));
  }, [imageOptions.colors]);

  useEffect(() => {
    if (!integrationEditorOpen) onClearIntegrationSecrets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [integrationEditorOpen]);

  async function createStoreLogin(event: React.FormEvent) {
    event.preventDefault();
    await onCreateStoreProfile({ name: newStoreName, username: newStoreUsername, password: newStorePassword });
    setNewStoreOpen(false);
    setNewStoreName("");
    setNewStoreUsername("");
    setNewStorePassword("");
  }

  async function saveAndCloseStoreProfile() {
    setProfileEditorOpen(false);
  }

  async function revealIntegrationSecrets() {
    if (integrationSecretsVisible) {
      setIntegrationSecretsVisible(false);
      return;
    }
    setLoadingIntegrationSecrets(true);
    try {
      const secrets = await api<SettingsSecrets>("/api/settings/secrets");
      onOpenRouterApiKeyChange(secrets.openrouter_api_key || "");
      onOpenRouterModelChange(secrets.openrouter_model || openRouterModelDraft);
      onKieApiKeyChange(secrets.kie_api_key || "");
      onKieImageModelChange(secrets.kie_image_model || kieImageModelDraft || "qwen/image-edit");
      onCodexBinChange(secrets.codex_bin || codexBinDraft || "");
      setIntegrationSecretsVisible(true);
    } finally {
      setLoadingIntegrationSecrets(false);
    }
  }

  async function saveAndCloseIntegrations() {
    setIntegrationSecretsVisible(false);
    setIntegrationEditorOpen(false);
  }

  function openIntegrationEditor() {
    setIntegrationEditorOpen(true);
    setIntegrationSecretsVisible(false);
  }

  function updateStoreDraft<K extends keyof StoreProfile>(key: K, value: StoreProfile[K]) {
    if (!storeProfileDraft) return;
    onStoreProfileDraftChange({ ...storeProfileDraft, [key]: value });
  }

  function updateStoreImagePrompt(promptId: string, value: string) {
    if (!storeProfileDraft) return;
    onStoreProfileDraftChange({
      ...storeProfileDraft,
      image_prompts: {
        ...(storeProfileDraft.image_prompts || {}),
        [promptId]: value,
      },
    });
  }

  function toggleStoreImagePrompt(promptId: string, enabled: boolean) {
    if (!storeProfileDraft) return;
    const disabled = new Set(storeProfileDraft.disabled_image_prompts || []);
    if (enabled) disabled.delete(promptId);
    else disabled.add(promptId);
    onStoreProfileDraftChange({
      ...storeProfileDraft,
      disabled_image_prompts: [...disabled],
    });
  }

  function handleStorePhotoChange(profileId: string, file?: File) {
    if (!file) return;
    onUploadStoreProfilePhoto(profileId, file);
  }

  function handleBackupUpload(file?: File) {
    if (!file) return;
    onRestoreAppBackup(file);
  }

  function updateColorDraft(index: number, key: "id" | "description", value: string) {
    setColorDrafts((current) => current.map((color, itemIndex) => itemIndex === index ? { ...color, [key]: value } : color));
  }

  function addColorDraft() {
    setColorDrafts((current) => [...current, { id: "Nova_Cor", description: "Descreva a cor, material e acabamento para o Kie/Qwen" }]);
  }

  function removeColorDraft(index: number) {
    setColorDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function updateFilamentDraft(index: number, key: keyof FilamentSpool, value: string) {
    setFilamentDrafts((current) =>
      current.map((item, itemIndex) => {
        if (itemIndex !== index) return item;
        if (key === "spool_price_brl" || key === "spool_weight_g") {
          return { ...item, [key]: Number(value.replace(",", ".")) || 0 };
        }
        return { ...item, [key]: value };
      }),
    );
  }

  function addFilamentDraftRow() {
    if (!storeProfileDraft?.id) return;
    setFilamentDrafts((current) => [
      ...current,
      {
        id: `${DRAFT_FILAMENT_PREFIX}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
        store_profile_id: storeProfileDraft.id,
        name: "",
        material: "PLA",
        color: "",
        spool_price_brl: 0,
        spool_weight_g: 1000,
        notes: "",
        created_at: "",
        updated_at: "",
      },
    ]);
  }

  // Saves only what differs from the server copy.
  async function saveProductionSection(draft: ProductionDrafts) {
    const current = productionSettings ?? defaultProductionSettings("");
    const settingsChanged = (Object.keys(draft.settings) as Array<keyof ProductionDrafts["settings"]>)
      .some((key) => draft.settings[key] !== Number(current[key]));
    if (settingsChanged || !productionSettings) await onSaveProductionSettings(draft.settings);
    for (const item of draft.filaments) {
      if (!item.name.trim()) continue;
      const temporary = item.id.startsWith(DRAFT_FILAMENT_PREFIX);
      const id = temporary ? createdFilamentIdsRef.current[item.id] : item.id;
      const saved = filaments.find((spool) => spool.id === id);
      if (saved && filamentDraftsEqual([{ ...item, id: saved.id }], [saved])) continue;
      const result = await onSaveFilament({
        id: id || undefined,
        name: item.name.trim(),
        material: item.material.trim() || "PLA",
        color: item.color || "",
        spool_price_brl: Number(item.spool_price_brl) || 0,
        spool_weight_g: Number(item.spool_weight_g) || 1000,
        notes: item.notes || "",
      });
      if (temporary && !id && result) {
        createdFilamentIdsRef.current[item.id] = result.id;
        filamentRowKeysRef.current[result.id] = item.id;
      }
    }
  }

  const savedProfile = storeProfiles.find((profile) => profile.id === storeProfileDraft?.id);
  const profileDirty = Boolean(
    profileEditorOpen && storeProfileDraft && savedProfile && !storeProfilesEqual(storeProfileDraft, savedProfile),
  );
  const integrationDirty = Boolean(
    integrationEditorOpen && settings && (
      openRouterModelDraft !== (settings.integrations.openrouter_model || "qwen/qwen3.5-flash-02-23")
      || kieImageModelDraft !== (settings.integrations.kie_image_model || "qwen/image-edit")
      || useCodexImageGenDraft !== Boolean(settings.integrations.codex_image_gen)
      || codexBinDraft !== (settings.integrations.codex_bin || "")
      || Boolean(openRouterApiKeyDraft.trim())
      || Boolean(kieApiKeyDraft.trim())
      || publicAppUrlDraft !== (settings.integrations.public_app_url || "")
    ),
  );
  const colorsDirty = settingsSection === "colors" && !imageColorsEqual(colorDrafts, imageOptions.colors);
  const productionDirty = settingsSection === "production" && (
    !productionSettingsDraftEqual(
      electricityPrice,
      printerPower,
      printerPurchasePrice,
      printerUsefulLifeHours,
      maintenanceCostPerHour,
      laborCostPerHour,
      productionSettings,
    )
    || !filamentDraftsEqual(filamentDrafts, filaments)
  );

  const profileAutosaveStatus = useAutosave<StoreProfile | null>({
    enabled: profileEditorOpen,
    scope: storeProfileDraft?.id ?? "",
    isDirty: profileDirty,
    snapshot: storeProfileDraft,
    save: async (draft) => {
      if (draft) await onSaveStoreProfile(draft);
    },
  });
  const integrationAutosaveStatus = useAutosave<IntegrationDrafts>({
    enabled: integrationEditorOpen,
    scope: "integrations",
    isDirty: integrationDirty,
    snapshot: {
      openrouter_api_key: openRouterApiKeyDraft,
      openrouter_model: openRouterModelDraft,
      kie_api_key: kieApiKeyDraft,
      kie_image_model: kieImageModelDraft,
      use_codex_image_gen: useCodexImageGenDraft,
      codex_bin: codexBinDraft,
      public_app_url: publicAppUrlDraft,
    },
    save: onSaveOpenRouterSettings,
  });
  const colorsAutosaveStatus = useAutosave<ImageOptions["colors"]>({
    enabled: settingsSection === "colors",
    scope: "colors",
    isDirty: colorsDirty,
    snapshot: colorDrafts,
    save: onSaveImageColorOptions,
  });
  const productionAutosaveStatus = useAutosave<ProductionDrafts>({
    enabled: settingsSection === "production",
    scope: "production",
    isDirty: productionDirty,
    snapshot: {
      settings: {
        electricity_kwh_price_brl: parseDecimal(electricityPrice),
        printer_power_watts: parseDecimal(printerPower),
        printer_purchase_price_brl: parseDecimal(printerPurchasePrice),
        printer_useful_life_hours: Math.max(1, parseDecimal(printerUsefulLifeHours) || 5000),
        maintenance_cost_per_hour_brl: parseDecimal(maintenanceCostPerHour),
        labor_cost_per_hour_brl: parseDecimal(laborCostPerHour),
      },
      filaments: filamentDrafts,
    },
    save: saveProductionSection,
  });
  return (
    <section className="settings-page settings-layout">
      <nav className="settings-nav" aria-label="Seções de ajustes">
        <button className={settingsSection === "store" ? "active" : ""} onClick={() => setSettingsSection("store")}>
          <ShoppingBag size={16} /> Loja e prompts
        </button>
        {isAdmin && (
          <button className={settingsSection === "integrations" ? "active" : ""} onClick={() => setSettingsSection("integrations")}>
            <KeyRound size={16} /> Integrações
          </button>
        )}
        <button className={settingsSection === "appearance" ? "active" : ""} onClick={() => setSettingsSection("appearance")}>
          <Palette size={16} /> Aparência
        </button>
        <button className={settingsSection === "colors" ? "active" : ""} onClick={() => setSettingsSection("colors")}>
          <ImagePlus size={16} /> Cores
        </button>
        <button className={settingsSection === "production" ? "active" : ""} onClick={() => setSettingsSection("production")}>
          <Coins size={16} /> Produção
        </button>
        <button className={settingsSection === "backup" ? "active" : ""} onClick={() => setSettingsSection("backup")}>
          <Download size={16} /> Backup e app
        </button>
      </nav>

      <div className="settings-content">
      {settingsSection === "store" && (
      <div className="panel store-settings-panel">
        <div className="panel-title">
          <ShoppingBag size={18} />
          <h2>Perfis de loja</h2>
        </div>
        <p className="settings-note">
          {isAdmin
            ? "Você está vendo apenas a loja deste login. Cadastre outra loja para gerar um acesso separado e isolado."
            : "Você está vendo somente a loja vinculada a este login."}
        </p>
        <div className="store-profile-list">
          {storeProfiles.map((profile) => (
            <div className={profile.id === storeProfileDraft?.id ? "store-profile-card active" : "store-profile-card"} key={profile.id}>
              <div className="store-profile-mark">
                {storePhotoUrl(profile) ? <img src={storePhotoUrl(profile)} alt="" /> : profile.name.trim().slice(0, 1).toUpperCase()}
              </div>
              <div>
                <strong>{profile.name}</strong>
                <small>{profile.niche} · {profile.marketplace.replace("_", " ")}</small>
              </div>
              <div className="store-profile-actions">
                <button
                  className="primary"
                  onClick={() => {
                    onSelectedStoreProfileChange(profile.id);
                    setProfileEditorOpen(true);
                  }}
                >
                  Editar prompts
                </button>
              </div>
            </div>
          ))}
        </div>
        {isAdmin && (
          <button className="primary profile-create-button" onClick={() => setNewStoreOpen(true)}>
            <FolderPlus size={18} /> Criar perfil de loja
          </button>
        )}
        {newStoreOpen && (
          <div className="modal-backdrop" role="presentation" onMouseDown={() => setNewStoreOpen(false)}>
            <form className="modal-card auth-form" role="dialog" aria-modal="true" aria-label="Cadastrar nova loja" onSubmit={createStoreLogin} onMouseDown={(event) => event.stopPropagation()}>
              <div><p className="eyebrow">Novo acesso</p><h2>Cadastrar loja</h2></div>
              <label>Nome da loja<input value={newStoreName} onChange={(event) => setNewStoreName(event.target.value)} required /></label>
              <label>Login<input value={newStoreUsername} onChange={(event) => setNewStoreUsername(event.target.value)} required minLength={3} autoComplete="off" /></label>
              <label>Senha<input type="password" value={newStorePassword} onChange={(event) => setNewStorePassword(event.target.value)} required minLength={8} autoComplete="new-password" /></label>
              <p className="settings-note">Esse login abrirá somente esta nova loja. Anote a senha: ela não será exibida depois.</p>
              <div className="modal-actions">
                <button type="button" className="primary ghost" onClick={() => setNewStoreOpen(false)}>Cancelar</button>
                <button className="primary"><FolderPlus size={18} /> Criar loja e acesso</button>
              </div>
            </form>
          </div>
        )}
      </div>
      )}

      {isAdmin && settingsSection === "integrations" && (
      <div className="panel integration-settings-panel">
        <div className="panel-title">
          <KeyRound size={18} />
          <h2>Integrações</h2>
        </div>
        <div className="integrations">
          <Integration label="OpenRouter" enabled={Boolean(settings?.integrations.openrouter)} />
          <Integration label="Kie.ai" enabled={Boolean(settings?.integrations.kie_ai)} />
          <Integration label="Endereço público" enabled={Boolean(settings?.integrations.public_app_url)} />
        </div>
        <p className="settings-note">
          Configure OpenRouter (texto/anúncios), Kie.ai (imagens) e o endereço público do app (links das imagens). As credenciais só são carregadas quando você pedir para mostrar.
        </p>
        <button className="primary profile-create-button" onClick={openIntegrationEditor}>
          <KeyRound size={18} /> Editar integrações
        </button>
      </div>
      )}

      {settingsSection === "appearance" && (
      <div className="panel appearance-settings-panel">
        <div className="panel-title">
          <Palette size={18} />
          <h2>Aparência da interface</h2>
        </div>
        <p className="settings-note">
          Escolha a paleta desta loja. Ela fica salva na loja e aparece em qualquer computador, inclusive na tela de login.
        </p>
        <div className="theme-grid">
          {UI_THEME_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={`theme-card${uiThemePreference.id === preset.id ? " active" : ""}`}
              onClick={() => selectUiTheme(preset.id)}
            >
              <span className="theme-card-swatch" style={{ background: preset.swatch }} aria-hidden="true" />
              <span className="theme-card-copy">
                <strong>{preset.name}</strong>
                <small>{preset.description}</small>
              </span>
            </button>
          ))}
        </div>
        <div className="theme-custom-panel">
          <label>
            Cor personalizada
            <div className="theme-custom-row">
              <input
                type="color"
                value={customAccentDraft.startsWith("#") ? customAccentDraft : `#${customAccentDraft}`}
                onChange={(event) => applyCustomAccent(event.target.value)}
              />
              <input
                value={customAccentDraft}
                onChange={(event) => setCustomAccentDraft(event.target.value)}
                onBlur={() => applyCustomAccent(customAccentDraft)}
                placeholder="#0f7a54"
              />
              <button
                className={uiThemePreference.id === "custom" ? "primary" : "quiet-button"}
                type="button"
                onClick={() => applyCustomAccent(customAccentDraft)}
              >
                Aplicar
              </button>
            </div>
          </label>
          <button className="quiet-button" type="button" onClick={() => selectUiTheme("forest")}>
            Restaurar tema padrão
          </button>
        </div>
      </div>
      )}

      {settingsSection === "colors" && (
      <div className="panel color-settings-panel">
        <div className="panel-title">
          <ImagePlus size={18} />
          <h2>Cores para variações</h2>
        </div>
        <p className="settings-note">
          Edite as descrições enviadas ao Kie/Qwen para gerar variações de cor. As alterações são salvas automaticamente.
        </p>
        <div className="color-editor-list">
          {colorDrafts.map((color, index) => (
            <div className="color-editor-row" key={`${color.id}-${index}`}>
              <label>
                ID da cor
                <input value={color.id} onChange={(event) => updateColorDraft(index, "id", event.target.value)} />
              </label>
              <label>
                Descrição para IA
                <input value={color.description} onChange={(event) => updateColorDraft(index, "description", event.target.value)} />
              </label>
              <button className="danger-button" onClick={() => removeColorDraft(index)}>
                <Trash2 size={16} /> Remover
              </button>
            </div>
          ))}
        </div>
        <div className="backup-actions">
          <button className="primary ghost" onClick={addColorDraft}>
            <FolderPlus size={18} /> Adicionar cor
          </button>
          <AutosaveIndicator status={colorsAutosaveStatus} />
        </div>
      </div>
      )}

      {settingsSection === "production" && (
      <div className="panel production-settings-panel">
        <div className="panel-title">
          <Coins size={18} />
          <h2>Custos fixos de produção</h2>
        </div>
        <p className="settings-note section-intro">
          Configure energia, depreciação, manutenção, mão de obra e filamentos por loja. Depreciação = valor da impressora ÷ vida útil em horas × tempo de impressão.
        </p>
        <div className="form-grid">
          <label>
            Energia elétrica (R$/kWh)
            <input value={electricityPrice} onChange={(event) => setElectricityPrice(event.target.value)} />
          </label>
          <label>
            Potência da impressora (W)
            <input value={printerPower} onChange={(event) => setPrinterPower(event.target.value)} />
          </label>
          <label>
            Valor da impressora (R$)
            <input value={printerPurchasePrice} onChange={(event) => setPrinterPurchasePrice(event.target.value)} />
          </label>
          <label>
            Vida útil da impressora (h de impressão)
            <input value={printerUsefulLifeHours} onChange={(event) => setPrinterUsefulLifeHours(event.target.value)} />
          </label>
          <label>
            Manutenção / consumíveis (R$/h)
            <input value={maintenanceCostPerHour} onChange={(event) => setMaintenanceCostPerHour(event.target.value)} />
          </label>
          <label>
            Mão de obra (R$/h)
            <input value={laborCostPerHour} onChange={(event) => setLaborCostPerHour(event.target.value)} />
          </label>
        </div>

        <div className="subsection-title">Filamentos</div>
        <div className="costs-table-wrap">
          <table className="costs-table settings-filament-table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Material</th>
                <th>Cor</th>
                <th>Preço rolo (R$)</th>
                <th>Peso rolo (g)</th>
                <th>R$/g</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filamentDrafts.map((spool, index) => (
                <tr key={filamentRowKeysRef.current[spool.id] ?? spool.id}>
                  <td><input value={spool.name} onChange={(event) => updateFilamentDraft(index, "name", event.target.value)} /></td>
                  <td><input value={spool.material} onChange={(event) => updateFilamentDraft(index, "material", event.target.value)} /></td>
                  <td><input value={spool.color || ""} onChange={(event) => updateFilamentDraft(index, "color", event.target.value)} /></td>
                  <td><DecimalInput value={spool.spool_price_brl} onChange={(value) => updateFilamentDraft(index, "spool_price_brl", String(value))} /></td>
                  <td><DecimalInput value={spool.spool_weight_g} onChange={(value) => updateFilamentDraft(index, "spool_weight_g", String(value))} /></td>
                  <td className="costs-readonly">{formatBrl(filamentCostPerGram(spool))}</td>
                  <td className="costs-actions-cell">
                    {spool.id && !spool.id.startsWith(DRAFT_FILAMENT_PREFIX) ? (
                      <button className="danger-button compact-danger" onClick={() => onDeleteFilament(spool.id)} disabled={!spool.id}>
                        <Trash2 size={14} />
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="action-row">
          <button className="quiet-button" onClick={addFilamentDraftRow}>+ Linha de filamento</button>
          <AutosaveIndicator status={productionAutosaveStatus} />
        </div>
      </div>
      )}

      {settingsSection === "backup" && (
      <>
      <div className="panel backup-settings-panel">
        <div className="panel-title">
          <Download size={18} />
          <h2>Backup desta loja</h2>
        </div>
        <p className="settings-note">
          Gera um ZIP somente com a loja deste login, seus produtos, filamentos e arquivos.
          Senhas e chaves de integração não entram no arquivo. Por segurança, este login só restaura backups da própria loja.
        </p>
        <div className="backup-actions">
          <button className="primary" onClick={() => onDownloadAppBackup()}>
            <Download size={18} /> Baixar backup da loja
          </button>
          <label className="backup-upload-button">
            <FolderOpen size={18} /> Restaurar backup ZIP
            <input
              accept=".zip,application/zip"
              type="file"
              onChange={(event) => {
                handleBackupUpload(event.target.files?.[0]);
                event.currentTarget.value = "";
              }}
            />
          </label>
        </div>
      </div>

      <div className="panel paths-settings-panel">
        <div className="panel-title">
          <Settings size={18} />
          <h2>Ambiente local</h2>
        </div>
        <div className="summary-list path-list">
          <SummaryItem label="Versão do app" value={`v${__APP_VERSION__}`} />
          <SummaryItem label="Armazenamento" value="Neste computador" />
          <SummaryItem label="Modelo OpenRouter" value={settings?.integrations.openrouter_model ?? "--"} />
          <SummaryItem label="Modelo Kie imagem" value={settings?.integrations.kie_image_model ?? "--"} />
        </div>
      </div>
      </>
      )}
      </div>

      {profileEditorOpen && storeProfileDraft && (
        <div className="profile-editor-backdrop" role="presentation" onClick={() => setProfileEditorOpen(false)}>
          <div className="profile-editor-dialog" role="dialog" aria-modal="true" aria-labelledby="profile-editor-title" onClick={(event) => event.stopPropagation()}>
            <div className="profile-editor-header">
              <div>
                <p className="eyebrow">Perfil de loja</p>
                <h2 id="profile-editor-title">IA, prompts e características</h2>
              </div>
              <button className="primary ghost" onClick={() => setProfileEditorOpen(false)}>
                Fechar
              </button>
            </div>
            <div className="profile-editor-body">
              <section className="profile-editor-section">
                <div className="subsection-title">Identidade da loja</div>
                <div className="store-photo-editor">
                  <div className="store-photo-preview">
                    {storePhotoUrl(storeProfileDraft) ? (
                      <img src={storePhotoUrl(storeProfileDraft)} alt="" />
                    ) : (
                      storeProfileDraft.name.trim().slice(0, 1).toUpperCase()
                    )}
                  </div>
                  <label>
                    Foto da loja
                    <small>Use um logo ou imagem quadrada. Se não houver foto, o app usa a primeira letra da loja.</small>
                    <input
                      accept="image/png,image/jpeg,image/webp"
                      type="file"
                      onChange={(event) => handleStorePhotoChange(storeProfileDraft.id, event.target.files?.[0])}
                    />
                  </label>
                </div>
                <div className="form-grid">
                  <label>
                    Nome da loja
                    <input value={storeProfileDraft.name} onChange={(event) => updateStoreDraft("name", event.target.value)} />
                  </label>
                  <label>
                    Marketplace
                    <select
                      value={storeProfileDraft.marketplace}
                      onChange={(event) => updateStoreDraft("marketplace", event.target.value as Marketplace)}
                    >
                      <option value="shopee">Shopee</option>
                      <option value="tiktok_shop">TikTok Shop</option>
                      <option value="kwai_shop">Kwai Shop</option>
                      <option value="mercado_livre">Mercado Livre</option>
                    </select>
                  </label>
                </div>
                <label>
                  Nicho e características
                  <small>Use este campo para resumir o tipo de loja, público e foco comercial.</small>
                  <input value={storeProfileDraft.niche} onChange={(event) => updateStoreDraft("niche", event.target.value)} />
                </label>
              </section>

              <section className="profile-editor-section">
                <div className="panel-title compact-title">
                  <BrainCircuit size={18} />
                  <h3>Prompts de IA</h3>
                </div>
                <div className="prompt-grid">
                  <label>
                    Busca no MakerWorld
                    <small>Orienta palavras-chave, foco e características procuradas na coleta.</small>
                    <textarea value={storeProfileDraft.search_prompt} onChange={(event) => updateStoreDraft("search_prompt", event.target.value)} />
                  </label>
                  <label>
                    Curadoria
                    <small>Define os critérios usados para avaliar os produtos coletados.</small>
                    <textarea value={storeProfileDraft.curation_prompt} onChange={(event) => updateStoreDraft("curation_prompt", event.target.value)} />
                  </label>
                  <label>
                    Conteúdo/anúncio
                    <small>Prompt usado para gerar título, descrição, categoria e campos comerciais.</small>
                    <textarea value={storeProfileDraft.listing_prompt} onChange={(event) => updateStoreDraft("listing_prompt", event.target.value)} />
                  </label>
                  <label>
                    Complemento geral de imagens
                    <small>Acrescentado aos prompts Kie/Qwen e às variações de cor.</small>
                    <textarea value={storeProfileDraft.image_prompt} onChange={(event) => updateStoreDraft("image_prompt", event.target.value)} />
                  </label>
                  <label>
                    Variação de cor Kie/Qwen
                    <small>Use {'{color_description}'} e {'{extra_prompt}'} para montar o prompt final.</small>
                    <textarea
                      value={storeProfileDraft.color_variation_prompt}
                      onChange={(event) => updateStoreDraft("color_variation_prompt", event.target.value)}
                    />
                  </label>
                </div>
              </section>

              <section className="profile-editor-section">
                <div className="subsection-title">Prompts de imagem Kie/Qwen</div>
                <div className="image-prompt-grid">
                  {imageOptions.studio_prompts.map((prompt) => {
                    const enabled = !(storeProfileDraft.disabled_image_prompts || []).includes(prompt.id);
                    return (
                    <div className={`image-prompt-card${enabled ? "" : " disabled"}`} key={prompt.id}>
                      <label className="inline-toggle image-prompt-toggle">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(event) => toggleStoreImagePrompt(prompt.id, event.target.checked)}
                        />
                        <span>
                          {prompt.name}
                          <small>{enabled ? "Incluída na geração de imagens base." : "Desativada para esta loja."}</small>
                        </span>
                      </label>
                      <textarea
                        aria-label={`Prompt de ${prompt.name}`}
                        value={(storeProfileDraft.image_prompts || {})[prompt.id] || ""}
                        onChange={(event) => updateStoreImagePrompt(prompt.id, event.target.value)}
                        disabled={!enabled}
                      />
                    </div>
                  )})}
                </div>
              </section>
            </div>
            <div className="profile-editor-footer">
              <AutosaveIndicator status={profileAutosaveStatus} />
              <button className="primary ghost" onClick={() => setProfileEditorOpen(false)}>
                Cancelar
              </button>
              <button className="primary" onClick={saveAndCloseStoreProfile}>
                Concluir
              </button>
            </div>
          </div>
        </div>
      )}

      {integrationEditorOpen && (
        <div className="profile-editor-backdrop" role="presentation" onClick={() => setIntegrationEditorOpen(false)}>
          <div className="profile-editor-dialog integration-editor-dialog" role="dialog" aria-modal="true" aria-labelledby="integration-editor-title" onClick={(event) => event.stopPropagation()}>
            <div className="profile-editor-header">
              <div>
                <p className="eyebrow">Credenciais</p>
                <h2 id="integration-editor-title">Integrações e APIs</h2>
              </div>
              <button className="primary ghost" onClick={() => setIntegrationEditorOpen(false)}>
                Fechar
              </button>
            </div>
            <div className="profile-editor-body">
              <section className="profile-editor-section">
                <div className="subsection-title">OpenRouter</div>
                <label>
                  Chave OpenRouter
                  <div className="credential-field">
                    <input
                      type={integrationSecretsVisible ? "text" : "password"}
                      value={openRouterApiKeyDraft}
                      onChange={(event) => onOpenRouterApiKeyChange(event.target.value)}
                      placeholder={settings?.integrations.openrouter ? "Configurada. Mostrar para visualizar ou cole uma nova." : "Cole sua OPENROUTER_API_KEY"}
                    />
                    <button type="button" onClick={revealIntegrationSecrets} disabled={loadingIntegrationSecrets}>
                      {integrationSecretsVisible ? "Ocultar" : "Mostrar"}
                    </button>
                  </div>
                </label>
                <label>
                  Modelo OpenRouter
                  <input value={openRouterModelDraft} onChange={(event) => onOpenRouterModelChange(event.target.value)} />
                </label>
              </section>

              <section className="profile-editor-section">
                <div className="subsection-title">Kie.ai</div>
                <label>
                  Chave Kie.ai
                  <div className="credential-field">
                    <input
                      type={integrationSecretsVisible ? "text" : "password"}
                      value={kieApiKeyDraft}
                      onChange={(event) => onKieApiKeyChange(event.target.value)}
                      placeholder={settings?.integrations.kie_ai ? "Configurada. Mostrar para visualizar ou cole uma nova." : "Cole sua KIE_API_KEY"}
                    />
                    <button type="button" onClick={revealIntegrationSecrets} disabled={loadingIntegrationSecrets}>
                      {integrationSecretsVisible ? "Ocultar" : "Mostrar"}
                    </button>
                  </div>
                </label>
                <label>
                  Modelo de imagem Kie
                  <ImageModelSelect
                    value={kieImageModelDraft}
                    models={settings?.integrations.image_models ?? []}
                    onChange={onKieImageModelChange}
                  />
                </label>
              </section>

              <section className="profile-editor-section">
                <div className="subsection-title">Codex CLI (geração de imagens)</div>
                <label className="inline-toggle">
                  <input
                    type="checkbox"
                    checked={useCodexImageGenDraft}
                    onChange={(event) => onUseCodexImageGenChange(event.target.checked)}
                  />
                  <span>
                    Usar o Codex CLI para gerar imagens
                    <small>
                      Quando ativado, a geração/edição de imagens usa o Codex CLI local (assinatura
                      ChatGPT, sem custo por imagem) em vez da Kie.ai. A imagem base é enviada como
                      arquivo local. Requer o Codex CLI instalado e logado, com o recurso
                      image_generation habilitado.
                    </small>
                  </span>
                </label>
                <label>
                  Caminho do executável Codex (opcional)
                  <small>Deixe em branco para usar "codex" do PATH. Ex.: C:\Users\seu-usuario\AppData\Local\codex\codex.cmd</small>
                  <input
                    value={codexBinDraft}
                    onChange={(event) => onCodexBinChange(event.target.value)}
                    placeholder="codex"
                  />
                </label>
              </section>

              <section className="profile-editor-section">
                <div className="subsection-title">Endereço público do app</div>
                <label>
                  Endereço na internet
                  <input
                    value={publicAppUrlDraft}
                    onChange={(event) => onPublicAppUrlChange(event.target.value)}
                    placeholder={settings?.integrations.public_app_url || "https://eco.seudominio.com"}
                  />
                  <small>O Kie.ai e a planilha da Shopee baixam as imagens por links que começam com este endereço.</small>
                </label>
              </section>
            </div>
            <div className="profile-editor-footer">
              <AutosaveIndicator status={integrationAutosaveStatus} />
              <button className="primary ghost" onClick={() => setIntegrationEditorOpen(false)}>
                Cancelar
              </button>
              <button className="primary" onClick={saveAndCloseIntegrations}>
                Concluir
              </button>
            </div>
          </div>
        </div>
      )}

    </section>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Integration({ label, enabled }: { label: string; enabled: boolean }) {
  return (
    <div className={enabled ? "integration enabled" : "integration"}>
      <span>{label}</span>
      <strong>{enabled ? "Configurado" : "Pendente"}</strong>
    </div>
  );
}

function AdminConsole({ auth, onLogout }: { auth: AuthStatus; onLogout: () => Promise<void> }) {
  useEffect(() => showUiTheme(null), []);
  const [usage, setUsage] = useState<AdminUsage | null>(null);
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [secrets, setSecrets] = useState<SettingsSecrets>({});
  const [notice, setNotice] = useState("");
  const [newStore, setNewStore] = useState({ name: "", username: "", password: "" });
  const [period, setPeriod] = useState("");

  const reload = useCallback(async () => {
    const [usagePayload, settingsPayload] = await Promise.all([
      api<AdminUsage>(`/api/admin/usage${period ? `?period=${encodeURIComponent(period)}` : ""}`),
      api<SettingsPayload>("/api/settings"),
    ]);
    setUsage(usagePayload);
    setPeriod(usagePayload.period);
    setSettings(settingsPayload);
  }, [period]);

  useEffect(() => { void reload(); }, [reload]);

  async function loadSecrets() {
    setSecrets(await api<SettingsSecrets>("/api/settings/secrets"));
  }

  async function saveIntegrations() {
    try {
      await api("/api/settings", { method: "PATCH", body: JSON.stringify(secrets) });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
      return;
    }
    setNotice("Integrações atualizadas.");
    await reload();
  }

  async function saveLimits(row: AdminStoreUsage) {
    await api(`/api/admin/stores/${row.store.id}/limits`, {
      method: "PUT",
      body: JSON.stringify({ enabled: row.enabled, ...row.quotas }),
    });
    setNotice(`Limites de ${row.store.name} atualizados.`);
    await reload();
  }

  async function createStore(event: React.FormEvent) {
    event.preventDefault();
    await api("/api/store-profiles", { method: "POST", body: JSON.stringify(newStore) });
    setNewStore({ name: "", username: "", password: "" });
    setNotice("Loja e acesso criados.");
    await reload();
  }

  function updateRow(storeId: string, update: Partial<AdminStoreUsage>, quota?: [string, string]) {
    setUsage((current) => current ? {
      ...current,
      stores: current.stores.map((row) => {
        if (row.store.id !== storeId) return row;
        if (!quota) return { ...row, ...update };
        const [key, raw] = quota;
        return { ...row, quotas: { ...row.quotas, [key]: raw === "" ? null : Number(raw) } };
      }),
    } : current);
  }

  return (
    <main className="auth-page admin-console-page">
      <section className="auth-card admin-console-card">
        <div className="panel-title">
          <Settings size={20} />
          <div><p className="eyebrow">Conta administrativa</p><h1>Painel unificado</h1></div>
          <button className="quiet-button" onClick={() => void onLogout()}><LogOut size={16} /> Sair ({auth.username})</button>
        </div>
        {notice && <p className="notice">{notice}</p>}

        <div className="dashboard-grid">
          <SummaryItem label="Lojas" value={String(usage?.stores.length ?? 0)} />
          <SummaryItem label="Coletas no período" value={String(usage?.totals.collect_monthly ?? 0)} />
          <SummaryItem label="Textos no período" value={String(usage?.totals.listing_monthly ?? 0)} />
          <SummaryItem label="Imagens no período" value={String(usage?.totals.image_monthly ?? 0)} />
          <SummaryItem label="Custo IA no período" value={formatUsd(usage?.totals.ai_cost_usd_monthly ?? 0)} />
        </div>

        <div className="panel">
          <div className="panel-title">
            <Gauge size={18} /><h2>Cotas e consumo por loja</h2>
            <label>Período
              <select value={period} onChange={(event) => setPeriod(event.target.value)}>
                <option value="all">Todo o histórico</option>
                {usage?.periods.map((item) => (
                  <option key={item} value={item}>{item === "legacy" ? "Legado sem período" : item}</option>
                ))}
              </select>
            </label>
          </div>
          <p className="settings-note">O período selecionado muda os números de consumo. As cotas são mensais recorrentes: deixe um limite vazio para uso ilimitado. O bloqueio acontece antes de iniciar uma nova operação.</p>
          <div className="costs-table-wrap"><table className="costs-table"><thead><tr><th>Loja / login</th><th>Coletas</th><th>Textos</th><th>Imagens</th><th>Custo IA (US$)</th><th>Ativa</th><th /></tr></thead><tbody>
            {usage?.stores.map((row) => (
              <tr key={row.store.id}>
                <td><strong>{row.store.name}</strong><small>{row.username || "Sem login"}</small></td>
                {(["collect_monthly", "listing_monthly", "image_monthly", "ai_cost_usd_monthly"] as const).map((key) => (
                  <td key={key}><input type="number" min="0" step={key === "ai_cost_usd_monthly" ? "0.01" : "1"} value={row.quotas[key] ?? ""} placeholder={`Usado: ${row.usage[key] ?? 0}`} onChange={(event) => updateRow(row.store.id, {}, [key, event.target.value])} /></td>
                ))}
                <td><input type="checkbox" checked={row.enabled} onChange={(event) => updateRow(row.store.id, { enabled: event.target.checked })} /></td>
                <td><button className="primary" onClick={() => void saveLimits(row)}>Salvar</button></td>
              </tr>
            ))}
          </tbody></table></div>
        </div>

        <form className="panel auth-form" onSubmit={createStore}>
          <div className="panel-title"><FolderPlus size={18} /><h2>Nova loja e acesso</h2></div>
          <div className="form-grid">
            <label>Nome da loja<input value={newStore.name} onChange={(e) => setNewStore({ ...newStore, name: e.target.value })} required /></label>
            <label>Login<input value={newStore.username} onChange={(e) => setNewStore({ ...newStore, username: e.target.value })} minLength={3} required /></label>
            <label>Senha<input type="password" value={newStore.password} onChange={(e) => setNewStore({ ...newStore, password: e.target.value })} minLength={8} required /></label>
          </div>
          <button className="primary"><FolderPlus size={16} /> Criar loja</button>
        </form>

        <div className="panel">
          <div className="panel-title"><KeyRound size={18} /><h2>Integrações globais</h2></div>
          <div className="integrations">
            <Integration label="OpenRouter" enabled={Boolean(settings?.integrations.openrouter)} />
            <Integration label="Kie.ai" enabled={Boolean(settings?.integrations.kie_ai)} />
            <Integration label="Endereço público" enabled={Boolean(settings?.integrations.public_app_url)} />
          </div>
          <button className="quiet-button" onClick={() => void loadSecrets()}>Carregar configuração</button>
          <div className="form-grid">
            <label>OpenRouter API key<input type="password" value={secrets.openrouter_api_key ?? ""} onChange={(e) => setSecrets({ ...secrets, openrouter_api_key: e.target.value })} /></label>
            <label>Modelo OpenRouter<input value={secrets.openrouter_model ?? ""} onChange={(e) => setSecrets({ ...secrets, openrouter_model: e.target.value })} /></label>
            <label>Kie API key<input type="password" value={secrets.kie_api_key ?? ""} onChange={(e) => setSecrets({ ...secrets, kie_api_key: e.target.value })} /></label>
            <label>Modelo Kie<ImageModelSelect value={secrets.kie_image_model ?? ""} models={settings?.integrations.image_models ?? []} onChange={(value) => setSecrets({ ...secrets, kie_image_model: value })} /></label>
            <label>Endereço público do app
              <input value={secrets.public_app_url ?? ""} placeholder="https://eco.seudominio.com" onChange={(e) => setSecrets({ ...secrets, public_app_url: e.target.value })} />
              <small>Os links das imagens enviados ao Kie.ai e à planilha da Shopee começam com este endereço.</small>
            </label>
          </div>
          <button className="primary" onClick={() => void saveIntegrations()}><Check size={16} /> Salvar integrações</button>
        </div>

      </section>
    </main>
  );
}

function LoginScreen({ status, onAuthenticated }: { status: AuthStatus; onAuthenticated: (status: AuthStatus) => void }) {
  const setupRequired = status.setup_required;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const stores = status.legacy_stores ?? [];
  const [storeName, setStoreName] = useState(stores[0]?.name ?? "Loja principal");
  const [storeCredentials, setStoreCredentials] = useState(() =>
    stores.map((store) => ({ store_profile_id: store.id, username: "", password: "" })),
  );
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const loginStores = status.stores ?? [];
  const [adminMode, setAdminMode] = useState(!loginStores.length);
  const [selectedStoreId, setSelectedStoreId] = useState(() => {
    const last = readLastLoginStore();
    if (loginStores.some((store) => store.id === last)) return last;
    return loginStores.length === 1 ? loginStores[0].id : "";
  });
  const selectedStore = loginStores.find((store) => store.id === selectedStoreId);
  // The chosen store's colours, already on the login page; the administrator uses the default.
  const loginThemeKey = JSON.stringify(setupRequired || adminMode ? null : selectedStore?.ui_theme ?? null);
  useEffect(() => showUiTheme(JSON.parse(loginThemeKey)), [loginThemeKey]);

  function chooseStore(storeId: string) {
    setSelectedStoreId(storeId);
    setPassword("");
    setMessage("");
  }

  function switchToAdmin(next: boolean) {
    setAdminMode(next);
    setPassword("");
    setMessage("");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setMessage("");
    try {
      const body = setupRequired
        ? { admin: { username, password }, stores: storeCredentials, store_name: stores.length === 1 ? storeName : undefined }
        : adminMode
          ? { username, password }
          : { store_profile_id: selectedStoreId, password };
      const nextStatus = await api<AuthStatus>(setupRequired ? "/api/auth/setup" : "/api/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!setupRequired && !adminMode) rememberLoginStore(selectedStoreId);
      onAuthenticated(nextStatus);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível entrar");
    } finally {
      setSubmitting(false);
    }
  }

  if (!setupRequired && adminMode) {
    return (
      <main className="auth-page">
        <section className="auth-card admin-auth-card">
          <div className="admin-auth-header">
            <span className="admin-auth-badge"><KeyRound size={14} /> Administração</span>
            <h1>Acesso do administrador</h1>
            <p className="auth-description">Gerencie lojas, limites de uso e integrações.</p>
          </div>
          <form onSubmit={submit} className="auth-form">
            <label>Login<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required minLength={3} autoFocus /></label>
            <label>Senha<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required minLength={8} /></label>
            {message && <p className="auth-error">{message}</p>}
            <button className="primary login-button" disabled={submitting}>
              {submitting ? <Loader2 size={18} className="spin" /> : <LogIn size={18} />} Entrar como administrador
            </button>
          </form>
          {loginStores.length > 0 && (
            <button type="button" className="link-button auth-switch" onClick={() => switchToAdmin(false)}>
              <ArrowLeft size={15} /> Voltar para as lojas
            </button>
          )}
        </section>
      </main>
    );
  }

  if (!setupRequired) {
    return (
      <main className="auth-page">
        <section className="auth-card store-auth-card">
          <img src="/eco-logo.png" alt="ECO Native" className="auth-logo" />
          <div>
            <p className="eyebrow">ECO Native Studio</p>
            <h1>Escolha sua loja</h1>
            <p className="auth-description">Toque na sua loja e digite a senha para entrar.</p>
          </div>
          <div className="login-store-grid" role="radiogroup" aria-label="Lojas">
            {loginStores.map((store) => (
              <button
                key={store.id}
                type="button"
                role="radio"
                aria-checked={store.id === selectedStoreId}
                className={`login-store${store.id === selectedStoreId ? " active" : ""}`}
                onClick={() => chooseStore(store.id)}
              >
                <span className="login-store-logo">
                  {store.photo_version
                    ? <img src={`${API_BASE}/api/auth/stores/${store.id}/photo?v=${encodeURIComponent(store.photo_version)}`} alt="" />
                    : store.name.trim().slice(0, 1).toUpperCase()}
                </span>
                <span className="login-store-name">{store.name}</span>
              </button>
            ))}
          </div>
          {selectedStore && (
            <form onSubmit={submit} className="auth-form" key={selectedStore.id}>
              <label>
                Senha de {selectedStore.name}
                <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required minLength={8} autoFocus />
              </label>
              {message && <p className="auth-error">{message}</p>}
              <button className="primary login-button" disabled={submitting}>
                {submitting ? <Loader2 size={18} className="spin" /> : <LogIn size={18} />} Entrar
              </button>
            </form>
          )}
          <button type="button" className="link-button auth-switch admin-switch" onClick={() => switchToAdmin(true)}>
            <KeyRound size={15} /> Acesso do administrador
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <img src="/eco-logo.png" alt="ECO Native" className="auth-logo" />
        <div>
          <p className="eyebrow">ECO Native Studio</p>
          <h1>Configure o primeiro acesso</h1>
          <p className="auth-description">
            Crie uma conta administrativa independente e um acesso para cada loja. Os dados continuarão neste computador.
          </p>
        </div>

        <form onSubmit={submit} className="auth-form">
          {stores.length === 1 && (
            <label>Nome da loja<input value={storeName} onChange={(event) => setStoreName(event.target.value)} required /></label>
          )}
          <fieldset className="migration-store">
            <legend>Conta administradora</legend>
            <label>Login administrativo<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required minLength={3} /></label>
            <label>Senha administrativa<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" required minLength={8} /></label>
          </fieldset>
          {storeCredentials.map((credential, index) => (
            <fieldset className="migration-store" key={credential.store_profile_id}>
              <legend>{stores[index]?.name ?? `Loja ${index + 1}`}</legend>
              <label>Login<input value={credential.username} onChange={(event) => setStoreCredentials((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, username: event.target.value } : item))} autoComplete="off" required minLength={3} /></label>
              <label>Senha<input type="password" value={credential.password} onChange={(event) => setStoreCredentials((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, password: event.target.value } : item))} autoComplete="new-password" required minLength={8} /></label>
            </fieldset>
          ))}
          {message && <p className="auth-error">{message}</p>}
          <button className="primary login-button" disabled={submitting}>
            {submitting ? <Loader2 size={18} className="spin" /> : <LogIn size={18} />} Criar acesso
          </button>
        </form>
      </section>
    </main>
  );
}

function Root() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);

  const loadStatus = useCallback(() => {
    api<AuthStatus>("/api/auth/status").then(setAuth).catch(() => setAuth({ authenticated: false, setup_required: false }));
  }, []);

  useEffect(() => {
    loadStatus();
    window.addEventListener("eco-native-auth-required", loadStatus);
    return () => window.removeEventListener("eco-native-auth-required", loadStatus);
  }, [loadStatus]);

  async function logout() {
    await api<void>("/api/auth/logout", { method: "POST" });
    // The login page needs the store list from the status, or it opens on the administrator card.
    setAuth(null);
    loadStatus();
  }

  if (!auth) return <main className="auth-page"><Loader2 size={28} className="spin" /></main>;
  if (!auth.authenticated) return <LoginScreen status={auth} onAuthenticated={setAuth} />;
  if (auth.is_admin) return <AdminConsole auth={auth} onLogout={logout} />;
  return <App auth={auth} onLogout={logout} />;
}

createRoot(document.getElementById("root")!).render(<Root />);
