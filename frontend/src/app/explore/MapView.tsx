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

// Fix for default marker icons
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.3.1/images/marker-icon-2x.png',
  iconUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.3.1/images/marker-shadow.png',
});

/**
 * MapController adjusts the map view to fit the provided route or coordinates.
 *
 * Props:
 * - startCoords: Coordinates object for the start point (lat, lng)
 * - endCoords: Coordinates object for the end point (lat, lng)
 * - route: Array of lat/lng tuples representing the route
 *
 * Behavior:
 * - If a route is provided, fit the map to its bounds (showing the full path).
 * - Otherwise, fit the map to the bounds defined by the start and end coordinates.
 * - This component is a "headless" map component that uses the useMap hook.
 */
const MapController = ({ startCoords, endCoords, route }: any) => {
  const map = useMap();

  React.useEffect(() => {
    if (route && route.length > 0) {
      const bounds = L.latLngBounds(route);
      map.fitBounds(bounds, { padding: [50, 50] });
    } else if (startCoords && endCoords) {
      const bounds = L.latLngBounds(
        [startCoords.lat, startCoords.lng],
        [endCoords.lat, endCoords.lng]
      );
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [map, route, startCoords, endCoords]);

  return null;
};

/**
 * InfoTip renders a small ⓘ icon that reveals a tooltip on hover.
 */
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

/**
 * Legend displays a visual guide to map markers and route colors.
 *
 * UI Legend includes:
 * - Blue circle: Start point
 * - Red circle: End point
 * - Yellow circle: Intermediate stop
 * - Blue line: Route path
 */
const Legend = () => {
  return (
    <div className="absolute bottom-5 right-5 bg-white p-4 rounded-lg shadow-lg z-[1000] text-sm text-black">
      <h4 className="font-semibold mb-2">Legend</h4>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-blue-500 rounded-full"></div>
          <span>Start</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-red-500 rounded-full"></div>
          <span>End</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-orange-400 rounded-full"></div>
          <span>Intermediate Stop</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-1 bg-blue-500"></div>
          <span>Route</span>
        </div>
      </div>
    </div>
  );
};

/**
 * ZoomControls adds custom zoom in/out buttons to the map.
 *
 * Behavior:
 * - Zoom in: increases the map's zoom level
 * - Zoom out: decreases the map's zoom level
 *
 * Styling ensures visibility and hover feedback.
 */
const ZoomControls = () => {
  const map = useMap();

  return (
    <div className="absolute left-5 bottom-20 flex flex-col gap-2 z-[1000] text-black">
      <button
        onClick={() => map.zoomIn()}
        className="bg-white rounded-lg p-2 shadow-lg hover:bg-gray-50"
        aria-label="Zoom in"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 6v6m0 0v6m0-6h6m-6 0H6"
          />
        </svg>
      </button>
      <button
        onClick={() => map.zoomOut()}
        className="bg-white rounded-lg p-2 shadow-lg hover:bg-gray-50"
        aria-label="Zoom out"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M20 12H4"
          />
        </svg>
      </button>
    </div>
  );
};

/**
 * AnalyticsPanel displays real route analytics from the backend physics model,
 * showing before/after comparison of distance, duration, fuel, and CO2.
 *
 * Props:
 * - isOpen: Boolean indicating whether the panel is visible
 * - onClose: Function to close the panel
 * - metrics: RouteMetrics object with optimized and original values from backend
 * - formData: Object containing form submission data, such as stops
 */
const AnalyticsPanel = ({ isOpen, onClose, metrics, formData }: any) => {
  const [runData, setRunData] = useState<any>(null);
  const [runLoading, setRunLoading] = useState(false);

  const fetchRunData = async () => {
    if (runData) { setRunData(null); return; }
    setRunLoading(true);
    try {
      let backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
      if (!backendUrl.startsWith('http')) backendUrl = `https://${backendUrl}`;
      const res = await fetch(`${backendUrl}/run/${metrics.matrixRunId}`);
      if (res.ok) setRunData(await res.json());
    } finally {
      setRunLoading(false);
    }
  };

  const hasData =
    metrics && (metrics.distanceKm != null || metrics.fuelLiters != null);
  const hasOriginal = metrics && metrics.originalDistanceKm != null;

  const buildGoogleMapsUrl = (stops: any[]) => {
    if (!stops || stops.length < 2) return null;
    const origin = `${stops[0].coords.lat},${stops[0].coords.lng}`;
    const dest = `${stops[stops.length - 1].coords.lat},${stops[stops.length - 1].coords.lng}`;
    const mids = stops.slice(1, -1);
    const waypointStr = mids.map((s: any) => `${s.coords.lat},${s.coords.lng}`).join('|');
    return `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${dest}${waypointStr ? `&waypoints=${encodeURIComponent(waypointStr)}` : ''}&travelmode=driving`;
  };

  const fuelSaved =
    hasOriginal && metrics.fuelLiters != null
      ? Math.round((metrics.originalFuelLiters - metrics.fuelLiters) * 100) /
        100
      : null;
  const co2Saved =
    hasOriginal && metrics.co2Kg != null
      ? Math.round((metrics.originalCo2Kg - metrics.co2Kg) * 100) / 100
      : null;
  const distanceSaved =
    hasOriginal && metrics.distanceKm != null
      ? Math.round((metrics.originalDistanceKm - metrics.distanceKm) * 100) /
        100
      : null;
  const fuelSavedPct =
    hasOriginal && metrics.originalFuelLiters > 0
      ? (
          ((metrics.originalFuelLiters - metrics.fuelLiters) /
            metrics.originalFuelLiters) *
          100
        ).toFixed(1)
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

  // Export route report as downloadable JSON
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
        fuelLiters: fuelSaved,
        co2Kg: co2Saved,
        distanceKm: distanceSaved,
        fuelPct: fuelSavedPct,
      },
    };
    const blob = new Blob([JSON.stringify(reportData, null, 2)], {
      type: 'application/json',
    });
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

  return (
    <div
      className={`fixed right-0 top-0 h-full w-96 bg-white shadow-lg transform transition-transform duration-300 ease-in-out z-[1001] flex flex-col ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold text-black">Route Analytics</h2>
          <button onClick={onClose} className="p-2">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-6 w-6 text-black"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
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
                <h3 className="text-lg font-semibold text-green-800 mb-3">
                  Optimization Savings
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white bg-opacity-60 rounded-lg p-3">
                    <p className="text-xs text-green-600 mb-0.5">Fuel saved</p>
                    <p className="text-xl font-bold text-green-700">
                      {fuelSaved} L
                    </p>
                    {fuelSavedPct && (
                      <p className="text-xs text-green-500">
                        {fuelSavedPct}% less
                      </p>
                    )}
                  </div>
                  <div className="bg-white bg-opacity-60 rounded-lg p-3">
                    <p className="text-xs text-green-600 mb-0.5">CO₂ saved</p>
                    <p className="text-xl font-bold text-green-700">
                      {co2Saved} kg
                    </p>
                  </div>
                </div>
                {distanceSaved != null && (
                  <div className="mt-3 bg-white bg-opacity-60 rounded-lg p-3">
                    <p className="text-xs text-green-600 mb-0.5">
                      Distance saved
                    </p>
                    <p className="text-xl font-bold text-green-700">
                      {distanceSaved} km
                    </p>
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
                        <span className="text-xs font-medium text-gray-600 w-12 text-right shrink-0">{metrics.originalFuelLiters} L</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-green-700 w-16 shrink-0">Optimized</span>
                        <div className="flex-1 bg-green-100 rounded-full h-2.5">
                          <div
                            className="bg-green-500 h-2.5 rounded-full transition-all duration-500"
                            style={{ width: `${(metrics.fuelLiters / metrics.originalFuelLiters) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium text-green-700 w-12 text-right shrink-0">{metrics.fuelLiters} L</span>
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
                    <p className="text-lg font-medium">
                      {metrics.originalDistanceKm} km
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-[#034626]">Optimized</p>
                  <p className="text-lg font-medium text-[#034626]">
                    {metrics.distanceKm} km
                  </p>
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
                    <p className="text-lg font-medium">
                      {formatDuration(metrics.originalDurationMin)}
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-[#034626]">Optimized</p>
                  <p className="text-lg font-medium text-[#034626]">
                    {formatDuration(metrics.durationMin)}
                  </p>
                  {timeDeltaMin != null && timeDeltaMin !== 0 && (
                    <p className={`text-xs mt-0.5 font-medium ${timeDeltaMin < 0 ? 'text-green-600' : 'text-amber-600'}`}>
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
                      <p className="text-lg font-medium">
                        {metrics.originalFuelLiters} L
                      </p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-[#034626]">Optimized</p>
                    <p className="text-lg font-medium text-[#034626]">
                      {metrics.fuelLiters} L
                    </p>
                    {fuelSaved != null && fuelSaved > 0 && (
                      <p className="text-xs mt-0.5 text-green-600 font-medium">
                        ↓ {fuelSaved} L less{fuelSavedPct ? ` (${fuelSavedPct}%)` : ''}
                      </p>
                    )}
                    {fuelSaved === 0 && hasOriginal && (
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
                      <p className="text-lg font-medium">
                        {metrics.originalCo2Kg} kg
                      </p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-[#034626]">Optimized</p>
                    <p className="text-lg font-medium text-[#034626]">
                      {metrics.co2Kg} kg
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Impact Equivalents */}
            {(fuelSaved != null || co2Saved != null) && (
              <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                <h3 className="text-sm font-semibold text-blue-800 mb-3">Impact Equivalents</h3>
                <div className="space-y-2 text-sm">
                  {co2Saved != null && co2Saved > 0 && (
                    <>
                      <div className="flex justify-between items-center">
                        <span className="text-blue-700 text-xs flex items-center">
                          Trees absorbing CO₂ for 1 year
                          <InfoTip text={`${co2Saved} kg CO₂ saved ÷ 21 kg/tree/yr = ${(Math.round(co2Saved / 21 * 10) / 10).toFixed(1)} trees. Source: US Forest Service avg of 21 kg CO₂ absorbed per mature tree per year.`} />
                        </span>
                        <span className="font-semibold text-blue-900 text-sm">{(Math.round(co2Saved / 21 * 10) / 10).toFixed(1)}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-blue-700 text-xs flex items-center">
                          Equivalent car km avoided
                          <InfoTip text={`${co2Saved} kg CO₂ saved ÷ 0.12 kg CO₂/km = ${Math.round(co2Saved / 0.12)} km. Based on an average passenger car emitting 120 g CO₂/km (EU average).`} />
                        </span>
                        <span className="font-semibold text-blue-900 text-sm">{Math.round(co2Saved / 0.12)} km</span>
                      </div>
                    </>
                  )}
                  {fuelSaved != null && fuelSaved > 0 && (
                    <div className="flex justify-between items-center">
                      <span className="text-blue-700 text-xs flex items-center">
                        Est. fuel cost saved
                        <InfoTip text={`${fuelSaved} L saved × $1.50/L = $${(Math.round(fuelSaved * 1.5 * 100) / 100).toFixed(2)}. Uses US average diesel pump price of ~$1.50/L.`} />
                      </span>
                      <span className="font-semibold text-blue-900 text-sm">${(Math.round(fuelSaved * 1.5 * 100) / 100).toFixed(2)}</span>
                    </div>
                  )}
                  {metrics.fuelLiters != null && metrics.distanceKm != null && metrics.distanceKm > 0 && (
                    <div className="flex justify-between items-center">
                      <span className="text-blue-700 text-xs flex items-center">
                        Optimized fuel efficiency
                        <InfoTip text={`${metrics.fuelLiters} L ÷ ${metrics.distanceKm} km × 100 = ${(metrics.fuelLiters / metrics.distanceKm * 100).toFixed(1)} L/100km. Standard metric: litres consumed per 100 km driven.`} />
                      </span>
                      <span className="font-semibold text-blue-900 text-sm">{(metrics.fuelLiters / metrics.distanceKm * 100).toFixed(1)} L/100km</span>
                    </div>
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

            {/* Run details */}
            {metrics.matrixRunId && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="flex justify-between items-center">
                  <h4 className="font-semibold text-sm">Run ID</h4>
                  <button
                    onClick={fetchRunData}
                    className="text-xs text-[#034626] underline"
                  >
                    {runLoading ? 'Loading...' : runData ? 'Hide' : 'View details'}
                  </button>
                </div>
                <p className="text-xs text-gray-500 font-mono mt-1 break-all">{metrics.matrixRunId}</p>
                {runData && (
                  <div className="mt-2 space-y-1 text-xs text-gray-600">
                    <p>Stops: {runData.n_stops}</p>
                    <p>Vehicle: {runData.vehicle_weight_kg} kg · {runData.fuel_type}</p>
                    <p>Saved: {new Date(runData.timestamp).toLocaleString()}</p>
                  </div>
                )}
              </div>
            )}

            {/* Export */}
            <button
              onClick={handleExport}
              className="w-full bg-[#034626] text-white py-2 px-4 rounded-lg hover:bg-[#023219] transition-colors"
            >
              Export Report
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * MapView renders a full-screen interactive map displaying the user's route and stops.
 * It uses Leaflet for map rendering and displays markers, a polyline route, and a side panel
 * for route analytics. It also provides controls for navigating back and viewing analytics.
 *
 * Props:
 * - formData: Object containing submitted route data, including stops and their coordinates
 * - route: Array of [lat, lng] points representing the optimized route polyline
 * - startCoords: Coordinates of the route start point
 * - endCoords: Coordinates of the route end point
 * - onBack: Function to navigate back to the previous UI step
 *
 * Note: The map uses OpenStreetMap tiles via CartoDB.
 */
const MapView = ({
  formData,
  route,
  startCoords,
  endCoords,
  onBack,
  metrics,
}: any) => {
  const [isAnalyticsPanelOpen, setIsAnalyticsPanelOpen] = useState(false);

  /**
   * Returns the color of a marker based on its index in the stop list:
   * - Start (first two): blue
   * - End (last): red
   * - Intermediate stops: orange
   */
  const getMarkerColor = (index: number, total: number) => {
    if (index === 0) return 'blue';
    if (index === total - 1) return 'red';
    return 'orange';
  };

  return (
    <div className="fixed inset-0 flex">
      <div className="absolute inset-0">
        <MapContainer
          center={[20.5937, 78.9629]}
          zoom={5}
          zoomControl={false}
          style={{ width: '100%', height: '100%' }}
        >
          {/* Tile layer for the map visuals */}
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CartoDB</a>'
          />

          {/* Center map based on route start and end */}
          <MapController
            startCoords={startCoords}
            endCoords={endCoords}
            route={route}
          />

          {/* Render a marker for each stop */}
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
              
              return (
                <Marker
                  key={index}
                  position={[stop.coords.lat, stop.coords.lng]}
                  icon={
                    new L.Icon({
                      iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${getMarkerColor(index, total)}.png`,
                      shadowUrl:
                        'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.3.1/images/marker-shadow.png',
                      iconSize: [25, 41],
                      iconAnchor: [12, 41],
                      popupAnchor: [1, -34],
                      shadowSize: [41, 41],
                    })
                  }
                >
                  {/* Hover Tooltip for quick weight info */}
                  <Tooltip direction="top" offset={[0, -35]} opacity={0.95}>
                     <div className="text-center font-sans tracking-wide">
                       <div className="font-semibold text-gray-800">
                         {isStart ? 'Start' : isEnd ? 'End' : `Stop ${index}`}
                       </div>
                       {weightValue > 0 && (
                         <div className="text-xs text-[#034626] font-extrabold mt-0.5">
                           {weightValue} kg
                         </div>
                       )}
                     </div>
                  </Tooltip>
                  
                  {/* Click Popup for detailed info */}
                  <Popup>
                    <div className="font-sans w-56 -m-1">
                      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-100">
                        <div className={`w-3 h-3 rounded-full ${isStart ? 'bg-blue-500' : isEnd ? 'bg-red-500' : 'bg-orange-400'}`}></div>
                        <span className="font-bold text-gray-800 text-sm">
                          {isStart ? 'Start Location' : isEnd ? 'Final Destination' : `Stop ${index}`}
                        </span>
                      </div>
                      <p className="text-[13px] text-gray-600 mb-3 leading-snug">
                        {stop.location}
                      </p>
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

          {/* Draw the route as a polyline if available */}
          {route && <Polyline positions={route} color="blue" weight={4} />}

          {/* Custom zoom control */}
          <ZoomControls />
        </MapContainer>
      </div>

      {/* Top navigation bar */}
      <div className="absolute top-0 w-full p-4 z-[1000] flex justify-between items-start text-black">
        <div className="flex gap-2">
          <button
            onClick={onBack}
            className="bg-white rounded-lg px-4 py-2 shadow-lg hover:bg-gray-50 flex items-center gap-2"
          >
            <span>Back</span>
          </button>
          <button
            onClick={() => setIsAnalyticsPanelOpen((o) => !o)}
            className="bg-[#034626] text-white rounded-lg px-4 py-2 shadow-lg hover:bg-[#023219] flex items-center gap-2"
          >
            <span>Analytics</span>
          </button>
        </div>

        {/* Route metrics pills */}
        {metrics &&
          (metrics.distanceKm != null || metrics.fuelLiters != null) &&
          (() => {
            const fmtDur = (min: number) =>
              min >= 60
                ? `${Math.floor(min / 60)}h ${Math.round(min % 60)}m`
                : `${Math.round(min)}m`;
            const fuelSaved =
              metrics.originalFuelLiters != null && metrics.fuelLiters != null
                ? Math.round(
                    (metrics.originalFuelLiters - metrics.fuelLiters) * 100
                  ) / 100
                : null;
            const co2Saved =
              metrics.originalCo2Kg != null && metrics.co2Kg != null
                ? Math.round((metrics.originalCo2Kg - metrics.co2Kg) * 100) /
                  100
                : null;
            const fuelSavedPct =
              metrics.originalFuelLiters != null &&
              metrics.originalFuelLiters > 0 &&
              fuelSaved != null
                ? ((fuelSaved / metrics.originalFuelLiters) * 100).toFixed(1)
                : null;
            return (
              <div className="flex gap-2 flex-wrap justify-end">
                {metrics.distanceKm != null && (
                  <div className="bg-white rounded-lg px-3 py-2 shadow-lg text-sm font-medium">
                    <span className="text-gray-500">Distance&nbsp;</span>
                    <span className="text-[#034626] font-bold">
                      {metrics.distanceKm} km
                    </span>
                  </div>
                )}
                {metrics.durationMin != null && (
                  <div className="bg-white rounded-lg px-3 py-2 shadow-lg text-sm font-medium">
                    <span className="text-gray-500">Duration&nbsp;</span>
                    <span className="text-[#034626] font-bold">
                      {fmtDur(metrics.durationMin)}
                    </span>
                  </div>
                )}
                {metrics.fuelLiters != null && (
                  <div className="bg-white rounded-lg px-3 py-2 shadow-lg text-sm font-medium">
                    <span className="text-gray-500">Fuel&nbsp;</span>
                    <span className="text-[#034626] font-bold">
                      {metrics.fuelLiters} L
                    </span>
                    {fuelSaved != null && fuelSaved > 0 && (
                      <span className="text-green-600 text-xs ml-1">
                        ↓{fuelSaved} L
                        {fuelSavedPct ? ` (${fuelSavedPct}%)` : ''}
                      </span>
                    )}
                  </div>
                )}
                {metrics.co2Kg != null && (
                  <div className="bg-white rounded-lg px-3 py-2 shadow-lg text-sm font-medium">
                    <span className="text-gray-500">CO₂&nbsp;</span>
                    <span className="text-[#034626] font-bold">
                      {metrics.co2Kg} kg
                    </span>
                    {co2Saved != null && co2Saved > 0 && (
                      <span className="text-green-600 text-xs ml-1">
                        ↓{co2Saved} kg
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })()}
      </div>

      {/* Map legend component (assumed to explain marker colors) */}
      <Legend />

      {/* Slide-in analytics panel */}
      <AnalyticsPanel
        isOpen={isAnalyticsPanelOpen}
        onClose={() => setIsAnalyticsPanelOpen(false)}
        metrics={metrics}
        formData={formData}
      />
    </div>
  );
};

export default MapView;
