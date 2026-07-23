import type { TimeseriesPoint } from "../../types";

interface Props {
  title: string;
  points: TimeseriesPoint[];
  emptyLabel: string;
}

export default function RequestsLineChartCard({ title, points, emptyLabel }: Props) {
  const width = 420;
  const height = 200;
  const pad = { top: 12, right: 12, bottom: 28, left: 36 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const values = points.map((p) => p.requests);
  const maxY = Math.max(...values, 1);
  const yTicks = [0, Math.round(maxY / 2), maxY];

  const coords =
    points.length === 0
      ? []
      : points.map((p, i) => {
          const x = pad.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
          const y = pad.top + innerH - (p.requests / maxY) * innerH;
          return { x, y, p };
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

  return (
    <article className="ov-analytics-card ov-analytics-card--chart">
      <h3 className="ov-analytics-card__title">{title}</h3>
      {points.length === 0 ? (
        <p className="ov-analytics-card__empty">{emptyLabel}</p>
      ) : (
        <svg
          className="ov-line-chart"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={title}
        >
          {yTicks.map((tick) => {
            const y = pad.top + innerH - (tick / maxY) * innerH;
            return (
              <g key={tick}>
                <line
                  x1={pad.left}
                  y1={y}
                  x2={width - pad.right}
                  y2={y}
                  className="ov-line-chart__grid"
                />
                <text x={pad.left - 8} y={y + 4} className="ov-line-chart__axis" textAnchor="end">
                  {tick}
                </text>
              </g>
            );
          })}
          {areaPath && <path d={areaPath} className="ov-line-chart__area" />}
          {linePath && <path d={linePath} className="ov-line-chart__line" fill="none" />}
          {coords.map((c) => (
            <circle key={c.p.hour} cx={c.x} cy={c.y} r="3" className="ov-line-chart__dot" />
          ))}
          {xLabels.map((p) => {
            const idx = points.indexOf(p);
            const x =
              pad.left +
              (points.length === 1 ? innerW / 2 : (idx / (points.length - 1)) * innerW);
            const label = new Date(p.hour).toLocaleTimeString(undefined, {
              hour: "2-digit",
              minute: "2-digit",
            });
            return (
              <text key={p.hour} x={x} y={height - 6} className="ov-line-chart__axis" textAnchor="middle">
                {label}
              </text>
            );
          })}
        </svg>
      )}
    </article>
  );
}
