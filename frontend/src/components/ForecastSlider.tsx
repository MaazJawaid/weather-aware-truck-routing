import { closestHour, formatWhen } from "../format";

interface ForecastSliderProps {
  hour: number;
  hours: string[];
  departure: string;
  onChange: (hour: number) => void;
}

export function ForecastSlider({ hour, hours, departure, onChange }: ForecastSliderProps) {
  const max = Math.max(0, hours.length - 1);
  const departHour = hours.length ? closestHour(hours, departure) : 0;
  const mark = max === 0 ? 0 : (departHour / max) * 100;

  return (
    <div className="slider">
      <div className="slider-top">
        <span>Corridor forecast</span>
        <strong>{hours[hour] ? formatWhen(hours[hour]) : "Now"}</strong>
      </div>
      <div className="slider-track">
        <input
          type="range"
          min={0}
          max={max}
          step={1}
          value={Math.min(hour, max)}
          aria-label="Forecast hour from now"
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <span className="depart-mark" style={{ left: `${mark}%` }}>
          Depart
        </span>
      </div>
      <div className="slider-scale">
        <span>0h</span>
        <span>12h</span>
        <span>24h</span>
        <span>36h</span>
        <span>48h</span>
      </div>
      <p>Checkpoints use the truck&apos;s arrival time. This slider is the corridor at each hour from now.</p>
    </div>
  );
}
