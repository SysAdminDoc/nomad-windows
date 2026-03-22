// NukeMap - Population Heatmap Overlay
window.NM = window.NM || {};

NM.Heatmap = {
  layer: null,
  visible: false,
  canvas: null,

  init(map) {
    this.map = map;
    // Create custom canvas overlay
    const HeatLayer = L.Layer.extend({
      onAdd(map) {
        this._map = map;
        this._canvas = L.DomUtil.create('canvas', 'pop-heatmap');
        this._canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;z-index:400;mix-blend-mode:screen';
        map.getPanes().overlayPane.appendChild(this._canvas);
        map.on('moveend zoomend resize', this._update, this);
        this._update();
      },
      onRemove(map) {
        L.DomUtil.remove(this._canvas);
        map.off('moveend zoomend resize', this._update, this);
      },
      _update() {
        const map = this._map;
        const size = map.getSize();
        const canvas = this._canvas;
        canvas.width = size.x;
        canvas.height = size.y;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, size.x, size.y);

        const bounds = map.getBounds();
        const zoom = map.getZoom();

        // Only show at certain zoom levels
        if (zoom < 3) return;

        // Draw population circles
        for (const city of NM.CITIES) {
          const pop = city[4];
          if (pop < 1000) continue;
          const lat = city[2], lng = city[3];
          if (!bounds.contains([lat, lng])) continue;

          const pt = map.latLngToContainerPoint([lat, lng]);
          const intensity = Math.min(1, Math.log10(pop) / 7.5);
          const baseRadius = Math.max(3, Math.min(80, Math.pow(pop, 0.25) * (zoom / 10)));

          const gradient = ctx.createRadialGradient(pt.x, pt.y, 0, pt.x, pt.y, baseRadius);
          gradient.addColorStop(0, `rgba(243, 139, 168, ${intensity * 0.6})`);
          gradient.addColorStop(0.4, `rgba(250, 179, 135, ${intensity * 0.3})`);
          gradient.addColorStop(1, 'rgba(250, 179, 135, 0)');

          ctx.beginPath();
          ctx.arc(pt.x, pt.y, baseRadius, 0, Math.PI * 2);
          ctx.fillStyle = gradient;
          ctx.fill();
        }

        // Position canvas
        const topLeft = map.containerPointToLayerPoint([0, 0]);
        L.DomUtil.setPosition(canvas, topLeft);
      }
    });

    this.layer = new HeatLayer();
  },

  toggle(map) {
    this.visible = !this.visible;
    if (this.visible) {
      this.layer.addTo(map);
    } else {
      map.removeLayer(this.layer);
    }
    return this.visible;
  }
};
