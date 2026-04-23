import React, { useState, useRef } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Tooltip,
  Polyline,
  useMap,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Unit conversion helpers (imperial toggle)
const toDistance = (km: number | null, imp: boolean) =>
  km == null ? null : imp ? +(km * 0.621371).toFixed(2) : km;
const toFuel = (L_: number | null, imp: boolean) =>
  L_ == null ? null : imp ? +(L_ * 0.264172).toFixed(2) : L_;
const toWeight = (kg: number | null, imp: boolean) =>
  kg == null ? null : imp ? +(kg * 2.20462).toFixed(1) : kg;
const toEff = (fuelL: number, distKm: number, imp: boolean) =>
  imp
    ? +((235.214 / ((fuelL / distKm) * 100)).toFixed(1))
    : +((fuelL / distKm) * 100).toFixed(1);

// Fix for default marker icons in leaflet
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.3.1/images/marker-icon-2x.png',
  iconUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.3.1/images/marker-shadow.png',
});

// Custom DivIcon with stop number label and hover highlighting
const createMarkerIcon = (index: number, total: number, isHovered: boolean) => {
  const isStart = index === 0;
  const isEnd = index === total - 1;
  const color = isStart ? '#3b82f6' : isEnd ? '#ef4444' : '#f97316';
  const label = isStart ? 'S' : isEnd ? 'E' : String(index);
  const size = isHovered ? 38 : 30;
  return new L.DivIcon({
    html: `<div style="width:${size}px;height:${size}px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:${color};display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,0.3);border:2px solid white;${isHovered ? `outline:3px solid ${color};outline-offset:2px;` : ''}"><span style="transform:rotate(45deg);color:white;font-weight:bold;font-size:${isHovered ? 13 : 11}px;font-family:sans-serif;">${label}</span></div>`,
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size],
  });
};

const MapController = ({ startCoords, endCoords, route }: any) => {
  const map = useMap();
  React.useEffect(() => {
    if (route && route.length > 0) {
      map.fitBounds(L.latLngBounds(route), { padding: [50, 50] });
    } else if (startCoords && endCoords) {
      map.fitBounds(
        L.latLngBounds(
          [startCoords.lat, startCoords.lng],
          [endCoords.lat, endCoords.lng]
        ),
        { padding: [50, 50] }
      );
    }
  }, [map, route, startCoords, endCoords]);
  return null;
};

const InfoTip = ({ text }: { text: string }) => {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  return (
    <span className="relative inline-flex items-center ml-1" ref={ref}>
      <button
        type="button"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        className="w-3.5 h-3.5 rounded-full bg-blue-200 text-blue-800 text-[9px] font-bold leading-none flex items-center justify-center hover:bg-blue-300 transition-colors"
        aria-label="More info"
      >
        i
      </button>
      {visible && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-52 bg-gray-900 text-white text-[11px] leading-snug rounded-lg px-3 py-2 z-50 shadow-lg pointer-events-none">
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </span>
      )}
    </span>
  );
};

const Legend = ({ showOriginalRoute }: { showOriginalRoute: boolean }) => (
  <div className="absolute bottom-5 right-5 bg-white p-4 rounded-lg shadow-lg z-[1000] text-sm text-black">
    <h4 className="font-semibold mb-2">Legend</h4>
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="w-4 h-4 bg-blue-500 rounded-full" />
        <span>Start</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-4 h-4 bg-red-500 rounded-full" />
        <span>End</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-4 h-4 bg-orange-400 rounded-full" />
        <span>Intermediate Stop</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-4 h-1 bg-blue-500" />
        <span>Optimized Route</span>
      </div>
      {showOriginalRoute && (
        <div className="flex items-center gap-2">
          <svg width="16" height="4" viewBox="0 0 16 4">
            <line x1="0" y1="2" x2="16" y2="2" stroke="#ef4444" strokeWidth="2" strokeDasharray="4,3" />
          </svg>
          <span>Original Route</span>
        </div>
      )}
    </div>
  </div>
);

const ZoomControls = () => {
  const map = useMap();
  return (
    <div className="absolute left-5 bottom-20 flex flex-col gap-2 z-[1000] text-black">
      <button
        onClick={() => map.zoomIn()}
        className="bg-white rounded-lg p-2 shadow-lg hover:bg-gray-50"
        aria-label="Zoom in"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
      </button>
      <button
        onClick={() => map.zoomOut()}
        className="bg-white rounded-lg p-2 shadow-lg hover:bg-gray-50"
        aria-label="Zoom out"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
        </svg>
      </button>
    </div>
  );
};

