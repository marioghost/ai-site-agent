import type { TimeseriesPoint } from "../../../../types";

export type TrendValueKey =
  | "requests"
  | "avg_latency_ms"
  | "cache_hit_rate"
  | "fallback_rate"
  | "context_usage_rate";

interface Props {
  title: string;
  points: TimeseriesPoint[];
  valueKey: TrendValueKey;
  emptyLabel: string;
  variant?: "purple" | "teal" | "orange";
  formatValue?: (v: number) => string;
  tall?: boolean;
}

export default function TrendChartCard({
  title,
  points,
  valueKey,
  emptyLabel,
  variant = "purple",
  formatValue,
  tall = false,
}: Props) {
  const width = 480;
  const height = tall ? 240 : 200;
  const pad = { top: 14, right: 14, bottom: 30, left: 40 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const valueOf = (p: TimeseriesPoint) => {
    const v = p[valueKey];
    return typeof v === "number" ? v : 0;
  };

  const values = points.map(valueOf);
  const maxY = Math.max(
    ...values,
    isRateKey(valueKey) ? 0.01 : 1
  );
  const isRate = isRateKey(valueKey);
  const yTicks = isRate
      ? [0, maxY / 2, maxY]
      : [0, Math.round(maxY / 2), Math.round(maxY * 10) / 10];

  const coords =
    points.length === 0
      ? []
      : points.map((p, i) => {
          const x =
            pad.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
          const y = pad.top + innerH - (valueOf(p) / maxY) * innerH;
          return { x, y, p, v: valueOf(p) };
        });

  const linePath =
    coords.length > 0
      ? coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(" ")
      : "";

  const areaPath =
    coords.length > 0
      ? `${linePath} L ${coords[coords.length - 1].x.toFixed(1)} ${(pad.top + innerH).toFixed(1)} L ${coords[0].x.toFixed(1)} ${(pad.top + innerH).toFixed(1)} Z`
      : "";

  const xLabels =
    points.length <= 6
      ? points
      : [points[0], points[Math.floor(points.length / 2)], points[points.length - 1]];

  const fmt = (v: number) => {
    if (formatValue) return formatValue(v);
    if (isRate) return `${(v * 100).toFixed(0)}%`;
    return String(Math.round(v));
  };

  return (
    <article className={`an-chart-card an-chart-card--${variant}${tall ? " an-chart-card--tall" : ""}`}>
      <h3 className="an-chart-card__title">{title}</h3>
      {points.length === 0 ? (
        <p className="an-chart-card__empty">{emptyLabel}</p>
      ) : (
        <svg
          className="an-chart-card__svg"
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={title}
        >
          {yTicks.map((tick, i) => {
            const y = pad.top + innerH - (tick / maxY) * innerH;
            return (
              <g key={`${tick}-${i}`}>
                <line x1={pad.left} y1={y} x2={width - pad.right} y2={y} className="an-chart-grid" />
                <text x={pad.left - 8} y={y + 4} className="an-chart-axis" textAnchor="end">
                  {fmt(tick)}
                </text>
              </g>
            );
          })}
          {areaPath && <path d={areaPath} className={`an-chart-area an-chart-area--${variant}`} />}
          {linePath && (
            <path d={linePath} className={`an-chart-line an-chart-line--${variant}`} fill="none" />
          )}
          {coords.map((c) => (
            <circle
              key={c.p.hour}
              cx={c.x}
              cy={c.y}
              r="3.5"
              className={`an-chart-dot an-chart-dot--${variant}`}
            >
              <title>{`${new Date(c.p.hour).toLocaleString()}: ${fmt(c.v ?? 0)}`}</title>
            </circle>
          ))}
          {xLabels.map((p) => {
            const idx = points.indexOf(p);
            const x =
              pad.left +
              (points.length === 1 ? innerW / 2 : (idx / (points.length - 1)) * innerW);
            return (
              <text
                key={p.hour}
                x={x}
                y={height - 8}
                className="an-chart-axis"
                textAnchor="middle"
              >
                {new Date(p.hour).toLocaleTimeString(undefined, {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </text>
            );
          })}
        </svg>
      )}
    </article>
  );
}

function isRateKey(key: TrendValueKey): boolean {
  return key === "cache_hit_rate" || key === "fallback_rate" || key === "context_usage_rate";
}
