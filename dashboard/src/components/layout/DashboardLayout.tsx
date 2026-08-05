import { Outlet } from "react-router-dom";
import { useEffect } from "react";
import { AppContent, AppMain, AppShell } from "../../ui";
import { SidebarProvider, useSidebar } from "../../context/SidebarContext";
import { useTranslation } from "../../i18n";
import AppSidebar from "./AppSidebar";
import AppTopBar from "./AppTopBar";
import ViewportGate, { DASHBOARD_MIN_WIDTH_PX } from "./ViewportGate";

function DashboardShell() {
  const { collapsed, setCollapsed } = useSidebar();
  const { t } = useTranslation();

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${DASHBOARD_MIN_WIDTH_PX - 1}px)`);
    const sync = () => {
      if (mq.matches) setCollapsed(true);
    };
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, [setCollapsed]);

  return (
    <>
      <a href="#main-content" className="ds-skip-link">
        {t("shell.skip_to_content")}
      </a>
      <AppShell className={collapsed ? "ds-shell--sidebar-collapsed" : undefined}>
        <AppSidebar />
        <AppMain>
          <AppTopBar />
          <AppContent id="main-content" tabIndex={-1}>
            <Outlet />
          </AppContent>
        </AppMain>
      </AppShell>
      <ViewportGate />
    </>
  );
}

export default function DashboardLayout() {
  return (
    <SidebarProvider>
      <DashboardShell />
    </SidebarProvider>
  );
}
