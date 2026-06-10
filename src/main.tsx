import React, { useEffect, useMemo, useRef, useState } from "react";
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
  Save,
  Settings,
  ShoppingBag,
  Trash2,
  UserRound,
} from "lucide-react";
import "./styles.css";

const API_BASE = "http://127.0.0.1:8765";
const ONBOARDING_COMPLETE_KEY = "eco_native_onboarding_complete";

declare global {
  interface Window {
    ecoNative?: {
      checkForUpdates: () => Promise<{ ok: boolean; message: string }>;
    };
  }
}

type Marketplace = "shopee" | "tiktok_shop" | "kwai_shop" | "mercado_livre";
type AppTab = "dashboard" | "collect" | "products" | "settings";
type ProductStatus =
  | "imported"
  | "scraped"
  | "ai_approved"
  | "assets_downloaded"
  | "images_generated"
  | "listing_generated"
  | "needs_review"
  | "approved"
  | "exported"
  | "failed";

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
  store_profiles: number;
  ai_profiles: number;
  projects: number;
  products: number;
  jobs: number;
  files: number;
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
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

function statusLabel(status: ProductStatus): string {
  const labels: Record<ProductStatus, string> = {
    imported: "Importado",
    scraped: "Coletado",
    ai_approved: "Aprovado IA",
    assets_downloaded: "Arquivos baixados",
    images_generated: "Imagens geradas",
    listing_generated: "Anúncio gerado",
    needs_review: "Revisão",
    approved: "Aprovado",
    exported: "Exportado",
    failed: "Falhou",
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

function displayText(value: string): string {
  return value
    .replace(/variacoes/g, "variações")
    .replace(/Variacoes/g, "Variações")
    .replace(/acao/g, "ação")
    .replace(/Acao/g, "Ação")
    .replace(/anuncio/g, "anúncio")
    .replace(/Anuncio/g, "Anúncio")
    .replace(/revisao/g, "revisão")
    .replace(/Revisao/g, "Revisão")
    .replace(/descricao/g, "descrição")
    .replace(/Descricao/g, "Descrição")
    .replace(/analise/g, "análise")
    .replace(/Analise/g, "Análise")
    .replace(/estudio/g, "estúdio")
    .replace(/Estudio/g, "Estúdio");
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

function productCostTotal(product: Product): number {
  const stored = Number(product.metadata.cost_total_usd);
  if (Number.isFinite(stored) && stored > 0) return stored;
  return productCostEvents(product).reduce((sum, event) => sum + Number(event.cost_usd || 0), 0);
}

function formatUsd(value: number): string {
  if (!value) return "US$ 0,0000";
  return `US$ ${value.toLocaleString("pt-BR", { minimumFractionDigits: 4, maximumFractionDigits: 6 })}`;
}

function formatBrl(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2, maximumFractionDigits: 2 });
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
    const hasModel = product.assets.some((asset) => asset.kind === "model_3mf");
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
    eyebrow: "Vis?o geral",
    title: "Dashboard",
  },
  collect: {
    eyebrow: "MakerWorld scraper",
    title: "Coleta",
  },
  products: {
    eyebrow: "Cat?logo e IA",
    title: "Produtos",
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
  const [listingDraft, setListingDraft] = useState<Listing | null>(null);
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

  useEffect(() => {
    if (selectedProduct) {
      setListingDraft(selectedProduct.listing);
    } else {
      setListingDraft(null);
    }
  }, [selectedProduct?.id]);

  async function runAction<T>(label: string, action: () => Promise<T>): Promise<T | undefined> {
    if (runtimeStatus?.requires_internet && runtimeStatus.online === false) {
      setNotice("Sem internet. O ECO Native Studio precisa de conexão para coletar, gerar IA e exportar com segurança.");
      return undefined;
    }
    try {
      setBusy(true);
      setNotice(`${label}...`);
      const result = await action();
      await refresh();
      if (isJobResult(result) && result.status === "failed") {
        const detail = result.logs?.length ? result.logs[result.logs.length - 1] : result.message;
        throw new Error(detail || "A tarefa falhou.");
      }
      setNotice(`${label} concluído.`);
      return result;
    } catch (error) {
      if (error instanceof Error && error.message === "__cancelled__") {
        setNotice("Ação cancelada.");
        return undefined;
      }
      setNotice(error instanceof Error ? error.message : "Erro inesperado");
      return undefined;
    } finally {
      setBusy(false);
    }
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
      const created = await runAction("Criando projeto", () =>
        api<Project>("/api/projects", {
          method: "POST",
          body: JSON.stringify({
            name: projectName,
            store: activeStoreProfile?.name ?? "Loja principal",
            store_profile_id: activeStoreProfile?.id ?? null,
            marketplace: activeStoreProfile?.marketplace ?? "shopee",
            niche: activeStoreProfile?.niche ?? "Utilidades para casa",
          }),
        }),
      );
      if (created) setActiveProjectId(created.id);
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
    );
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
    );
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
    return runAction("Salvando integrações IA", async () => {
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
      return updated;
    });
  }

  function finishOnboarding(payload: OnboardingPayload) {
    return runAction("Salvando configuração inicial", async () => {
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
        setActiveStoreProfileId(updatedProfile.id);
        setStoreProfileDraft(updatedProfile);
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
      setActiveProjectId(nextProject?.id ?? "");
      setSelectedProductId("");
      setSelectedProductIds([]);
      setDetailsOpen(false);
    }
  }

  function saveStoreProfile() {
    if (!storeProfileDraft) return Promise.resolve();
    return runAction("Salvando perfil de loja", async () => {
      const updated = await api<StoreProfile>(`/api/store-profiles/${storeProfileDraft.id}`, {
        method: "PATCH",
        body: JSON.stringify(storeProfileDraft),
      });
      setStoreProfileDraft(updated);
      setActiveStoreProfileId(updated.id);
      return updated;
    });
  }

  function createStoreProfile() {
    return runAction("Criando perfil de loja", async () => {
      const created = await api<StoreProfile>("/api/store-profiles", {
        method: "POST",
        body: JSON.stringify({
          name: `${storeProfileDraft?.name || "Nova loja"} copia`,
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
      setActiveStoreProfileId(created.id);
      setStoreProfileDraft(created);
      return created;
    });
  }

  function uploadStoreProfilePhoto(profileId: string, file: File) {
    return runAction("Salvando foto da loja", async () => {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(new Error("Nao foi possivel ler a imagem."));
        reader.readAsDataURL(file);
      });
      const updated = await api<StoreProfile>(`/api/store-profiles/${profileId}/photo`, {
        method: "POST",
        body: JSON.stringify({ data_url: dataUrl }),
      });
      setStoreProfileDraft(updated);
      setActiveStoreProfileId(updated.id);
      return updated;
    });
  }

  function saveImageColorOptions(colors: ImageOptions["colors"]) {
    return runAction("Salvando cores", async () => {
      const updated = await api<ImageOptions>("/api/image-options", {
        method: "PUT",
        body: JSON.stringify({ colors }),
      });
      setImageOptions(updated);
      return updated;
    });
  }

  function downloadStoreBackup(profileId = storeProfileDraft?.id || activeStoreProfile?.id) {
    if (!profileId) return Promise.resolve();
    return runAction("Gerando backup da loja", async () => {
      const response = await fetch(`${API_BASE}/api/backups/stores/${profileId}`);
      if (!response.ok) throw new Error(await response.text());
      const blob = await response.blob();
      const fallback = `backup-${activeStoreProfile?.name || storeProfileDraft?.name || "loja"}.zip`;
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

  function restoreStoreBackup(file: File) {
    return runAction("Restaurando backup da loja", async () => {
      const response = await fetch(`${API_BASE}/api/backups/restore`, {
        method: "POST",
        headers: { "Content-Type": "application/zip" },
        body: await file.arrayBuffer(),
      });
      if (!response.ok) throw new Error(await response.text());
      const summary = await response.json() as BackupRestoreSummary;
      if (summary.store_profile_id) {
        setActiveStoreProfileId(summary.store_profile_id);
      }
      setNotice(
        `Backup restaurado: ${summary.products} produto(s), ${summary.projects} projeto(s), ${summary.files} arquivo(s).`,
      );
      return summary;
    });
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
    );
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
    );
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
    );
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
    );
  }

  function saveListing() {
    if (!selectedProduct || !listingDraft) return Promise.resolve();
    return runAction("Salvando anúncio", () =>
      api<Product>(`/api/products/${selectedProduct.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          listing: listingDraft,
          status: listingDraft.title && listingDraft.description ? "needs_review" : selectedProduct.status,
        }),
      }),
    );
  }

  function approveProduct() {
    if (!selectedProduct || !listingDraft) return Promise.resolve();
    return runAction("Aprovando produto", () =>
      api<Product>(`/api/products/${selectedProduct.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          listing: listingDraft,
          status: "approved",
        }),
      }),
    );
  }

  function updateProductListed(productId: string, listed: boolean) {
    return runAction(listed ? "Marcando produto à venda" : "Removendo marcação de venda", () =>
      api<Product>(`/api/products/${productId}`, {
        method: "PATCH",
        body: JSON.stringify({
          metadata: {
            listed,
            listed_at: listed ? new Date().toISOString() : null,
          },
        }),
      }),
    );
  }

  async function deleteProduct(productId = selectedProduct?.id) {
    if (!productId) return Promise.resolve();
    const product = projectProducts.find((item) => item.id === productId);
    if (!(await confirmDangerousDelete(`Apagar o produto "${product?.name ?? productId}"?`))) return Promise.resolve();
    return runAction("Apagando produto", () =>
      api<{ status: string; product_id: string }>(`/api/products/${productId}`, {
        method: "DELETE",
      }),
    );
  }

  function openProductFolder(productId = selectedProduct?.id) {
    if (!productId) return Promise.resolve();
    return runAction("Abrindo pasta do produto", () =>
      api<{ status: string; path: string }>(`/api/products/${productId}/open-folder`, {
        method: "POST",
      }),
    );
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
        await refresh();
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
      }
      setSelectedProductIds([]);
      if (productIds.includes(selectedProductId)) setSelectedProductId("");
      await refresh();
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
    });
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <img src="./eco-logo.png" alt="" />
          </span>
          <div>
            <strong>ECO Native</strong>
            <span>Studio</span>
          </div>
        </div>
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
            productCount={projectProducts.length}
            projectName={projectName}
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
            onVisibleBrowserChange={setVisibleBrowser}
          />
        )}

        {activeTab === "products" && (
          <ProductsTab
            batchProgress={batchProgress}
            busy={busy}
            imageOptions={imageOptions}
            jobs={storeJobs}
            listingDraft={listingDraft}
            filters={productFilters}
            products={filteredProjectProducts}
            totalProductCount={projectProducts.length}
            selectedProduct={selectedProduct}
            selectedProductIds={selectedProductIds}
            selectedColorVariations={selectedColorVariations}
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
            onListingDraftChange={setListingDraft}
            onSaveListing={saveListing}
            onUpdateProductListed={updateProductListed}
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
            onDownloadStoreBackup={downloadStoreBackup}
            onSaveStoreProfile={saveStoreProfile}
            onSaveImageColorOptions={saveImageColorOptions}
            onSelectedStoreProfileChange={selectStoreProfile}
            onRestoreStoreBackup={restoreStoreBackup}
            onUploadStoreProfilePhoto={uploadStoreProfilePhoto}
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
      {runtimeStatus?.requires_internet && runtimeStatus.online === false && (
        <div className="offline-backdrop" role="alert" aria-live="assertive">
          <div className="offline-dialog">
            <p className="eyebrow">Conexão necessária</p>
            <h2>O app precisa de internet para funcionar</h2>
            <p>
              As coletas, geração de conteúdo por IA, geração de imagens, câmbio e exportações dependem de serviços online.
              Reconecte a internet para continuar usando o ECO Native Studio.
            </p>
          </div>
        </div>
      )}
    </main>
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
}: {
  activeStoreProfile?: StoreProfile;
  jobs: Job[];
  lastExport: { path: string; count: number; marketplace: string } | null;
  products: Product[];
  projects: Project[];
  runtimeStatus: RuntimeStatus | null;
}) {
  const readyCount = products.filter((product) => product.listing.title && product.listing.description).length;
  const imageCount = products.filter((product) => product.assets.some(isImageAsset)).length;
  const modelCount = products.filter((product) => product.assets.some((asset) => asset.kind === "model_3mf")).length;
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
  onVisibleBrowserChange,
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
  onVisibleBrowserChange: (value: boolean) => void;
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
          <label>
            Nome do projeto
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

        {loginStatus?.message && <p className="session-note">{loginStatus.message}</p>}
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

function ProductsTab({
  batchProgress,
  busy,
  detailsOpen,
  filters,
  imageOptions,
  jobs,
  listingDraft,
  products,
  selectedProduct,
  selectedProductIds,
  selectedColorVariations,
  totalProductCount,
  onApproveProduct,
  onBatchGenerateImages,
  onBatchGenerateListings,
  onBatchDeleteProducts,
  onCloseDetails,
  onDeleteProduct,
  onFiltersChange,
  onGenerateColorVariations,
  onGenerateImages,
  onGenerateListing,
  onExportSelected,
  onListingDraftChange,
  onOpenDetails,
  onOpenProductFolder,
  onRegenerateImage,
  onSaveListing,
  onUpdateProductListed,
  onSelectedProductIdsChange,
  onSelectedColorVariationsChange,
  onSelectProduct,
}: {
  batchProgress: BatchProgress;
  busy: boolean;
  detailsOpen: boolean;
  filters: ProductFilters;
  imageOptions: ImageOptions;
  jobs: Job[];
  listingDraft: Listing | null;
  products: Product[];
  selectedProduct?: Product;
  selectedProductIds: string[];
  selectedColorVariations: string[];
  totalProductCount: number;
  onApproveProduct: () => void;
  onBatchGenerateImages: (ids?: string[]) => void;
  onBatchGenerateListings: (ids?: string[]) => void;
  onBatchDeleteProducts: (ids?: string[]) => void;
  onCloseDetails: () => void;
  onDeleteProduct: (id?: string) => void;
  onFiltersChange: (filters: ProductFilters) => void;
  onGenerateColorVariations: (id?: string, colorVariations?: string[]) => void;
  onGenerateImages: (id?: string) => void;
  onGenerateListing: (id?: string) => void;
  onExportSelected: (ids?: string[]) => void;
  onListingDraftChange: (listing: Listing) => void;
  onOpenDetails: (id: string) => void;
  onOpenProductFolder: (id?: string) => void;
  onRegenerateImage: (productId: string, promptKey: string, extraPrompt: string) => void;
  onSaveListing: () => void;
  onUpdateProductListed: (productId: string, listed: boolean) => void;
  onSelectedProductIdsChange: (ids: string[]) => void;
  onSelectedColorVariationsChange: (ids: string[]) => void;
  onSelectProduct: (id: string) => void;
}) {
  const [fullscreenAsset, setFullscreenAsset] = useState<Asset | null>(null);
  const [imageExtraPrompts, setImageExtraPrompts] = useState<Record<string, string>>({});
  const [costDetailsOpen, setCostDetailsOpen] = useState(false);
  const [colorDialogOpen, setColorDialogOpen] = useState(false);
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
  }, [selectedProduct?.id]);

  useEffect(() => {
    setPage(1);
  }, [filters.query, filters.status, filters.characteristic, totalProductCount]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

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

  return (
    <section className="products-page">
      <div className="panel products-table-panel">
        <div className="panel-title">
          <ShoppingBag size={18} />
          <h2>Produtos capturados</h2>
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
              <option value="imported">Importado</option>
              <option value="ai_approved">Aprovado IA (legado)</option>
              <option value="images_generated">Imagens geradas</option>
              <option value="listing_generated">Anúncio gerado</option>
              <option value="needs_review">Revisar</option>
              <option value="approved">Aprovado</option>
              <option value="failed">Falhou</option>
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
            {selectedProductIds.length} selecionado(s) - pagina {currentPage}/{totalPages} - {products.length}/{totalProductCount} visiveis
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
        <div className="table-wrap">
          <table className="products-table">
            <thead>
              <tr>
                <th className="select-column">Sel.</th>
                <th>Produto</th>
                <th>SKU</th>
                <th>Status</th>
                <th>Descrição</th>
                <th>Imagens</th>
                <th>Venda</th>
                <th>Custo IA</th>
                <th>Arquivos</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {paginatedProducts.map((product) => {
                const hasListing = Boolean(product.listing.title);
                const coverAsset = getCoverAsset(product);
                const hasImages = Boolean(coverAsset);
                const hasModel = product.assets.some((asset) => asset.kind === "model_3mf");
                return (
                  <tr key={product.id} className={product.id === selectedProduct?.id ? "selected-table-row" : ""}>
                    <td className="select-column">
                      <input
                        type="checkbox"
                        checked={selectedProductIds.includes(product.id)}
                        onChange={() => toggleProductSelection(product.id)}
                        disabled={busy}
                        aria-label={`Selecionar ${product.name}`}
                      />
                    </td>
                    <td>
                      <button className="table-product-button" onClick={() => onOpenDetails(product.id)}>
                        <span className="table-thumb">
                          {coverAsset ? <img src={assetUrl(coverAsset)} alt="" /> : <ShoppingBag size={18} />}
                        </span>
                        <span>
                          <strong>{product.name}</strong>
                          <small>{product.source_url || "Produto vindo da coleta"}</small>
                        </span>
                      </button>
                    </td>
                    <td><code>{productSku(product) || "--"}</code></td>
                    <td><span className="status-pill">{statusLabel(product.status)}</span></td>
                    <td>{hasListing ? "Gerada" : "Pendente"}</td>
                    <td>{hasImages ? "Imagem salva" : "Pendente"}</td>
                    <td>{productListed(product) ? "À venda" : "Não"}</td>
                    <td>{formatUsd(productCostTotal(product))}</td>
                    <td>{hasModel ? "3MF salvo" : "Pendente"}</td>
                    <td>
                      <div className="row-actions">
                        <IconAction
                          label="Gerar descrição"
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
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
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
                <BrainCircuit size={18} />
                <h2>Detalhes do produto</h2>
              </div>
              <button className="close-button" onClick={onCloseDetails}>Fechar</button>
            </div>
        {selectedProduct ? (
          <>
            <ProductImageGallery
              busy={busy}
              extraPrompts={imageExtraPrompts}
              product={selectedProduct}
              onExtraPromptChange={updateImageExtraPrompt}
              onOpenImage={setFullscreenAsset}
              onRegenerateImage={onRegenerateImage}
            />
            <div className="product-header">
              <div>
                <p className="eyebrow">{statusLabel(selectedProduct.status)}</p>
                <h3>{selectedProduct.name}</h3>
                <div className="sku-line">
                  <span>SKU principal</span>
                  <code>{productSku(selectedProduct) || "Será gerado na próxima ação"}</code>
                </div>
                <label className="listed-toggle">
                  <input
                    type="checkbox"
                    checked={productListed(selectedProduct)}
                    onChange={(event) => onUpdateProductListed(selectedProduct.id, event.target.checked)}
                    disabled={busy}
                  />
                  <span>Produto já está à venda</span>
                </label>
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
                <button onClick={() => onGenerateListing()} disabled={busy}>
                  <BrainCircuit size={16} /> Descrição
                </button>
                <button onClick={() => onGenerateImages()} disabled={busy}>
                  <ImagePlus size={16} /> Imagens base
                </button>
                <button onClick={onSaveListing} disabled={busy || !listingDraft}>
                  <Save size={16} /> Salvar
                </button>
                <button onClick={onApproveProduct} disabled={busy || !listingDraft?.title || !listingDraft?.description}>
                  <BadgeCheck size={16} /> Aprovar
                </button>
              </div>
            </div>

            <div className="image-generation-options">
              <div className="subsection-title">Custo de criação</div>
              <div className="cost-summary">
                <div>
                  <strong>{formatUsd(productCostTotal(selectedProduct))}</strong>
                  <span>
                    {selectedCostEvents.length} registro(s) - Texto {formatUsd(selectedCostSummary.openRouter)} - Imagens {formatUsd(selectedCostSummary.kie)}
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
                        <strong>{event.action || "A??o IA"}</strong>
                        <small>{event.provider || "IA"} ? {event.model || "modelo"} ? {event.source || "estimado"}</small>
                      </div>
                      <span>{formatUsd(Number(event.cost_usd || 0))}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="image-generation-options">
              <div className="subsection-title">Variações de cor</div>
              <div className="option-row">
                <small>
                  As cores marcadas usam a imagem base gerada pela IA como referência.
                </small>
                <button
                  className="primary compact-primary"
                  onClick={() => setColorDialogOpen(true)}
                  disabled={busy || !imageOptions.colors.length}
                >
                  <ImagePlus size={16} /> Gerar variações de cor
                </button>
              </div>
            </div>

            {listingDraft && (
              <div className="listing-editor">
                <label className="full-span">
                  Título do anúncio
                  <input value={listingDraft.title} onChange={(event) => updateDraft("title", event.target.value)} />
                </label>
                <label>
                  Categoria
                  <input value={listingDraft.category} onChange={(event) => updateDraft("category", event.target.value)} />
                </label>
                <label>
                  Preço
                  <input value={listingDraft.price} onChange={(event) => updateDraft("price", event.target.value)} />
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
                  Peso
                  <input value={listingDraft.weight} onChange={(event) => updateDraft("weight", event.target.value)} />
                </label>
                <label className="full-span">
                  Dimensões do pacote
                  <input value={listingDraft.parcel_size} onChange={(event) => updateDraft("parcel_size", event.target.value)} />
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
                  />
                </label>
              </div>
            )}

            <div className="chips">
              {(selectedProduct.listing.keywords.length ? selectedProduct.listing.keywords : selectedProduct.tags).map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
            <div className="asset-list">
              <h4>Arquivos salvos</h4>
              {selectedProduct.assets.map((asset) => (
                <div className="asset-row" key={asset.id}>
                  <strong>{asset.kind === "model_3mf" ? "Modelo 3MF" : "Imagem"}</strong>
                  <code>{asset.path}</code>
                </div>
              ))}
              {!selectedProduct.assets.length && <p className="empty">Imagem e 3MF aparecerão aqui após aprovação da IA e download.</p>}
              {typeof selectedProduct.metadata.model_download_error === "string" && selectedProduct.metadata.model_download_error && (
                <p className="asset-error">3MF: {selectedProduct.metadata.model_download_error}</p>
              )}
            </div>
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
        <GalleryGroup assets={capturedImages} emptyText="Imagem capturada aparecera aqui." onOpenImage={onOpenImage} title="Capturada" />
        <GalleryGroup
          allowRegenerate
          assets={baseImages}
          busy={busy}
          emptyText="Use o botao Imagens base para gerar."
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
  onDownloadStoreBackup,
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
  onRestoreStoreBackup,
  onStoreProfileDraftChange,
  onUploadStoreProfilePhoto,
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
  onDownloadStoreBackup: (profileId?: string) => Promise<unknown> | void;
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
  onRestoreStoreBackup: (file: File) => Promise<unknown> | void;
  onStoreProfileDraftChange: (value: StoreProfile) => void;
  onUploadStoreProfilePhoto: (profileId: string, file: File) => Promise<unknown> | void;
}) {
  const [profileEditorOpen, setProfileEditorOpen] = useState(false);
  const [integrationEditorOpen, setIntegrationEditorOpen] = useState(false);
  const [integrationSecretsVisible, setIntegrationSecretsVisible] = useState(false);
  const [loadingIntegrationSecrets, setLoadingIntegrationSecrets] = useState(false);
  const [colorDrafts, setColorDrafts] = useState<ImageOptions["colors"]>(imageOptions.colors);
  const [updateStatus, setUpdateStatus] = useState("");
  const [checkingUpdates, setCheckingUpdates] = useState(false);

  useEffect(() => {
    setColorDrafts(imageOptions.colors);
  }, [imageOptions.colors]);

  async function createAndEditStoreProfile() {
    await onCreateStoreProfile();
    setProfileEditorOpen(true);
  }

  async function saveAndCloseStoreProfile() {
    await onSaveStoreProfile();
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
    await onSaveOpenRouterSettings();
    setIntegrationSecretsVisible(false);
    setIntegrationEditorOpen(false);
  }

  function openIntegrationEditor() {
    setIntegrationEditorOpen(true);
    setIntegrationSecretsVisible(false);
  }

  async function checkForAppUpdates() {
    if (!window.ecoNative?.checkForUpdates) {
      setUpdateStatus("Atualizações automáticas ficam disponíveis no app instalado.");
      return;
    }
    setCheckingUpdates(true);
    try {
      const result = await window.ecoNative.checkForUpdates();
      setUpdateStatus(result.message);
    } finally {
      setCheckingUpdates(false);
    }
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
    onRestoreStoreBackup(file);
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

  return (
    <section className="settings-page">
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
                  Editar
                </button>
              </div>
            </div>
          ))}
        </div>
        <button className="primary profile-create-button" onClick={createAndEditStoreProfile}>
          <FolderPlus size={18} /> Criar perfil de loja
        </button>
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
              <button className="primary ghost" onClick={() => setProfileEditorOpen(false)}>
                Cancelar
              </button>
              <button className="primary" onClick={saveAndCloseStoreProfile}>
                <Save size={18} /> Salvar perfil
              </button>
            </div>
          </div>
        </div>
      )}

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
          Edite as chaves de OpenRouter, Kie.ai e Cloudflare R2 em uma janela separada. As credenciais só são carregadas quando você pedir para mostrar.
        </p>
        <button className="primary profile-create-button" onClick={openIntegrationEditor}>
          <KeyRound size={18} /> Editar integrações
        </button>
      </div>

      <div className="panel color-settings-panel">
        <div className="panel-title">
          <ImagePlus size={18} />
          <h2>Cores para variações</h2>
        </div>
        <p className="settings-note">
          Edite as descrições enviadas ao Kie/Qwen para gerar variações de cor. O ID vira parte do SKU da variação, então prefira nomes curtos e sem acentos.
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
          <button className="primary" onClick={() => onSaveImageColorOptions(colorDrafts)}>
            <Save size={18} /> Salvar cores
          </button>
        </div>
      </div>

      <div className="panel backup-settings-panel">
        <div className="panel-title">
          <Download size={18} />
          <h2>Backup da loja</h2>
        </div>
        <p className="settings-note">
          Gere um arquivo ZIP com o perfil da loja selecionada, projetos, produtos, histÃ³rico de execuÃ§Ãµes e arquivos salvos.
          Ao restaurar, os itens do backup sÃ£o adicionados ou substituem registros com o mesmo ID.
        </p>
        <div className="backup-actions">
          <button className="primary" onClick={() => onDownloadStoreBackup(storeProfileDraft?.id)} disabled={!storeProfileDraft}>
            <Download size={18} /> Baixar backup de {storeProfileDraft?.name ?? "loja"}
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
        <p className="settings-note">
          No app instalado, esta opção consulta o GitHub Releases e baixa atualizações publicadas. A instalação acontece ao fechar e abrir o aplicativo.
        </p>
        <div className="backup-actions">
          <button className="primary" onClick={checkForAppUpdates} disabled={checkingUpdates}>
            {checkingUpdates ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />} Verificar atualizações
          </button>
          {updateStatus && <span className="update-status">{updateStatus}</span>}
        </div>
      </div>

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
              <button className="primary ghost" onClick={() => setIntegrationEditorOpen(false)}>
                Cancelar
              </button>
              <button className="primary" onClick={saveAndCloseIntegrations}>
                <Save size={18} /> Salvar integrações
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="panel paths-settings-panel">
        <div className="panel-title">
          <Settings size={18} />
          <h2>Pastas locais</h2>
        </div>
        <div className="summary-list path-list">
          <SummaryItem label="Dados" value={settings?.data_dir ?? "--"} />
          <SummaryItem label="Projetos" value={settings?.projects_dir ?? "--"} />
          <SummaryItem label="Exportações" value={settings?.exports_dir ?? "--"} />
          <SummaryItem label="Modelo OpenRouter" value={settings?.integrations.openrouter_model ?? "--"} />
          <SummaryItem label="Modelo Kie imagem" value={settings?.integrations.kie_image_model ?? "--"} />
        </div>
      </div>
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
