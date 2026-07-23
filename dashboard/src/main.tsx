import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { I18nProvider } from "./i18n";
import { AuthProvider } from "./context/AuthContext";
import { ChatSessionProvider } from "./context/ChatSessionContext";
import App from "./App";
import { ThemeProvider } from "./ui";
import "./ui/styles/index.css";
import "./styles.css";
import "./auth-layout.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <I18nProvider>
          <AuthProvider>
            <ChatSessionProvider>
              <App />
            </ChatSessionProvider>
          </AuthProvider>
        </I18nProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
