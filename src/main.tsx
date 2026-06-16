import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { createRoot } from "react-dom/client";
import {
  BadgeCheck,
  BarChart3,
  BrainCircuit,
  Check,
  ChevronDown,
  Download,
  Eye,
  FolderOpen,
  FolderPlus,
  Link2,
  LogIn,
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
} from "lucide-react";
import "./styles.css";
import {
  applyUiThemePreference,
  initUiTheme,
  readUiThemePreference,
  saveUiThemePreference,
  UI_THEME_PRESETS,
  type UiThemeId,
  type UiThemePreference,
} from "./uiTheme";

initUiTheme();

const API_BASE = "http://127.0.0.1:8765";
const ONBOARDING_COMPLETE_KEY = "eco_native_onboarding_complete";

declare global {
  interface Window {
    ecoNative?: {
      checkForUpdates: () => Promise<AppUpdateCheckResult>;
      downloadUpdate: () => Promise<{ ok: boolean; message?: string }>;
      getAppInfo: () => Promise<{ name: string; version: string; platform?: string; titleBarHeight?: number }>;
      installUpdate: () => Promise<{ ok: boolean; message?: string }>;
      onUpdateEvent: (callback: (event: AppUpdateEvent) => void) => () => void;
      platform?: string;
      titleBarHeight?: number;
      setTitleBarOverlay?: (options: { color: string; symbolColor: string }) => Promise<{ ok: boolean }>;
    };
  }
}

function initElectronChrome() {
  if (typeof window === "undefined" || !window.ecoNative) return;
  document.documentElement.classList.add("electron-app");
  if (window.ecoNative.platform === "win32") {
    document.documentElement.classList.add("electron-win");
    document.documentElement.style.setProperty(
      "--electron-titlebar-height",
      `${window.ecoNative.titleBarHeight ?? 36}px`,
    );
  }
}

initElectronChrome();

type AppUpdatePhase = "idle" | "checking" | "available" | "uptodate" | "downloading" | "downloaded" | "error";

type AppUpdateState = {
  phase: AppUpdatePhase;
  version?: string;
  currentVersion?: string;
  progress?: number;
  message?: string;
  bannerDismissed?: boolean;
};

type AppUpdateCheckResult = {
  ok: boolean;
  status?: "available" | "uptodate" | "error";
  version?: string;
  currentVersion?: string;
  message?: string;
};

type AppUpdateEvent =
  | { type: "available"; version: string; currentVersion: string }
  | { type: "not-available"; version: string; currentVersion: string }
  | { type: "progress"; percent: number; transferred: number; total: number }
  | { type: "downloaded"; version: string }
  | { type: "error"; message: string };

type AppInfo = {
  name: string;
  version: string;
};

const DEFAULT_APP_INFO: AppInfo = {
  name: __APP_NAME__,
  version: __APP_VERSION__,
};

type Marketplace = "shopee" | "tiktok_shop" | "kwai_shop" | "mercado_livre";
type AppTab = "dashboard" | "collect" | "products" | "costs" | "schedule" | "settings";
type ProductDetailSection = "listing" | "images" | "files" | "printing" | "info";
type SettingsSection = "store" | "integrations" | "appearance" | "colors" | "production" | "printing" | "backup";
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

type PrintScheduleStatus = "planned" | "printing" | "done" | "failed" | "cancelled";

type ScheduleView = "day" | "week" | "month";

type PrintScheduleTask = {
  id: string;
  printer_id: string;
  scheduled_date: string;
  start_time: string;
  duration_minutes: number;
  product_id?: string | null;
  plate_id?: string | null;
  title: string;
  quantity: number;
  notes: string;
  status: PrintScheduleStatus;
  created_at: string;
  updated_at: string;
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

type Project = {
  id: string;
  name: string;
  store: string;
  store_profile_id?: string | null;
  marketplace: Marketplace;
  niche: string;
  created_at: string;
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
  status: "queued" | "running" | "completed" | "failed";
  project_id?: string;
  product_id?: string;
  progress: number;
  message: string;
  logs?: string[];
  metadata?: Record<string, unknown>;
};

type SettingsPayload = {
  data_dir: string;
  projects_dir: string;
  exports_dir: string;
  integrations: {
    openrouter: boolean;
    openrouter_model?: string;
    kie_ai: boolean;
    kie_image_model?: string;
    cloudflare_r2: boolean;
  };
};

type SettingsSecrets = {
  openrouter_api_key?: string | null;
  openrouter_model?: string | null;
  kie_api_key?: string | null;
  kie_image_model?: string | null;
  cloudflare_account_id?: string | null;
  cloudflare_r2_bucket_name?: string | null;
  cloudflare_r2_access_key?: string | null;
  cloudflare_r2_secret_key?: string | null;
  cloudflare_r2_public_url?: string | null;
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
    cache_path?: string;
  };
};

type BackupRestoreSummary = {
  kind?: "full_app" | "legacy_store";
  store_profiles: number;
  ai_profiles: number;
  projects: number;
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
  open: boolean;
  url?: string | null;
  message: string;
};

type StoreProfile = {
  id: string;
  name: string;
  marketplace: Marketplace;
  niche: string;
  logo_path?: string | null;
  ai_profile_id?: string | null;
  search_prompt: string;
  curation_prompt: string;
  listing_prompt: string;
  image_prompt: string;
  image_prompts: Record<string, string>;
  color_variation_prompt: string;
  updated_at?: string;
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
  cloudflare_account_id: string;
  cloudflare_r2_bucket_name: string;
  cloudflare_r2_access_key: string;
  cloudflare_r2_secret_key: string;
  cloudflare_r2_public_url: string;
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
    | "not_listed";
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  return response.json() as Promise<T>;
}

async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
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

