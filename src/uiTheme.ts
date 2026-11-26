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
};

export type UiThemePreference = {
  id: UiThemeId;
  accent?: string;
};

export const UI_THEME_STORAGE_KEY = "eco_native_ui_theme";

/**
 * Surfaces, borders and text stay neutral in every theme, so the theme colour
 * only shows in the sidebar, the accent and the content.
 */
const NEUTRAL_SURFACES = {
  ink: "#1b1b19",
  panel: "#ffffff",
  page: "#f4f4f2",
  soft: "#f1f1ef",
  soft2: "#ebebe8",
  line: "#e2e2de",
  muted: "#6b6b66",
} satisfies Partial<UiThemeTokens>;

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
      ink: "#1b1b19",
      forest: "#071f16",
      forest2: "#103020",
      panel: "#ffffff",
      page: "#f4f4f2",
      soft: "#f1f1ef",
      soft2: "#ebebe8",
      line: "#e2e2de",
      muted: "#6b6b66",
      mint: "#bff2c8",
      green: "#24b96f",
      greenDark: "#0f7a54",
      teal: "#0c6a5a",
    },
  },
  {
    id: "ocean",
    name: "Oceano",
    description: "Azul calmo para foco prolongado.",
    swatch: "#1d6fb8",
    tokens: {
      ink: "#1b1b19",
      forest: "#071626",
      forest2: "#102842",
      panel: "#ffffff",
      page: "#f4f4f2",
      soft: "#f1f1ef",
      soft2: "#ebebe8",
      line: "#e2e2de",
      muted: "#6b6b66",
      mint: "#cfe8ff",
      green: "#3b8fd9",
      greenDark: "#1d6fb8",
      teal: "#155f96",
    },
  },
  {
    id: "sunset",
    name: "Pôr do sol",
    description: "Tons quentes e acolhedores.",
    swatch: "#c45c1a",
    tokens: {
      ink: "#1b1b19",
      forest: "#241005",
      forest2: "#3a1c0a",
      panel: "#ffffff",
      page: "#f4f4f2",
      soft: "#f1f1ef",
      soft2: "#ebebe8",
      line: "#e2e2de",
      muted: "#6b6b66",
      mint: "#ffd9b8",
      green: "#e07a2f",
      greenDark: "#c45c1a",
      teal: "#9a4512",
    },
  },
  {
    id: "grape",
    name: "Uva",
    description: "Roxo elegante para criatividade.",
    swatch: "#7c3aed",
    tokens: {
      ink: "#1b1b19",
      forest: "#140b20",
      forest2: "#241538",
      panel: "#ffffff",
      page: "#f4f4f2",
      soft: "#f1f1ef",
      soft2: "#ebebe8",
      line: "#e2e2de",
      muted: "#6b6b66",
      mint: "#e4d4ff",
      green: "#9f67ff",
      greenDark: "#7c3aed",
      teal: "#5b21b6",
    },
  },
  {
    id: "slate",
    name: "Ardósia",
    description: "Neutro moderno com toque azulado.",
    swatch: "#475569",
    tokens: {
      ink: "#1b1b19",
      forest: "#0f172a",
      forest2: "#1e293b",
      panel: "#ffffff",
      page: "#f4f4f2",
      soft: "#f1f1ef",
      soft2: "#ebebe8",
      line: "#e2e2de",
      muted: "#6b6b66",
      mint: "#dbeafe",
      green: "#64748b",
      greenDark: "#475569",
      teal: "#334155",
    },
  },
  {
    id: "rose",
    name: "Rosa",
    description: "Rosa suave com contraste confortável.",
    swatch: "#db2777",
    tokens: {
      ink: "#1b1b19",
      forest: "#220918",
      forest2: "#3a1230",
      panel: "#ffffff",
      page: "#f4f4f2",
      soft: "#f1f1ef",
      soft2: "#ebebe8",
      line: "#e2e2de",
      muted: "#6b6b66",
      mint: "#ffd6ea",
      green: "#ec4899",
      greenDark: "#db2777",
      teal: "#9d174d",
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
  const forest = mixHex(greenDark, "#000000", 0.72);
  return {
    ...NEUTRAL_SURFACES,
    forest,
    forest2: mixHex(greenDark, "#000000", 0.55),
    mint: mixHex(greenDark, "#ffffff", 0.72),
    green: mixHex(greenDark, "#ffffff", 0.22),
    greenDark,
    teal: mixHex(greenDark, "#000000", 0.35),
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
  for (const [key, value] of Object.entries(buildDerivedThemeVariables(tokens))) {
    root.style.setProperty(key, value);
  }
  root.dataset.uiTheme = tokens.greenDark;
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
    "--eco-shadow": "rgba(20, 20, 18, 0.1)",
    "--eco-shadow-md": "rgba(20, 20, 18, 0.12)",
    "--eco-shadow-lg": "rgba(20, 20, 18, 0.14)",
    "--eco-shadow-xl": "rgba(20, 20, 18, 0.16)",
    "--eco-shadow-deep": "rgba(20, 20, 18, 0.18)",
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
    "--eco-shadow-sm": "rgba(20, 20, 18, 0.06)",
    "--eco-shadow-menu": "rgba(20, 20, 18, 0.12)",
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

export function normalizeUiThemePreference(value: Partial<UiThemePreference> | null | undefined): UiThemePreference {
  if (!value) return DEFAULT_THEME;
  if (value.id === "custom") {
    const accent = normalizeHex(value.accent ?? "");
    return accent ? { id: "custom", accent } : DEFAULT_THEME;
  }
  if (UI_THEME_PRESETS.some((preset) => preset.id === value.id)) {
    return { id: value.id as Exclude<UiThemeId, "custom"> };
  }
  return DEFAULT_THEME;
}

export function readUiThemePreference(): UiThemePreference {
  try {
    const raw = window.localStorage.getItem(UI_THEME_STORAGE_KEY);
    return raw ? normalizeUiThemePreference(JSON.parse(raw) as UiThemePreference) : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

export function saveUiThemePreference(preference: UiThemePreference) {
  try {
    window.localStorage.setItem(UI_THEME_STORAGE_KEY, JSON.stringify(preference));
  } catch {
    // Only avoids a flash of the default colours on the next load.
  }
}

/** Shows a store's theme (the default when none) and remembers it for the next page load. */
export function showUiTheme(value: Partial<UiThemePreference> | null | undefined) {
  const preference = normalizeUiThemePreference(value);
  saveUiThemePreference(preference);
  applyUiThemePreference(preference);
}

export function applyUiThemePreference(preference: UiThemePreference) {
  applyUiTheme(resolveUiThemeTokens(preference));
}

export function initUiTheme() {
  applyUiThemePreference(readUiThemePreference());
}
