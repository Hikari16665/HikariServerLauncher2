export interface ThemeVars {
  [key: string]: string;
}

export interface ThemeDef {
  name: string;
  label: string;
  vars: ThemeVars;
}

const SANS =
  'system-ui, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif';
const MONO =
  '"JetBrains Mono", "Cascadia Code", "SF Mono", Consolas, monospace';

const SHARED: ThemeVars = {
  "--radius": "8px",
  "--radius-sm": "5px",
  "--font": SANS,
  "--mono": MONO,
};

export const THEMES: ThemeDef[] = [
  {
    name: "softPink",
    label: "温柔粉",
    vars: {
      ...SHARED,
      "--bg-primary": "#fefafc",
      "--bg-secondary": "#fdf0f5",
      "--bg-tertiary": "#fbe0ea",
      "--border": "#e8c4d4",
      "--text-primary": "#2d1a24",
      "--text-secondary": "#7a5a6a",
      "--text-muted": "#b0909e",
      "--accent": "#d44a7a",
      "--accent-hover": "#b83a64",
      "--accent-light": "rgba(212,74,122,0.08)",
      "--green": "#2d9d6f",
      "--green-bg": "rgba(45,157,111,0.10)",
      "--red": "#d94848",
      "--red-bg": "rgba(217,72,72,0.09)",
      "--yellow": "#c8882e",
      "--yellow-bg": "rgba(200,136,46,0.09)",
      "--shadow": "0 2px 16px rgba(180,60,100,0.08)",
      "--shadow-lg": "0 8px 32px rgba(180,60,100,0.12)",
    },
  },
  {
    name: "eyeBlack",
    label: "护眼黑",
    vars: {
      ...SHARED,
      "--bg-primary": "#0f1117",
      "--bg-secondary": "#171a23",
      "--bg-tertiary": "#1f2432",
      "--border": "#2a3040",
      "--text-primary": "#e4e6ed",
      "--text-secondary": "#9498a5",
      "--text-muted": "#606470",
      "--accent": "#4ecca3",
      "--accent-hover": "#3cb68a",
      "--accent-light": "rgba(78,204,163,0.08)",
      "--green": "#4ecca3",
      "--green-bg": "rgba(78,204,163,0.10)",
      "--red": "#f06060",
      "--red-bg": "rgba(240,96,96,0.09)",
      "--yellow": "#e0c04a",
      "--yellow-bg": "rgba(224,192,74,0.10)",
      "--shadow": "0 2px 16px rgba(0,0,0,0.3)",
      "--shadow-lg": "0 8px 32px rgba(0,0,0,0.5)",
    },
  },
  {
    name: "milkWhite",
    label: "轻奶白",
    vars: {
      ...SHARED,
      "--bg-primary": "#fdfaf5",
      "--bg-secondary": "#f7f0e4",
      "--bg-tertiary": "#efe4cf",
      "--border": "#d8cbb5",
      "--text-primary": "#3a3026",
      "--text-secondary": "#8a7a65",
      "--text-muted": "#b8a890",
      "--accent": "#9b7a55",
      "--accent-hover": "#7d5f40",
      "--accent-light": "rgba(155,122,85,0.08)",
      "--green": "#5a9b6a",
      "--green-bg": "rgba(90,155,106,0.10)",
      "--red": "#c47070",
      "--red-bg": "rgba(196,112,112,0.09)",
      "--yellow": "#c49a50",
      "--yellow-bg": "rgba(196,154,80,0.09)",
      "--shadow": "0 2px 16px rgba(120,90,60,0.06)",
      "--shadow-lg": "0 8px 32px rgba(120,90,60,0.10)",
    },
  },
  {
    name: "dynamicBlue",
    label: "灵动蓝",
    vars: {
      ...SHARED,
      "--bg-primary": "#f5f8fc",
      "--bg-secondary": "#eaf0f8",
      "--bg-tertiary": "#dae4f2",
      "--border": "#bcc8dc",
      "--text-primary": "#1a2332",
      "--text-secondary": "#5a6878",
      "--text-muted": "#8c98a8",
      "--accent": "#4a8ad4",
      "--accent-hover": "#3870b8",
      "--accent-light": "rgba(74,138,212,0.08)",
      "--green": "#38a07a",
      "--green-bg": "rgba(56,160,122,0.10)",
      "--red": "#d45858",
      "--red-bg": "rgba(212,88,88,0.09)",
      "--yellow": "#d49a40",
      "--yellow-bg": "rgba(212,154,64,0.09)",
      "--shadow": "0 2px 16px rgba(60,100,160,0.06)",
      "--shadow-lg": "0 8px 32px rgba(60,100,160,0.10)",
    },
  },
];

export function applyTheme(name: string): void {
  const theme = THEMES.find((t) => t.name === name) ?? THEMES[0];
  const root = document.documentElement;
  for (const [key, val] of Object.entries(theme.vars)) {
    root.style.setProperty(key, val);
  }
}
