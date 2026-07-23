import type { Meta, StoryObj } from "@storybook/react";
import { MetricCard, MetricGrid } from "./MetricCard";
import { Check } from "lucide-react";

const meta: Meta<typeof MetricCard> = {
  title: "Design System/MetricCard",
  component: MetricCard,
  tags: ["autodocs"],
};

export default meta;
type Story = StoryObj<typeof MetricCard>;

export const Ready: Story = {
  args: {
    label: "Ready to use",
    value: 360,
    helper: "Indexed and available",
    delta: "+24 today",
    icon: <Check size={18} />,
    tone: "success",
  },
};

export const Grid: Story = {
  render: () => (
    <MetricGrid columns={3} style={{ width: 720 }}>
      <MetricCard label="Ready" value={360} tone="success" icon={<Check size={18} />} />
      <MetricCard label="Pending" value={42} tone="warning" icon={<Check size={18} />} />
      <MetricCard label="Failed" value={3} tone="danger" icon={<Check size={18} />} />
    </MetricGrid>
  ),
};
