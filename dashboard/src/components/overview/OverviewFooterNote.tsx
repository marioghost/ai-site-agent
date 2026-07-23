import { PageSection } from "../../ui";

export default function OverviewFooterNote({ text }: { text: string }) {
  return (
    <PageSection>
      <footer className="ov-footer">{text}</footer>
    </PageSection>
  );
}
