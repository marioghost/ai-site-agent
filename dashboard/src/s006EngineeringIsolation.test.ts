import { describe, expect, it } from "vitest";
import { ENGINEERING_NAV } from "./lib/navConfig";
import askScreenSource from "./features/ask/AskScreen.tsx?raw";
import askDiagnosticsSlotSource from "./features/ask/widgets/AskDiagnosticsSlot.tsx?raw";
import chatToolbarSource from "./components/chat/ChatToolbar.tsx?raw";
import updateScreenSource from "./features/knowledge/update/UpdateScreen.tsx?raw";
import engKnowledgeScreenSource from "./features/engineering/knowledge/EngKnowledgeScreen.tsx?raw";
import engAdvancedScreenSource from "./features/engineering/advanced/EngAdvancedScreen.tsx?raw";
import engBuildScreenSource from "./features/engineering/build/EngBuildScreen.tsx?raw";
import engStatusScreenSource from "./features/engineering/status/EngStatusScreen.tsx?raw";
import engTensionsScreenSource from "./features/engineering/tensions/EngTensionsScreen.tsx?raw";
import engineeringLayoutSource from "./layouts/EngineeringLayout.tsx?raw";
import generalScreenSource from "./features/settings/general/GeneralScreen.tsx?raw";
import modelsScreenSource from "./features/settings/models/ModelsScreen.tsx?raw";
import answersScreenSource from "./features/settings/answers/AnswersScreen.tsx?raw";
import accessScreenSource from "./features/settings/access/AccessScreen.tsx?raw";

describe("S006 Engineering isolation + Ask handoff", () => {
  it("Ask keeps product surface free of ChatHistoryModal; diagnostics only via Eng Mode slot", () => {
    expect(askScreenSource).not.toMatch(/ChatHistoryModal/);
    expect(askScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(askScreenSource).not.toMatch(/ChatDiagnosticsSidebar/);
    expect(askScreenSource).toMatch(/AskDiagnosticsSlot/);
    expect(askScreenSource).toMatch(/useEngineeringMode/);
    expect(askScreenSource).toMatch(/engineeringModeOn/);
  });

  it("AskDiagnosticsSlot owns ChatDiagnosticsSidebar (RFC-102 Eng Mode slot)", () => {
    expect(askDiagnosticsSlotSource).toMatch(/ChatDiagnosticsSidebar/);
    expect(askDiagnosticsSlotSource).toMatch(/useAskDiagnosticsView/);
  });

  it("keeps Ask's core chat chrome (progressive disclosure — simple, not empty)", () => {
    expect(askScreenSource).toMatch(/useChatSession/);
    expect(askScreenSource).toMatch(/ChatToolbar/);
    expect(askScreenSource).toMatch(/ChatMessageList/);
    expect(askScreenSource).toMatch(/ChatComposer/);
  });

  it("hands off chat history from Ask to Insights Activity instead of a modal", () => {
    expect(askScreenSource).toMatch(/onOpenHistory=\{\(\) => navigate\("\/insights\/activity"\)\}/);
    expect(askScreenSource).toMatch(/useNavigate/);
  });

  it("ChatToolbar remains a presentational callback-driven toolbar (does not itself own history modal state)", () => {
    expect(chatToolbarSource).not.toMatch(/ChatHistoryModal/);
    expect(chatToolbarSource).not.toMatch(/historyOpen/);
  });

  it("Eng screens no longer use the S001 MigrationPlaceholder scaffold", () => {
    expect(engKnowledgeScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(engAdvancedScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(engBuildScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(engStatusScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(engTensionsScreenSource).not.toMatch(/MigrationPlaceholder/);
  });

  it("moves Source Intelligence generate/preview chrome from Update into Eng Knowledge (G4-P4)", () => {
    expect(updateScreenSource).not.toMatch(/SourceIntelligencePanel/);
    expect(updateScreenSource).not.toMatch(/SourceIntelligencePreviewModal/);
    expect(updateScreenSource).not.toMatch(/generateSourceIntelligence/);
    expect(updateScreenSource).toMatch(/startIndexing/);
    expect(updateScreenSource).toMatch(/stopIndexing/);
    expect(updateScreenSource).toMatch(/reindexAll/);
    expect(updateScreenSource).toMatch(/reprocessExisting/);
    expect(updateScreenSource).toMatch(/useEngineeringMode/);
    expect(updateScreenSource).toMatch(/engineeringModeOn/);
    expect(updateScreenSource).toMatch(/\/engineering\/knowledge/);

    expect(engKnowledgeScreenSource).toMatch(/generateSourceIntelligence/);
    expect(engKnowledgeScreenSource).toMatch(/SourceIntelligencePanel/);
    expect(engKnowledgeScreenSource).toMatch(/SourceIntelligencePreviewModal/);
  });

  it("EngAdvancedScreen hosts SettingsAdvancedSection + retrieval knobs; EngBuildScreen hosts MigrationFlagsPanel (G7-P5)", () => {
    expect(engAdvancedScreenSource).toMatch(/SettingsAdvancedSection/);
    expect(engBuildScreenSource).toMatch(/MigrationFlagsPanel/);
  });

  it("Product Settings (General/Models/Answers/Access) never mounts advanced knobs or the flag catalog", () => {
    for (const source of [
      generalScreenSource,
      modelsScreenSource,
      answersScreenSource,
      accessScreenSource,
    ]) {
      expect(source).not.toMatch(/SettingsAdvancedSection/);
      expect(source).not.toMatch(/RetrievalEnginePanel/);
      expect(source).not.toMatch(/MigrationFlagsPanel/);
    }
  });

  it("EngStatusScreen is a real health screen using getHealth/getBuildInfo", () => {
    expect(engStatusScreenSource).toMatch(/getHealth/);
    expect(engStatusScreenSource).toMatch(/getBuildInfo/);
    expect(engStatusScreenSource).toMatch(/SubsystemHealthPanel/);
  });

  it("EngTensionsScreen links to the epistemic-health tension explorer", () => {
    expect(engTensionsScreenSource).toMatch(/\/diagnostics\/epistemic-health/);
  });

  it("EngineeringLayout adds section nav for remaining Engineering destinations (no Chat details)", () => {
    expect(engineeringLayoutSource).toMatch(/NavLink/);
    expect(engineeringLayoutSource).toMatch(/ENGINEERING_NAV/);
    expect(engineeringLayoutSource).toMatch(/<Outlet/);
    expect(ENGINEERING_NAV.items).toHaveLength(5);
    expect(ENGINEERING_NAV.items.map((item) => item.to)).toEqual([
      "/engineering/status",
      "/engineering/knowledge",
      "/engineering/tensions",
      "/engineering/advanced",
      "/engineering/build",
    ]);
  });
});
