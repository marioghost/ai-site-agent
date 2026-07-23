import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import LanguageSwitcher from "../LanguageSwitcher";
import { useSidebar } from "../../context/SidebarContext";
import { useTranslation } from "../../i18n";
import { IconButton, Topbar } from "../../ui";

export default function AppTopBar() {
  const { t } = useTranslation();
  const { collapsed, toggle } = useSidebar();

  return (
    <Topbar
      start={
        <IconButton
          label={collapsed ? t("app.sidebar_expand") : t("app.sidebar_collapse")}
          onClick={toggle}
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </IconButton>
      }
      context={t("app.header")}
      actions={<LanguageSwitcher />}
    />
  );
}
