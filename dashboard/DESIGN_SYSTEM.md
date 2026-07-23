# AI Site Agent — Design System (v2)

Enterprise SaaS UI kit for the dashboard. All pages compose screens from `dashboard/src/ui/` — no page-local button, badge, table, or card styles.

**Aesthetic:** calm, spacious, minimal — Linear / Vercel / Stripe / Supabase — not Bootstrap or admin templates.

## Quick start

```tsx
import {
  PageLayout,
  PageHeader,
  Section,
  Button,
  MetricGrid,
  StatCard,
  DataTable,
  StatusBadge,
  FilterBar,
  InfoBanner,
} from "../ui";
```

Global styles: `main.tsx` → `./ui/styles/index.css`. App root wrapped in `ThemeProvider`.

## Design tokens

Canonical source: `ui/styles/tokens.css` (`--ds-*`). TypeScript mirror: `ui/tokens/index.ts`.

### Semantic colors

| Token | Usage |
|-------|--------|
| `--ds-bg` | App background |
| `--ds-surface` | Cards, panels |
| `--ds-surface-muted` | Table headers, subtle fills |
| `--ds-border` / `--ds-border-soft` | Borders |
| `--ds-text` / `--ds-text-secondary` / `--ds-text-muted` | Text hierarchy |
| `--ds-color-accent` | Primary actions, links |
| `--ds-color-success` / `warning` / `danger` / `info` / `neutral` | Semantic states |

### Spacing (4px grid only)

`4, 8, 12, 16, 20, 24, 32, 40, 48, 64` → `--ds-space-1` … `--ds-space-16`

Never use arbitrary spacing in components.

### Radius (only 8 / 12 / 16)

| Token | Value |
|-------|-------|
| `--ds-radius-sm` | 8px — controls, tags |
| `--ds-radius-md` | 12px — inputs, alerts |
| `--ds-radius-lg` | 16px — cards, tables |

### Shadows (xs / sm / md only)

Soft, never heavy. `--ds-shadow-xs`, `--ds-shadow-sm`, `--ds-shadow-md`.

### Typography

| Class / token | Use |
|---------------|-----|
| `.ds-display`, `--ds-text-display` | Marketing hero |
| `.ds-page-title`, `--ds-text-page-title` | Page titles |
| `.ds-section-title`, `--ds-text-section-title` | Section headings |
| `.ds-card-title`, `--ds-text-card-title` | Card / drawer titles |
| `.ds-body`, `--ds-text-body` | Default body |
| `.ds-caption`, `--ds-text-caption` | Meta, hints |
| `.ds-tiny`, `--ds-text-tiny` | Uppercase labels |
| `--ds-text-stat` | KPI values |

Legacy aliases (`ds-h1`, `ds-h2`, …) remain for compatibility.

### Motion

`--ds-duration-fast` (150ms), `--ds-duration-normal` (200ms), `--ds-duration-slow` (250ms), `--ds-ease`.

### Layout

| Token | Default |
|-------|---------|
| `--ds-content-max-w` | 1280px |
| `--ds-page-gutter` | 32px |
| `--ds-page-gap` | 32px |
| `--ds-card-padding` | 24px |
| `--ds-control-h` | 36px |

## Layout

```
AppShell (ds-shell)
├── Sidebar (fixed, ds-sidebar)
└── AppMain
    ├── Topbar (ds-topbar)
    └── AppContent (scroll, ds-content)
        └── PageLayout (ds-page — max-width + rhythm)
            ├── PageHeader
            ├── Section (whitespace-first)
            └── SectionCard (elevated, when needed)
```

## Visual noise rules

- Prefer **Section** over nested cards — use whitespace and dividers to separate content.
- **FilterBar** is inline by default (no card wrapper). Pass `elevated` only when filters need a surface.
- **DataTable** uses one outer card; inner table has no double border.
- Avoid card-in-card-in-card layouts.

## Components

### Actions

- **Button** — `primary | secondary | outline | ghost | danger`, sizes `sm | md | lg`
- **IconButton** — square control, required `label` for a11y

### Structure

- **Card** — `elevated | flat | ghost`; `CardHeader`, `CardBody`, `CardFooter`
- **SectionCard** — grouped elevated surface
- **Section** — title + optional divider + body (no card chrome)
- **PageHeader** — title, subtitle, status, refresh, actions

### Metrics

- **StatCard** — single KPI primitive: icon, label, value, trend, badge
- **MetricCard** — StatCard + delta/helper
- **MetricGrid** — responsive grid; `columns={4|6}`
- **ProgressCard** — title, value, description, progress bar

### Status

- **StatusBadge** — semantic: `success | warning | danger | neutral | info` (+ legacy job statuses)
- **statusToVariant()**, **healthStatusToBadge()**

### Forms

- **Field, Input, Select, SearchInput, Dropdown**
- **FormGrid, FormStack, Textarea, CheckboxField, SwitchField, HelpText**

All controls share `--ds-control-h`, `--ds-control-radius`, focus ring.

### Data

- **FilterBar** — inline filters (optional `elevated`)
- **ActionToolbar** — bulk selection bar
- **DataTable** — columns, selection, empty/loading, footer
- **Pagination**

### Overlays

- **Drawer** — overlay or inline split pane
- **Modal / ConfirmDialog**

### Feedback

- **EmptyState / LoadingState / ErrorState / Skeleton**
- **Alert / InfoBanner / Toast**
- **ProgressBar / ProgressRing / ProgressCard**

### Navigation

- **Sidebar, Topbar, NavigationItem, UserMenu, KnowledgeMiniCard**

### Content

- **ActivityFeed, LogViewer, CodeBlock, Tabs, Accordion, InfoCard**

## Usage

### Page shell

```tsx
<PageLayout>
  <PageHeader
    title="Sources"
    subtitle="Manage indexed content"
    onRefresh={refresh}
    actions={<Button variant="primary">Add source</Button>}
  />
  <Section title="Filters">
    <FilterBar>{/* controls */}</FilterBar>
  </Section>
  <DataTable columns={cols} data={rows} keyFn={(r) => r.id} />
</PageLayout>
```

### KPI row

```tsx
<MetricGrid columns={4}>
  <StatCard label="Ready" value={360} icon={<Check size={16} />} tone="success" trend="+24 today" trendDirection="up" />
</MetricGrid>
```

## File map

```
ui/
  styles/tokens.css      — CSS custom properties
  styles/foundations.css — typography + grid utilities
  styles/components.css  — all ds-* component styles
  styles/charts.css      — analytics/chart surfaces (token-aligned)
  components/            — React primitives
  tokens/index.ts        — TS token constants
```

Legacy `styles.css` aliases `--surface`, `--accent`, etc. to `--ds-*` — do not redefine colors there.
