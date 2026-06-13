export type UiThemeId = "forest" | "ocean" | "sunset" | "grape" | "slate" | "rose" | "custom";

export type UiThemeTokens = {
  ink: string;
  forest: string;
  forest2: string;
  panel: string;
  page: string;
  soft: string;
  soft2: string;
  line: string;
  muted: string;
  mint: string;
  green: string;
  greenDark: string;
  teal: string;
  sidebarGlow: string;
};

export type UiThemePreference = {
  id: UiThemeId;
  accent?: string;
};

export const UI_THEME_STORAGE_KEY = "eco_native_ui_theme";

const DEFAULT_THEME: UiThemePreference = { id: "forest" };

export const UI_THEME_PRESETS: Array<{
  id: Exclude<UiThemeId, "custom">;
  name: string;
  description: string;
  swatch: string;
  tokens: UiThemeTokens;
}> = [
  {
    id: "forest",
    name: "Floresta",
    description: "Verde original do ECO Native.",
    swatch: "#0f7a54",
    tokens: {
      ink: "#0b1f16",
      forest: "#071f16",
      forest2: "#103020",
      panel: "#fffef7",
      page: "#f4f8f0",
      soft: "#edf7ef",
      soft2: "#e7f3e7",
      line: "#d9e7d9",
      muted: "#5f7167",
      mint: "#bff2c8",
      green: "#24b96f",
      greenDark: "#0f7a54",
      teal: "#0c6a5a",
      sidebarGlow: "rgba(36, 185, 111, 0.18)",
    },
  },
  {
    id: "ocean",
    name: "Oceano",
    description: "Azul calmo para foco prolongado.",
    swatch: "#1d6fb8",
    tokens: {
      ink: "#0b1a2a",
      forest: "#071626",
      forest2: "#102842",
      panel: "#fbfdff",
      page: "#f2f7fc",
      soft: "#eaf3fb",
      soft2: "#e1edf8",
      line: "#d4e3f2",
      muted: "#5f6f82",
      mint: "#cfe8ff",
      green: "#3b8fd9",
      greenDark: "#1d6fb8",
      teal: "#155f96",
      sidebarGlow: "rgba(59, 143, 217, 0.2)",
    },
  },
  {
    id: "sunset",
    name: "Pôr do sol",
    description: "Tons quentes e acolhedores.",
    swatch: "#c45c1a",
    tokens: {
      ink: "#2a1608",
      forest: "#241005",
      forest2: "#3a1c0a",
      panel: "#fffaf5",
      page: "#fbf4ec",
      soft: "#f8ebde",
      soft2: "#f3e2d1",
      line: "#ead7c6",
      muted: "#7a6455",
      mint: "#ffd9b8",
      green: "#e07a2f",
      greenDark: "#c45c1a",
      teal: "#9a4512",
      sidebarGlow: "rgba(224, 122, 47, 0.2)",
    },
  },
  {
    id: "grape",
    name: "Uva",
    description: "Roxo elegante para criatividade.",
    swatch: "#7c3aed",
    tokens: {
      ink: "#1a1028",
      forest: "#140b20",
      forest2: "#241538",
      panel: "#fdfbff",
      page: "#f7f2fc",
      soft: "#f0e8fa",
      soft2: "#e8ddf7",
      line: "#ddd0ef",
      muted: "#6f6282",
      mint: "#e4d4ff",
      green: "#9f67ff",
      greenDark: "#7c3aed",
      teal: "#5b21b6",
      sidebarGlow: "rgba(124, 58, 237, 0.2)",
    },
  },
  {
    id: "slate",
    name: "Ardósia",
    description: "Neutro moderno com toque azulado.",
    swatch: "#475569",
    tokens: {
      ink: "#111827",
      forest: "#0f172a",
      forest2: "#1e293b",
      panel: "#ffffff",
      page: "#f4f6f8",
      soft: "#eef2f6",
      soft2: "#e6ebf0",
      line: "#d7dee7",
      muted: "#64748b",
      mint: "#dbeafe",
      green: "#64748b",
      greenDark: "#475569",
      teal: "#334155",
      sidebarGlow: "rgba(100, 116, 139, 0.18)",
    },
  },
  {
    id: "rose",
    name: "Rosa",
    description: "Rosa suave com contraste confortável.",
    swatch: "#db2777",
    tokens: {
      ink: "#2a0f1c",
      forest: "#220918",
      forest2: "#3a1230",
      panel: "#fffafd",
      page: "#fdf2f8",
      soft: "#fce7f3",
      soft2: "#f9daea",
      line: "#f0c4da",
      muted: "#7a5568",
      mint: "#ffd6ea",
      green: "#ec4899",
      greenDark: "#db2777",
      teal: "#9d174d",
      sidebarGlow: "rgba(219, 39, 119, 0.18)",
    },
  },
];

