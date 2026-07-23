import { Outlet } from "react-router-dom";
import { AppContent, AppMain, AppShell } from "../../ui";
import { SidebarProvider, useSidebar } from "../../context/SidebarContext";
import AppSidebar from "./AppSidebar";
import AppTopBar from "./AppTopBar";

function DashboardShell() {
  const { collapsed } = useSidebar();

  return (
    <AppShell className={collapsed ? "ds-shell--sidebar-collapsed" : undefined}>
      <AppSidebar />
      <AppMain>
        <AppTopBar />
        <AppContent>
          <Outlet />
        </AppContent>
      </AppMain>
    </AppShell>
  );
}

export default function DashboardLayout() {
  return (
    <SidebarProvider>
      <DashboardShell />
    </SidebarProvider>
  );
}
