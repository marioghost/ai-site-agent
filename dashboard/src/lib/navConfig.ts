import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  BookOpen,
  Flag,
  Globe,
  Home,
  MessageSquare,
  RefreshCw,
  Settings,
  SlidersHorizontal,
  Stethoscope,
  TriangleAlert,
  Users,
  Wrench,
} from "lucide-react";

export type NavItem = {
  kind: "item";
  to: string;
  labelKey: string;
  Icon: LucideIcon;
};

export type NavSection = {
  kind: "section";
  labelKey: string;
  items: Array<{
    to: string;
    labelKey: string;
    Icon: LucideIcon;
  }>;
};

export type NavEntry = NavItem | NavSection;

/** Product top-level nav (Mode off). RFC-101 job families. */
export const PRODUCT_NAV: NavEntry[] = [
  { kind: "item", to: "/home", labelKey: "nav.home", Icon: Home },
  {
    kind: "section",
    labelKey: "nav.knowledge",
    items: [
      { to: "/knowledge/library", labelKey: "nav.library", Icon: BookOpen },
      { to: "/knowledge/update", labelKey: "nav.update", Icon: RefreshCw },
      { to: "/knowledge/site", labelKey: "nav.site", Icon: Globe },
    ],
  },
  { kind: "item", to: "/ask", labelKey: "nav.ask", Icon: MessageSquare },
  {
    kind: "section",
    labelKey: "nav.insights",
    items: [
      { to: "/insights/performance", labelKey: "nav.performance", Icon: BarChart3 },
      { to: "/insights/activity", labelKey: "nav.activity", Icon: Activity },
    ],
  },
  {
    kind: "section",
    labelKey: "nav.settings",
    items: [
      { to: "/settings/general", labelKey: "nav.general", Icon: Settings },
      { to: "/settings/models", labelKey: "nav.models", Icon: SlidersHorizontal },
      { to: "/settings/answers", labelKey: "nav.answers", Icon: MessageSquare },
      { to: "/settings/access", labelKey: "nav.access", Icon: Users },
    ],
  },
];

/** Engineering nav — append only when Mode on (Owner/admin). */
export const ENGINEERING_NAV: NavSection = {
  kind: "section",
  labelKey: "nav.engineering",
  items: [
    { to: "/engineering/status", labelKey: "nav.eng_status", Icon: Stethoscope },
    { to: "/engineering/ask-details", labelKey: "nav.eng_ask_details", Icon: Wrench },
    { to: "/engineering/knowledge", labelKey: "nav.eng_knowledge", Icon: BookOpen },
    { to: "/engineering/tensions", labelKey: "nav.eng_tensions", Icon: TriangleAlert },
    { to: "/engineering/advanced", labelKey: "nav.eng_advanced", Icon: SlidersHorizontal },
    { to: "/engineering/build", labelKey: "nav.eng_build", Icon: Flag },
  ],
};

export function buildNavEntries(engineeringModeOn: boolean): NavEntry[] {
  if (!engineeringModeOn) return PRODUCT_NAV;
  return [...PRODUCT_NAV, ENGINEERING_NAV];
}
