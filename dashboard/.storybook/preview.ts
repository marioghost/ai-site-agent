import type { Preview } from "@storybook/react";
import "../src/ui/styles/index.css";

const preview: Preview = {
  parameters: {
    layout: "centered",
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
  },
  decorators: [
    (Story) => (
      <div style={{ fontFamily: "var(--ds-font)", padding: 24 }}>
        <Story />
      </div>
    ),
  ],
};

export default preview;