function assetUrl(asset: Asset): string {
  return `${API_BASE}/api/assets/${asset.id}`;
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

function isImageAsset(asset: Asset): boolean {
  return asset.kind.includes("image") || /\.(png|jpe?g|webp)$/i.test(asset.path);
}

function getCoverAsset(product: Product): Asset | undefined {
  return product.assets.find((asset) => asset.kind === "cover_image" && isImageAsset(asset))
    ?? product.assets.find(isImageAsset);
}

function getImageAssets(product: Product): Asset[] {
  return product.assets.filter(isImageAsset);
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
  if (productListed(product)) {
    publicationDetail = "À venda";
    publicationState = "done";
  } else if (product.status === "exported") {
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
      key: "publish",
      label: "Publicação",
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

function useAutosave({
  enabled = true,
  isDirty,
  save,
  debounceMs = 800,
}: {
  enabled?: boolean;
  isDirty: boolean;
  save: () => Promise<unknown>;
  debounceMs?: number;
}): AutosaveStatus {
  const [status, setStatus] = useState<AutosaveStatus>("saved");
  const savingRef = useRef(false);
  const saveRef = useRef(save);
  saveRef.current = save;

  useEffect(() => {
    if (!enabled) {
      setStatus("saved");
      return undefined;
    }
    if (!isDirty) {
      setStatus((current) => (current === "saving" ? current : "saved"));
      return undefined;
    }
    setStatus("pending");
    const timer = window.setTimeout(async () => {
      if (savingRef.current) return;
      savingRef.current = true;
      setStatus("saving");
      try {
        await saveRef.current();
        setStatus("saved");
      } catch {
        setStatus("error");
      } finally {
        savingRef.current = false;
      }
    }, debounceMs);
    return () => window.clearTimeout(timer);
  }, [enabled, isDirty, debounceMs]);

  return status;
}

function AutosaveIndicator({ status }: { status: AutosaveStatus }) {
  if (status === "saving") {
    return (
      <span className="autosave-indicator saving">
        <Loader2 size={14} className="spin" /> Salvando...
      </span>
    );
  }
  if (status === "pending") {
    return <span className="autosave-indicator pending">Salvando em instantes...</span>;
  }
  if (status === "error") {
    return <span className="autosave-indicator error">Erro ao salvar</span>;
  }
  return <span className="autosave-indicator saved">Salvo automaticamente</span>;
}

function plateTotals(plates: PrintPlate[]) {
  return {
    plate_count: plates.length,
    total_print_time_minutes: plates.reduce((sum, plate) => sum + plate.print_time_minutes * plate.quantity, 0),
    total_filament_grams: Math.round(plates.reduce((sum, plate) => sum + plate.filament_grams * plate.quantity, 0) * 100) / 100,
  };
}

function addMinutesToTime(time: string, minutes: number): string {
  const [hoursRaw, minutesRaw] = time.split(":");
  const hours = Number(hoursRaw || 0);
  const mins = Number(minutesRaw || 0);
  const total = hours * 60 + mins + minutes;
  const nextHours = Math.floor(total / 60) % 24;
  const nextMinutes = total % 60;
  return `${String(nextHours).padStart(2, "0")}:${String(nextMinutes).padStart(2, "0")}`;
}

const AGENDA_START_HOUR = 6;
const AGENDA_END_HOUR = 22;
const AGENDA_HOUR_HEIGHT = 56;
const AGENDA_SNAP_MINUTES = 15;
const AGENDA_MIN_EVENT_HEIGHT = 34;
const AGENDA_GRID_HEIGHT = (AGENDA_END_HOUR - AGENDA_START_HOUR + 1) * AGENDA_HOUR_HEIGHT;

function timeToMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + (minutes || 0);
}

function snapAgendaMinutes(minutes: number): number {
  return Math.round(minutes / AGENDA_SNAP_MINUTES) * AGENDA_SNAP_MINUTES;
}

function clampAgendaMinutes(minutes: number, durationMinutes = 0): number {
  const min = AGENDA_START_HOUR * 60;
  const max = AGENDA_END_HOUR * 60 - Math.max(AGENDA_SNAP_MINUTES, durationMinutes);
  return Math.max(min, Math.min(max, snapAgendaMinutes(minutes)));
}

function agendaOffsetTop(minutes: number): number {
  return ((minutes - AGENDA_START_HOUR * 60) / 60) * AGENDA_HOUR_HEIGHT;
}

function agendaBlockHeight(durationMinutes: number): number {
  return Math.max(AGENDA_MIN_EVENT_HEIGHT, (durationMinutes / 60) * AGENDA_HOUR_HEIGHT);
}

function minutesFromAgendaY(relativeY: number): number {
  return AGENDA_START_HOUR * 60 + (relativeY / AGENDA_HOUR_HEIGHT) * 60;
}

function minutesToTimeString(minutes: number): string {
  const hours = Math.floor(minutes / 60) % 24;
  const mins = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
}

type AgendaColumn = { id: string; label: string; sublabel?: string };

type AgendaOverlapLayout = { lane: number; lanes: number };

function computeAgendaOverlapLayout(tasks: PrintScheduleTask[]): Map<string, AgendaOverlapLayout> {
  type TimedEvent = { id: string; start: number; end: number };
  const timedEvents: TimedEvent[] = tasks
    .map((task) => ({
      id: task.id,
      start: timeToMinutes(task.start_time),
      end: timeToMinutes(task.start_time) + task.duration_minutes,
    }))
    .sort((left, right) => left.start - right.start || (right.end - right.start) - (left.end - left.start));

  const laneById = new Map<string, number>();
  const columnEnds: number[] = [];

  timedEvents.forEach((event) => {
    let lane = columnEnds.findIndex((end) => end <= event.start);
    if (lane === -1) {
      lane = columnEnds.length;
      columnEnds.push(event.end);
    } else {
      columnEnds[lane] = event.end;
    }
    laneById.set(event.id, lane);
  });

  const layout = new Map<string, AgendaOverlapLayout>();
  timedEvents.forEach((event) => {
    const overlapping = timedEvents.filter((other) => other.start < event.end && other.end > event.start);
    const lanes = Math.max(1, ...overlapping.map((other) => (laneById.get(other.id) ?? 0) + 1));
    layout.set(event.id, { lane: laneById.get(event.id) ?? 0, lanes });
  });
  return layout;
}

type AgendaDragState = {
  taskId: string;
  mode: "move" | "resize";
  pointerId: number;
  startPointerY: number;
  startPointerX: number;
  originStart: number;
  originDuration: number;
  originColumnId: string;
  moved: boolean;
};

function scheduleStatusLabel(status: PrintScheduleStatus): string {
  switch (status) {
    case "planned":
      return "Planejado";
    case "printing":
      return "Imprimindo";
    case "done":
      return "Concluído";
    case "failed":
      return "Falhou";
    case "cancelled":
      return "Cancelado";
    default:
      return status;
  }
}

function parseIsoDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
}

function formatIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatBrazilianDate(iso: string): string {
  const date = parseIsoDate(iso);
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${day}/${month}/${date.getFullYear()}`;
}

function parseBrazilianDateInput(value: string): string | null {
  const trimmed = value.trim();
  const match = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!match) return null;
  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
  return formatIsoDate(date);
}

function capitalizeBrazilianDateLabel(label: string): string {
  if (!label) return label;
  return label.charAt(0).toLocaleUpperCase("pt-BR") + label.slice(1);
}

function BrazilianDateInput({
  value,
  onChange,
  className,
  disabled,
  "aria-label": ariaLabel,
}: {
  value: string;
  onChange: (iso: string) => void;
  className?: string;
  disabled?: boolean;
  "aria-label"?: string;
}) {
  const [draft, setDraft] = useState(() => formatBrazilianDate(value));

  useEffect(() => {
    setDraft(formatBrazilianDate(value));
  }, [value]);

  function commitDraft(nextDraft: string) {
    const parsed = parseBrazilianDateInput(nextDraft);
    if (parsed) {
      onChange(parsed);
      setDraft(formatBrazilianDate(parsed));
      return;
    }
    setDraft(formatBrazilianDate(value));
  }

  return (
    <input
      className={className}
      type="text"
      inputMode="numeric"
      autoComplete="off"
      placeholder="dd/mm/aaaa"
      aria-label={ariaLabel}
      disabled={disabled}
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => commitDraft(draft)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          commitDraft(draft);
        }
      }}
    />
  );
}

function startOfWeek(date: Date): Date {
  const copy = new Date(date);
  const day = copy.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + diff);
  return copy;
}

function addDays(date: Date, days: number): Date {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function scheduleRange(view: ScheduleView, anchor: string): { from: string; to: string } {
  const date = parseIsoDate(anchor);
  if (view === "day") return { from: anchor, to: anchor };
  if (view === "week") {
    const monday = startOfWeek(date);
    return { from: formatIsoDate(monday), to: formatIsoDate(addDays(monday, 6)) };
  }
  const first = new Date(date.getFullYear(), date.getMonth(), 1);
  const last = new Date(date.getFullYear(), date.getMonth() + 1, 0);
  return { from: formatIsoDate(first), to: formatIsoDate(last) };
}

function daysInRange(from: string, to: string): number {
  const start = parseIsoDate(from);
  const end = parseIsoDate(to);
  return Math.max(1, Math.round((end.getTime() - start.getTime()) / 86400000) + 1);
}

function eachDateInRange(from: string, to: string): string[] {
  const dates: string[] = [];
  let current = parseIsoDate(from);
  const end = parseIsoDate(to);
  while (current <= end) {
    dates.push(formatIsoDate(current));
    current = addDays(current, 1);
  }
  return dates;
}

function shiftScheduleAnchor(view: ScheduleView, anchor: string, delta: number): string {
  const date = parseIsoDate(anchor);
  if (view === "day") return formatIsoDate(addDays(date, delta));
  if (view === "week") return formatIsoDate(addDays(date, delta * 7));
  return formatIsoDate(new Date(date.getFullYear(), date.getMonth() + delta, 1));
}

function schedulePeriodLabel(view: ScheduleView, anchor: string, from: string, to: string): string {
  if (view === "day") {
    return capitalizeBrazilianDateLabel(
      parseIsoDate(anchor).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" }),
    );
  }
  if (view === "week") {
    return `${formatBrazilianDate(from)} – ${formatBrazilianDate(to)}`;
  }
  return capitalizeBrazilianDateLabel(
    parseIsoDate(anchor).toLocaleDateString("pt-BR", { month: "long", year: "numeric" }),
  );
}

function isScheduleFailure(task: PrintScheduleTask): boolean {
  return task.status === "failed" || task.status === "cancelled";
}

function schedulePrintingMinutes(task: PrintScheduleTask): number {
  if (task.status === "cancelled") return 0;
  return Math.max(0, task.duration_minutes);
}

function computeScheduleMetrics(
  tasks: PrintScheduleTask[],
  printers: Printer3D[],
  from: string,
  to: string,
) {
  const activePrinters = printers.filter((printer) => printer.active);
  const printerCount = activePrinters.length;
  const dayCount = daysInRange(from, to);
  const availableMinutes = printerCount * 24 * 60 * dayCount;
  const printingMinutes = tasks.reduce((sum, task) => sum + schedulePrintingMinutes(task), 0);
  const failures = tasks.filter(isScheduleFailure).length;
  const perPrinter = activePrinters.map((printer) => {
    const minutes = tasks
      .filter((task) => task.printer_id === printer.id)
      .reduce((sum, task) => sum + schedulePrintingMinutes(task), 0);
    const dailyOccupancy = printerCount ? minutes / (24 * 60 * dayCount) : 0;
    return { printer, minutes, dailyOccupancy };
  });
  return {
    activePrinters,
    printerCount,
    dayCount,
    availableMinutes,
    printingMinutes,
    farmOccupancy: availableMinutes > 0 ? printingMinutes / availableMinutes : 0,
    failureRate: tasks.length ? failures / tasks.length : 0,
    failures,
    totalTasks: tasks.length,
    perPrinter,
  };
}

function formatPercent(value: number): string {
  return `${Math.round(value * 1000) / 10}%`;
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
        productListed(product) ? "a venda à venda vendido publicado" : "nao esta a venda não está à venda",
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
  schedule: {
    eyebrow: "Agenda",
    title: "Impressões",
  },
  settings: {
    eyebrow: "Chaves e pastas",
    title: "Ajustes",
  },
}

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [storeProfiles, setStoreProfiles] = useState<StoreProfile[]>([]);
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [activeTab, setActiveTab] = useState<AppTab>("dashboard");
  const [activeProjectId, setActiveProjectId] = useState<string>("");
  const [selectedProductId, setSelectedProductId] = useState<string>("");
  const [projectName, setProjectName] = useState("Campanha utilidades casa");
  const [keyword, setKeyword] = useState("organizador cozinha");
  const [manualUrl, setManualUrl] = useState("");
  const [collectLimit, setCollectLimit] = useState(8);
  const [collectScrolls, setCollectScrolls] = useState(8);
  const [visibleBrowser, setVisibleBrowser] = useState(true);
  const [activeStoreProfileId, setActiveStoreProfileId] = useState("");
  const [storeProfileDraft, setStoreProfileDraft] = useState<StoreProfile | null>(null);
  const [openRouterApiKeyDraft, setOpenRouterApiKeyDraft] = useState("");
  const [openRouterModelDraft, setOpenRouterModelDraft] = useState("qwen/qwen3.5-flash-02-23");
  const [kieApiKeyDraft, setKieApiKeyDraft] = useState("");
  const [kieImageModelDraft, setKieImageModelDraft] = useState("qwen/image-edit");
  const [r2AccountIdDraft, setR2AccountIdDraft] = useState("");
  const [r2BucketDraft, setR2BucketDraft] = useState("");
  const [r2AccessKeyDraft, setR2AccessKeyDraft] = useState("");
  const [r2SecretKeyDraft, setR2SecretKeyDraft] = useState("");
  const [r2PublicUrlDraft, setR2PublicUrlDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [appUpdate, setAppUpdate] = useState<AppUpdateState>({ phase: "idle" });
  const [listingDraft, setListingDraft] = useState<Listing | null>(null);
  const [productNameDraft, setProductNameDraft] = useState("");
  const [lastExport, setLastExport] = useState<{ path: string; count: number; marketplace: string } | null>(null);
  const [makerWorldLogin, setMakerWorldLogin] = useState<MakerWorldLoginStatus | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [productFilters, setProductFilters] = useState<ProductFilters>({ query: "", status: "all", characteristic: "all" });
  const [imageOptions, setImageOptions] = useState<ImageOptions>({ studio_prompts: [], colors: [] });
  const [selectedColorVariations, setSelectedColorVariations] = useState<string[]>([]);
  const [batchProgress, setBatchProgress] = useState<BatchProgress>(null);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialog>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [blockedSourceUrls, setBlockedSourceUrls] = useState<BlockedSourceUrl[]>([]);
  const [filaments, setFilaments] = useState<FilamentSpool[]>([]);
  const [productionSettings, setProductionSettings] = useState<ProductionSettings | null>(null);
  const [printers, setPrinters] = useState<Printer3D[]>([]);
  const [scheduleTasks, setScheduleTasks] = useState<PrintScheduleTask[]>([]);
  const [scheduleDate, setScheduleDate] = useState(todayDateString());
  const [scheduleView, setScheduleView] = useState<ScheduleView>("day");

  const activeStoreProfile = storeProfiles.find((profile) => profile.id === activeStoreProfileId) ?? storeProfiles[0];
  const activeStoreProjects = useMemo(() => {
    if (!activeStoreProfile) return [];
    return projects.filter((project) =>
      project.store_profile_id
        ? project.store_profile_id === activeStoreProfile.id
        : project.store === activeStoreProfile.name,
    );
  }, [projects, activeStoreProfile?.id, activeStoreProfile?.name]);
  const activeStoreProjectIds = useMemo(
    () => new Set(activeStoreProjects.map((project) => project.id)),
    [activeStoreProjects],
  );
  const activeProject = activeStoreProjects.find((project) => project.id === activeProjectId) ?? activeStoreProjects[0];
  const storeJobs = useMemo(
    () => jobs.filter((job) => !job.project_id || activeStoreProjectIds.has(job.project_id)),
    [jobs, activeStoreProjectIds],
  );
  const projectProducts = useMemo(
    () => products.filter((product) => activeStoreProjectIds.has(product.project_id)),
    [products, activeStoreProjectIds],
  );
  const filteredProjectProducts = useMemo(
    () => filterProducts(projectProducts, productFilters),
    [projectProducts, productFilters],
  );
  const selectedProduct = projectProducts.find((product) => product.id === selectedProductId) ?? filteredProjectProducts[0] ?? projectProducts[0];

  async function refresh() {
    const [nextProjects, nextProducts, nextJobs, nextSettings, nextStoreProfiles, nextImageOptions, nextRuntimeStatus] = await Promise.all([
      api<Project[]>("/api/projects"),
      api<Product[]>("/api/products"),
      api<Job[]>("/api/jobs"),
      api<SettingsPayload>("/api/settings"),
      api<StoreProfile[]>("/api/store-profiles"),
      api<ImageOptions>("/api/image-options"),
      api<RuntimeStatus>("/api/runtime/status"),
    ]);
    setProjects(nextProjects);
    setProducts(nextProducts);
    setJobs(nextJobs);
    setStoreProfiles(nextStoreProfiles);
    const nextStore = nextStoreProfiles.find((profile) => profile.id === activeStoreProfileId) ?? nextStoreProfiles[0];
    if (nextStore && !activeStoreProfileId) setActiveStoreProfileId(nextStore.id);
    if (nextStore) {
      const nextStoreProjects = nextProjects.filter((project) =>
        project.store_profile_id ? project.store_profile_id === nextStore.id : project.store === nextStore.name,
      );
      if ((!activeProjectId || !nextStoreProjects.some((project) => project.id === activeProjectId)) && nextStoreProjects[0]) {
        setActiveProjectId(nextStoreProjects[0].id);
        setProjectName(nextStoreProjects[0].name);
      }
    }
    if (nextStore && (!storeProfileDraft || nextStore.id === activeStoreProfileId)) setStoreProfileDraft(nextStore);
    setSettings(nextSettings);
    setRuntimeStatus(nextRuntimeStatus);
    setImageOptions(nextImageOptions);
    setOpenRouterModelDraft(nextSettings.integrations.openrouter_model || "qwen/qwen3.5-flash-02-23");
    setKieImageModelDraft(nextSettings.integrations.kie_image_model || "qwen/image-edit");
    const isCleanDefaultWorkspace =
      (nextStoreProfiles.length === 0 || (nextStoreProfiles.length === 1 && nextStoreProfiles[0]?.name === "Loja principal")) &&
      nextProjects.length === 0 &&
      nextProducts.length === 0;
    if (isCleanDefaultWorkspace && window.localStorage.getItem(ONBOARDING_COMPLETE_KEY) !== "true") {
      setOnboardingOpen(true);
    }
    api<MakerWorldLoginStatus>("/api/jobs/makerworld-login")
      .then(setMakerWorldLogin)
      .catch(() => undefined);
  }

  async function refreshCatalog() {
    const [nextProjects, nextProducts, nextJobs] = await Promise.all([
      api<Project[]>("/api/projects"),
      api<Product[]>("/api/products"),
      api<Job[]>("/api/jobs"),
    ]);
    setProjects(nextProjects);
    setProducts(nextProducts);
    setJobs(nextJobs);
  }

  async function refreshProducts() {
    const nextProducts = await api<Product[]>("/api/products");
    setProducts(nextProducts);
  }

  function patchProduct(updated: Product) {
    setProducts((current) => {
      const exists = current.some((product) => product.id === updated.id);
      if (!exists) return [...current, updated];
      return current.map((product) => (product.id === updated.id ? updated : product));
    });
  }

  function patchProject(updated: Project) {
    setProjects((current) => {
      const exists = current.some((project) => project.id === updated.id);
      if (!exists) return [...current, updated];
      return current.map((project) => (project.id === updated.id ? updated : project));
    });
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
    setProducts((current) => current.filter((product) => product.id !== productId));
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
    if (mode === "all") await refresh();
    else if (mode === "catalog") await refreshCatalog();
  }

  useEffect(() => {
    refresh().catch((error) => setNotice(error.message));
  }, []);

  useEffect(() => {
    if (!window.ecoNative?.onUpdateEvent) return;
    return window.ecoNative.onUpdateEvent((event) => {
      if (event.type === "available") {
        setAppUpdate((prev) => ({
          phase: "available",
          version: event.version,
          currentVersion: event.currentVersion,
          bannerDismissed: prev.bannerDismissed && prev.version === event.version,
        }));
        return;
      }
      if (event.type === "not-available") {
        setAppUpdate((prev) => (
          prev.phase === "checking"
            ? {
                phase: "uptodate",
                currentVersion: event.currentVersion,
                message: `Você já está na versão mais recente (${event.currentVersion}).`,
              }
            : prev
        ));
        return;
      }
      if (event.type === "progress") {
        setAppUpdate((prev) => ({
          ...prev,
          phase: "downloading",
          progress: Math.min(100, Math.max(0, event.percent ?? 0)),
          bannerDismissed: false,
        }));
        return;
      }
      if (event.type === "downloaded") {
        setAppUpdate((prev) => ({
          ...prev,
          phase: "downloaded",
          version: event.version ?? prev.version,
          progress: 100,
          message: "Atualização pronta para instalar.",
          bannerDismissed: false,
        }));
        return;
      }
      setAppUpdate((prev) => ({
        ...prev,
        phase: "error",
        message: event.message ?? "Erro ao atualizar.",
      }));
    });
  }, []);

  async function checkAppUpdates() {
    if (!window.ecoNative?.checkForUpdates) {
      setAppUpdate({ phase: "error", message: "Atualizações ficam disponíveis no app instalado." });
      return;
    }
    setAppUpdate((prev) => ({ ...prev, phase: "checking", message: undefined }));
    const result = await window.ecoNative.checkForUpdates();
    if (!result.ok) {
      setAppUpdate({ phase: "error", message: result.message ?? "Não foi possível verificar atualizações." });
      return;
    }
    if (result.status === "available") {
      setAppUpdate({
        phase: "available",
        version: result.version,
        currentVersion: result.currentVersion,
        message: result.message,
      });
      return;
    }
    setAppUpdate({
      phase: "uptodate",
      currentVersion: result.currentVersion,
      message: result.message,
    });
  }

  async function downloadAppUpdate() {
    if (!window.ecoNative?.downloadUpdate) return;
    setAppUpdate((prev) => ({
      ...prev,
      phase: "downloading",
      progress: 0,
      message: "Baixando atualização...",
      bannerDismissed: false,
    }));
    const result = await window.ecoNative.downloadUpdate();
    if (!result.ok) {
      setAppUpdate((prev) => ({
        ...prev,
        phase: "error",
        message: result.message ?? "Falha no download.",
      }));
    }
  }

  async function installAppUpdate() {
    await window.ecoNative?.installUpdate();
  }

  function dismissAppUpdateBanner() {
    setAppUpdate((prev) => ({ ...prev, bannerDismissed: true }));
  }

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

  useEffect(() => {
    if (selectedProduct) {
      setListingDraft(selectedProduct.listing);
      setProductNameDraft(selectedProduct.name);
    } else {
      setListingDraft(null);
      setProductNameDraft("");
    }
  }, [selectedProduct?.id, selectedProduct?.name, listingFingerprint(selectedProduct?.listing)]);

  useEffect(() => {
    if (!activeProject?.id) {
      setBlockedSourceUrls([]);
      return undefined;
    }
    let cancelled = false;
    api<BlockedSourceUrl[]>(`/api/projects/${activeProject.id}/blocked-urls`)
      .then((entries) => {
        if (!cancelled) setBlockedSourceUrls(entries);
      })
      .catch(() => {
        if (!cancelled) setBlockedSourceUrls([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeProject?.id, products.length]);

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
  }, [activeStoreProfile?.id, products.length]);

  useEffect(() => {
    let cancelled = false;
    api<Printer3D[]>("/api/printers")
      .then((entries) => {
        if (!cancelled) setPrinters(entries);
      })
      .catch(() => {
        if (!cancelled) setPrinters([]);
      });
    return () => {
      cancelled = true;
    };
  }, [products.length]);

  useEffect(() => {
    const viewRange = scheduleRange(scheduleView, scheduleDate);
    const weekRange = scheduleRange("week", todayDateString());
    const from = viewRange.from < weekRange.from ? viewRange.from : weekRange.from;
    const to = viewRange.to > weekRange.to ? viewRange.to : weekRange.to;
    let cancelled = false;
    api<PrintScheduleTask[]>(`/api/schedule?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`)
      .then((entries) => {
        if (!cancelled) setScheduleTasks(entries);
      })
      .catch(() => {
        if (!cancelled) setScheduleTasks([]);
      });
    return () => {
      cancelled = true;
    };
  }, [scheduleView, scheduleDate, products.length]);

  async function removeBlockedUrl(entryId: string) {
    if (!activeProject?.id) return;
    try {
      setBusy(true);
      await api(`/api/projects/${activeProject.id}/blocked-urls/${entryId}`, { method: "DELETE" });
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
      return;
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

  async function savePrinter(payload: {
    id?: string;
    name: string;
    model: string;
    notes: string;
    active: boolean;
  }) {
    if (payload.id) {
      const updated = await api<Printer3D>(`/api/printers/${payload.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: payload.name,
          model: payload.model || null,
          notes: payload.notes || null,
          active: payload.active,
        }),
      });
      setPrinters((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      return updated;
    }
    const created = await api<Printer3D>("/api/printers", {
      method: "POST",
      body: JSON.stringify({
        name: payload.name,
        model: payload.model || null,
        notes: payload.notes || null,
        active: payload.active,
      }),
    });
    setPrinters((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name, "pt-BR")));
    return created;
  }

  async function deletePrinter(printerId: string) {
    await api(`/api/printers/${printerId}`, { method: "DELETE" });
    setPrinters((current) => current.filter((item) => item.id !== printerId));
    setScheduleTasks((current) => current.filter((item) => item.printer_id !== printerId));
  }

  async function reloadPrinters() {
    const entries = await api<Printer3D[]>("/api/printers");
    setPrinters(entries);
    return entries;
  }

  async function createScheduleTask(payload: {
    printer_id: string;
    scheduled_date: string;
    start_time: string;
    duration_minutes: number;
    product_id?: string | null;
    plate_id?: string | null;
    title: string;
    quantity: number;
    notes: string;
  }) {
    const created = await api<PrintScheduleTask>("/api/schedule", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (created.scheduled_date >= scheduleRange(scheduleView, scheduleDate).from
      && created.scheduled_date <= scheduleRange(scheduleView, scheduleDate).to) {
      setScheduleTasks((current) => [...current, created].sort((a, b) =>
        a.scheduled_date.localeCompare(b.scheduled_date) || a.start_time.localeCompare(b.start_time)));
    }
    return created;
  }

  async function updateScheduleTask(taskId: string, payload: Partial<PrintScheduleTask>) {
    const previous = scheduleTasks.find((item) => item.id === taskId);
    if (previous) {
      const optimistic: PrintScheduleTask = { ...previous, ...payload };
      setScheduleTasks((current) => {
        const without = current.filter((item) => item.id !== taskId);
        const { from, to } = scheduleRange(scheduleView, scheduleDate);
        if (optimistic.scheduled_date < from || optimistic.scheduled_date > to) return without;
        return [...without, optimistic].sort((a, b) =>
          a.scheduled_date.localeCompare(b.scheduled_date) || a.start_time.localeCompare(b.start_time));
      });
    }
    try {
      const updated = await api<PrintScheduleTask>(`/api/schedule/${taskId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setScheduleTasks((current) => {
        const without = current.filter((item) => item.id !== taskId);
        const { from, to } = scheduleRange(scheduleView, scheduleDate);
        if (updated.scheduled_date < from || updated.scheduled_date > to) return without;
        return [...without, updated].sort((a, b) =>
          a.scheduled_date.localeCompare(b.scheduled_date) || a.start_time.localeCompare(b.start_time));
      });
      return updated;
    } catch (error) {
      if (previous) {
        setScheduleTasks((current) => {
          const without = current.filter((item) => item.id !== taskId);
          const { from, to } = scheduleRange(scheduleView, scheduleDate);
          if (previous.scheduled_date < from || previous.scheduled_date > to) return without;
          return [...without, previous].sort((a, b) =>
            a.scheduled_date.localeCompare(b.scheduled_date) || a.start_time.localeCompare(b.start_time));
        });
      }
      throw error;
    }
  }

  async function deleteScheduleTask(taskId: string) {
    await api(`/api/schedule/${taskId}`, { method: "DELETE" });
    setScheduleTasks((current) => current.filter((item) => item.id !== taskId));
  }

  async function savePrintPlates(productId: string, plates: PrintPlate[]) {
    const result = await api<{ plates: PrintPlate[] }>(`/api/products/${productId}/print-plates`, {
      method: "PUT",
      body: JSON.stringify({ plates }),
    });
    setProducts((current) =>
      current.map((product) =>
        product.id === productId
          ? { ...product, metadata: { ...product.metadata, print_plates: result.plates } }
          : product,
      ),
    );
    return result.plates;
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
    setProducts((current) => current.map((product) => {
      const draft = updates.get(product.id);
      if (!draft) return product;
      return {
        ...product,
        metadata: {
          ...product.metadata,
          production_cost: productionCostPayloadFromDraft(draft),
        },
      };
    }));
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

  function createProject() {
    return (async () => {
      const created = await runAction("Criando projeto", async () => {
        const project = await api<Project>("/api/projects", {
          method: "POST",
          body: JSON.stringify({
            name: projectName,
            store: activeStoreProfile?.name ?? "Loja principal",
            store_profile_id: activeStoreProfile?.id ?? null,
            marketplace: activeStoreProfile?.marketplace ?? "shopee",
            niche: activeStoreProfile?.niche ?? "Utilidades para casa",
          }),
        });
        patchProject(project);
        return project;
      }, { refresh: false, blockUi: true, notifySuccess: true });
      if (created) selectProject(created.id);
      return created;
    })();
  }

  function collectProducts() {
    if (!activeProject) return Promise.resolve();
    return runAction("Coletando produtos", () =>
      api<Job>("/api/jobs/collect", {
        method: "POST",
        body: JSON.stringify({
          project_id: activeProject.id,
          store_profile_id: activeStoreProfile?.id ?? null,
          keyword,
          urls: [],
          limit: collectLimit,
          scrolls: collectScrolls,
          visible_browser: visibleBrowser,
          skip_ai_curation: true,
        }),
      }),
    { refresh: "catalog", blockUi: true });
  }

  function extractSelectedLinks() {
    if (!activeProject) return Promise.resolve();
    const urls = manualUrl
      .split(/\s|,|\n/)
      .map((url) => url.trim())
      .filter(Boolean);
    if (!urls.length) {
      setNotice("Cole ao menos um link MakerWorld para extrair.");
      return Promise.resolve();
    }
    return runAction("Extraindo links selecionados", () =>
      api<Job>("/api/jobs/collect", {
        method: "POST",
        body: JSON.stringify({
          project_id: activeProject.id,
          store_profile_id: activeStoreProfile?.id ?? null,
          keyword: "",
          urls,
          limit: urls.length,
          scrolls: collectScrolls,
          visible_browser: visibleBrowser,
          skip_ai_curation: true,
        }),
      }),
    { refresh: "catalog", blockUi: true });
  }

  function openMakerWorldLogin() {
    return runAction("Abrindo login MakerWorld", async () => {
      const result = await api<MakerWorldLoginStatus>("/api/jobs/makerworld-login", {
        method: "POST",
      });
      setMakerWorldLogin(result);
      return result;
    });
  }

  function closeMakerWorldLogin() {
    return runAction("Fechando navegador MakerWorld", async () => {
      const result = await api<MakerWorldLoginStatus>("/api/jobs/makerworld-login/close", {
        method: "POST",
      });
      setMakerWorldLogin(result);
      return result;
    });
  }

  function saveOpenRouterSettings() {
    return runFluidAction("Salvando integrações IA", async () => {
      const updated = await api<SettingsPayload>("/api/settings", {
        method: "PATCH",
        body: JSON.stringify({
          openrouter_api_key: openRouterApiKeyDraft,
          openrouter_model: openRouterModelDraft,
          kie_api_key: kieApiKeyDraft,
          kie_image_model: kieImageModelDraft,
          cloudflare_account_id: r2AccountIdDraft,
          cloudflare_r2_bucket_name: r2BucketDraft,
          cloudflare_r2_access_key: r2AccessKeyDraft,
          cloudflare_r2_secret_key: r2SecretKeyDraft,
          cloudflare_r2_public_url: r2PublicUrlDraft,
        }),
      });
      setSettings(updated);
      setOpenRouterApiKeyDraft("");
      setKieApiKeyDraft("");
      setR2AccountIdDraft("");
      setR2BucketDraft("");
      setR2AccessKeyDraft("");
      setR2SecretKeyDraft("");
      setR2PublicUrlDraft("");
      setNotice("Integrações salvas.");
      return updated;
    });
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
      if (payload.cloudflare_account_id.trim()) integrationPayload.cloudflare_account_id = payload.cloudflare_account_id.trim();
      if (payload.cloudflare_r2_bucket_name.trim()) integrationPayload.cloudflare_r2_bucket_name = payload.cloudflare_r2_bucket_name.trim();
      if (payload.cloudflare_r2_access_key.trim()) integrationPayload.cloudflare_r2_access_key = payload.cloudflare_r2_access_key.trim();
      if (payload.cloudflare_r2_secret_key.trim()) integrationPayload.cloudflare_r2_secret_key = payload.cloudflare_r2_secret_key.trim();
      if (payload.cloudflare_r2_public_url.trim()) integrationPayload.cloudflare_r2_public_url = payload.cloudflare_r2_public_url.trim();
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
    if (profile) {
      setStoreProfileDraft(profile);
      const nextProject = projects.find((project) =>
        project.store_profile_id ? project.store_profile_id === profile.id : project.store === profile.name,
      );
      selectProject(nextProject?.id ?? "", { syncName: Boolean(nextProject) });
    }
  }

  function selectProject(projectId: string, options?: { syncName?: boolean }) {
    setActiveProjectId(projectId);
    if (options?.syncName !== false) {
      const project = projects.find((item) => item.id === projectId);
      if (project) setProjectName(project.name);
    }
    setSelectedProductId("");
    setSelectedProductIds([]);
    setDetailsOpen(false);
  }

  function saveStoreProfile() {
    if (!storeProfileDraft) return Promise.resolve();
    return runFluidAction("Salvando perfil de loja", async () => {
      const updated = await api<StoreProfile>(`/api/store-profiles/${storeProfileDraft.id}`, {
        method: "PATCH",
        body: JSON.stringify(storeProfileDraft),
      });
      patchStoreProfile(updated);
      setActiveStoreProfileId(updated.id);
      setNotice("Perfil de loja salvo.");
      return updated;
    });
  }

  function createStoreProfile() {
    return runFluidAction("Criando perfil de loja", async () => {
      const created = await api<StoreProfile>("/api/store-profiles", {
        method: "POST",
        body: JSON.stringify({
          name: `${storeProfileDraft?.name || "Nova loja"} cópia`,
          marketplace: storeProfileDraft?.marketplace || "shopee",
          niche: storeProfileDraft?.niche || "Utilidades para casa",
          ai_profile_id: storeProfileDraft?.ai_profile_id || null,
          search_prompt: storeProfileDraft?.search_prompt || "",
          curation_prompt: storeProfileDraft?.curation_prompt || "",
          listing_prompt: storeProfileDraft?.listing_prompt || "",
          image_prompt: storeProfileDraft?.image_prompt || "",
          image_prompts: storeProfileDraft?.image_prompts || {},
          color_variation_prompt: storeProfileDraft?.color_variation_prompt || "",
        }),
      });
      patchStoreProfile(created);
      setActiveStoreProfileId(created.id);
      setNotice("Perfil de loja criado.");
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

  function saveImageColorOptions(colors: ImageOptions["colors"]) {
    return runFluidAction("Salvando cores", async () => {
      const updated = await api<ImageOptions>("/api/image-options", {
        method: "PUT",
        body: JSON.stringify({ colors }),
      });
      setImageOptions(updated);
      setNotice("Cores salvas.");
      return updated;
    });
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
        `${summary.projects} projeto(s)`,
        `${summary.store_profiles} loja(s)`,
        summary.printers_3d ? `${summary.printers_3d} impressora(s)` : null,
        summary.print_schedule_tasks ? `${summary.print_schedule_tasks} impressão(ões) agendada(s)` : null,
        summary.filament_spools ? `${summary.filament_spools} filamento(s)` : null,
        `${summary.files} arquivo(s)`,
        summary.env_restored ? "integrações (.env)" : null,
      ].filter(Boolean).join(", ");
      setNotice(`Backup restaurado: ${restoredParts}.`);
      return summary;
    }, { refresh: "all", blockUi: true, notifySuccess: true });
  }

  function generateListing(productId = selectedProduct?.id) {
    if (!productId) return Promise.resolve();
    if (!settings?.integrations.openrouter) {
      setNotice("Configure OPENROUTER_API_KEY em Ajustes para gerar anúncios com IA.");
      return Promise.resolve();
    }
    return runAction("Gerando anúncio", () =>
      (async () => {
        const product = projectProducts.find((item) => item.id === productId);
        if (
          hasListingContent(product)
          && !(await confirmRegeneration(`"${product?.name ?? "Este produto"}" já possui descrição/anúncio gerado. Gerar novamente pode substituir o texto atual e somar novo custo de IA. Deseja continuar?`))
        ) {
          throw new Error("__cancelled__");
        }
        return api<Job>("/api/jobs/listing", {
        method: "POST",
        body: JSON.stringify({ product_id: productId }),
        });
      })(),
    { refresh: "catalog", blockUi: true });
  }

  function generateImages(productId = selectedProduct?.id) {
    if (!productId) return Promise.resolve();
    if (!settings?.integrations.kie_ai) {
      setNotice("Configure KIE_API_KEY em Ajustes para gerar imagens com Kie.ai/Qwen.");
      return Promise.resolve();
    }
    if (!settings?.integrations.cloudflare_r2) {
      setNotice("Configure Cloudflare R2 em Ajustes para salvar imagens permanentes e enviar URLs ao Kie.ai/Qwen.");
      return Promise.resolve();
    }
    return runAction("Gerando imagens base", () =>
      (async () => {
        const product = projectProducts.find((item) => item.id === productId);
        if (
          hasBaseImages(product)
          && !(await confirmRegeneration(`"${product?.name ?? "Este produto"}" já possui imagens base geradas. O sistema reutiliza arquivos existentes quando possível. Para recriar uma imagem específica, use o botão IA na miniatura. Deseja continuar?`))
        ) {
          throw new Error("__cancelled__");
        }
        return api<Job>("/api/jobs/images", {
        method: "POST",
        body: JSON.stringify({ product_id: productId, color_variations: [], generate_base_images: true }),
        });
      })(),
    { refresh: "catalog", blockUi: true });
  }

  function generateColorVariations(productId = selectedProduct?.id, colorVariations = selectedColorVariations) {
    if (!productId || !colorVariations.length) return Promise.resolve();
    if (!settings?.integrations.kie_ai) {
      setNotice("Configure KIE_API_KEY em Ajustes para gerar variações de cor com Kie.ai/Qwen.");
      return Promise.resolve();
    }
    if (!settings?.integrations.cloudflare_r2) {
      setNotice("Configure Cloudflare R2 em Ajustes para usar URLs permanentes nas variações de cor.");
      return Promise.resolve();
    }
    return runAction("Gerando variações de cor", () =>
      (async () => {
        const product = projectProducts.find((item) => item.id === productId);
        const alreadyGenerated = existingColorVariations(product, colorVariations);
        if (
          alreadyGenerated.length
          && !(await confirmRegeneration(`Este produto já possui variação(ões) para: ${alreadyGenerated.join(", ")}. O sistema reutiliza arquivos existentes quando possível. Deseja continuar?`))
        ) {
          throw new Error("__cancelled__");
        }
        return api<Job>("/api/jobs/images", {
        method: "POST",
        body: JSON.stringify({ product_id: productId, color_variations: colorVariations, generate_base_images: false }),
        });
      })(),
    { refresh: "catalog", blockUi: true });
  }

  function regenerateImage(productId: string, promptKey: string, extraPrompt: string) {
    if (!settings?.integrations.kie_ai) {
      setNotice("Configure KIE_API_KEY em Ajustes para recriar imagens com Kie.ai/Qwen.");
      return Promise.resolve();
    }
    if (!settings?.integrations.cloudflare_r2) {
      setNotice("Configure Cloudflare R2 em Ajustes para salvar a imagem recriada com URL permanente.");
      return Promise.resolve();
    }
    return runAction("Recriando imagem", () =>
      api<Job>("/api/jobs/image-regenerate", {
        method: "POST",
        body: JSON.stringify({ product_id: productId, prompt_key: promptKey, extra_prompt: extraPrompt }),
      }),
    { refresh: "catalog", blockUi: true });
  }

  function saveListing() {
    if (!selectedProduct || !listingDraft) return Promise.resolve();
    const payload: { listing: Listing; status?: ProductStatus; name?: string } = {
      listing: listingDraft,
      status: listingDraft.title && listingDraft.description ? "in_edit" : selectedProduct.status,
    };
    if (productNameDraft.trim() && productNameDraft.trim() !== selectedProduct.name) {
      payload.name = productNameDraft.trim();
    }
    return runFluidAction("Salvando anúncio", async () => {
      const updated = await api<Product>(`/api/products/${selectedProduct.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      patchProduct(updated);
      setNotice("Anúncio salvo.");
      return updated;
    });
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

  function uploadModelFile(productId: string, file: File) {
    return runAction("Enviando arquivo 3D", async () => {
      const updated = await apiUpload<Product>(`/api/products/${productId}/model-files`, file);
      patchProduct(updated);
      return updated;
    }, { refresh: false, blockUi: true, notifySuccess: true });
  }

  function deleteModelAsset(productId: string, assetId: string) {
    return runFluidAction("Removendo arquivo 3D", async () => {
      const updated = await api<Product>(`/api/products/${productId}/assets/${assetId}`, { method: "DELETE" });
      patchProduct(updated);
      setNotice("Arquivo 3D removido.");
      return updated;
    });
  }

  function updateProductListed(productId: string, listed: boolean) {
    return runFluidAction(listed ? "Marcando produto à venda" : "Removendo marcação de venda", async () => {
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

  async function deleteProduct(productId = selectedProduct?.id) {
    if (!productId) return Promise.resolve();
    const product = projectProducts.find((item) => item.id === productId);
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
    if (!activeProject?.id) {
      setNotice("Selecione um projeto antes de criar um produto.");
      return undefined;
    }
    const trimmedName = name.trim();
    if (!trimmedName) {
      setNotice("Informe o nome do produto.");
      return undefined;
    }
    return runFluidAction("Criando produto", async () => {
      const created = await api<Product>("/api/products", {
        method: "POST",
        body: JSON.stringify({
          project_id: activeProject.id,
          name: trimmedName,
          source_url: sourceUrl?.trim() || null,
        }),
      });
      patchProduct(created);
      setSelectedProductId(created.id);
      setDetailsOpen(true);
      setNotice(`Produto "${created.name}" criado.`);
      return created;
    });
  }

  function openProductFolder(productId = selectedProduct?.id) {
    if (!productId) return Promise.resolve();
    return runAction("Abrindo pasta do produto", () =>
      api<{ status: string; path: string }>(`/api/products/${productId}/open-folder`, {
        method: "POST",
      }),
    { refresh: false, blockUi: true, notifySuccess: true });
  }

  useEffect(() => {
    setSelectedProductIds((current) => {
      const projectIds = new Set(projectProducts.map((product) => product.id));
      const next = current.filter((id) => projectIds.has(id));
      return next.length === current.length ? current : next;
    });
  }, [projectProducts]);

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
        .map((id) => projectProducts.find((product) => product.id === id))
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
        .map((id) => projectProducts.find((product) => product.id === id))
        .filter((product): product is Product => Boolean(product && hasBaseImages(product)));
      if (
        withExisting.length
        && !(await confirmRegeneration(`${withExisting.length} produto(s) selecionado(s) já possuem imagens base. O sistema reutiliza arquivos existentes quando possível; para recriar imagens específicas, use o botão IA nas miniaturas. Deseja continuar?`))
      ) {
        return;
      }
    }
    try {
      setBusy(true);
      setBatchProgress({ label, total: productIds.length, done: 0, current: "Preparando..." });
      for (let index = 0; index < productIds.length; index += 1) {
        const productId = productIds[index];
        const product = projectProducts.find((item) => item.id === productId);
        const current = product?.name ?? productId;
        setNotice(`${label}: ${index + 1}/${productIds.length}`);
        setBatchProgress({ label, total: productIds.length, done: index, current });
        const job = await action(productId);
        await refreshCatalog();
        if (job.status === "failed") {
          const detail = job.logs?.length ? job.logs[job.logs.length - 1] : job.message;
          throw new Error(detail || `Falha em ${current}`);
        }
        setBatchProgress({ label, total: productIds.length, done: index + 1, current });
      }
      setNotice(`${label} concluído para ${productIds.length} produto(s).`);
    } catch (error) {
      if (error instanceof Error && error.message === "__cancelled__") {
        setNotice("Ação cancelada.");
        return;
      }
      setNotice(error instanceof Error ? error.message : "Erro inesperado no lote");
    } finally {
      setBusy(false);
      setTimeout(() => setBatchProgress(null), 1200);
    }
  }

  function generateListingsBatch(productIds = selectedProductIds) {
    if (!settings?.integrations.openrouter) {
      setNotice("Configure OPENROUTER_API_KEY em Ajustes para gerar anúncios com IA.");
      return Promise.resolve();
    }
    return runBatchProductAction("Gerando anúncios em lote", productIds, (productId) =>
      (async () => {
        const product = projectProducts.find((item) => item.id === productId);
        if (
          hasListingContent(product)
          && !(await confirmRegeneration(`"${product?.name ?? "Este produto"}" já possui descrição/anúncio gerado. Gerar novamente pode substituir o texto atual e somar novo custo de IA. Deseja continuar?`))
        ) {
          throw new Error("__cancelled__");
        }
        return api<Job>("/api/jobs/listing", {
        method: "POST",
        body: JSON.stringify({ product_id: productId }),
        });
      })(),
    );
  }

  function generateImagesBatch(productIds = selectedProductIds) {
    if (!settings?.integrations.kie_ai) {
      setNotice("Configure KIE_API_KEY em Ajustes para gerar imagens com Kie.ai/Qwen.");
      return Promise.resolve();
    }
    if (!settings?.integrations.cloudflare_r2) {
      setNotice("Configure Cloudflare R2 em Ajustes para salvar imagens permanentes e enviar URLs ao Kie.ai/Qwen.");
      return Promise.resolve();
    }
    return runBatchProductAction("Gerando imagens base em lote", productIds, (productId) =>
      (async () => {
        const product = projectProducts.find((item) => item.id === productId);
        if (
          hasBaseImages(product)
          && !(await confirmRegeneration(`"${product?.name ?? "Este produto"}" já possui imagens base geradas. O sistema reutiliza arquivos existentes quando possível. Para recriar uma imagem específica, use o botão IA na miniatura. Deseja continuar?`))
        ) {
          throw new Error("__cancelled__");
        }
        return api<Job>("/api/jobs/images", {
        method: "POST",
        body: JSON.stringify({ product_id: productId, color_variations: [], generate_base_images: true }),
        });
      })(),
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
      for (const productId of productIds) {
        await api<{ status: string; product_id: string }>(`/api/products/${productId}`, { method: "DELETE" });
        removeProductFromState(productId);
      }
      setSelectedProductIds([]);
      setNotice(`${productIds.length} produto(s) apagado(s).`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Erro ao apagar produtos");
    } finally {
      setBusy(false);
    }
  }

  function exportCsv(productIds = selectedProductIds) {
    if (!activeProject && !projectProducts.length) return Promise.resolve();
    if (!productIds.length) {
      setNotice("Selecione pelo menos um produto pronto para exportar.");
      return Promise.resolve();
    }
    const readySelectedIds = productIds.filter((id) => {
      const product = projectProducts.find((item) => item.id === id);
      return Boolean(product?.listing.title && product?.listing.description);
    });
    if (!readySelectedIds.length) {
      setNotice("Selecione produtos com anúncio gerado antes de exportar.");
      return Promise.resolve();
    }
    return runAction("Exportando CSV", async () => {
      const result = await api<{ path: string; count: number; marketplace: string }>("/api/exports", {
        method: "POST",
        body: JSON.stringify({
          project_id: activeProject?.id ?? projectProducts[0]?.project_id,
          marketplace: activeStoreProfile?.marketplace ?? activeProject?.marketplace ?? "shopee",
          product_ids: readySelectedIds,
        }),
      });
      setLastExport(result);
      return result;
    }, { refresh: false, blockUi: true, notifySuccess: true });
  }

  return (
    <main className="app-shell">
      {window.ecoNative?.platform === "win32" && (
        <div className="window-drag-region" aria-hidden="true" />
      )}
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
          <TabButton active={activeTab === "schedule"} icon={<CalendarDays size={18} />} onClick={() => setActiveTab("schedule")}>
            Impressões
          </TabButton>
        </nav>
        <nav className="sidebar-footer" aria-label="Ajustes">
          <TabButton active={activeTab === "settings"} icon={<Settings size={18} />} onClick={() => setActiveTab("settings")}>
            Ajustes
          </TabButton>
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
            activeStoreProfile={activeStoreProfile}
            jobs={storeJobs}
            lastExport={lastExport}
            products={projectProducts}
            projects={activeStoreProjects}
            runtimeStatus={runtimeStatus}
            printers={printers}
            scheduleTasks={scheduleTasks}
            onOpenSchedule={() => setActiveTab("schedule")}
          />
        )}

        {activeTab === "collect" && (
          <CollectTab
            activeProject={activeProject}
            activeStoreProfile={activeStoreProfile}
            busy={busy}
            jobs={storeJobs}
            keyword={keyword}
            limit={collectLimit}
            loginStatus={makerWorldLogin}
            manualUrl={manualUrl}
            productCount={projectProducts.filter((product) => product.project_id === activeProject?.id).length}
            projectName={projectName}
            projects={activeStoreProjects}
            scrolls={collectScrolls}
            visibleBrowser={visibleBrowser}
            onCollect={collectProducts}
            onExtractSelectedLinks={extractSelectedLinks}
            onCreateProject={createProject}
            onCloseLogin={closeMakerWorldLogin}
            onKeywordChange={setKeyword}
            onLimitChange={setCollectLimit}
            onOpenLogin={openMakerWorldLogin}
            onManualUrlChange={setManualUrl}
            onProjectNameChange={setProjectName}
            onScrollsChange={setCollectScrolls}
            onSelectProject={selectProject}
            onVisibleBrowserChange={setVisibleBrowser}
            blockedSourceUrls={blockedSourceUrls}
            onRemoveBlockedUrl={removeBlockedUrl}
          />
        )}

        {activeTab === "products" && (
          <ProductsTab
            activeProject={activeProject}
            batchProgress={batchProgress}
            busy={busy}
            imageOptions={imageOptions}
            jobs={storeJobs}
            listingDraft={listingDraft}
            productNameDraft={productNameDraft}
            filters={productFilters}
            products={filteredProjectProducts}
            totalProductCount={projectProducts.length}
            selectedProduct={selectedProduct}
            selectedProductIds={selectedProductIds}
            selectedColorVariations={selectedColorVariations}
            onCreateManualProduct={createManualProduct}
            onApproveProduct={approveProduct}
            onBatchGenerateImages={generateImagesBatch}
            onBatchGenerateListings={generateListingsBatch}
            onBatchDeleteProducts={deleteProductsBatch}
            onDeleteProduct={deleteProduct}
            onFiltersChange={setProductFilters}
            onGenerateColorVariations={generateColorVariations}
            onGenerateImages={generateImages}
            onGenerateListing={generateListing}
            onRegenerateImage={regenerateImage}
            onExportSelected={exportCsv}
            onOpenProductFolder={openProductFolder}
            onDeleteModelAsset={deleteModelAsset}
            onListingDraftChange={setListingDraft}
            onProductNameDraftChange={setProductNameDraft}
            onSaveListing={saveListing}
            onUploadModelFile={uploadModelFile}
            onUpdateProductListed={updateProductListed}
            onSavePrintPlates={(productId, plates) => runFluidAction("Salvando placas", () => savePrintPlates(productId, plates))}
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
            projects={activeStoreProjects}
            onSelectProject={selectProject}
          />
        )}

        {activeTab === "costs" && (
          <CostsTab
            activeStoreProfile={activeStoreProfile}
            busy={busy}
            filaments={filaments}
            productionSettings={productionSettings}
            products={projectProducts}
            runtimeStatus={runtimeStatus}
            onSaveAllProductionCosts={saveProductionCostsBatch}
            onProductionCostsSaved={syncProductionCostsInProducts}
          />
        )}

        {activeTab === "schedule" && (
          <ScheduleTab
            busy={busy}
            printers={printers.filter((item) => item.active)}
            products={products}
            projects={projects}
            scheduleDate={scheduleDate}
            scheduleView={scheduleView}
            tasks={scheduleTasks}
            onCreateTask={(payload) => runFluidAction("Adicionando impressão", () => createScheduleTask(payload))}
            onDeleteTask={(taskId) => runFluidAction("Removendo impressão", () => deleteScheduleTask(taskId))}
            onScheduleDateChange={setScheduleDate}
            onScheduleViewChange={setScheduleView}
            onUpdateTask={(taskId, payload) => runFluidAction("Atualizando impressão", () => updateScheduleTask(taskId, payload))}
          />
        )}

        {activeTab === "settings" && (
          <SettingsTab
            storeProfileDraft={storeProfileDraft}
            storeProfiles={storeProfiles}
            imageOptions={imageOptions}
            openRouterApiKeyDraft={openRouterApiKeyDraft}
            openRouterModelDraft={openRouterModelDraft}
            kieApiKeyDraft={kieApiKeyDraft}
            kieImageModelDraft={kieImageModelDraft}
            r2AccessKeyDraft={r2AccessKeyDraft}
            r2AccountIdDraft={r2AccountIdDraft}
            r2BucketDraft={r2BucketDraft}
            r2PublicUrlDraft={r2PublicUrlDraft}
            r2SecretKeyDraft={r2SecretKeyDraft}
            settings={settings}
            onOpenRouterApiKeyChange={setOpenRouterApiKeyDraft}
            onOpenRouterModelChange={setOpenRouterModelDraft}
            onKieApiKeyChange={setKieApiKeyDraft}
            onKieImageModelChange={setKieImageModelDraft}
            onR2AccessKeyChange={setR2AccessKeyDraft}
            onR2AccountIdChange={setR2AccountIdDraft}
            onR2BucketChange={setR2BucketDraft}
            onR2PublicUrlChange={setR2PublicUrlDraft}
            onR2SecretKeyChange={setR2SecretKeyDraft}
            onSaveOpenRouterSettings={saveOpenRouterSettings}
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
            onSavePrinter={savePrinter}
            onDeletePrinter={deletePrinter}
            onPrintersSaved={reloadPrinters}
            printers={printers}
            onWrapAction={runAction}
            appUpdate={appUpdate}
            onCheckAppUpdates={checkAppUpdates}
            onDownloadAppUpdate={downloadAppUpdate}
            onInstallAppUpdate={installAppUpdate}
          />
        )}
      </section>
      {onboardingOpen && (
        <OnboardingModal
          busy={busy}
          storeProfile={activeStoreProfile}
          openRouterModel={openRouterModelDraft}
          kieImageModel={kieImageModelDraft}
          onFinish={finishOnboarding}
          onSkip={skipOnboarding}
        />
      )}
      {window.ecoNative && (
        <AppUpdateBanner
          state={appUpdate}
          onDismiss={dismissAppUpdateBanner}
          onDownload={downloadAppUpdate}
          onInstall={installAppUpdate}
        />
      )}
      {notice && (
        <div className={busy ? "toast-notice busy-toast" : "toast-notice"} role="status" aria-live="polite">
          {busy && <Loader2 className="spin" size={16} />}
          <span>{displayText(notice)}</span>
          {!busy && (
            <button aria-label="Fechar aviso" onClick={() => setNotice("")}>
              ×
            </button>
          )}
        </div>
      )}
      {confirmDialog && (
        <ConfirmModal dialog={confirmDialog} onClose={closeConfirmDialog} />
      )}
    </main>
  );
}

function AppUpdateBanner({
  state,
  onDismiss,
  onDownload,
  onInstall,
}: {
  state: AppUpdateState;
  onDismiss: () => void;
  onDownload: () => void;
  onInstall: () => void;
}) {
  if (state.bannerDismissed) return null;
  if (state.phase === "idle" || state.phase === "checking" || state.phase === "uptodate" || state.phase === "error") {
    return null;
  }

  return (
    <div className="update-banner" role="status" aria-live="polite">
      {state.phase === "available" && (
        <>
          <div className="update-banner-copy">
            <strong>Nova versão {state.version}</strong>
            <span>Atualização disponível para o ECO Native Studio.</span>
          </div>
          <div className="update-banner-actions">
            <button className="primary" type="button" onClick={onDownload}>Baixar</button>
            <button className="primary ghost" type="button" onClick={onDismiss}>Agora não</button>
          </div>
        </>
      )}
      {state.phase === "downloading" && (
        <>
          <div className="update-banner-copy">
            <strong>Baixando {state.version ?? "atualização"}</strong>
            <span>{state.message ?? "Aguarde o download terminar."}</span>
          </div>
          <div className="update-progress">
            <div className="update-progress-track">
              <span style={{ width: `${Math.min(100, Math.max(0, state.progress ?? 0))}%` }} />
            </div>
            <small>{Math.round(state.progress ?? 0)}%</small>
          </div>
        </>
      )}
      {state.phase === "downloaded" && (
        <>
          <div className="update-banner-copy">
            <strong>Atualização pronta</strong>
            <span>Versão {state.version} baixada. Instale ao reiniciar o app.</span>
          </div>
          <div className="update-banner-actions">
            <button className="primary" type="button" onClick={onInstall}>Instalar e reiniciar</button>
            <button className="primary ghost" type="button" onClick={onDismiss}>Depois</button>
          </div>
        </>
      )}
    </div>
  );
}

function AppUpdateControls({
  state,
  onCheck,
  onDownload,
  onInstall,
}: {
  state: AppUpdateState;
  onCheck: () => void;
  onDownload: () => void;
  onInstall: () => void;
}) {
  const checking = state.phase === "checking";
  const downloading = state.phase === "downloading";

  return (
    <div className="app-update-controls">
      <div className="backup-actions">
        <button className="primary" type="button" onClick={onCheck} disabled={checking || downloading}>
          {checking ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />} Verificar atualizações
        </button>
        {state.phase === "available" && (
          <button className="primary ghost" type="button" onClick={onDownload}>
            <Download size={18} /> Baixar versão {state.version}
          </button>
        )}
        {state.phase === "downloaded" && (
          <button className="primary" type="button" onClick={onInstall}>
            <RefreshCw size={18} /> Instalar e reiniciar
          </button>
        )}
      </div>
      {downloading && (
        <div className="update-progress">
          <div className="update-progress-track">
            <span style={{ width: `${Math.min(100, Math.max(0, state.progress ?? 0))}%` }} />
          </div>
          <small>Baixando... {Math.round(state.progress ?? 0)}%</small>
        </div>
      )}
      {state.message && state.phase !== "downloading" && (
        <span className="update-status">{state.message}</span>
      )}
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

function OnboardingModal({
  busy,
  kieImageModel,
  openRouterModel,
  storeProfile,
  onFinish,
  onSkip,
}: {
  busy: boolean;
  kieImageModel: string;
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
  const [r2AccountId, setR2AccountId] = useState("");
  const [r2Bucket, setR2Bucket] = useState("");
  const [r2AccessKey, setR2AccessKey] = useState("");
  const [r2SecretKey, setR2SecretKey] = useState("");
  const [r2PublicUrl, setR2PublicUrl] = useState("");

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
      cloudflare_account_id: r2AccountId,
      cloudflare_r2_bucket_name: r2Bucket,
      cloudflare_r2_access_key: r2AccessKey,
      cloudflare_r2_secret_key: r2SecretKey,
      cloudflare_r2_public_url: r2PublicUrl,
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
              <input value={kieImageModelValue} onChange={(event) => setKieImageModelValue(event.target.value)} />
            </label>
          </section>

          <section className="onboarding-section">
            <div className="panel-title compact">
              <FolderOpen size={18} />
              <h3>Arquivos e exportação</h3>
            </div>
            <label>
              Cloudflare Account ID
              <input value={r2AccountId} onChange={(event) => setR2AccountId(event.target.value)} placeholder="opcional agora" />
            </label>
            <label>
              Bucket R2
              <input value={r2Bucket} onChange={(event) => setR2Bucket(event.target.value)} placeholder="opcional agora" />
            </label>
            <label>
              Access key
              <input type="password" value={r2AccessKey} onChange={(event) => setR2AccessKey(event.target.value)} placeholder="opcional agora" />
            </label>
            <label>
              Secret key
              <input type="password" value={r2SecretKey} onChange={(event) => setR2SecretKey(event.target.value)} placeholder="opcional agora" />
            </label>
            <label>
              URL pública do R2
              <input value={r2PublicUrl} onChange={(event) => setR2PublicUrl(event.target.value)} placeholder="https://..." />
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

function DashboardTab({
  activeStoreProfile,
  jobs,
  lastExport,
  products,
  projects,
  runtimeStatus,
  printers,
  scheduleTasks,
  onOpenSchedule,
}: {
  activeStoreProfile?: StoreProfile;
  jobs: Job[];
  lastExport: { path: string; count: number; marketplace: string } | null;
  products: Product[];
  projects: Project[];
  runtimeStatus: RuntimeStatus | null;
  printers: Printer3D[];
  scheduleTasks: PrintScheduleTask[];
  onOpenSchedule: () => void;
}) {
  const readyCount = products.filter((product) => product.listing.title && product.listing.description).length;
  const imageCount = products.filter((product) => product.assets.some(isImageAsset)).length;
  const modelCount = products.filter((product) => product.assets.some(isModelAsset)).length;
  const exportedCount = products.filter((product) => product.status === "exported").length;
  const pendingCount = Math.max(products.length - readyCount, 0);
  const totalCost = products.reduce((sum, product) => sum + productCostTotal(product), 0);
  const costEvents = products.flatMap(productCostEvents);
  const costSummary = summarizeCostEvents(costEvents);
  const collectJobs = jobs.filter((job) => job.type === "collect_products").slice(0, 5);
  const collectSummary = collectJobsSummary(jobs.filter((job) => job.type === "collect_products"));
  const readyPercent = products.length ? Math.round((readyCount / products.length) * 100) : 0;
  const chartReady = readyPercent;
  const chartImage = products.length ? Math.round((imageCount / products.length) * 100) : 0;
  const chartModel = products.length ? Math.round((modelCount / products.length) * 100) : 0;
  const chartExported = products.length ? Math.round((exportedCount / products.length) * 100) : 0;
  const maxCost = Math.max(costSummary.openRouter, costSummary.kie, costSummary.other, 0.000001);
  const usdBrl = Number(runtimeStatus?.exchange.usd_brl);
  const totalCostBrl = Number.isFinite(usdBrl) && usdBrl > 0 ? totalCost * usdBrl : null;
  const weekAnchor = todayDateString();
  const weekRange = useMemo(() => scheduleRange("week", weekAnchor), [weekAnchor]);
  const weekTasks = useMemo(
    () => scheduleTasks.filter((task) => task.scheduled_date >= weekRange.from && task.scheduled_date <= weekRange.to),
    [scheduleTasks, weekRange.from, weekRange.to],
  );
  const farmMetrics = useMemo(
    () => computeScheduleMetrics(weekTasks, printers, weekRange.from, weekRange.to),
    [weekTasks, printers, weekRange.from, weekRange.to],
  );
  const weekDates = useMemo(() => eachDateInRange(weekRange.from, weekRange.to), [weekRange.from, weekRange.to]);
  const weekTrend = useMemo(
    () => weekDates.map((date) => {
      const dayMinutes = weekTasks
        .filter((task) => task.scheduled_date === date)
        .reduce((sum, task) => sum + schedulePrintingMinutes(task), 0);
      const available = Math.max(1, farmMetrics.printerCount) * 24 * 60;
      return {
        label: parseIsoDate(date).toLocaleDateString("pt-BR", { weekday: "short", day: "numeric" }),
        value: available > 0 ? dayMinutes / available : 0,
      };
    }),
    [weekDates, weekTasks, farmMetrics.printerCount],
  );
  const weekLabel = schedulePeriodLabel("week", weekAnchor, weekRange.from, weekRange.to);

  return (
    <section className="dashboard-page">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Loja ativa</p>
          <h2>{activeStoreProfile?.name ?? "Nenhuma loja selecionada"}</h2>
          <span>{activeStoreProfile?.niche ?? "Crie ou selecione um perfil de loja"}</span>
        </div>
        <div className="dashboard-cost">
          <span>Custo IA total</span>
          <strong>{formatUsd(totalCost)}</strong>
          {totalCostBrl !== null && (
            <small>
              {formatBrl(totalCostBrl)}
              {runtimeStatus?.exchange.stale ? " · câmbio em cache" : ""}
            </small>
          )}
        </div>
      </div>

      <div className="dashboard-visual-grid">
        <div className="panel dashboard-chart-panel">
          <div className="panel-title">
            <BadgeCheck size={18} />
            <h2>Prontos para venda</h2>
          </div>
          <div className="donut-card">
            <div className="donut-chart" style={{ "--value": `${readyPercent}%` } as React.CSSProperties}>
              <span>{readyPercent}%</span>
            </div>
            <div className="donut-legend">
              <strong>{readyCount} de {products.length}</strong>
              <span>{pendingCount} pendente(s) de anúncio completo</span>
            </div>
          </div>
        </div>

        <div className="panel dashboard-chart-panel">
          <div className="panel-title">
            <ShoppingBag size={18} />
            <h2>Pipeline de produtos</h2>
          </div>
          <div className="bar-chart-list">
            <ChartBar label="Imagens" value={imageCount} total={products.length} percent={chartImage} />
            <ChartBar label="3MF" value={modelCount} total={products.length} percent={chartModel} />
            <ChartBar label="Anúncios" value={readyCount} total={products.length} percent={chartReady} />
            <ChartBar label="Exportados" value={exportedCount} total={products.length} percent={chartExported} />
          </div>
        </div>

        <div className="panel dashboard-chart-panel">
          <div className="panel-title">
            <BrainCircuit size={18} />
            <h2>Custo IA</h2>
          </div>
          <div className="cost-bars">
            <CostBar label="Texto/OpenRouter" value={costSummary.openRouter} max={maxCost} />
            <CostBar label="Imagem/Kie" value={costSummary.kie} max={maxCost} />
            <CostBar label="Outros" value={costSummary.other} max={maxCost} />
          </div>
        </div>
      </div>

      <div className="panel dashboard-farm-panel">
        <div className="panel-title dashboard-farm-title">
          <div>
            <CalendarDays size={18} />
            <h2>Farm de impressão</h2>
          </div>
          <button className="quiet-button" onClick={onOpenSchedule}>Abrir agenda</button>
        </div>
        <p className="settings-note section-intro">Semana atual · {weekLabel}</p>
        {!farmMetrics.printerCount ? (
          <div className="compact-empty">
            <strong>Nenhuma impressora ativa</strong>
            <span>Cadastre impressoras em Ajustes → Impressão para acompanhar ocupação e falhas.</span>
          </div>
        ) : (
          <>
            <div className="schedule-metrics-grid">
              <div className="schedule-metric-card">
                <span className="schedule-metric-label">Ocupação da farm</span>
                <strong>{formatPercent(farmMetrics.farmOccupancy)}</strong>
                <small>{formatPrintMinutes(farmMetrics.printingMinutes)} de {formatPrintMinutes(farmMetrics.availableMinutes)} disponíveis</small>
                <ScheduleMetricBar label="Capacidade geral" value={farmMetrics.farmOccupancy} />
              </div>
              <div className="schedule-metric-card">
                <span className="schedule-metric-label">Taxa de falha</span>
                <strong>{formatPercent(farmMetrics.failureRate)}</strong>
                <small>{farmMetrics.failures} falha(s) em {farmMetrics.totalTasks} impressão(ões)</small>
                <ScheduleMetricBar
                  label="Falhas + canceladas"
                  value={farmMetrics.failureRate}
                  tone={farmMetrics.failureRate > 0.15 ? "danger" : farmMetrics.failureRate > 0.05 ? "warn" : "default"}
                />
              </div>
              <div className="schedule-metric-card">
                <span className="schedule-metric-label">Impressoras ativas</span>
                <strong>{farmMetrics.printerCount}</strong>
                <small>{farmMetrics.totalTasks} job(s) nesta semana</small>
              </div>
            </div>
            <div className="schedule-metrics-charts">
              <div className="subsection-title">Ocupação por dia</div>
              {weekTrend.map((entry) => (
                <ScheduleMetricBar key={entry.label} label={entry.label} value={entry.value} tone={entry.value > 0.85 ? "warn" : "default"} />
              ))}
            </div>
          </>
        )}
      </div>

      <div className="dashboard-grid">
        <SummaryItem label="Projetos" value={projects.length.toString()} />
        <SummaryItem label="Produtos" value={products.length.toString()} />
        <SummaryItem label="Coletas" value={collectSummary.totalJobs.toString()} />
        <SummaryItem label="Coletados" value={collectSummary.totalProducts.toString()} />
        <SummaryItem label="Curadoria" value="Manual" />
        <SummaryItem label="CSV exportado" value={exportedCount.toString()} />
      </div>

      <div className="dashboard-panels">
        <div className="panel">
          <div className="panel-title">
            <PackageSearch size={18} />
            <h2>Últimas coletas</h2>
          </div>
          <div className="mini-job-list">
            {collectJobs.length ? (
              collectJobs.map((job) => {
                const cost = collectJobCost(job);
                return (
                  <div className="mini-job" key={job.id}>
                    <span>
                      <strong>{job.status === "completed" ? "Concluída" : job.status === "failed" ? "Falhou" : "Em andamento"}</strong>
                      <small>{displayText(job.message)}</small>
                      <small>IA: {formatUsd(cost.cost)}</small>
                    </span>
                    <progress max={100} value={job.progress} />
                  </div>
                );
              })
            ) : (
              <div className="compact-empty">
                <strong>Nenhuma coleta ainda</strong>
                <span>As coletas recentes da loja ativa aparecerão aqui.</span>
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">
            <Download size={18} />
            <h2>Último CSV</h2>
          </div>
          {lastExport ? (
            <div className="export-result">
              <strong>{lastExport.count} produto(s)</strong>
              <span>{lastExport.marketplace}</span>
              <code>{lastExport.path}</code>
            </div>
          ) : (
            <div className="compact-empty">
              <strong>Nenhuma exportação nesta sessão</strong>
              <span>Selecione produtos em Produtos e use Exportar CSV.</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function ChartBar({ label, percent, total, value }: { label: string; percent: number; total: number; value: number }) {
  return (
    <div className="chart-bar-row">
      <div>
        <strong>{label}</strong>
        <span>{value}/{total}</span>
      </div>
      <div className="chart-bar-track">
        <span style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
      </div>
    </div>
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

function ProjectPicker({
  activeProject,
  projects,
  onChange,
  variant = "inline",
}: {
  activeProject?: Project;
  projects: Project[];
  onChange: (projectId: string) => void;
  variant?: "inline" | "sidebar";
}) {
  const [open, setOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement | null>(null);

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
    <div className={variant === "sidebar" ? "project-picker sidebar" : "project-picker inline"} ref={pickerRef}>
      <div className="project-picker-control">
        <button
          className="project-picker-button"
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          disabled={!projects.length}
        >
          <FolderOpen size={16} aria-hidden="true" />
          <span>{activeProject?.name ?? (projects.length ? "Selecionar projeto" : "Nenhum projeto")}</span>
          <ChevronDown size={16} aria-hidden="true" />
        </button>
        {open && projects.length > 0 && (
          <div className="project-picker-menu" role="listbox">
            {projects.map((project) => {
              const selected = project.id === activeProject?.id;
              return (
                <button
                  className={selected ? "project-picker-option active" : "project-picker-option"}
                  key={project.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => {
                    onChange(project.id);
                    setOpen(false);
                  }}
                >
                  <span className="project-picker-option-icon" aria-hidden="true">
                    <FolderOpen size={15} />
                  </span>
                  <span className="project-picker-option-copy">
                    <strong>{project.name}</strong>
                    <small>{formatProjectDate(project.created_at)}</small>
                  </span>
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

function formatProjectDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Projeto";
  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}

function CollectTab({
  activeProject,
  activeStoreProfile,
  busy,
  jobs,
  keyword,
  limit,
  loginStatus,
  manualUrl,
  productCount,
  projectName,
  projects,
  scrolls,
  visibleBrowser,
  onCollect,
  onCloseLogin,
  onCreateProject,
  onExtractSelectedLinks,
  onKeywordChange,
  onLimitChange,
  onOpenLogin,
  onManualUrlChange,
  onProjectNameChange,
  onScrollsChange,
  onSelectProject,
  onVisibleBrowserChange,
  blockedSourceUrls,
  onRemoveBlockedUrl,
}: {
  activeProject?: Project;
  activeStoreProfile?: StoreProfile;
  busy: boolean;
  jobs: Job[];
  keyword: string;
  limit: number;
  loginStatus: MakerWorldLoginStatus | null;
  manualUrl: string;
  productCount: number;
  projectName: string;
  projects: Project[];
  scrolls: number;
  visibleBrowser: boolean;
  onCollect: () => void;
  onCloseLogin: () => void;
  onCreateProject: () => void;
  onExtractSelectedLinks: () => void;
  onKeywordChange: (value: string) => void;
  onLimitChange: (value: number) => void;
  onOpenLogin: () => void;
  onManualUrlChange: (value: string) => void;
  onProjectNameChange: (value: string) => void;
  onScrollsChange: (value: number) => void;
  onSelectProject: (projectId: string) => void;
  onVisibleBrowserChange: (value: boolean) => void;
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

        <div className="form-grid">
          <label className="full-span project-active-field">
            Projeto ativo
            <ProjectPicker activeProject={activeProject} projects={projects} onChange={onSelectProject} />
            <small>
              {activeProject
                ? `${productCount} produto(s) neste projeto · ${blockedSourceUrls.length} URL(s) bloqueada(s)`
                : "Selecione ou crie um projeto para coletar."}
            </small>
          </label>

          <label>
            Nome do novo projeto
            <input value={projectName} onChange={(event) => onProjectNameChange(event.target.value)} />
          </label>

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
            checked={visibleBrowser}
            onChange={(event) => onVisibleBrowserChange(event.target.checked)}
          />
          Usar navegador visível com sessão salva
        </label>

        <div className="action-row">
          <button className="primary login-button" onClick={onOpenLogin} disabled={busy}>
            <LogIn size={18} /> Logar no MakerWorld
          </button>
          <button className="primary ghost" onClick={onCloseLogin} disabled={busy || !loginStatus?.open}>
            Fechar navegador
          </button>
          <button className="primary" onClick={onCreateProject} disabled={busy}>
            <FolderPlus size={18} /> Criar projeto
          </button>
          <button className="primary dark" onClick={onCollect} disabled={!activeProject || busy}>
            <Play size={18} /> Iniciar coleta
          </button>
        </div>

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
            <button className="primary" onClick={onExtractSelectedLinks} disabled={!activeProject || busy || !manualUrl.trim()}>
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
            <p className="settings-note">Nenhuma URL bloqueada neste projeto.</p>
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
                  <strong>{job.status === "completed" ? "Concluída" : job.status === "failed" ? "Falhou" : "Em andamento"}</strong>
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
    delayMs: 500,
  },
  products: {
    previewClass: "product-thumb-preview",
    captionClass: "product-thumb-preview-caption",
    width: 380,
    height: 400,
    delayMs: 500,
  },
} as const;

type ThumbPreviewVariant = keyof typeof THUMB_PREVIEW_LAYOUT;

function useProductThumbPreview(product: Product, variant: ThumbPreviewVariant) {
  const coverAsset = getCoverAsset(product);
  const layout = THUMB_PREVIEW_LAYOUT[variant];
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
    if (!anchor || !coverAsset) return;
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
    if (!coverAsset) return;
    clearHoverTimer();
    hoverTimerRef.current = window.setTimeout(openPreview, layout.delayMs);
  }

  function handleMouseLeave() {
    clearHoverTimer();
    setPreviewOpen(false);
  }

  return {
    anchorRef,
    coverAsset,
    handleMouseEnter,
    handleMouseLeave,
    layout,
    previewOpen,
    previewPos,
  };
}

function ProductThumbPreviewPortal({
  coverAsset,
  layout,
  open,
  position,
  productName,
}: {
  coverAsset: Asset;
  layout: (typeof THUMB_PREVIEW_LAYOUT)[ThumbPreviewVariant];
  open: boolean;
  position: { top: number; left: number };
  productName: string;
}) {
  if (!open) return null;
  return createPortal(
    <div className={layout.previewClass} style={{ top: position.top, left: position.left }}>
      <img src={assetUrl(coverAsset)} alt={productName} />
      <span className={layout.captionClass} title={productName}>{productName}</span>
    </div>,
    document.body,
  );
}

function ProductCardThumb({
  product,
  onOpen,
}: {
  product: Product;
  onOpen: () => void;
}) {
  const {
    anchorRef,
    coverAsset,
    handleMouseEnter,
    handleMouseLeave,
    layout,
    previewOpen,
    previewPos,
  } = useProductThumbPreview(product, "products");

  return (
    <>
      <button
        ref={anchorRef as React.RefObject<HTMLButtonElement>}
        className="product-card-thumb"
        onClick={onOpen}
        aria-label={`Abrir ${product.name}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        {coverAsset ? <img src={assetUrl(coverAsset)} alt="" /> : <ShoppingBag size={22} />}
      </button>
      {coverAsset && (
        <ProductThumbPreviewPortal
          coverAsset={coverAsset}
          layout={layout}
          open={previewOpen}
          position={previewPos}
          productName={product.name}
        />
      )}
    </>
  );
}

function CostsProductCell({ product }: { product: Product }) {
  const sku = productSku(product) || "—";
  const {
    anchorRef,
    coverAsset,
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
          {coverAsset ? (
            <img src={assetUrl(coverAsset)} alt="" />
          ) : (
            <span className="costs-product-thumb-fallback">
              <ShoppingBag size={18} />
            </span>
          )}
        </div>
        <code className="costs-product-sku">{sku}</code>
      </div>
      {coverAsset && (
        <ProductThumbPreviewPortal
          coverAsset={coverAsset}
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
  runtimeStatus,
  onSaveAllProductionCosts,
  onProductionCostsSaved,
}: {
  activeStoreProfile?: StoreProfile;
  busy: boolean;
  filaments: FilamentSpool[];
  productionSettings: ProductionSettings | null;
  products: Product[];
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
    () => filterProducts(products, { query: searchQuery, status: "all", characteristic: "all" }),
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
          {!products.length && <p className="empty table-empty">Nenhum produto nesta loja.</p>}
          {products.length > 0 && !filteredProducts.length && (
            <p className="empty table-empty">Nenhum produto corresponde à busca.</p>
          )}
        </div>
      </div>
    </section>
  );
}

function ProductsTab({
  activeProject,
  batchProgress,
  busy,
  detailsOpen,
  filters,
  imageOptions,
  jobs,
  listingDraft,
  productNameDraft,
  products,
  selectedProduct,
  selectedProductIds,
  selectedColorVariations,
  totalProductCount,
  onCreateManualProduct,
  onApproveProduct,
  onBatchGenerateImages,
  onBatchGenerateListings,
  onBatchDeleteProducts,
  onCloseDetails,
  onDeleteModelAsset,
  onDeleteProduct,
  onFiltersChange,
  onGenerateColorVariations,
  onGenerateImages,
  onGenerateListing,
  onExportSelected,
  onListingDraftChange,
  onOpenDetails,
  onOpenProductFolder,
  onProductNameDraftChange,
  onRegenerateImage,
  onSaveListing,
  onUpdateProductListed,
  onUploadModelFile,
  onSavePrintPlates,
  filaments,
  productionSettings,
  activeStoreProfile,
  onSelectedProductIdsChange,
  onSelectedColorVariationsChange,
  onSelectProduct,
  projects,
  onSelectProject,
}: {
  activeProject?: Project;
  batchProgress: BatchProgress;
  busy: boolean;
  detailsOpen: boolean;
  filters: ProductFilters;
  imageOptions: ImageOptions;
  jobs: Job[];
  listingDraft: Listing | null;
  productNameDraft: string;
  products: Product[];
  selectedProduct?: Product;
  selectedProductIds: string[];
  selectedColorVariations: string[];
  totalProductCount: number;
  onCreateManualProduct: (name: string, sourceUrl?: string) => Promise<Product | undefined>;
  onApproveProduct: () => void;
  onBatchGenerateImages: (ids?: string[]) => void;
  onBatchGenerateListings: (ids?: string[]) => void;
  onBatchDeleteProducts: (ids?: string[]) => void;
  onCloseDetails: () => void;
  onDeleteModelAsset: (productId: string, assetId: string) => void;
  onDeleteProduct: (id?: string) => void;
  onFiltersChange: (filters: ProductFilters) => void;
  onGenerateColorVariations: (id?: string, colorVariations?: string[]) => void;
  onGenerateImages: (id?: string) => void;
  onGenerateListing: (id?: string) => void;
  onExportSelected: (ids?: string[]) => void;
  onListingDraftChange: (listing: Listing) => void;
  onOpenDetails: (id: string) => void;
  onOpenProductFolder: (id?: string) => void;
  onProductNameDraftChange: (value: string) => void;
  onRegenerateImage: (productId: string, promptKey: string, extraPrompt: string) => void;
  onSaveListing: () => Promise<unknown> | void;
  onUpdateProductListed: (productId: string, listed: boolean) => void;
  onUploadModelFile: (productId: string, file: File) => void;
  onSavePrintPlates: (productId: string, plates: PrintPlate[]) => Promise<unknown>;
  filaments: FilamentSpool[];
  productionSettings: ProductionSettings | null;
  activeStoreProfile?: StoreProfile;
  onSelectedProductIdsChange: (ids: string[]) => void;
  onSelectedColorVariationsChange: (ids: string[]) => void;
  onSelectProduct: (id: string) => void;
  projects: Project[];
  onSelectProject: (projectId: string) => void;
}) {
  const [fullscreenAsset, setFullscreenAsset] = useState<Asset | null>(null);
  const [imageExtraPrompts, setImageExtraPrompts] = useState<Record<string, string>>({});
  const [costDetailsOpen, setCostDetailsOpen] = useState(false);
  const [colorDialogOpen, setColorDialogOpen] = useState(false);
  const [manualProductDialogOpen, setManualProductDialogOpen] = useState(false);
  const [manualProductName, setManualProductName] = useState("");
  const [manualProductSourceUrl, setManualProductSourceUrl] = useState("");
  const [detailSection, setDetailSection] = useState<ProductDetailSection>("listing");
  const [plateDrafts, setPlateDrafts] = useState<PrintPlate[]>([]);
  const [savedPlates, setSavedPlates] = useState<PrintPlate[]>([]);
  const modelFileInputRef = useRef<HTMLInputElement>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const totalPages = Math.max(1, Math.ceil(products.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const paginatedProducts = products.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const visibleProductIds = paginatedProducts.map((product) => product.id);
  const allSelected = visibleProductIds.length > 0 && visibleProductIds.every((id) => selectedProductIds.includes(id));
  const progressValue = batchProgress ? Math.round((batchProgress.done / Math.max(batchProgress.total, 1)) * 100) : 0;
  const progressLabel = batchProgress ? `${batchProgress.label}: ${batchProgress.done}/${batchProgress.total}` : "";
  const visibleReadyCount = products.filter((product) => product.listing.title).length;
  const selectedCostEvents = selectedProduct ? productCostEvents(selectedProduct) : [];
  const selectedCostSummary = summarizeCostEvents(selectedCostEvents);

  useEffect(() => {
    setCostDetailsOpen(false);
    setDetailSection("listing");
  }, [selectedProduct?.id]);

  useEffect(() => {
    setPage(1);
  }, [filters.query, filters.status, filters.characteristic, totalProductCount]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    if (!selectedProduct) {
      setPlateDrafts([]);
      setSavedPlates([]);
      return;
    }
    const plates = readPrintPlates(selectedProduct);
    setPlateDrafts(plates);
    setSavedPlates(plates);
  }, [selectedProduct?.id, selectedProduct?.metadata?.print_plates]);

  const plateDraftTotals = plateTotals(plateDrafts);
  const platesDirty = !printPlatesEqual(plateDrafts, savedPlates);
  const listingDirty = Boolean(
    detailsOpen
    && selectedProduct
    && listingDraft
    && (
      !listingsEqual(listingDraft, selectedProduct.listing)
      || productNameDraft.trim() !== selectedProduct.name
    ),
  );

  const listingAutosaveStatus = useAutosave({
    enabled: detailsOpen && detailSection === "listing" && Boolean(selectedProduct && listingDraft),
    isDirty: listingDirty,
    save: async () => {
      await onSaveListing();
    },
  });

  const platesAutosaveStatus = useAutosave({
    enabled: detailsOpen && detailSection === "printing" && Boolean(selectedProduct),
    isDirty: platesDirty,
    save: async () => {
      if (!selectedProduct) return;
      await onSavePrintPlates(selectedProduct.id, plateDrafts);
      setSavedPlates(plateDrafts);
    },
  });

  function updatePlateDraft(index: number, update: Partial<PrintPlate>) {
    setPlateDrafts((current) =>
      current.map((plate, plateIndex) => (plateIndex === index ? { ...plate, ...update } : plate)),
    );
  }

  function addPlateDraftRow() {
    setPlateDrafts((current) => [...current, defaultPrintPlate(current.length + 1)]);
  }

  function removePlateDraftRow(index: number) {
    setPlateDrafts((current) => current.filter((_, plateIndex) => plateIndex !== index));
  }

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
          <h2>Produtos capturados</h2>
          <div className="panel-title-actions">
            <ProjectPicker activeProject={activeProject} projects={projects} onChange={onSelectProject} />
            <button
              className="primary panel-title-action"
              onClick={openManualProductDialog}
              disabled={!activeProject || busy}
            >
              <Plus size={16} /> Novo produto
            </button>
          </div>
        </div>
        <div className="product-filters">
          <label>
            Buscar
            <input
              value={filters.query}
              onChange={(event) => updateFilters({ query: event.target.value })}
              placeholder="Nome, link, tag, categoria..."
            />
          </label>
          <label>
            Status
            <select value={filters.status} onChange={(event) => updateFilters({ status: event.target.value as ProductFilters["status"] })}>
              <option value="all">Todos</option>
              <option value="collected">Coletado</option>
              <option value="in_edit">Em edição</option>
              <option value="ready">Pronto</option>
              <option value="exported">Exportado</option>
            </select>
          </label>
          <label>
            Característica
            <select
              value={filters.characteristic}
              onChange={(event) => updateFilters({ characteristic: event.target.value as ProductFilters["characteristic"] })}
            >
              <option value="all">Todas</option>
              <option value="with_listing">Com anúncio</option>
              <option value="without_listing">Sem anúncio</option>
              <option value="with_image">Com imagem</option>
              <option value="without_image">Sem imagem</option>
              <option value="with_model">Com 3MF</option>
              <option value="without_model">Sem 3MF</option>
              <option value="listed">À venda</option>
              <option value="not_listed">Não está à venda</option>
            </select>
          </label>
          <button className="quiet-button filter-reset" onClick={() => onFiltersChange({ query: "", status: "all", characteristic: "all" })}>
            Limpar filtros
          </button>
        </div>
        <div className="batch-toolbar">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAllProducts}
              disabled={!products.length || busy}
            />
            Selecionar página
          </label>
          <div className="batch-actions">
            <button className="primary" onClick={() => onBatchGenerateListings()} disabled={busy || !selectedProductIds.length}>
              <BrainCircuit size={16} /> Gerar anúncios
            </button>
            <button className="primary dark" onClick={() => onBatchGenerateImages()} disabled={busy || !selectedProductIds.length}>
              <ImagePlus size={16} /> Gerar imagens base
            </button>
            <button className="primary ghost" onClick={() => onExportSelected(selectedProductIds)} disabled={busy || !selectedProductIds.length}>
              <Download size={16} /> Exportar CSV
            </button>
            <button className="danger-button" onClick={() => onBatchDeleteProducts()} disabled={busy || !selectedProductIds.length}>
              <Trash2 size={16} /> Apagar selecionados
            </button>
          </div>
          <span className="selection-count">
            {selectedProductIds.length} selecionado(s) - página {currentPage}/{totalPages} - {products.length}/{totalProductCount} visíveis
          </span>
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
        <div className="product-card-list">
          {paginatedProducts.map((product) => {
            const subtitle = productCardSubtitle(product);
            const pipeline = productPipelineBadges(product);
            const isSelected = selectedProductIds.includes(product.id);
            const isActive = product.id === selectedProduct?.id;
            return (
              <article
                key={product.id}
                className={isActive ? "product-card active" : isSelected ? "product-card selected" : "product-card"}
              >
                <label className="product-card-select" aria-label={`Selecionar ${product.name}`}>
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleProductSelection(product.id)}
                    disabled={busy}
                  />
                </label>
                <ProductCardThumb product={product} onOpen={() => onOpenDetails(product.id)} />
                <button className="product-card-main" onClick={() => onOpenDetails(product.id)}>
                  <strong>{product.name}</strong>
                  {subtitle ? <span className="product-card-subtitle">{subtitle}</span> : (
                    <span className="product-card-subtitle muted">Sem anúncio gerado ainda</span>
                  )}
                  <div className="pipeline-badges">
                    {pipeline.map((badge) => (
                      <span className={`pipeline-badge ${badge.state}`} key={badge.key} title={`${badge.label}: ${badge.detail}`}>
                        <span className="pipeline-badge-label">{badge.label}</span>
                        <span className="pipeline-badge-detail">{badge.detail}</span>
                      </span>
                    ))}
                  </div>
                </button>
                <div className="product-card-cost">
                  <span>Custo IA</span>
                  <strong>{formatUsd(productCostTotal(product))}</strong>
                </div>
                <div className="row-actions product-card-actions">
                  <IconAction
                    label="Gerar anúncio"
                    onClick={() => {
                      onSelectProduct(product.id);
                      onGenerateListing(product.id);
                    }}
                    disabled={busy}
                  >
                    <BrainCircuit size={16} />
                  </IconAction>
                  <IconAction
                    label="Gerar imagens"
                    onClick={() => {
                      onSelectProduct(product.id);
                      onGenerateImages(product.id);
                    }}
                    disabled={busy}
                  >
                    <ImagePlus size={16} />
                  </IconAction>
                  <IconAction label="Abrir detalhes" onClick={() => onOpenDetails(product.id)} disabled={busy}>
                    <Eye size={16} />
                  </IconAction>
                  <IconAction label="Apagar produto" onClick={() => onDeleteProduct(product.id)} disabled={busy}>
                    <Trash2 size={16} />
                  </IconAction>
                </div>
              </article>
            );
          })}
          {!products.length && <p className="empty table-empty">Nenhum produto encontrado com os filtros atuais.</p>}
        </div>
        {products.length > pageSize && (
          <div className="pagination-bar">
            <button className="quiet-button" onClick={() => setPage(1)} disabled={currentPage === 1 || busy}>
              Primeira
            </button>
            <button className="quiet-button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={currentPage === 1 || busy}>
              Anterior
            </button>
            <span>
              Página {currentPage} de {totalPages} · {paginatedProducts.length} de {products.length} produto(s)
            </span>
            <button className="quiet-button" onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={currentPage === totalPages || busy}>
              Próxima
            </button>
            <button className="quiet-button" onClick={() => setPage(totalPages)} disabled={currentPage === totalPages || busy}>
              Última
            </button>
          </div>
        )}
      </div>

      <div className="panel products-summary-panel">
        <div className="panel-title">
          <BadgeCheck size={18} />
          <h2>Resumo</h2>
        </div>
        <div className="summary-list">
          <SummaryItem label="Total" value={products.length.toString()} />
          <SummaryItem label="Com anúncio" value={visibleReadyCount.toString()} />
          <SummaryItem label="Pendentes" value={(products.length - visibleReadyCount).toString()} />
        </div>
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
                  <button onClick={() => onOpenProductFolder(selectedProduct.id)} disabled={busy}>
                    <FolderOpen size={14} /> Pasta dos arquivos
                  </button>
                </div>
              </div>
              <div className="compact-actions">
                <AutosaveIndicator status={listingAutosaveStatus} />
                <button onClick={() => onGenerateListing()} disabled={busy}>
                  <BrainCircuit size={16} /> Gerar anúncio
                </button>
                <button onClick={() => onGenerateImages()} disabled={busy}>
                  <ImagePlus size={16} /> Imagens base
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
                className={detailSection === "printing" ? "active" : ""}
                onClick={() => setDetailSection("printing")}
                role="tab"
                aria-selected={detailSection === "printing"}
              >
                <Printer size={15} /> Impressão
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
                    <input
                      value={listingDraft.keywords.join(", ")}
                      onChange={(event) =>
                        updateDraft(
                          "keywords",
                          event.target.value
                            .split(",")
                            .map((keyword) => keyword.trim())
                            .filter(Boolean),
                        )
                      }
                      placeholder="Separe por vírgula"
                    />
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
                  onExtraPromptChange={updateImageExtraPrompt}
                  onOpenImage={setFullscreenAsset}
                  onRegenerateImage={onRegenerateImage}
                />
                <div className="image-generation-options">
                  <div className="subsection-title">Variações de cor</div>
                  <div className="option-row">
                    <small>As cores marcadas usam a imagem base gerada pela IA como referência.</small>
                    <button
                      className="primary compact-primary"
                      onClick={() => setColorDialogOpen(true)}
                      disabled={busy || !imageOptions.colors.length}
                    >
                      <ImagePlus size={16} /> Gerar variações de cor
                    </button>
                  </div>
                </div>
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
                        <small>{asset.path}</small>
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
                        <strong>{asset.kind.replace(/^generated_/, "IA ").replace(/^color_/, "Cor ").replace(/_/g, " ")}</strong>
                        <code>{fileBasename(asset.path)}</code>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {detailSection === "printing" && selectedProduct && (
              <div className="detail-section">
                <p className="settings-note section-intro">
                  Configure as placas de impressão deste produto. Filamento, gramas e tempo aqui alimentam automaticamente a aba Custos. As alterações são salvas automaticamente.
                </p>
                <div className="print-plates-summary">
                  <span>{plateDraftTotals.plate_count} placa(s)</span>
                  <span>{formatPrintMinutes(plateDraftTotals.total_print_time_minutes)} total</span>
                  <span>{plateDraftTotals.total_filament_grams} g filamento</span>
                </div>
                <div className="costs-table-wrap">
                  <table className="costs-table print-plates-table">
                    <thead>
                      <tr>
                        <th>Nome</th>
                        <th>Tempo (min)</th>
                        <th>Filamento (g)</th>
                        <th>Filamento</th>
                        <th>Qtd/un.</th>
                        <th>Notas</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {plateDrafts.map((plate, index) => (
                        <tr key={plate.id || `plate-${index}`}>
                          <td>
                            <input
                              value={plate.name}
                              onChange={(event) => updatePlateDraft(index, { name: event.target.value })}
                              disabled={busy}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              min="0"
                              value={plate.print_time_minutes || ""}
                              onChange={(event) => updatePlateDraft(index, { print_time_minutes: Number(event.target.value) || 0 })}
                              disabled={busy}
                            />
                          </td>
                          <td>
                            <input
                              type="number"
                              min="0"
                              step="0.1"
                              value={plate.filament_grams || ""}
                              onChange={(event) => updatePlateDraft(index, { filament_grams: Number(event.target.value) || 0 })}
                              disabled={busy}
                            />
                          </td>
                          <td>
                            <select
                              value={plate.filament_id || ""}
                              onChange={(event) => updatePlateDraft(index, { filament_id: event.target.value || null })}
                              disabled={busy || !filaments.length}
                            >
                              <option value="">—</option>
                              {filaments.map((spool) => (
                                <option key={spool.id} value={spool.id}>
                                  {spool.name}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <input
                              type="number"
                              min="1"
                              value={plate.quantity || 1}
                              onChange={(event) => updatePlateDraft(index, { quantity: Math.max(1, Number(event.target.value) || 1) })}
                              disabled={busy}
                            />
                          </td>
                          <td>
                            <input
                              value={plate.notes}
                              onChange={(event) => updatePlateDraft(index, { notes: event.target.value })}
                              disabled={busy}
                            />
                          </td>
                          <td className="costs-actions-cell">
                            <button className="danger-button compact-danger" onClick={() => removePlateDraftRow(index)} disabled={busy}>
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!plateDrafts.length && <p className="empty">Nenhuma placa cadastrada. Adicione uma placa para planejar a impressão deste produto.</p>}
                <div className="action-row">
                  <button className="quiet-button" onClick={addPlateDraftRow} disabled={busy}>+ Placa</button>
                  <AutosaveIndicator status={platesAutosaveStatus} />
                </div>
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
                  <span>Produto já está à venda</span>
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
            <img src={assetUrl(fullscreenAsset)} alt="" />
            <span>{fullscreenAsset.kind.replace(/^generated_/, "").replace(/^color_/, "").replace(/_/g, " ")}</span>
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
              <button className="primary" onClick={() => void submitManualProduct()} disabled={busy || !manualProductName.trim() || !activeProject}>
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
  onExtraPromptChange,
  onOpenImage,
  onRegenerateImage,
}: {
  busy: boolean;
  extraPrompts: Record<string, string>;
  product: Product;
  onExtraPromptChange: (promptKey: string, value: string) => void;
  onOpenImage: (asset: Asset) => void;
  onRegenerateImage: (productId: string, promptKey: string, extraPrompt: string) => void;
}) {
  const images = getImageAssets(product);
  const capturedImages = images.filter((asset) => asset.kind === "cover_image");
  const baseImages = images.filter((asset) => asset.kind.startsWith("generated_"));
  const colorImages = images.filter((asset) => asset.kind.startsWith("color_"));
  const mainImage = baseImages[0] ?? capturedImages[0] ?? colorImages[0];
  const colorSkus = productColorSkus(product);

  return (
    <div className="product-gallery">
      <div className="gallery-main">
        {mainImage ? (
          <button className="gallery-main-button" onClick={() => onOpenImage(mainImage)}>
            <img src={assetUrl(mainImage)} alt="" />
          </button>
        ) : (
          <div className="gallery-placeholder">
            <ImagePlus size={24} />
            <span>Nenhuma imagem salva ainda</span>
          </div>
        )}
      </div>
      <div className="gallery-groups">
        <GalleryGroup assets={capturedImages} emptyText="Imagem capturada aparecerá aqui." onOpenImage={onOpenImage} title="Capturada" />
        <GalleryGroup
          allowRegenerate
          assets={baseImages}
          busy={busy}
          emptyText="Use o botão Imagens base para gerar."
          extraPrompts={extraPrompts}
          productId={product.id}
          skuByKey={colorSkus}
          title="Imagens base IA"
          onExtraPromptChange={onExtraPromptChange}
          onOpenImage={onOpenImage}
          onRegenerateImage={onRegenerateImage}
        />
        <GalleryGroup
          allowRegenerate
          assets={colorImages}
          busy={busy}
          emptyText="Escolha cores e use Gerar cores."
          extraPrompts={extraPrompts}
          productId={product.id}
          skuByKey={colorSkus}
          title="Variações de cor"
          onExtraPromptChange={onExtraPromptChange}
          onOpenImage={onOpenImage}
          onRegenerateImage={onRegenerateImage}
        />
      </div>
    </div>
  );
}

function GalleryGroup({
  allowRegenerate = false,
  assets,
  busy = false,
  emptyText,
  extraPrompts = {},
  productId,
  skuByKey = {},
  onExtraPromptChange,
  onOpenImage,
  onRegenerateImage,
  title,
}: {
  allowRegenerate?: boolean;
  assets: Asset[];
  busy?: boolean;
  emptyText: string;
  extraPrompts?: Record<string, string>;
  productId?: string;
  skuByKey?: Record<string, string>;
  onExtraPromptChange?: (promptKey: string, value: string) => void;
  onOpenImage: (asset: Asset) => void;
  onRegenerateImage?: (productId: string, promptKey: string, extraPrompt: string) => void;
  title: string;
}) {
  const [activeRegenerateKey, setActiveRegenerateKey] = useState("");

  return (
    <div className="gallery-group">
      <div className="gallery-group-title">{title}</div>
      <div className="gallery-strip">
        {assets.map((asset) => {
          const promptKey = asset.kind.replace(/^generated_/, "");
          const label = asset.kind.replace(/^generated_/, "").replace(/^color_/, "").replace(/_/g, " ");
          const sku = skuByKey[asset.kind.replace(/^color_/, "")];
          const regenerateOpen = activeRegenerateKey === promptKey;

          return (
            <div className="gallery-thumb" key={asset.id}>
              <div className="thumb-image-frame">
                <button className="thumb-open" onClick={() => onOpenImage(asset)}>
                  <img src={assetUrl(asset)} alt="" />
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
    </div>
  );
}

function IconAction({
  children,
  disabled,
  label,
  onClick,
}: {
  children: React.ReactNode;
  disabled: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button className="icon-action" disabled={disabled} onClick={onClick} title={label} aria-label={label}>
      {children}
    </button>
  );
}

function ScheduleMetricBar({ label, value, tone = "default" }: { label: string; value: number; tone?: "default" | "warn" | "danger" }) {
  const pct = Math.min(100, Math.round(value * 1000) / 10);
  return (
    <div className={`schedule-metric-bar tone-${tone}`}>
      <div className="schedule-metric-bar-head">
        <span>{label}</span>
        <strong>{formatPercent(value)}</strong>
      </div>
      <div className="schedule-metric-bar-track">
        <div className="schedule-metric-bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ScheduleTaskCard({
  task,
  busy,
  products,
  onUpdateTask,
  onDeleteTask,
  showDate = false,
}: {
  task: PrintScheduleTask;
  busy: boolean;
  products: Product[];
  onUpdateTask: (taskId: string, payload: Partial<PrintScheduleTask>) => Promise<unknown>;
  onDeleteTask: (taskId: string) => Promise<unknown>;
  showDate?: boolean;
}) {
  const linkedProduct = task.product_id ? products.find((product) => product.id === task.product_id) : undefined;
  const endTime = addMinutesToTime(task.start_time, task.duration_minutes);
  return (
    <div className={`schedule-task-card status-${task.status}`}>
      <div className="schedule-task-time">
        {showDate && <span>{formatBrazilianDate(task.scheduled_date)} · </span>}
        {task.start_time} – {endTime} · {formatPrintMinutes(task.duration_minutes)}
      </div>
      <strong>{task.title}</strong>
      {linkedProduct && (
        <small>{productSku(linkedProduct) || linkedProduct.name}{task.quantity > 1 ? ` × ${task.quantity}` : ""}</small>
      )}
      {!linkedProduct && task.quantity > 1 && <small>Quantidade: {task.quantity}</small>}
      {task.notes && <small>{task.notes}</small>}
      <div className="schedule-task-actions">
        <select
          value={task.status}
          onChange={(event) => onUpdateTask(task.id, { status: event.target.value as PrintScheduleStatus })}
          disabled={busy}
        >
          <option value="planned">Planejado</option>
          <option value="printing">Imprimindo</option>
          <option value="done">Concluído</option>
          <option value="failed">Falhou</option>
          <option value="cancelled">Cancelado</option>
        </select>
        <button className="danger-button compact-danger" onClick={() => onDeleteTask(task.id)} disabled={busy}>
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

function ScheduleAgendaGrid({
  view,
  columns,
  scheduleDate,
  tasks,
  products,
  printers,
  busy,
  selectedTaskId,
  onSelectTask,
  onUpdateTask,
  onCreateAt,
}: {
  view: "day" | "week";
  columns: AgendaColumn[];
  scheduleDate: string;
  tasks: PrintScheduleTask[];
  products: Product[];
  printers: Printer3D[];
  busy: boolean;
  selectedTaskId: string | null;
  onSelectTask: (taskId: string | null) => void;
  onUpdateTask: (taskId: string, payload: Partial<PrintScheduleTask>) => Promise<unknown>;
  onCreateAt: (columnId: string, startTime: string) => void;
}) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const suppressClickRef = useRef(false);
  const [drag, setDrag] = useState<AgendaDragState | null>(null);
  const [preview, setPreview] = useState<{ taskId: string; columnId: string; startMinutes: number; durationMinutes: number } | null>(null);
  const hours = useMemo(
    () => Array.from({ length: AGENDA_END_HOUR - AGENDA_START_HOUR + 1 }, (_, index) => AGENDA_START_HOUR + index),
    [],
  );

  function tasksInColumn(columnId: string) {
    if (view === "day") {
      return tasks.filter((task) => task.printer_id === columnId && task.scheduled_date === scheduleDate);
    }
    return tasks.filter((task) => task.scheduled_date === columnId);
  }

  function visibleTasksInColumn(columnId: string) {
    const columnTasks = tasksInColumn(columnId);
    if (!preview) return columnTasks;
    const previewTask = tasks.find((task) => task.id === preview.taskId);
    if (!previewTask) return columnTasks;
    if (preview.columnId === columnId) {
      if (columnTasks.some((task) => task.id === preview.taskId)) return columnTasks;
      return [...columnTasks, previewTask];
    }
    return columnTasks.filter((task) => task.id !== preview.taskId);
  }

  function layoutTasksInColumn(columnId: string) {
    const visible = visibleTasksInColumn(columnId);
    const adjusted = visible.map((task) => {
      if (preview?.taskId !== task.id) return task;
      return {
        ...task,
        start_time: minutesToTimeString(preview.startMinutes),
        duration_minutes: preview.durationMinutes,
      };
    });
    return computeAgendaOverlapLayout(adjusted);
  }

  function columnIndexFromClientX(clientX: number) {
    const body = bodyRef.current?.querySelector(".agenda-body") as HTMLElement | null;
    if (!body || !columns.length) return 0;
    const rect = body.getBoundingClientRect();
    const scrollLeft = bodyRef.current?.scrollLeft ?? 0;
    const relativeX = clientX - rect.left + scrollLeft;
    const columnWidth = body.scrollWidth / columns.length;
    return Math.max(0, Math.min(columns.length - 1, Math.floor(relativeX / columnWidth)));
  }

  function syncHeaderScroll() {
    if (headerRef.current && bodyRef.current) {
      headerRef.current.scrollLeft = bodyRef.current.scrollLeft;
    }
  }

  function beginDrag(task: PrintScheduleTask, mode: AgendaDragState["mode"], event: React.PointerEvent) {
    if (busy) return;
    event.preventDefault();
    event.stopPropagation();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    const columnId = view === "day" ? task.printer_id : task.scheduled_date;
    setDrag({
      taskId: task.id,
      mode,
      pointerId: event.pointerId,
      startPointerY: event.clientY,
      startPointerX: event.clientX,
      originStart: timeToMinutes(task.start_time),
      originDuration: task.duration_minutes,
      originColumnId: columnId,
      moved: false,
    });
    setPreview({
      taskId: task.id,
      columnId,
      startMinutes: timeToMinutes(task.start_time),
      durationMinutes: task.duration_minutes,
    });
  }

  function handlePointerMove(event: React.PointerEvent) {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const deltaY = event.clientY - drag.startPointerY;
    const deltaX = event.clientX - drag.startPointerX;
    if (Math.abs(deltaY) > 3 || Math.abs(deltaX) > 3) {
      if (!drag.moved) setDrag((current) => (current ? { ...current, moved: true } : current));
    }
    const columnId = drag.mode === "move" && Math.abs(deltaX) > 12
      ? columns[columnIndexFromClientX(event.clientX)]?.id || drag.originColumnId
      : drag.originColumnId;
    if (drag.mode === "resize") {
      const nextDuration = Math.max(
        AGENDA_SNAP_MINUTES,
        snapAgendaMinutes(drag.originDuration + (deltaY / AGENDA_HOUR_HEIGHT) * 60),
      );
      setPreview({ taskId: drag.taskId, columnId, startMinutes: drag.originStart, durationMinutes: nextDuration });
      return;
    }
    const nextStart = clampAgendaMinutes(drag.originStart + (deltaY / AGENDA_HOUR_HEIGHT) * 60, drag.originDuration);
    setPreview({ taskId: drag.taskId, columnId, startMinutes: nextStart, durationMinutes: drag.originDuration });
  }

  async function handlePointerUp(event: React.PointerEvent) {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const task = tasks.find((item) => item.id === drag.taskId);
    if (!task) {
      setDrag(null);
      setPreview(null);
      return;
    }
    if (!drag.moved) {
      onSelectTask(task.id);
    } else if (preview) {
      suppressClickRef.current = true;
      const payload: Partial<PrintScheduleTask> = {
        start_time: minutesToTimeString(preview.startMinutes),
        duration_minutes: preview.durationMinutes,
      };
      if (view === "day") payload.printer_id = preview.columnId;
      else payload.scheduled_date = preview.columnId;
      await onUpdateTask(task.id, payload);
      onSelectTask(task.id);
    }
    setDrag(null);
    setPreview(null);
  }

  function renderTaskBlock(task: PrintScheduleTask, columnId: string, overlapLayout: Map<string, AgendaOverlapLayout>) {
    const isPreview = preview?.taskId === task.id;
    const startMinutes = isPreview ? preview.startMinutes : timeToMinutes(task.start_time);
    const durationMinutes = isPreview ? preview.durationMinutes : task.duration_minutes;
    const displayColumnId = isPreview ? preview.columnId : columnId;
    if (displayColumnId !== columnId) return null;
    const linkedProduct = task.product_id ? products.find((product) => product.id === task.product_id) : undefined;
    const coverAsset = linkedProduct ? getCoverAsset(linkedProduct) : undefined;
    const printer = printers.find((item) => item.id === task.printer_id);
    const top = agendaOffsetTop(startMinutes);
    const height = agendaBlockHeight(durationMinutes);
    const isSelected = selectedTaskId === task.id;
    const layout = overlapLayout.get(task.id) ?? { lane: 0, lanes: 1 };
    const laneWidth = 100 / layout.lanes;
    const laneLeft = layout.lane * laneWidth;
    const compactLane = layout.lanes > 1;
    return (
      <div
        key={task.id}
        className={`agenda-event status-${task.status}${isSelected ? " selected" : ""}${drag?.taskId === task.id ? " dragging" : ""}${compactLane ? " compact-lane" : ""}`}
        style={{
          top,
          height,
          left: `calc(${laneLeft}% + 2px)`,
          width: `calc(${laneWidth}% - 4px)`,
        }}
        onPointerDown={(event) => beginDrag(task, "move", event)}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <div className="agenda-event-body">
          {!compactLane && (
            <div className="agenda-event-thumb" aria-hidden="true">
              {coverAsset ? <img src={assetUrl(coverAsset)} alt="" /> : <ShoppingBag size={14} />}
            </div>
          )}
          <div className="agenda-event-copy">
            <strong>{task.title}</strong>
            {!compactLane && (
              <span>{minutesToTimeString(startMinutes)} – {addMinutesToTime(minutesToTimeString(startMinutes), durationMinutes)}</span>
            )}
            {(view === "week" || compactLane) && printer && <small>{printer.name}</small>}
          </div>
        </div>
        <div
          className="agenda-event-resize"
          onPointerDown={(event) => beginDrag(task, "resize", event)}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        />
      </div>
    );
  }

  function handleColumnClick(columnId: string, event: React.MouseEvent<HTMLDivElement>) {
    if (busy || drag) return;
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    const target = event.target as HTMLElement;
    if (target.closest(".agenda-event")) return;
    const bodyInner = bodyRef.current?.querySelector(".agenda-body") as HTMLElement | null;
    if (!bodyInner) return;
    const rect = bodyInner.getBoundingClientRect();
    const scrollTop = bodyRef.current?.scrollTop ?? 0;
    const relativeY = event.clientY - rect.top + scrollTop;
    const startTime = minutesToTimeString(clampAgendaMinutes(minutesFromAgendaY(relativeY)));
    onCreateAt(columnId, startTime);
  }

  const columnTemplate = `repeat(${Math.max(columns.length, 1)}, minmax(120px, 1fr))`;
  const agendaMinWidth = Math.max(columns.length, 1) * 120;

  return (
    <div className="agenda-grid-wrap">
      <div
        className="agenda-grid"
        style={{ "--agenda-min-width": `${agendaMinWidth}px` } as React.CSSProperties}
      >
        <div className="agenda-corner" aria-hidden="true" />
        <div className="agenda-column-headers-wrap" ref={headerRef}>
          <div className="agenda-column-headers" style={{ gridTemplateColumns: columnTemplate }}>
            {columns.map((column) => (
              <div className="agenda-column-header" key={column.id}>
                <strong>{column.label}</strong>
                {column.sublabel && <small>{column.sublabel}</small>}
              </div>
            ))}
          </div>
        </div>
        <div className="agenda-body-scroll" ref={bodyRef} onScroll={syncHeaderScroll}>
          <div className="agenda-body-scroll-inner">
            <div className="agenda-time-gutter" style={{ height: AGENDA_GRID_HEIGHT }}>
              {hours.map((hour) => (
                <div className="agenda-hour-label" key={hour} style={{ height: AGENDA_HOUR_HEIGHT }}>
                  {String(hour).padStart(2, "0")}:00
                </div>
              ))}
            </div>
            <div className="agenda-body" style={{ height: AGENDA_GRID_HEIGHT }}>
              <div className="agenda-hour-lines">
                {hours.map((hour) => (
                  <div className="agenda-hour-line" key={hour} style={{ height: AGENDA_HOUR_HEIGHT }} />
                ))}
              </div>
              <div className="agenda-columns" style={{ gridTemplateColumns: columnTemplate }}>
                {columns.map((column) => {
                  const overlapLayout = layoutTasksInColumn(column.id);
                  return (
                    <div
                      className="agenda-column"
                      key={column.id}
                      onClick={(event) => handleColumnClick(column.id, event)}
                    >
                      {visibleTasksInColumn(column.id).map((task) => renderTaskBlock(task, column.id, overlapLayout))}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ScheduleTab({
  busy,
  printers,
  products,
  projects,
  scheduleDate,
  scheduleView,
  tasks,
  onCreateTask,
  onDeleteTask,
  onScheduleDateChange,
  onScheduleViewChange,
  onUpdateTask,
}: {
  busy: boolean;
  printers: Printer3D[];
  products: Product[];
  projects: Project[];
  scheduleDate: string;
  scheduleView: ScheduleView;
  tasks: PrintScheduleTask[];
  onCreateTask: (payload: {
    printer_id: string;
    scheduled_date: string;
    start_time: string;
    duration_minutes: number;
    product_id?: string | null;
    plate_id?: string | null;
    title: string;
    quantity: number;
    notes: string;
  }) => Promise<unknown>;
  onDeleteTask: (taskId: string) => Promise<unknown>;
  onScheduleDateChange: (value: string) => void;
  onScheduleViewChange: (view: ScheduleView) => void;
  onUpdateTask: (taskId: string, payload: Partial<PrintScheduleTask>) => Promise<unknown>;
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogPrinterId, setDialogPrinterId] = useState("");
  const [dialogDate, setDialogDate] = useState(scheduleDate);
  const [taskMode, setTaskMode] = useState<"product" | "custom">("product");
  const [selectedProductId, setSelectedProductId] = useState("");
  const [selectedPlateId, setSelectedPlateId] = useState("");
  const [customTitle, setCustomTitle] = useState("");
  const [startTime, setStartTime] = useState("08:00");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [quantity, setQuantity] = useState(1);
  const [notes, setNotes] = useState("");
  const [productSearchQuery, setProductSearchQuery] = useState("");
  const [productPickerOpen, setProductPickerOpen] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const productPickerRef = useRef<HTMLDivElement>(null);

  const range = useMemo(() => scheduleRange(scheduleView, scheduleDate), [scheduleView, scheduleDate]);
  const periodLabel = useMemo(() => schedulePeriodLabel(scheduleView, scheduleDate, range.from, range.to), [scheduleView, scheduleDate, range.from, range.to]);
  const projectById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects]);
  const datesInRange = useMemo(() => eachDateInRange(range.from, range.to), [range.from, range.to]);
  const monthGrid = useMemo(() => {
    if (scheduleView !== "month") return [];
    const first = parseIsoDate(range.from);
    const offset = (first.getDay() + 6) % 7;
    const cells: Array<{ date: string | null; inMonth: boolean }> = [];
    for (let index = 0; index < offset; index += 1) cells.push({ date: null, inMonth: false });
    datesInRange.forEach((date) => cells.push({ date, inMonth: true }));
    while (cells.length % 7 !== 0) cells.push({ date: null, inMonth: false });
    return cells;
  }, [scheduleView, range.from, datesInRange]);

  const selectedProduct = products.find((product) => product.id === selectedProductId);
  const productPlates = readPrintPlates(selectedProduct);
  const selectedPlate = productPlates.find((plate) => plate.id === selectedPlateId);
  const filteredScheduleProducts = useMemo(
    () => filterProducts(products, { query: productSearchQuery, status: "all", characteristic: "all" }),
    [products, productSearchQuery],
  );
  const selectedCoverAsset = selectedProduct ? getCoverAsset(selectedProduct) : undefined;
  const selectedTask = tasks.find((task) => task.id === selectedTaskId) || null;
  const dayAgendaColumns = useMemo(
    () => printers.map((printer) => ({
      id: printer.id,
      label: printer.name,
      sublabel: printer.model || undefined,
    })),
    [printers],
  );
  const weekAgendaColumns = useMemo(
    () => datesInRange.map((date) => ({
      id: date,
      label: parseIsoDate(date).toLocaleDateString("pt-BR", { weekday: "short" }),
      sublabel: formatBrazilianDate(date),
    })),
    [datesInRange],
  );

  useEffect(() => {
    if (!dialogOpen) return;
    if (!dialogPrinterId && printers[0]) setDialogPrinterId(printers[0].id);
  }, [dialogOpen, dialogPrinterId, printers]);

  useEffect(() => {
    if (!productPickerOpen) return undefined;
    function handleDocumentClick(event: MouseEvent) {
      if (!productPickerRef.current?.contains(event.target as Node)) setProductPickerOpen(false);
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setProductPickerOpen(false);
    }
    document.addEventListener("mousedown", handleDocumentClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleDocumentClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [productPickerOpen]);

  useEffect(() => {
    if (dialogOpen) return;
    setProductPickerOpen(false);
    setProductSearchQuery("");
  }, [dialogOpen]);

  useEffect(() => {
    if (taskMode !== "product" || !selectedPlate) return;
    setDurationMinutes(Math.max(selectedPlate.print_time_minutes * Math.max(quantity, 1), 0));
  }, [taskMode, selectedPlate?.id, selectedPlate?.print_time_minutes, quantity]);

  function tasksForPrinter(printerId: string, date = scheduleDate) {
    return tasks
      .filter((task) => task.printer_id === printerId && task.scheduled_date === date)
      .sort((a, b) => a.start_time.localeCompare(b.start_time));
  }

  function tasksForDate(date: string) {
    return tasks
      .filter((task) => task.scheduled_date === date)
      .sort((a, b) => a.start_time.localeCompare(b.start_time) || a.title.localeCompare(b.title));
  }

  function taskEndTime(task: PrintScheduleTask) {
    return addMinutesToTime(task.start_time, task.duration_minutes);
  }

  function suggestedStartTime(printerId: string, date: string) {
    const printerTasks = tasksForPrinter(printerId, date);
    if (!printerTasks.length) return "08:00";
    return taskEndTime(printerTasks[printerTasks.length - 1]);
  }

  function openCreateDialog(printerId?: string, date?: string, presetStartTime?: string) {
    const targetDate = date || scheduleDate;
    setTaskMode("product");
    setSelectedProductId(products[0]?.id || "");
    setSelectedPlateId("");
    setCustomTitle("");
    setDialogDate(targetDate);
    setStartTime(presetStartTime || suggestedStartTime(printerId || printers[0]?.id || "", targetDate));
    setDurationMinutes(60);
    setQuantity(1);
    setNotes("");
    setProductSearchQuery("");
    setProductPickerOpen(false);
    setDialogPrinterId(printerId || printers[0]?.id || "");
    setDialogOpen(true);
  }

  function handleAgendaCreateAt(columnId: string, presetStartTime: string) {
    if (scheduleView === "day") openCreateDialog(columnId, scheduleDate, presetStartTime);
    else openCreateDialog(undefined, columnId, presetStartTime);
  }

  function openDayView(date: string) {
    onScheduleViewChange("day");
    onScheduleDateChange(date);
  }

  async function submitTask() {
    if (!dialogPrinterId) return;
    const title = taskMode === "product"
      ? `${productSku(selectedProduct) || selectedProduct?.name || "Produto"} · ${selectedPlate?.name || "Placa"}`
      : customTitle.trim();
    if (!title) return;
    await onCreateTask({
      printer_id: dialogPrinterId,
      scheduled_date: dialogDate,
      start_time: startTime,
      duration_minutes: durationMinutes,
      product_id: taskMode === "product" ? selectedProductId || null : null,
      plate_id: taskMode === "product" ? selectedPlateId || null : null,
      title,
      quantity: Math.max(1, quantity),
      notes,
    });
    setDialogOpen(false);
  }

  const printerCount = Math.max(1, printers.length);

  return (
    <section className={`schedule-page schedule-page-clean${selectedTask ? " has-sidebar" : ""}`}>
      <header className="schedule-header">
        <div className="schedule-header-primary">
          <button className="primary" onClick={() => openCreateDialog()} disabled={busy || !printers.length}>
            <Plus size={16} /> Nova impressão
          </button>
          <div className="schedule-view-toggle">
            <button className={scheduleView === "day" ? "active" : ""} onClick={() => onScheduleViewChange("day")}>Dia</button>
            <button className={scheduleView === "week" ? "active" : ""} onClick={() => onScheduleViewChange("week")}>Semana</button>
            <button className={scheduleView === "month" ? "active" : ""} onClick={() => onScheduleViewChange("month")}>Mês</button>
          </div>
        </div>
        <div className="schedule-header-nav">
          <div className="schedule-date-nav">
            <button
              className="quiet-button schedule-nav-arrow"
              aria-label="Período anterior"
              onClick={() => onScheduleDateChange(shiftScheduleAnchor(scheduleView, scheduleDate, -1))}
            >
              ‹
            </button>
            <div className="schedule-date-nav-center">
              <strong className="schedule-period-label">{periodLabel}</strong>
              {scheduleView === "day" && (
                <BrazilianDateInput
                  className="schedule-date-inline"
                  value={scheduleDate}
                  onChange={onScheduleDateChange}
                  aria-label="Data"
                />
              )}
            </div>
            <button
              className="quiet-button schedule-nav-arrow"
              aria-label="Próximo período"
              onClick={() => onScheduleDateChange(shiftScheduleAnchor(scheduleView, scheduleDate, 1))}
            >
              ›
            </button>
          </div>
          <button className="quiet-button schedule-today-button" onClick={() => onScheduleDateChange(todayDateString())}>
            Hoje
          </button>
        </div>
        <div className="schedule-header-meta">
          <span className="schedule-header-hint">Clique no horário vazio para criar · arraste para mover</span>
        </div>
      </header>

      {!printers.length && (
        <div className="panel schedule-empty-banner">
          <strong>Nenhuma impressora ativa</strong>
          <span>Cadastre impressoras em Ajustes → Impressão para usar a agenda.</span>
        </div>
      )}

      <div className="schedule-agenda-shell">
        <div className="schedule-agenda-main">
          {scheduleView === "day" && !!printers.length && (
            <ScheduleAgendaGrid
              view="day"
              columns={dayAgendaColumns}
              scheduleDate={scheduleDate}
              tasks={tasks}
              products={products}
              printers={printers}
              busy={busy}
              selectedTaskId={selectedTaskId}
              onSelectTask={setSelectedTaskId}
              onUpdateTask={onUpdateTask}
              onCreateAt={handleAgendaCreateAt}
            />
          )}

          {scheduleView === "week" && (
            <ScheduleAgendaGrid
              view="week"
              columns={weekAgendaColumns}
              scheduleDate={scheduleDate}
              tasks={tasks}
              products={products}
              printers={printers}
              busy={busy}
              selectedTaskId={selectedTaskId}
              onSelectTask={setSelectedTaskId}
              onUpdateTask={onUpdateTask}
              onCreateAt={handleAgendaCreateAt}
            />
          )}

          {scheduleView === "month" && (
            <div className="schedule-month-panel">
              <div className="schedule-month-weekdays">
                {["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"].map((label) => (
                  <span key={label}>{label}</span>
                ))}
              </div>
              <div className="schedule-month-grid">
                {monthGrid.map((cell, index) => {
                  if (!cell.date) return <div className="schedule-month-cell empty" key={`empty-${index}`} />;
                  const dateTasks = tasksForDate(cell.date);
                  const minutes = dateTasks.reduce((sum, task) => sum + schedulePrintingMinutes(task), 0);
                  const occupancy = minutes / (printerCount * 24 * 60);
                  const isToday = cell.date === todayDateString();
                  const isSelected = cell.date === scheduleDate;
                  return (
                    <button
                      className={`schedule-month-cell${isSelected ? " selected" : ""}${isToday ? " today" : ""}`}
                      key={cell.date}
                      onClick={() => openDayView(cell.date!)}
                    >
                      <span className="schedule-month-day">{parseIsoDate(cell.date).getDate()}</span>
                      <div className="agenda-month-events">
                        {dateTasks.slice(0, 4).map((task) => {
                          const linkedProduct = task.product_id ? products.find((product) => product.id === task.product_id) : undefined;
                          const coverAsset = linkedProduct ? getCoverAsset(linkedProduct) : undefined;
                          return (
                            <span className={`agenda-month-chip status-${task.status}`} key={task.id} title={task.title}>
                              <span className="agenda-month-chip-thumb" aria-hidden="true">
                                {coverAsset ? <img src={assetUrl(coverAsset)} alt="" /> : <ShoppingBag size={10} />}
                              </span>
                              <span className="agenda-month-chip-copy">
                                <strong>{task.start_time}</strong> {task.title}
                              </span>
                            </span>
                          );
                        })}
                        {dateTasks.length > 4 && (
                          <span className="agenda-month-more">+{dateTasks.length - 4} mais</span>
                        )}
                      </div>
                      {dateTasks.length > 0 && (
                        <span className="schedule-month-bar" style={{ width: `${Math.min(100, occupancy * 100)}%` }} />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {selectedTask && (
          <aside className="schedule-task-sidebar">
            <div className="schedule-task-sidebar-head">
              <strong>Impressão selecionada</strong>
              <button className="quiet-button" aria-label="Fechar detalhes" onClick={() => setSelectedTaskId(null)}>×</button>
            </div>
            <ScheduleTaskCard
              task={selectedTask}
              busy={busy}
              products={products}
              onUpdateTask={onUpdateTask}
              onDeleteTask={async (taskId) => {
                await onDeleteTask(taskId);
                setSelectedTaskId(null);
              }}
              showDate={scheduleView !== "day"}
            />
          </aside>
        )}
      </div>

      {dialogOpen && (
        <div className="confirm-backdrop" role="presentation" onClick={() => setDialogOpen(false)}>
          <div className="confirm-dialog schedule-dialog" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div>
              <p className="eyebrow">Nova impressão</p>
              <h2>{formatBrazilianDate(dialogDate)}</h2>
            </div>
            <div className="schedule-mode-toggle">
              <button className={taskMode === "product" ? "active" : ""} onClick={() => setTaskMode("product")}>Produto</button>
              <button className={taskMode === "custom" ? "active" : ""} onClick={() => setTaskMode("custom")}>Avulsa</button>
            </div>
            <div className="form-grid">
              <label>
                Data
                <BrazilianDateInput value={dialogDate} onChange={setDialogDate} />
              </label>
              <label>
                Impressora
                <select value={dialogPrinterId} onChange={(event) => {
                  setDialogPrinterId(event.target.value);
                  setStartTime(suggestedStartTime(event.target.value, dialogDate));
                }}>
                  {printers.map((printer) => (
                    <option key={printer.id} value={printer.id}>{printer.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Início
                <input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
              </label>
              {taskMode === "product" ? (
                <>
                  <div className="schedule-product-picker full-span" ref={productPickerRef}>
                    <span className="schedule-picker-label">Produto</span>
                    <button
                      type="button"
                      className="schedule-product-trigger"
                      aria-expanded={productPickerOpen}
                      aria-haspopup="listbox"
                      onClick={() => setProductPickerOpen((open) => !open)}
                    >
                      {selectedProduct ? (
                        <>
                          <div className="schedule-product-thumb" aria-hidden="true">
                            {selectedCoverAsset ? (
                              <img src={assetUrl(selectedCoverAsset)} alt="" />
                            ) : (
                              <ShoppingBag size={18} />
                            )}
                          </div>
                          <div className="schedule-product-copy">
                            <strong>{productSku(selectedProduct) || selectedProduct.name}</strong>
                            <span>{selectedProduct.name}</span>
                          </div>
                        </>
                      ) : (
                        <span className="schedule-product-placeholder">Selecione um produto...</span>
                      )}
                      <ChevronDown size={16} aria-hidden="true" className={productPickerOpen ? "open" : ""} />
                    </button>
                    {productPickerOpen && (
                      <div className="schedule-product-menu">
                        <div className="schedule-product-search">
                          <Search size={14} />
                          <input
                            value={productSearchQuery}
                            onChange={(event) => setProductSearchQuery(event.target.value)}
                            placeholder="Buscar SKU, nome, projeto..."
                            autoFocus
                          />
                        </div>
                        <div className="schedule-product-list" role="listbox" aria-label="Selecionar produto">
                          {filteredScheduleProducts.map((product) => {
                            const coverAsset = getCoverAsset(product);
                            const project = projectById.get(product.project_id);
                            const isSelected = selectedProductId === product.id;
                            return (
                              <button
                                type="button"
                                key={product.id}
                                role="option"
                                aria-selected={isSelected}
                                className={isSelected ? "schedule-product-option active" : "schedule-product-option"}
                                onClick={() => {
                                  setSelectedProductId(product.id);
                                  setSelectedPlateId("");
                                  setProductPickerOpen(false);
                                  setProductSearchQuery("");
                                }}
                              >
                                <div className="schedule-product-thumb" aria-hidden="true">
                                  {coverAsset ? (
                                    <img src={assetUrl(coverAsset)} alt="" />
                                  ) : (
                                    <ShoppingBag size={18} />
                                  )}
                                </div>
                                <div className="schedule-product-copy">
                                  <strong>{productSku(product) || product.name}</strong>
                                  <span>{product.name}</span>
                                  {project && <small>{project.name}</small>}
                                </div>
                              </button>
                            );
                          })}
                          {!filteredScheduleProducts.length && (
                            <p className="empty schedule-product-empty">Nenhum produto encontrado.</p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                  <label className="full-span">
                    Placa
                    <select
                      value={selectedPlateId}
                      onChange={(event) => setSelectedPlateId(event.target.value)}
                      disabled={!productPlates.length}
                    >
                      <option value="">Selecione...</option>
                      {productPlates.map((plate) => (
                        <option key={plate.id} value={plate.id}>
                          {plate.name} · {formatPrintMinutes(plate.print_time_minutes)} · {plate.filament_grams} g
                        </option>
                      ))}
                    </select>
                  </label>
                  {!productPlates.length && selectedProductId && (
                    <p className="settings-note full-span">Este produto ainda não tem placas. Configure em Produtos → Impressão.</p>
                  )}
                </>
              ) : (
                <label className="full-span">
                  Título
                  <input value={customTitle} onChange={(event) => setCustomTitle(event.target.value)} placeholder="Ex.: Teste de calibração" />
                </label>
              )}
              <label>
                Quantidade
                <input type="number" min="1" value={quantity} onChange={(event) => setQuantity(Math.max(1, Number(event.target.value) || 1))} />
              </label>
              <label>
                Duração (min)
                <input type="number" min="0" value={durationMinutes} onChange={(event) => setDurationMinutes(Number(event.target.value) || 0)} />
              </label>
              <label className="full-span">
                Observações
                <input value={notes} onChange={(event) => setNotes(event.target.value)} />
              </label>
            </div>
            <div className="confirm-actions">
              <button className="primary ghost" onClick={() => setDialogOpen(false)}>Cancelar</button>
              <button
                className="primary"
                onClick={submitTask}
                disabled={busy || !dialogPrinterId || (taskMode === "product" ? !selectedProductId || !selectedPlateId : !customTitle.trim())}
              >
                Adicionar ao schedule
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function SettingsTab({
  imageOptions,
  openRouterApiKeyDraft,
  openRouterModelDraft,
  kieApiKeyDraft,
  kieImageModelDraft,
  r2AccessKeyDraft,
  r2AccountIdDraft,
  r2BucketDraft,
  r2PublicUrlDraft,
  r2SecretKeyDraft,
  settings,
  storeProfileDraft,
  storeProfiles,
  onCreateStoreProfile,
  onDownloadAppBackup,
  onOpenRouterApiKeyChange,
  onOpenRouterModelChange,
  onKieApiKeyChange,
  onKieImageModelChange,
  onR2AccessKeyChange,
  onR2AccountIdChange,
  onR2BucketChange,
  onR2PublicUrlChange,
  onR2SecretKeyChange,
  onSaveOpenRouterSettings,
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
  onSavePrinter,
  onDeletePrinter,
  onPrintersSaved,
  printers,
  onWrapAction,
  appUpdate,
  onCheckAppUpdates,
  onDownloadAppUpdate,
  onInstallAppUpdate,
}: {
  imageOptions: ImageOptions;
  openRouterApiKeyDraft: string;
  openRouterModelDraft: string;
  kieApiKeyDraft: string;
  kieImageModelDraft: string;
  r2AccessKeyDraft: string;
  r2AccountIdDraft: string;
  r2BucketDraft: string;
  r2PublicUrlDraft: string;
  r2SecretKeyDraft: string;
  settings: SettingsPayload | null;
  storeProfileDraft: StoreProfile | null;
  storeProfiles: StoreProfile[];
  onCreateStoreProfile: () => Promise<unknown> | void;
  onDownloadAppBackup: () => Promise<unknown> | void;
  onOpenRouterApiKeyChange: (value: string) => void;
  onOpenRouterModelChange: (value: string) => void;
  onKieApiKeyChange: (value: string) => void;
  onKieImageModelChange: (value: string) => void;
  onR2AccessKeyChange: (value: string) => void;
  onR2AccountIdChange: (value: string) => void;
  onR2BucketChange: (value: string) => void;
  onR2PublicUrlChange: (value: string) => void;
  onR2SecretKeyChange: (value: string) => void;
  onSaveOpenRouterSettings: () => void;
  onSaveStoreProfile: () => Promise<unknown> | void;
  onSaveImageColorOptions: (colors: ImageOptions["colors"]) => Promise<unknown> | void;
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
  }) => Promise<unknown>;
  onSaveProductionSettings: (payload: {
    electricity_kwh_price_brl: number;
    printer_power_watts: number;
    printer_purchase_price_brl: number;
    printer_useful_life_hours: number;
    maintenance_cost_per_hour_brl: number;
    labor_cost_per_hour_brl: number;
  }) => Promise<unknown>;
  onSavePrinter: (payload: {
    id?: string;
    name: string;
    model: string;
    notes: string;
    active: boolean;
  }) => Promise<unknown>;
  onDeletePrinter: (printerId: string) => Promise<unknown>;
  onPrintersSaved: () => Promise<Printer3D[] | void>;
  printers: Printer3D[];
  onWrapAction: <T,>(label: string, action: () => Promise<T>) => Promise<T | undefined>;
  appUpdate: AppUpdateState;
  onCheckAppUpdates: () => Promise<void>;
  onDownloadAppUpdate: () => Promise<void>;
  onInstallAppUpdate: () => Promise<void>;
}) {
  const [profileEditorOpen, setProfileEditorOpen] = useState(false);
  const [integrationEditorOpen, setIntegrationEditorOpen] = useState(false);
  const [integrationSecretsVisible, setIntegrationSecretsVisible] = useState(false);
  const [loadingIntegrationSecrets, setLoadingIntegrationSecrets] = useState(false);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("store");
  const [colorDrafts, setColorDrafts] = useState<ImageOptions["colors"]>(imageOptions.colors);
  const [appInfo, setAppInfo] = useState<AppInfo>(DEFAULT_APP_INFO);
  const [filamentDrafts, setFilamentDrafts] = useState<FilamentSpool[]>(filaments);
  const [printerDrafts, setPrinterDrafts] = useState<Printer3D[]>(printers);
  const [electricityPrice, setElectricityPrice] = useState("0.85");
  const [printerPower, setPrinterPower] = useState("200");
  const [printerPurchasePrice, setPrinterPurchasePrice] = useState("0");
  const [printerUsefulLifeHours, setPrinterUsefulLifeHours] = useState("5000");
  const [maintenanceCostPerHour, setMaintenanceCostPerHour] = useState("0");
  const [laborCostPerHour, setLaborCostPerHour] = useState("0");
  const [uiThemePreference, setUiThemePreference] = useState<UiThemePreference>(() => readUiThemePreference());
  const [customAccentDraft, setCustomAccentDraft] = useState(
    () => readUiThemePreference().accent ?? UI_THEME_PRESETS[0].tokens.greenDark,
  );

  function selectUiTheme(id: UiThemeId) {
    const next: UiThemePreference = id === "custom"
      ? { id: "custom", accent: customAccentDraft }
      : { id: id as Exclude<UiThemeId, "custom"> };
    setUiThemePreference(next);
    saveUiThemePreference(next);
    applyUiThemePreference(next);
  }

  function applyCustomAccent(accent: string) {
    setCustomAccentDraft(accent);
    const next: UiThemePreference = { id: "custom", accent };
    setUiThemePreference(next);
    saveUiThemePreference(next);
    applyUiThemePreference(next);
  }

  useEffect(() => {
    setFilamentDrafts(filaments);
  }, [filaments]);

  useEffect(() => {
    setPrinterDrafts(printers);
  }, [printers]);

  useEffect(() => {
    if (!productionSettings) return;
    setElectricityPrice(String(productionSettings.electricity_kwh_price_brl));
    setPrinterPower(String(productionSettings.printer_power_watts));
    setPrinterPurchasePrice(String(productionSettings.printer_purchase_price_brl ?? 0));
    setPrinterUsefulLifeHours(String(productionSettings.printer_useful_life_hours ?? 5000));
    setMaintenanceCostPerHour(String(productionSettings.maintenance_cost_per_hour_brl ?? 0));
    setLaborCostPerHour(String(productionSettings.labor_cost_per_hour_brl ?? 0));
  }, [productionSettings]);

  useEffect(() => {
    setColorDrafts(imageOptions.colors);
  }, [imageOptions.colors]);

  useEffect(() => {
    let cancelled = false;
    if (!window.ecoNative?.getAppInfo) return;
    window.ecoNative.getAppInfo()
      .then((info) => {
        if (!cancelled) setAppInfo(info);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function createAndEditStoreProfile() {
    await onCreateStoreProfile();
    setProfileEditorOpen(true);
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
      onR2AccountIdChange(secrets.cloudflare_account_id || "");
      onR2BucketChange(secrets.cloudflare_r2_bucket_name || "");
      onR2AccessKeyChange(secrets.cloudflare_r2_access_key || "");
      onR2SecretKeyChange(secrets.cloudflare_r2_secret_key || "");
      onR2PublicUrlChange(secrets.cloudflare_r2_public_url || "");
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
        id: "",
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

  function updatePrinterDraft(index: number, key: keyof Printer3D, value: string | boolean) {
    setPrinterDrafts((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, [key]: value } : item)),
    );
  }

  function addPrinterDraftRow() {
    setPrinterDrafts((current) => [
      ...current,
      {
        id: "",
        name: "",
        model: "",
        notes: "",
        active: true,
        created_at: "",
        updated_at: "",
      },
    ]);
  }

  async function savePrintingSection() {
    for (const draft of printerDrafts) {
      if (!draft.name.trim()) continue;
      await onSavePrinter({
        id: draft.id || undefined,
        name: draft.name.trim(),
        model: draft.model || "",
        notes: draft.notes || "",
        active: draft.active,
      });
    }
    const reloaded = await onPrintersSaved();
    if (Array.isArray(reloaded)) {
      setPrinterDrafts(reloaded);
    }
  }

  async function saveProductionSection() {
    await onSaveProductionSettings({
      electricity_kwh_price_brl: Number(electricityPrice.replace(",", ".")) || 0,
      printer_power_watts: Number(printerPower.replace(",", ".")) || 0,
      printer_purchase_price_brl: Number(printerPurchasePrice.replace(",", ".")) || 0,
      printer_useful_life_hours: Math.max(1, Number(printerUsefulLifeHours.replace(",", ".")) || 5000),
      maintenance_cost_per_hour_brl: Number(maintenanceCostPerHour.replace(",", ".")) || 0,
      labor_cost_per_hour_brl: Number(laborCostPerHour.replace(",", ".")) || 0,
    });
    for (const draft of filamentDrafts) {
      if (!draft.name.trim()) continue;
      await onSaveFilament({
        id: draft.id || undefined,
        name: draft.name.trim(),
        material: draft.material.trim() || "PLA",
        color: draft.color || "",
        spool_price_brl: Number(draft.spool_price_brl) || 0,
        spool_weight_g: Number(draft.spool_weight_g) || 1000,
        notes: draft.notes || "",
      });
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
      || Boolean(openRouterApiKeyDraft.trim())
      || Boolean(kieApiKeyDraft.trim())
      || Boolean(r2AccountIdDraft.trim())
      || Boolean(r2BucketDraft.trim())
      || Boolean(r2AccessKeyDraft.trim())
      || Boolean(r2SecretKeyDraft.trim())
      || Boolean(r2PublicUrlDraft.trim())
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
  const printingDirty = settingsSection === "printing" && !printerDraftsEqual(printerDrafts, printers);

  const profileAutosaveStatus = useAutosave({
    enabled: profileEditorOpen,
    isDirty: profileDirty,
    save: async () => { await onSaveStoreProfile(); },
  });
  const integrationAutosaveStatus = useAutosave({
    enabled: integrationEditorOpen,
    isDirty: integrationDirty,
    save: async () => { await onSaveOpenRouterSettings(); },
  });
  const colorsAutosaveStatus = useAutosave({
    enabled: settingsSection === "colors",
    isDirty: colorsDirty,
    save: async () => { await onSaveImageColorOptions(colorDrafts); },
  });
  const productionAutosaveStatus = useAutosave({
    enabled: settingsSection === "production",
    isDirty: productionDirty,
    save: () => saveProductionSection(),
  });
  const printingAutosaveStatus = useAutosave({
    enabled: settingsSection === "printing",
    isDirty: printingDirty,
    save: () => savePrintingSection(),
  });

  return (
    <section className="settings-page settings-layout">
      <nav className="settings-nav" aria-label="Seções de ajustes">
        <button className={settingsSection === "store" ? "active" : ""} onClick={() => setSettingsSection("store")}>
          <ShoppingBag size={16} /> Loja e prompts
        </button>
        <button className={settingsSection === "integrations" ? "active" : ""} onClick={() => setSettingsSection("integrations")}>
          <KeyRound size={16} /> Integrações
        </button>
        <button className={settingsSection === "appearance" ? "active" : ""} onClick={() => setSettingsSection("appearance")}>
          <Palette size={16} /> Aparência
        </button>
        <button className={settingsSection === "colors" ? "active" : ""} onClick={() => setSettingsSection("colors")}>
          <ImagePlus size={16} /> Cores
        </button>
        <button className={settingsSection === "production" ? "active" : ""} onClick={() => setSettingsSection("production")}>
          <Coins size={16} /> Produção
        </button>
        <button className={settingsSection === "printing" ? "active" : ""} onClick={() => setSettingsSection("printing")}>
          <Printer size={16} /> Impressão
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
          Cada perfil representa uma loja/modo de trabalho. Ao trocar a loja ativa, os prompts de anúncio e imagem também mudam.
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
                <button className="primary ghost" onClick={() => onSelectedStoreProfileChange(profile.id)}>
                  Ativar
                </button>
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
        <button className="primary profile-create-button" onClick={createAndEditStoreProfile}>
          <FolderPlus size={18} /> Criar perfil de loja
        </button>
      </div>
      )}

      {settingsSection === "integrations" && (
      <div className="panel integration-settings-panel">
        <div className="panel-title">
          <KeyRound size={18} />
          <h2>Integrações</h2>
        </div>
        <div className="integrations">
          <Integration label="OpenRouter" enabled={Boolean(settings?.integrations.openrouter)} />
          <Integration label="Kie.ai" enabled={Boolean(settings?.integrations.kie_ai)} />
          <Integration label="Cloudflare R2" enabled={Boolean(settings?.integrations.cloudflare_r2)} />
        </div>
        <p className="settings-note">
          Configure OpenRouter (texto/anúncios), Kie.ai (imagens) e Cloudflare R2 (hospedagem pública). As credenciais só são carregadas quando você pedir para mostrar.
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
          Escolha a paleta do app. A preferência fica salva neste navegador/computador e é aplicada imediatamente.
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
                <tr key={spool.id || `new-${index}`}>
                  <td><input value={spool.name} onChange={(event) => updateFilamentDraft(index, "name", event.target.value)} /></td>
                  <td><input value={spool.material} onChange={(event) => updateFilamentDraft(index, "material", event.target.value)} /></td>
                  <td><input value={spool.color || ""} onChange={(event) => updateFilamentDraft(index, "color", event.target.value)} /></td>
                  <td><input value={spool.spool_price_brl || ""} onChange={(event) => updateFilamentDraft(index, "spool_price_brl", event.target.value)} /></td>
                  <td><input value={spool.spool_weight_g || ""} onChange={(event) => updateFilamentDraft(index, "spool_weight_g", event.target.value)} /></td>
                  <td className="costs-readonly">{formatBrl(filamentCostPerGram(spool))}</td>
                  <td className="costs-actions-cell">
                    {spool.id ? (
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

      {settingsSection === "printing" && (
      <div className="panel printing-settings-panel">
        <div className="panel-title">
          <Printer size={18} />
          <h2>Impressoras 3D</h2>
        </div>
        <p className="settings-note section-intro">
          Impressoras compartilhadas por todas as lojas. As alterações são salvas automaticamente.
        </p>
        <div className="costs-table-wrap">
          <table className="costs-table settings-printer-table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Modelo</th>
                <th>Notas</th>
                <th>Ativa</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {printerDrafts.map((printer, index) => (
                <tr key={printer.id || `new-printer-${index}`}>
                  <td><input value={printer.name} onChange={(event) => updatePrinterDraft(index, "name", event.target.value)} /></td>
                  <td><input value={printer.model || ""} onChange={(event) => updatePrinterDraft(index, "model", event.target.value)} /></td>
                  <td><input value={printer.notes || ""} onChange={(event) => updatePrinterDraft(index, "notes", event.target.value)} /></td>
                  <td className="costs-actions-cell">
                    <input
                      type="checkbox"
                      checked={printer.active}
                      onChange={(event) => updatePrinterDraft(index, "active", event.target.checked)}
                    />
                  </td>
                  <td className="costs-actions-cell">
                    {printer.id ? (
                      <button className="danger-button compact-danger" onClick={() => onDeletePrinter(printer.id)} disabled={!printer.id}>
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
          <button className="quiet-button" onClick={addPrinterDraftRow}>+ Impressora</button>
          <AutosaveIndicator status={printingAutosaveStatus} />
        </div>
      </div>
      )}

      {settingsSection === "backup" && (
      <>
      <div className="panel backup-settings-panel">
        <div className="panel-title">
          <Download size={18} />
          <h2>Backup completo</h2>
        </div>
        <p className="settings-note">
          Gera um ZIP com todos os dados do app: lojas, projetos, produtos, filamentos, impressoras, agenda de impressão,
          integrações (.env), arquivos de produto (3MF, imagens) e logos das lojas.
          Ao restaurar, o conteúdo do backup substitui os dados atuais do app.
        </p>
        <div className="backup-actions">
          <button className="primary" onClick={() => onDownloadAppBackup()}>
            <Download size={18} /> Baixar backup completo
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

      <div className="panel app-update-panel">
        <div className="panel-title">
          <RefreshCw size={18} />
          <h2>Aplicativo</h2>
        </div>
        <div className="settings-app-about">
          <span className="brand-mark">
            <img src="./eco-logo.png" alt="" />
          </span>
          <div>
            <strong>{appInfo.name}</strong>
            <span>Versão instalada: {appInfo.version}</span>
          </div>
        </div>
        <p className="settings-note">
          A versão acima é a do app que você está usando agora. O app verifica novas versões ao abrir e avisa discretamente;
          o download só começa quando você confirmar, aqui ou no aviso na tela.
        </p>
        <AppUpdateControls
          state={appUpdate}
          onCheck={onCheckAppUpdates}
          onDownload={onDownloadAppUpdate}
          onInstall={onInstallAppUpdate}
        />
      </div>

      <div className="panel paths-settings-panel">
        <div className="panel-title">
          <Settings size={18} />
          <h2>Pastas e modelos</h2>
        </div>
        <div className="summary-list path-list">
          <SummaryItem label="Dados" value={settings?.data_dir ?? "--"} />
          <SummaryItem label="Projetos" value={settings?.projects_dir ?? "--"} />
          <SummaryItem label="Exportações" value={settings?.exports_dir ?? "--"} />
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
                  {imageOptions.studio_prompts.map((prompt) => (
                    <label key={prompt.id}>
                      {prompt.name}
                      <small>Prompt individual enviado ao Kie/Qwen para este tipo de imagem.</small>
                      <textarea
                        value={(storeProfileDraft.image_prompts || {})[prompt.id] || ""}
                        onChange={(event) => updateStoreImagePrompt(prompt.id, event.target.value)}
                      />
                    </label>
                  ))}
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
                  <small>Modelo enviado no campo model da API Kie. Padrão atual: qwen/image-edit.</small>
                  <input
                    value={kieImageModelDraft}
                    onChange={(event) => onKieImageModelChange(event.target.value)}
                    placeholder={settings?.integrations.kie_image_model || "qwen/image-edit"}
                  />
                </label>
              </section>

              <section className="profile-editor-section">
                <div className="subsection-title">Cloudflare R2</div>
                <div className="form-grid">
                  <label>
                    Account ID
                    <div className="credential-field">
                      <input
                        type={integrationSecretsVisible ? "text" : "password"}
                        value={r2AccountIdDraft}
                        onChange={(event) => onR2AccountIdChange(event.target.value)}
                        placeholder={settings?.integrations.cloudflare_r2 ? "Configurado. Mostrar para visualizar ou cole um novo." : "CLOUDFLARE_ACCOUNT_ID"}
                      />
                      <button type="button" onClick={revealIntegrationSecrets} disabled={loadingIntegrationSecrets}>
                        {integrationSecretsVisible ? "Ocultar" : "Mostrar"}
                      </button>
                    </div>
                  </label>
                  <label>
                    Bucket
                    <div className="credential-field">
                      <input
                        type={integrationSecretsVisible ? "text" : "password"}
                        value={r2BucketDraft}
                        onChange={(event) => onR2BucketChange(event.target.value)}
                        placeholder={settings?.integrations.cloudflare_r2 ? "Configurado. Mostrar para visualizar ou cole um novo." : "CLOUDFLARE_R2_BUCKET_NAME"}
                      />
                      <button type="button" onClick={revealIntegrationSecrets} disabled={loadingIntegrationSecrets}>
                        {integrationSecretsVisible ? "Ocultar" : "Mostrar"}
                      </button>
                    </div>
                  </label>
                  <label>
                    Access Key
                    <div className="credential-field">
                      <input
                        type={integrationSecretsVisible ? "text" : "password"}
                        value={r2AccessKeyDraft}
                        onChange={(event) => onR2AccessKeyChange(event.target.value)}
                        placeholder={settings?.integrations.cloudflare_r2 ? "Configurado. Mostrar para visualizar ou cole uma nova." : "CLOUDFLARE_R2_ACCESS_KEY"}
                      />
                      <button type="button" onClick={revealIntegrationSecrets} disabled={loadingIntegrationSecrets}>
                        {integrationSecretsVisible ? "Ocultar" : "Mostrar"}
                      </button>
                    </div>
                  </label>
                  <label>
                    Secret Key
                    <div className="credential-field">
                      <input
                        type={integrationSecretsVisible ? "text" : "password"}
                        value={r2SecretKeyDraft}
                        onChange={(event) => onR2SecretKeyChange(event.target.value)}
                        placeholder={settings?.integrations.cloudflare_r2 ? "Configurado. Mostrar para visualizar ou cole uma nova." : "CLOUDFLARE_R2_SECRET_KEY"}
                      />
                      <button type="button" onClick={revealIntegrationSecrets} disabled={loadingIntegrationSecrets}>
                        {integrationSecretsVisible ? "Ocultar" : "Mostrar"}
                      </button>
                    </div>
                  </label>
                  <label className="full-span">
                    URL pública do bucket
                    <div className="credential-field">
                      <input
                        type={integrationSecretsVisible ? "text" : "password"}
                        value={r2PublicUrlDraft}
                        onChange={(event) => onR2PublicUrlChange(event.target.value)}
                        placeholder={settings?.integrations.cloudflare_r2 ? "Configurada. Mostrar para visualizar ou cole uma nova." : "https://pub-...r2.dev"}
                      />
                      <button type="button" onClick={revealIntegrationSecrets} disabled={loadingIntegrationSecrets}>
                        {integrationSecretsVisible ? "Ocultar" : "Mostrar"}
                      </button>
                    </div>
                  </label>
                </div>
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

createRoot(document.getElementById("root")!).render(<App />);