const AnalyticsPanel = ({ isOpen, onClose, metrics, formData, imperial, setImperial }: any) => {
  const [exportOpen, setExportOpen] = useState(false);
  const [equivTab, setEquivTab] = useState<'original' | 'optimized' | 'yearly'>('optimized');

  const distUnit   = imperial ? 'mi'  : 'km';
  const fuelUnit   = imperial ? 'gal' : 'L';
  const weightUnit = imperial ? 'lbs' : 'kg';
  const effLabel   = imperial ? 'MPG' : 'L/100km';

  const hasData = metrics && (metrics.distanceKm != null || metrics.fuelLiters != null);
  const hasOriginal = metrics && metrics.originalDistanceKm != null;

  // Raw metric savings (always in SI for computation)
  const fuelSavedRaw =
    hasOriginal && metrics.fuelLiters != null
      ? Math.round((metrics.originalFuelLiters - metrics.fuelLiters) * 100) / 100
      : null;
  const co2SavedRaw =
    hasOriginal && metrics.co2Kg != null
      ? Math.round((metrics.originalCo2Kg - metrics.co2Kg) * 100) / 100
      : null;
  const distanceSavedRaw =
    hasOriginal && metrics.distanceKm != null
      ? Math.round((metrics.originalDistanceKm - metrics.distanceKm) * 100) / 100
      : null;

  // Converted display values
  const fuelSaved     = toFuel(fuelSavedRaw, imperial);
  const co2Saved      = toWeight(co2SavedRaw, imperial);
  const distanceSaved = toDistance(distanceSavedRaw, imperial);
  const dispDistKm    = toDistance(metrics?.distanceKm, imperial);
  const dispOrigDistKm= toDistance(metrics?.originalDistanceKm, imperial);
  const dispFuelL     = toFuel(metrics?.fuelLiters, imperial);
  const dispOrigFuelL = toFuel(metrics?.originalFuelLiters, imperial);
  const dispCo2Kg     = toWeight(metrics?.co2Kg, imperial);
  const dispOrigCo2Kg = toWeight(metrics?.originalCo2Kg, imperial);

  const fuelSavedPct =
    hasOriginal && metrics.originalFuelLiters > 0
      ? (((metrics.originalFuelLiters - metrics.fuelLiters) / metrics.originalFuelLiters) * 100).toFixed(1)
      : null;
  const timeDeltaMin =
    hasOriginal && metrics.durationMin != null && metrics.originalDurationMin != null
      ? Math.round((metrics.durationMin - metrics.originalDurationMin) * 10) / 10
      : null;

  const formatDuration = (min: number | null) => {
    if (min == null) return '—';
    if (min >= 60) return `${Math.floor(min / 60)}h ${Math.round(min % 60)}m`;
    return `${Math.round(min)}m`;
  };

  const buildGoogleMapsUrl = (stops: any[]) => {
    if (!stops || stops.length < 2) return null;
    const origin = `${stops[0].coords.lat},${stops[0].coords.lng}`;
    const dest = `${stops[stops.length - 1].coords.lat},${stops[stops.length - 1].coords.lng}`;
    const mids = stops.slice(1, -1);
    const waypointStr = mids.map((s: any) => `${s.coords.lat},${s.coords.lng}`).join('|');
    return `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${dest}${waypointStr ? `&waypoints=${encodeURIComponent(waypointStr)}` : ''}&travelmode=driving`;
  };

  const handleExport = () => {
    const googleMapsUrl = buildGoogleMapsUrl(formData.stops);
    const reportData = {
      routeInfo: {
        vehicleNumber: formData.vehicleNumber,
        startLocation: formData.stops[0]?.location,
        endLocation: formData.stops[formData.stops.length - 1]?.location,
        date: new Date().toLocaleDateString(),
        googleMapsUrl,
      },
      stops: formData.stops.map((stop: any, idx: number) => ({
        stopNumber: idx + 1,
        location: stop.location,
        coords: stop.coords,
        weightKg: stop.weightKg || 0,
      })),
      original: {
        distanceKm: metrics?.originalDistanceKm,
        durationMin: metrics?.originalDurationMin,
        fuelLiters: metrics?.originalFuelLiters,
        co2Kg: metrics?.originalCo2Kg,
      },
      optimized: {
        distanceKm: metrics?.distanceKm,
        durationMin: metrics?.durationMin,
        fuelLiters: metrics?.fuelLiters,
        co2Kg: metrics?.co2Kg,
      },
      savings: {
        fuelLiters: fuelSavedRaw,
        co2Kg: co2SavedRaw,
        distanceKm: distanceSavedRaw,
        fuelPct: fuelSavedPct,
      },
    };
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const vehicle = formData.vehicleNumber ? `${formData.vehicleNumber}-` : '';
    link.download = `route-report-${vehicle}${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleExportCsv = () => {
    const vehicle = formData.vehicleNumber ? `${formData.vehicleNumber}-` : '';
    const date = new Date().toISOString().split('T')[0];
    const rows = [
      ['Stop #', 'Label', 'Location', 'Lat', 'Lng', 'Weight (kg)'],
      ...formData.stops.map((s: any, i: number) => {
        const total = formData.stops.length;
        const label = i === 0 ? 'Start' : i === total - 1 ? 'End' : `Stop ${i}`;
        return [i + 1, label, `"${s.location}"`, s.coords?.lat ?? '', s.coords?.lng ?? '', s.weightKg || 0];
      }),
    ];
    if (metrics) {
      rows.push([]);
      rows.push(['Metric', 'Original', 'Optimized', 'Saved']);
      rows.push(['Distance (km)', metrics.originalDistanceKm ?? '—', metrics.distanceKm ?? '—', distanceSavedRaw ?? '—']);
      rows.push(['Duration (min)', metrics.originalDurationMin ?? '—', metrics.durationMin ?? '—', '']);
      rows.push(['Fuel (L)', metrics.originalFuelLiters ?? '—', metrics.fuelLiters ?? '—', fuelSavedRaw ?? '—']);
      rows.push(['CO2 (kg)', metrics.originalCo2Kg ?? '—', metrics.co2Kg ?? '—', co2SavedRaw ?? '—']);
    }
    const csv = rows.map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `route-report-${vehicle}${date}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleExportPdf = () => {
    const vehicle = formData.vehicleNumber || 'Route';
    const date = new Date().toLocaleDateString();
    const googleMapsUrl = buildGoogleMapsUrl(formData.stops);
    const stopsHtml = formData.stops
      .map((s: any, i: number) => {
        const total = formData.stops.length;
        const label = i === 0 ? 'Start' : i === total - 1 ? 'End' : `Stop ${i}`;
        const weight = s.weightKg
          ? `<span style="color:#034626;font-size:11px;"> · ${s.weightKg} kg pickup</span>`
          : '';
        return `<tr><td style="padding:6px 8px;color:#888;font-size:12px;">${label}</td><td style="padding:6px 8px;font-size:13px;">${s.location}${weight}</td></tr>`;
      })
      .join('');
    const metricsHtml = metrics
      ? `<table style="width:100%;border-collapse:collapse;margin-top:16px;">
        <thead><tr style="background:#f3f4f6;">
          <th style="padding:8px;text-align:left;font-size:12px;color:#555;">Metric</th>
          <th style="padding:8px;text-align:right;font-size:12px;color:#555;">Original</th>
          <th style="padding:8px;text-align:right;font-size:12px;color:#034626;">Optimized</th>
          <th style="padding:8px;text-align:right;font-size:12px;color:#16a34a;">Saved</th>
        </tr></thead>
        <tbody>
          <tr><td style="padding:6px 8px;font-size:13px;">Distance</td><td style="text-align:right;padding:6px 8px;">${metrics.originalDistanceKm ?? '—'} km</td><td style="text-align:right;padding:6px 8px;color:#034626;">${metrics.distanceKm ?? '—'} km</td><td style="text-align:right;padding:6px 8px;color:#16a34a;">${distanceSavedRaw != null ? `${distanceSavedRaw} km` : '—'}</td></tr>
          <tr style="background:#f9fafb;"><td style="padding:6px 8px;font-size:13px;">Duration</td><td style="text-align:right;padding:6px 8px;">${metrics.originalDurationMin != null ? formatDuration(metrics.originalDurationMin) : '—'}</td><td style="text-align:right;padding:6px 8px;color:#034626;">${metrics.durationMin != null ? formatDuration(metrics.durationMin) : '—'}</td><td style="text-align:right;padding:6px 8px;color:#16a34a;">—</td></tr>
          <tr><td style="padding:6px 8px;font-size:13px;">Fuel</td><td style="text-align:right;padding:6px 8px;">${metrics.originalFuelLiters ?? '—'} L</td><td style="text-align:right;padding:6px 8px;color:#034626;">${metrics.fuelLiters ?? '—'} L</td><td style="text-align:right;padding:6px 8px;color:#16a34a;">${fuelSavedRaw != null ? `${fuelSavedRaw} L` : '—'}</td></tr>
          <tr style="background:#f9fafb;"><td style="padding:6px 8px;font-size:13px;">CO₂</td><td style="text-align:right;padding:6px 8px;">${metrics.originalCo2Kg ?? '—'} kg</td><td style="text-align:right;padding:6px 8px;color:#034626;">${metrics.co2Kg ?? '—'} kg</td><td style="text-align:right;padding:6px 8px;color:#16a34a;">${co2SavedRaw != null ? `${co2SavedRaw} kg` : '—'}</td></tr>
        </tbody>
      </table>`
      : '';
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Route Report - ${vehicle}</title>
      <style>body{font-family:sans-serif;max-width:720px;margin:40px auto;color:#111;} h1{color:#034626;} table{width:100%;border-collapse:collapse;} @media print{body{margin:20px;}}</style>
      </head><body>
      <h1>Route Report</h1>
      <p style="color:#555;font-size:13px;">Vehicle: <strong>${vehicle}</strong> &nbsp;·&nbsp; Date: <strong>${date}</strong></p>
      ${googleMapsUrl ? `<p style="font-size:12px;"><a href="${googleMapsUrl}" style="color:#034626;">Open in Google Maps</a></p>` : ''}
      <h2 style="font-size:15px;margin-top:24px;border-bottom:1px solid #e5e7eb;padding-bottom:6px;">Stop Order</h2>
      <table><tbody>${stopsHtml}</tbody></table>
      <h2 style="font-size:15px;margin-top:24px;border-bottom:1px solid #e5e7eb;padding-bottom:6px;">Route Metrics</h2>
      ${metricsHtml}
      </body></html>`;
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); }, 300);
  };

  return (
    <div
      className={`fixed right-0 top-0 h-full w-96 bg-white shadow-lg transform transition-transform duration-300 ease-in-out z-[1001] flex flex-col ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold text-black">Route Analytics</h2>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-gray-400">km</span>
              <button
                onClick={() => setImperial((v: boolean) => !v)}
                className={`relative w-9 h-5 rounded-full transition-colors duration-200 ${imperial ? 'bg-[#034626]' : 'bg-gray-300'}`}
                aria-label="Toggle imperial units"
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${imperial ? 'translate-x-4' : 'translate-x-0'}`}
                />
              </button>
              <span className="text-xs text-gray-400">mi</span>
            </div>
            <button onClick={onClose} className="p-2">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {!hasData ? (
          <p className="text-gray-500 text-sm">No analytics data available.</p>
        ) : (
          <div className="space-y-5 text-black">
            {/* Savings Summary */}
            {hasOriginal && fuelSaved != null && (
              <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-5 rounded-xl border border-green-100">
                <h3 className="text-lg font-semibold text-green-800 mb-3">Optimization Savings</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white bg-opacity-60 rounded-lg p-3">
                    <p className="text-xs text-green-600 mb-0.5">Fuel saved</p>
                    <p className="text-xl font-bold text-green-700">{fuelSaved} {fuelUnit}</p>
                    {fuelSavedPct && <p className="text-xs text-green-500">{fuelSavedPct}% less</p>}
                  </div>
                  <div className="bg-white bg-opacity-60 rounded-lg p-3">
                    <p className="text-xs text-green-600 mb-0.5">CO₂ saved</p>
                    <p className="text-xl font-bold text-green-700">{co2Saved} {weightUnit}</p>
                  </div>
                </div>
                {distanceSaved != null && (
                  <div className="mt-3 bg-white bg-opacity-60 rounded-lg p-3">
                    <p className="text-xs text-green-600 mb-0.5">Distance saved</p>
                    <p className="text-xl font-bold text-green-700">{distanceSaved} {distUnit}</p>
                  </div>
                )}
                {fuelSavedPct && metrics.originalFuelLiters > 0 && (
                  <div className="mt-3">
                    <div className="flex justify-between text-xs text-green-700 mb-2">
                      <span>Fuel comparison</span>
                      <span>{fuelSavedPct}% reduction</span>
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500 w-16 shrink-0">Original</span>
                        <div className="flex-1 bg-gray-200 rounded-full h-2.5">
                          <div className="bg-gray-400 h-2.5 rounded-full w-full" />
                        </div>
                        <span className="text-xs font-medium text-gray-600 w-14 text-right shrink-0">{dispOrigFuelL} {fuelUnit}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-green-700 w-16 shrink-0">Optimized</span>
                        <div className="flex-1 bg-green-100 rounded-full h-2.5">
                          <div
                            className="bg-green-500 h-2.5 rounded-full transition-all duration-500"
                            style={{ width: `${(metrics.fuelLiters / metrics.originalFuelLiters) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium text-green-700 w-14 text-right shrink-0">{dispFuelL} {fuelUnit}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Distance */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-semibold mb-3">Distance</h4>
              <div className="grid grid-cols-2 gap-4">
                {hasOriginal && (
                  <div>
                    <p className="text-xs text-gray-500">Original</p>
                    <p className="text-lg font-medium">{dispOrigDistKm} {distUnit}</p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-[#034626]">Optimized</p>
                  <p className="text-lg font-medium text-[#034626]">{dispDistKm} {distUnit}</p>
                </div>
              </div>
            </div>

            {/* Duration */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-semibold mb-3">Duration</h4>
              <div className="grid grid-cols-2 gap-4">
                {hasOriginal && (
                  <div>
                    <p className="text-xs text-gray-500">Original</p>
                    <p className="text-lg font-medium">{formatDuration(metrics.originalDurationMin)}</p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-[#034626]">Optimized</p>
                  <p className="text-lg font-medium text-[#034626]">{formatDuration(metrics.durationMin)}</p>
                  {timeDeltaMin != null && timeDeltaMin !== 0 && (
                    <p className="text-xs mt-0.5 font-medium text-blue-600">
                      {timeDeltaMin < 0
                        ? `↓ ${formatDuration(Math.abs(timeDeltaMin))} faster`
                        : `↑ ${formatDuration(timeDeltaMin)} slower`}
                    </p>
                  )}
                  {timeDeltaMin === 0 && hasOriginal && (
                    <p className="text-xs mt-0.5 text-gray-400">no change</p>
                  )}
                </div>
              </div>
            </div>

            {/* Fuel */}
            {metrics.fuelLiters != null && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-semibold mb-3">Fuel Consumption</h4>
                <div className="grid grid-cols-2 gap-4">
                  {hasOriginal && (
                    <div>
                      <p className="text-xs text-gray-500">Original</p>
                      <p className="text-lg font-medium">{dispOrigFuelL} {fuelUnit}</p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-[#034626]">Optimized</p>
                    <p className="text-lg font-medium text-[#034626]">{dispFuelL} {fuelUnit}</p>
                    {fuelSaved != null && fuelSavedRaw! > 0 && (
                      <p className="text-xs mt-0.5 text-blue-600 font-medium">
                        ↓ {fuelSaved} {fuelUnit} less{fuelSavedPct ? ` (${fuelSavedPct}%)` : ''}
                      </p>
                    )}
                    {fuelSavedRaw === 0 && hasOriginal && (
                      <p className="text-xs mt-0.5 text-gray-400">no change</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* CO2 */}
            {metrics.co2Kg != null && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-semibold mb-3">CO₂ Emissions</h4>
                <div className="grid grid-cols-2 gap-4">
                  {hasOriginal && (
                    <div>
                      <p className="text-xs text-gray-500">Original</p>
                      <p className="text-lg font-medium">{dispOrigCo2Kg} {weightUnit}</p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-[#034626]">Optimized</p>
                    <p className="text-lg font-medium text-[#034626]">{dispCo2Kg} {weightUnit}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Impact Equivalents — 3 tabs */}
            {(fuelSavedRaw != null || co2SavedRaw != null || hasOriginal) && (
              <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                <h3 className="text-sm font-semibold text-blue-800 mb-3">Impact Equivalents</h3>
                {/* Tab bar */}
                <div className="flex gap-1 mb-3">
                  {(['original', 'optimized', 'yearly'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setEquivTab(tab)}
                      className={`flex-1 text-xs py-1 px-1 rounded-full font-medium transition-colors ${
                        equivTab === tab
                          ? 'bg-[#034626] text-white'
                          : 'bg-white text-gray-500 hover:bg-gray-50'
                      }`}
                    >
                      {tab === 'original' ? 'Original' : tab === 'optimized' ? 'Optimized' : 'Per Year'}
                    </button>
                  ))}
                </div>

                <div className="space-y-2 text-sm">
                  {equivTab === 'original' && hasOriginal && (
                    <>
                      {metrics.originalCo2Kg != null && metrics.originalCo2Kg > 0 && (
                        <>
                          <div className="flex justify-between items-center">
                            <span className="text-blue-700 text-xs flex items-center">
                              Trees to offset CO₂
                              <InfoTip text={`${metrics.originalCo2Kg} kg CO₂ emitted ÷ 21 kg/tree/yr = ${(Math.round(metrics.originalCo2Kg / 21 * 10) / 10).toFixed(1)} trees needed to offset.`} />
                            </span>
                            <span className="font-semibold text-blue-900 text-sm">{(Math.round(metrics.originalCo2Kg / 21 * 10) / 10).toFixed(1)}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-blue-700 text-xs flex items-center">
                              Equivalent car {distUnit} driven
                              <InfoTip text={`${metrics.originalCo2Kg} kg CO₂ ÷ 0.12 kg CO₂/km = ${Math.round(metrics.originalCo2Kg / 0.12)} km equivalent.`} />
                            </span>
                            <span className="font-semibold text-blue-900 text-sm">{toDistance(Math.round(metrics.originalCo2Kg / 0.12), imperial)} {distUnit}</span>
                          </div>
                        </>
                      )}
                      {metrics.originalFuelLiters != null && (
                        <div className="flex justify-between items-center">
                          <span className="text-blue-700 text-xs flex items-center">
                            Est. fuel cost
                            <InfoTip text={`${metrics.originalFuelLiters} L × $1.50/L = $${(Math.round(metrics.originalFuelLiters * 1.5 * 100) / 100).toFixed(2)}.`} />
                          </span>
                          <span className="font-semibold text-blue-900 text-sm">${(Math.round(metrics.originalFuelLiters * 1.5 * 100) / 100).toFixed(2)}</span>
                        </div>
                      )}
                      {metrics.originalFuelLiters != null && metrics.originalDistanceKm != null && metrics.originalDistanceKm > 0 && (
                        <div className="flex justify-between items-center">
                          <span className="text-blue-700 text-xs flex items-center">
                            Original fuel efficiency
                            <InfoTip text={`Original route: ${toEff(metrics.originalFuelLiters, metrics.originalDistanceKm, imperial)} ${effLabel}.`} />
                          </span>
                          <span className="font-semibold text-blue-900 text-sm">{toEff(metrics.originalFuelLiters, metrics.originalDistanceKm, imperial)} {effLabel}</span>
                        </div>
                      )}
                    </>
                  )}

                  {equivTab === 'optimized' && (
                    <>
                      {co2SavedRaw != null && co2SavedRaw > 0 && (
                        <>
                          <div className="flex justify-between items-center">
                            <span className="text-blue-700 text-xs flex items-center">
                              Trees absorbing CO₂ for 1 year
                              <InfoTip text={`${co2SavedRaw} kg CO₂ saved ÷ 21 kg/tree/yr = ${(Math.round(co2SavedRaw / 21 * 10) / 10).toFixed(1)} trees. Source: US Forest Service.`} />
                            </span>
                            <span className="font-semibold text-blue-900 text-sm">{(Math.round(co2SavedRaw / 21 * 10) / 10).toFixed(1)}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-blue-700 text-xs flex items-center">
                              Equivalent car {distUnit} avoided
                              <InfoTip text={`${co2SavedRaw} kg CO₂ saved ÷ 0.12 kg CO₂/km = ${Math.round(co2SavedRaw / 0.12)} km avoided. Based on avg passenger car emitting 120 g CO₂/km.`} />
                            </span>
                            <span className="font-semibold text-blue-900 text-sm">{toDistance(Math.round(co2SavedRaw / 0.12), imperial)} {distUnit}</span>
                          </div>
                        </>
                      )}
                      {fuelSavedRaw != null && fuelSavedRaw > 0 && (
                        <div className="flex justify-between items-center">
                          <span className="text-blue-700 text-xs flex items-center">
                            Est. fuel cost saved
                            <InfoTip text={`${fuelSavedRaw} L saved × $1.50/L = $${(Math.round(fuelSavedRaw * 1.5 * 100) / 100).toFixed(2)}. Uses US average diesel price of ~$1.50/L.`} />
                          </span>
                          <span className="font-semibold text-blue-900 text-sm">${(Math.round(fuelSavedRaw * 1.5 * 100) / 100).toFixed(2)}</span>
                        </div>
                      )}
                      {metrics.fuelLiters != null && metrics.distanceKm != null && metrics.distanceKm > 0 && (
                        <div className="flex justify-between items-center">
                          <span className="text-blue-700 text-xs flex items-center">
                            Optimized fuel efficiency
                            <InfoTip text={`${metrics.fuelLiters} L ÷ ${metrics.distanceKm} km × 100 = ${toEff(metrics.fuelLiters, metrics.distanceKm, imperial)} ${effLabel}.`} />
                          </span>
                          <span className="font-semibold text-blue-900 text-sm">{toEff(metrics.fuelLiters, metrics.distanceKm, imperial)} {effLabel}</span>
                        </div>
                      )}
                    </>
                  )}

                  {equivTab === 'yearly' && (
                    <>
                      {fuelSavedRaw != null && fuelSavedRaw > 0 ? (
                        <>
                          <div className="flex justify-between items-center">
                            <span className="text-blue-700 text-xs">Annual fuel saved (260 days)</span>
                            <span className="font-semibold text-blue-900 text-sm">
                              {toFuel(Math.round(fuelSavedRaw * 260 * 100) / 100, imperial)} {fuelUnit}
                            </span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-blue-700 text-xs">Annual cost saved</span>
                            <span className="font-semibold text-blue-900 text-sm">${(Math.round(fuelSavedRaw * 260 * 1.5 * 100) / 100).toFixed(2)}</span>
                          </div>
                        </>
                      ) : null}
                      {co2SavedRaw != null && co2SavedRaw > 0 ? (
                        <>
                          <div className="flex justify-between items-center">
                            <span className="text-blue-700 text-xs">Annual CO₂ saved</span>
                            <span className="font-semibold text-blue-900 text-sm">
                              {toWeight(Math.round(co2SavedRaw * 260 * 100) / 100, imperial)} {weightUnit}
                            </span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-blue-700 text-xs">Annual trees equivalent</span>
                            <span className="font-semibold text-blue-900 text-sm">{(Math.round(co2SavedRaw * 260 / 21 * 10) / 10).toFixed(1)}</span>
                          </div>
                        </>
                      ) : null}
                      {(fuelSavedRaw == null || fuelSavedRaw <= 0) && (co2SavedRaw == null || co2SavedRaw <= 0) && (
                        <p className="text-xs text-gray-500">No savings to project annually.</p>
                      )}
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Open in Google Maps */}
            {formData.stops?.length >= 2 && (
              <button
                onClick={() => {
                  const url = buildGoogleMapsUrl(formData.stops);
                  if (url) window.open(url, '_blank');
                }}
                className="w-full border border-[#034626] text-[#034626] py-2 px-4 rounded-lg hover:bg-green-50 transition-colors text-sm font-medium"
              >
                Open in Google Maps
              </button>
            )}

            {/* Export */}
            <div className="relative">
              <button
                onClick={() => setExportOpen((o) => !o)}
                className="w-full bg-[#034626] text-white py-2 px-4 rounded-lg hover:bg-[#023219] transition-colors flex items-center justify-between"
              >
                <span>Export Report</span>
                <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 transition-transform ${exportOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {exportOpen && (
                <div className="absolute bottom-full mb-1 left-0 w-full bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden z-10">
                  <button
                    onClick={() => { handleExport(); setExportOpen(false); }}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 flex items-center gap-3"
                  >
                    <span className="text-gray-400 font-mono text-xs w-8">JSON</span>
                    <span className="text-gray-700">Full data export</span>
                  </button>
                  <button
                    onClick={() => { handleExportCsv(); setExportOpen(false); }}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 flex items-center gap-3 border-t border-gray-100"
                  >
                    <span className="text-gray-400 font-mono text-xs w-8">CSV</span>
                    <span className="text-gray-700">Stops + metrics (Excel)</span>
                  </button>
                  <button
                    onClick={() => { handleExportPdf(); setExportOpen(false); }}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 flex items-center gap-3 border-t border-gray-100"
                  >
                    <span className="text-gray-400 font-mono text-xs w-8">PDF</span>
                    <span className="text-gray-700">Printable route report</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const MapView = ({
  formData,
  route,
  startCoords,
  endCoords,
  onBack,
  metrics,
  originalRoute,
  originalStops,
}: any) => {
  const [isAnalyticsPanelOpen, setIsAnalyticsPanelOpen] = useState(true);
  const [isStopsPanelOpen, setIsStopsPanelOpen] = useState(false);
  const [hoveredStopIndex, setHoveredStopIndex] = useState<number | null>(null);
  const [imperial, setImperial] = useState(false);
  const [showOriginalRoute, setShowOriginalRoute] = useState(false);

  const panelOpen = isAnalyticsPanelOpen || isStopsPanelOpen;
  const panelWidth = '384px';

  const distUnit = imperial ? 'mi' : 'km';
  const fuelUnit = imperial ? 'gal' : 'L';

  return (
    <div className="fixed inset-0 flex">
      <div className="absolute inset-0">
        <MapContainer
          center={[20.5937, 78.9629]}
          zoom={5}
          zoomControl={false}
          style={{ width: '100%', height: '100%' }}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CartoDB</a>'
          />
          <MapController startCoords={startCoords} endCoords={endCoords} route={route} />

          {/* Stop markers with DivIcon labels and hover highlighting */}
          {formData.stops.map(
            (
              stop: { location: string; coords: { lat: number; lng: number }; weightKg?: number },
              index: number
            ) => {
              if (!stop.coords) return null;
              const total = formData.stops.length;
              const isStart = index === 0;
              const isEnd = index === total - 1;
              const weightValue = stop.weightKg ? Number(stop.weightKg) : 0;
              const isHovered = hoveredStopIndex === index;

              return (
                <Marker
                  key={`${index}-${isHovered}`}
                  position={[stop.coords.lat, stop.coords.lng]}
                  icon={createMarkerIcon(index, total, isHovered)}
                >
                  <Tooltip direction="top" offset={[0, -35]} opacity={0.95}>
                    <div className="text-center font-sans tracking-wide">
                      <div className="font-semibold text-gray-800">
                        {isStart ? 'Start' : isEnd ? 'End' : `Stop ${index}`}
                      </div>
                      <div className={`text-xs mt-0.5 ${weightValue > 0 ? 'text-[#034626] font-extrabold' : 'text-gray-400'}`}>
                        {weightValue} kg pickup
                      </div>
                    </div>
                  </Tooltip>
                  <Popup>
                    <div className="font-sans w-56 -m-1">
                      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-100">
                        <div className={`w-3 h-3 rounded-full ${isStart ? 'bg-blue-500' : isEnd ? 'bg-red-500' : 'bg-orange-400'}`} />
                        <span className="font-bold text-gray-800 text-sm">
                          {isStart ? 'Start Location' : isEnd ? 'Final Destination' : `Stop ${index}`}
                        </span>
                      </div>
                      <p className="text-[13px] text-gray-600 mb-3 leading-snug">{stop.location}</p>
                      {weightValue > 0 && (
                        <div className="bg-green-50 border border-green-100 rounded-md p-2 flex justify-between items-center">
                          <span className="text-[11px] text-green-800 font-semibold tracking-wide uppercase">Pickup Weight</span>
                          <span className="text-sm text-green-900 font-bold">{weightValue} kg</span>
                        </div>
                      )}
                    </div>
                  </Popup>
                </Marker>
              );
            }
          )}

          {/* Optimized route polyline */}
          {route && <Polyline positions={route} color="blue" weight={4} />}

          {/* Original route overlay (dashed red) */}
          {showOriginalRoute && originalRoute && originalRoute.length > 0 && (
            <Polyline positions={originalRoute} color="#ef4444" weight={3} dashArray="8,6" opacity={0.7} />
          )}

          <ZoomControls />
        </MapContainer>
      </div>

      {/* Top navigation bar */}
      <div
        className="absolute top-0 p-4 z-[1000] flex justify-between items-start text-black transition-all duration-300 ease-in-out"
        style={{ left: 0, right: panelOpen ? panelWidth : '0px' }}
      >
        <div className="flex gap-2 items-center">
          {/* Back button — arrow icon only */}
          <button
            onClick={onBack}
            className="bg-white rounded-lg px-3 py-2 shadow-lg hover:bg-gray-50 flex items-center"
            aria-label="Back"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        </div>

        {/* Route metrics pills */}
        {metrics && (metrics.distanceKm != null || metrics.fuelLiters != null) && (() => {
          const fmtDur = (min: number) =>
            min >= 60
              ? `${Math.floor(min / 60)}h ${Math.round(min % 60)}m`
              : `${Math.round(min)}m`;
          const fuelSavedRaw =
            metrics.originalFuelLiters != null && metrics.fuelLiters != null
              ? Math.round((metrics.originalFuelLiters - metrics.fuelLiters) * 100) / 100
              : null;
          const co2SavedRaw =
            metrics.originalCo2Kg != null && metrics.co2Kg != null
              ? Math.round((metrics.originalCo2Kg - metrics.co2Kg) * 100) / 100
              : null;
          const fuelSavedPct =
            metrics.originalFuelLiters != null && metrics.originalFuelLiters > 0 && fuelSavedRaw != null
              ? ((fuelSavedRaw / metrics.originalFuelLiters) * 100).toFixed(1)
              : null;
          const dispDist = toDistance(metrics.distanceKm, imperial);
          const dispFuel = toFuel(metrics.fuelLiters, imperial);
          const dispCo2  = toWeight(metrics.co2Kg, imperial);
          const dispFuelSaved = toFuel(fuelSavedRaw, imperial);
          const dispCo2Saved  = toWeight(co2SavedRaw, imperial);
          return (
            <div className="flex gap-2 flex-wrap justify-end">
              {metrics.distanceKm != null && (
                <div className="bg-white rounded-lg px-3 py-2 shadow-lg text-sm font-medium">
                  <span className="text-gray-500">Distance&nbsp;</span>
                  <span className="text-[#034626] font-bold">{dispDist} {distUnit}</span>
                </div>
              )}
              {metrics.durationMin != null && (
                <div className="bg-white rounded-lg px-3 py-2 shadow-lg text-sm font-medium">
                  <span className="text-gray-500">Duration&nbsp;</span>
                  <span className="text-[#034626] font-bold">{fmtDur(metrics.durationMin)}</span>
                </div>
              )}
              {metrics.fuelLiters != null && (
                <div className="bg-white rounded-lg px-3 py-2 shadow-lg text-sm font-medium">
                  <span className="text-gray-500">Fuel&nbsp;</span>
                  <span className="text-[#034626] font-bold">{dispFuel} {fuelUnit}</span>
                  {dispFuelSaved != null && fuelSavedRaw! > 0 && (
                    <span className="text-blue-600 text-xs ml-1">
                      ↓{dispFuelSaved} {fuelUnit}{fuelSavedPct ? ` (${fuelSavedPct}%)` : ''}
                    </span>
                  )}
                </div>
              )}
              {metrics.co2Kg != null && (
                <div className="bg-white rounded-lg px-3 py-2 shadow-lg text-sm font-medium">
                  <span className="text-gray-500">CO₂&nbsp;</span>
                  <span className="text-[#034626] font-bold">{dispCo2} kg</span>
                  {dispCo2Saved != null && co2SavedRaw! > 0 && (
                    <span className="text-blue-600 text-xs ml-1">↓{dispCo2Saved} kg</span>
                  )}
                </div>
              )}
            </div>
          );
        })()}
      </div>

      {/* Floating icon button stack — sits to the left of whichever panel is open */}
      <div
        className="fixed z-[1002] flex flex-col gap-2 transition-all duration-300 ease-in-out"
        style={{
          right: panelOpen ? panelWidth : '0px',
          top: '50%',
          transform: 'translateY(-50%)',
        }}
      >
        {/* Analytics icon button */}
        <button
          onClick={() => {
            setIsAnalyticsPanelOpen((o) => !o);
            setIsStopsPanelOpen(false);
          }}
          className={`p-3 rounded-l-xl shadow-lg transition-colors ${isAnalyticsPanelOpen ? 'bg-[#034626] text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
          aria-label="Analytics"
          title="Analytics"
        >
          {/* Bar chart icon */}
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </button>

        {/* Stops icon button */}
        <button
          onClick={() => {
            setIsStopsPanelOpen((o) => !o);
            setIsAnalyticsPanelOpen(false);
          }}
          className={`p-3 rounded-l-xl shadow-lg transition-colors ${isStopsPanelOpen ? 'bg-[#034626] text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
          aria-label="Stops"
          title="Stops"
        >
          {/* Ordered list icon */}
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
        </button>
      </div>

      {/* Stops list panel */}
      <div
        className={`fixed right-0 top-0 h-full w-96 bg-white shadow-lg transform transition-transform duration-300 ease-in-out z-[1001] flex flex-col ${isStopsPanelOpen ? 'translate-x-0' : 'translate-x-full'}`}
      >
        <div className="p-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-black">Stop Order</h2>
          <button onClick={() => setIsStopsPanelOpen(false)} className="p-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Original route toggle */}
        {originalRoute && originalRoute.length > 0 && originalStops && originalStops.length > 0 && (
          <div className="px-4 pt-3 pb-0">
            <button
              onClick={() => setShowOriginalRoute((v) => !v)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors border ${
                showOriginalRoute
                  ? 'bg-gray-100 border-gray-300 text-gray-700'
                  : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'
              }`}
            >
              <span>{showOriginalRoute ? 'Showing original order' : 'Show original route'}</span>
              <span className="flex items-center gap-1.5">
                <svg width="12" height="4" viewBox="0 0 12 4" className="shrink-0">
                  <line x1="0" y1="2" x2="12" y2="2" stroke={showOriginalRoute ? '#ef4444' : '#9ca3af'} strokeWidth="2" strokeDasharray="3,2" />
                </svg>
              </span>
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-4">
          {showOriginalRoute && originalStops && originalStops.length > 0 && (
            <p className="text-xs text-gray-400 mb-2 italic">Original unoptimized order</p>
          )}
          <div className="space-y-2">
            {(showOriginalRoute && originalStops && originalStops.length > 0 ? originalStops : formData.stops).map((stop: any, index: number) => {
              const displayList = showOriginalRoute && originalStops && originalStops.length > 0 ? originalStops : formData.stops;
              const total = displayList.length;
              const isStart = index === 0;
              const isEnd = index === total - 1;
              const weightValue = stop.weightKg ? Number(stop.weightKg) : 0;
              return (
                <div
                  key={index}
                  className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg cursor-default"
                  onMouseEnter={() => setHoveredStopIndex(index)}
                  onMouseLeave={() => setHoveredStopIndex(null)}
                >
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0 mt-0.5 ${isStart ? 'bg-blue-500' : isEnd ? 'bg-red-500' : 'bg-orange-400'}`}
                  >
                    {isStart ? 'S' : isEnd ? 'E' : index}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800 leading-snug">{stop.location}</p>
                    <p className={`text-xs mt-0.5 ${weightValue > 0 ? 'text-[#034626] font-semibold' : 'text-gray-400'}`}>
                      {weightValue} kg pickup
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <Legend showOriginalRoute={showOriginalRoute} />

      <AnalyticsPanel
        isOpen={isAnalyticsPanelOpen}
        onClose={() => setIsAnalyticsPanelOpen(false)}
        metrics={metrics}
        formData={formData}
        imperial={imperial}
        setImperial={setImperial}
      />
    </div>
  );
};

export default MapView;