function clamp(value: number, min = 0, max = 255) {
  return Math.min(max, Math.max(min, Math.round(value)));
}

function normalizeHex(value: string): string | null {
  const trimmed = value.trim();
  const match = trimmed.match(/^#?([0-9a-fA-F]{6})$/);
  if (!match) return null;
  return `#${match[1].toLowerCase()}`;
}

function hexToRgb(hex: string): [number, number, number] {
  const normalized = normalizeHex(hex);
  if (!normalized) return [15, 122, 84];
  const value = normalized.slice(1);
  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16),
  ];
}

function rgbToHex(r: number, g: number, b: number): string {
  return `#${[r, g, b].map((channel) => clamp(channel).toString(16).padStart(2, "0")).join("")}`;
}

function mixHex(base: string, target: string, weight: number): string {
  const [r1, g1, b1] = hexToRgb(base);
  const [r2, g2, b2] = hexToRgb(target);
  const ratio = Math.min(1, Math.max(0, weight));
  return rgbToHex(
    r1 + (r2 - r1) * ratio,
    g1 + (g2 - g1) * ratio,
    b1 + (b2 - b1) * ratio,
  );
}

function rgbaFromHex(hex: string, alpha: number): string {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function deriveThemeFromAccent(accent: string): UiThemeTokens {
  const greenDark = normalizeHex(accent) ?? "#0f7a54";
  const green = mixHex(greenDark, "#ffffff", 0.22);
  const mint = mixHex(greenDark, "#ffffff", 0.72);
  const forest = mixHex(greenDark, "#000000", 0.72);
  const forest2 = mixHex(greenDark, "#000000", 0.55);
  const ink = mixHex(forest, "#000000", 0.25);
  const page = mixHex(mint, "#ffffff", 0.55);
  const soft = mixHex(mint, "#ffffff", 0.35);
  const soft2 = mixHex(mint, "#ffffff", 0.22);
  const line = mixHex(greenDark, "#ffffff", 0.78);
  const muted = mixHex(ink, "#ffffff", 0.45);
  const teal = mixHex(greenDark, "#000000", 0.35);
  return {
    ink,
    forest,
    forest2,
    panel: mixHex(page, "#ffffff", 0.35),
    page,
    soft,
    soft2,
    line,
    muted,
    mint,
    green,
    greenDark,
    teal,
    sidebarGlow: rgbaFromHex(green, 0.18),
  };
}

export function applyUiTheme(tokens: UiThemeTokens) {
  const root = document.documentElement;
  root.style.setProperty("--eco-ink", tokens.ink);
  root.style.setProperty("--eco-forest", tokens.forest);
  root.style.setProperty("--eco-forest-2", tokens.forest2);
  root.style.setProperty("--eco-panel", tokens.panel);
  root.style.setProperty("--eco-page", tokens.page);
  root.style.setProperty("--eco-soft", tokens.soft);
  root.style.setProperty("--eco-soft-2", tokens.soft2);
  root.style.setProperty("--eco-line", tokens.line);
  root.style.setProperty("--eco-muted", tokens.muted);
  root.style.setProperty("--eco-mint", tokens.mint);
  root.style.setProperty("--eco-green", tokens.green);
  root.style.setProperty("--eco-green-dark", tokens.greenDark);
  root.style.setProperty("--eco-teal", tokens.teal);
  root.style.setProperty("--eco-sidebar-glow", tokens.sidebarGlow);
  for (const [key, value] of Object.entries(buildDerivedThemeVariables(tokens))) {
    root.style.setProperty(key, value);
  }
  root.dataset.uiTheme = tokens.greenDark;
  if (typeof window !== "undefined" && window.ecoNative?.setTitleBarOverlay) {
    window.ecoNative.setTitleBarOverlay({
      color: "#00000000",
      symbolColor: tokens.muted,
    }).catch(() => undefined);
  }
}

export function buildDerivedThemeVariables(tokens: UiThemeTokens): Record<string, string> {
  return {
    "--eco-accent-border": mixHex(tokens.green, tokens.line, 0.55),
    "--eco-surface-muted": mixHex(tokens.soft2, tokens.line, 0.45),
    "--eco-surface-muted-border": mixHex(tokens.line, tokens.muted, 0.35),
    "--eco-accent-highlight": mixHex(tokens.soft, tokens.green, 0.28),
    "--eco-accent-track": mixHex(tokens.line, tokens.soft2, 0.55),
    "--eco-sidebar-text": mixHex(tokens.mint, "#ffffff", 0.72),
    "--eco-sidebar-text-muted": mixHex(tokens.mint, tokens.forest, 0.35),
    "--eco-sidebar-text-strong": mixHex(tokens.panel, tokens.mint, 0.1),
    "--eco-sidebar-border": rgbaFromHex(tokens.mint, 0.18),
    "--eco-sidebar-border-strong": rgbaFromHex(tokens.mint, 0.22),
    "--eco-sidebar-border-subtle": rgbaFromHex(tokens.mint, 0.14),
    "--eco-sidebar-hover": rgbaFromHex(tokens.mint, 0.13),
    "--eco-on-sidebar": mixHex(tokens.panel, tokens.mint, 0.08),
    "--eco-shadow": rgbaFromHex(tokens.forest, 0.25),
    "--eco-shadow-md": rgbaFromHex(tokens.forest, 0.28),
    "--eco-shadow-lg": rgbaFromHex(tokens.forest, 0.34),
    "--eco-shadow-xl": rgbaFromHex(tokens.forest, 0.38),
    "--eco-shadow-deep": rgbaFromHex(tokens.forest, 0.42),
    "--eco-overlay": rgbaFromHex(tokens.forest, 0.58),
    "--eco-overlay-strong": rgbaFromHex(tokens.forest, 0.72),
    "--eco-accent-tint-12": rgbaFromHex(tokens.greenDark, 0.12),
    "--eco-accent-tint-18": rgbaFromHex(tokens.greenDark, 0.18),
    "--eco-accent-border-alpha": rgbaFromHex(tokens.green, 0.38),
    "--eco-forest-alpha-08": rgbaFromHex(tokens.forest2, 0.08),
    "--eco-forest-alpha-12": rgbaFromHex(tokens.forest2, 0.12),
    "--eco-success-bg": mixHex(tokens.soft, tokens.green, 0.15),
    "--eco-success-border": mixHex(tokens.line, tokens.green, 0.48),
    "--eco-success-text": mixHex(tokens.greenDark, tokens.ink, 0.65),
    "--eco-accent-mid": mixHex(tokens.green, tokens.greenDark, 0.42),
    "--eco-highlight-bg": mixHex(tokens.soft, tokens.green, 0.22),
    "--eco-page-subtle": mixHex(tokens.page, "#ffffff", 0.38),
    "--eco-highlight-surface": mixHex(tokens.soft2, tokens.green, 0.18),
    "--eco-highlight-border": mixHex(tokens.line, tokens.green, 0.42),
    "--eco-surface-hover": mixHex(tokens.soft2, tokens.line, 0.35),
    "--eco-forest-alpha-14": rgbaFromHex(tokens.forest2, 0.14),
    "--eco-shadow-sm": rgbaFromHex(tokens.forest2, 0.08),
    "--eco-shadow-menu": rgbaFromHex(tokens.forest, 0.24),
    "--eco-backdrop-heavy": rgbaFromHex(tokens.forest, 0.82),
  };
}

export function resolveUiThemeTokens(preference: UiThemePreference): UiThemeTokens {
  if (preference.id === "custom" && preference.accent) {
    return deriveThemeFromAccent(preference.accent);
  }
  const preset = UI_THEME_PRESETS.find((item) => item.id === preference.id);
  return preset?.tokens ?? UI_THEME_PRESETS[0].tokens;
}

export function readUiThemePreference(): UiThemePreference {
  try {
    const raw = window.localStorage.getItem(UI_THEME_STORAGE_KEY);
    if (!raw) return DEFAULT_THEME;
    const parsed = JSON.parse(raw) as UiThemePreference;
    if (parsed.id === "custom") {
      const accent = normalizeHex(parsed.accent ?? "");
      if (!accent) return DEFAULT_THEME;
      return { id: "custom", accent };
    }
    if (UI_THEME_PRESETS.some((preset) => preset.id === parsed.id)) {
      return { id: parsed.id as Exclude<UiThemeId, "custom"> };
    }
  } catch {
    return DEFAULT_THEME;
  }
  return DEFAULT_THEME;
}

export function saveUiThemePreference(preference: UiThemePreference) {
  window.localStorage.setItem(UI_THEME_STORAGE_KEY, JSON.stringify(preference));
}

export function applyUiThemePreference(preference: UiThemePreference) {
  applyUiTheme(resolveUiThemeTokens(preference));
}

export function initUiTheme() {
  applyUiThemePreference(readUiThemePreference());
}
