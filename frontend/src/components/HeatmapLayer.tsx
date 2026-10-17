import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import { HEAT_RGB } from "../colors";
import type { HeatPoint } from "../types";

interface HeatState {
  points: HeatPoint[];
  hour: number;
}

class CorridorHeat extends L.Layer {
  private mapRef: L.Map | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private frame = 0;

  constructor(private read: () => HeatState) {
    super();
  }

  override onAdd(map: L.Map): this {
    this.mapRef = map;
    if (!map.getPane("heat")) {
      const pane = map.createPane("heat");
      pane.style.zIndex = "250";
      pane.style.pointerEvents = "none";
    }
    const canvas = document.createElement("canvas");
    canvas.className = "heat-canvas";
    this.canvas = canvas;
    map.getPane("heat")?.appendChild(canvas);
    map.on("move zoom resize", this.scheduleDraw);
    this.scheduleDraw();
    return this;
  }

  override onRemove(map: L.Map): this {
    map.off("move zoom resize", this.scheduleDraw);
    cancelAnimationFrame(this.frame);
    this.canvas?.remove();
    this.canvas = null;
    this.mapRef = null;
    return this;
  }

  scheduleDraw = () => {
    cancelAnimationFrame(this.frame);
    this.frame = requestAnimationFrame(() => this.draw());
  };

  private draw() {
    const map = this.mapRef;
    const canvas = this.canvas;
    if (!map || !canvas) return;

    const size = map.getSize();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.floor(size.x * ratio));
    const height = Math.max(1, Math.floor(size.y * ratio));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      canvas.style.width = `${size.x}px`;
      canvas.style.height = `${size.y}px`;
    }

    const topLeft = map.containerPointToLayerPoint([0, 0]);
    L.DomUtil.setPosition(canvas, topLeft);

    const context = canvas.getContext("2d");
    if (!context) return;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, size.x, size.y);

    const { points, hour } = this.read();
    const zoom = map.getZoom();
    const radius = Math.min(88, Math.max(18, 16 * Math.pow(1.45, zoom - 5)));
    for (const point of points) {
      const projected = map.latLngToContainerPoint([point.lat, point.lon]);
      if (projected.x < -radius || projected.y < -radius || projected.x > size.x + radius || projected.y > size.y + radius) {
        continue;
      }
      const color = HEAT_RGB[point.risks[hour] ?? 0] ?? HEAT_RGB[0];
      const gradient = context.createRadialGradient(projected.x, projected.y, 0, projected.x, projected.y, radius);
      gradient.addColorStop(0, `rgba(${color},0.5)`);
      gradient.addColorStop(0.55, `rgba(${color},0.18)`);
      gradient.addColorStop(1, `rgba(${color},0)`);
      context.fillStyle = gradient;
      context.beginPath();
      context.arc(projected.x, projected.y, radius, 0, Math.PI * 2);
      context.fill();
    }
  }
}

export function HeatmapLayer({ points, hour }: HeatState) {
  const map = useMap();
  const state = useRef<HeatState>({ points, hour });
  const layerRef = useRef<CorridorHeat | null>(null);
  state.current = { points, hour };

  useEffect(() => {
    const layer = new CorridorHeat(() => state.current);
    layer.addTo(map);
    layerRef.current = layer;
    return () => {
      layer.remove();
      layerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    layerRef.current?.scheduleDraw();
  }, [points, hour]);

  return null;
}
