type Item = { label: string; value: number | string };

export default function IndexingMetricsRow({ items }: { items: Item[] }) {
  return (
    <div className="ds-metrics-row">
      {items.map((item) => (
        <div key={item.label} className="ds-metrics-row__item">
          <div className="ds-metrics-row__label">{item.label}</div>
          <div className="ds-metrics-row__value">{item.value}</div>
        </div>
      ))}
    </div>
  );
}
