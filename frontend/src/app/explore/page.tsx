'use client';
import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import PlacesAutocomplete from './PlacesAutocomplete';
import Footer from '../components/Footer';
import Navbar from '../components/Navbar';

// Dynamically import the map component with no Server-Side Rendering
const MapView = dynamic(() => import('./MapView'), {
  ssr: false,
  loading: () => (
    <div className="fixed inset-0 flex items-center justify-center bg-gray-50">
      <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
    </div>
  ),
});

// Add preset route data
const presetRoute = {
  stops: [
    {
      location: 'TST BOCES, 555 Warren Road, Northeast Ithaca, NY 14850',
      coords: { lat: 42.476169, lng: -76.465092 },
    },
    {
      location: 'Dewitt Middle School, 560 Warren Road, Ithaca, NY 14850',
      coords: { lat: 42.475434, lng: -76.468026 },
    },
    {
      location:
        'Northeast Elementary School, 425 Winthrop Dr, Ithaca, NY 14850',
      coords: { lat: 42.472932, lng: -76.468742 },
    },
    {
      location:
        'Cayuga Heights Elementary School, 110 E Upland Rd, Ithaca, NY 14850',
      coords: { lat: 42.465637, lng: -76.488499 },
    },
    {
      location:
        'Belle Sherman Elementary School, Valley Road, Ithaca, NY 14853',
      coords: { lat: 42.435757, lng: -76.481317 },
    },
    {
      location:
        'Caroline Elementary School, Slaterville Road, Besemer, NY 14881',
      coords: { lat: 42.392593, lng: -76.3715585 },
    },
    {
      location:
        'South Hill Elementary School, 520 Hudson Street, Ithaca, NY 14850',
      coords: { lat: 42.4338533, lng: -76.4931807 },
    },
    {
      location:
        'Beverly J. Martin Elementary School, 302 West Buffalo Street, Ithaca, NY',
      coords: { lat: 42.4422, lng: -76.4976 },
    },
    {
      location: 'Fall Creek School, Linn Street, Ithaca, NY 14850',
      coords: { lat: 42.4415514, lng: -76.5021644 },
    },
    {
      location:
        'Boynton Middle School, 1601 North Cayuga Street, Ithaca, NY 14850',
      coords: { lat: 42.4606674, lng: -76.500035 },
    },
    {
      location: '602 Hancock Street, Ithaca, NY 14850',
      coords: { lat: 42.4460873, lng: -76.5065422 },
    },
    {
      location: '737 Willow Ave, Ithaca, NY 14850',
      coords: { lat: 42.453183, lng: -76.5053133 },
    },
    {
      location: 'Enfield School, 20 Enfield Main Road, Ithaca, NY 14850',
      coords: { lat: 42.449517, lng: -76.6316132 },
    },
    {
      location:
        'Lehmann Alternative Community School, 111 Chestnut Street, Ithaca, NY',
      coords: { lat: 42.440077, lng: -76.5177744 },
    },
    {
      location:
        'Recycling and Solid Waste Center, 160 Commercial Avenue, Ithaca, NY',
      coords: { lat: 42.4242689, lng: -76.5159428 },
    },
  ],
  maintainOrder: false,
  currentFuel: '40.0',
  time: '80.0',
  vehicleNumber: 'BUS-001',
};

/**
 *
 * Renders the explore page, handling changes to input. Enables MapView when a route is submitted.
 *
 */
const ExplorePage = () => {
  /*=======================================================
  
    INTERFACES
  
  =========================================================*/

  // define a coordinates interface for standardization
  interface Coords {
    lat: number;
    lng: number;
  }

  // define an interface that defines a place
  interface Place {
    formatted_address: string;
    geometry: {
      location: {
        lat: number;
        lng: number;
      };
    };
  }

  //define an interface for a stop
  interface Stop {
    location: string;
    coords: Coords | null;
  }

  /*=======================================================
  
    STATES
  
  =========================================================*/

  // define a stateful variable formdata holding necessary data to display
  // formData: Holds the user's input for stops, fuel info, and vehicle details.
  // This state is the source of truth for the optimization request.
  const [formData, setFormData] = useState({
    stops: [
      { location: '', coords: null as Coords | null }, // Start
      { location: '', coords: null as Coords | null }, // End
    ],
    maintainOrder: false,
    currentFuel: '40.0',
    time: '80.0',
    vehicleNumber: 'BUS-001',
  });

  //debug whenever formData.stops updates
  useEffect(() => {
    console.log('Updated stops:', formData.stops);
  }, [formData.stops]); // Runs whenever `stops` changes




  // define stateful variables for the route, and the current view
  const [route, setRoute] = useState(null); // Stores the optimized route geometry (polyline)
  const [isMapView, setIsMapView] = useState(false); // Toggles between the input form and the map view
  const [dropdownVisible, setDropdownVisible] = useState(
    Array(formData.stops.length).fill(false)
  );
  const [isLoading, setIsLoading] = useState(false); // Loading state for the optimization request
  const [loadingMessage, setLoadingMessage] = useState('Optimizing...');

  // Add these computed values
  const startCoords = formData.stops[0]?.coords || null;
  const endCoords = formData.stops[formData.stops.length - 1]?.coords || null;

  // look at later
  interface Place {
    formatted_address: string;
    geometry: {
      location: {
        lat: number;
        lng: number;
      };
    };
  }

  // handle a change to the selection of stops
  const handleStopSelect = (place: Place, index: number) => {
    const newStops = [...formData.stops];
    newStops[index] = {
      location: place.formatted_address,
      coords: place.geometry.location,
    };
    setFormData((prev) => ({ ...prev, stops: newStops }));
  };

  // handle adding a stop
  const addStop = () => {
    setFormData((prev) => ({
      ...prev,
      stops: [
        ...prev.stops.slice(0, -1),
        { location: '', coords: null },
        prev.stops[prev.stops.length - 1],
      ],
    }));
  };

  //handle removing a stop
  const removeStop = (index: number) => {
    if (formData.stops.length <= 2) return; // Keep at least start and end
    setFormData((prev) => ({
      ...prev,
      stops: prev.stops.filter((_, i) => i !== index),
    }));
  };

  // handle a change to the form input
  const handleInputChange = (e: any) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  // look at later
  interface Stop {
    location: string;
    coords: Coords | null;
  }

  // given a list of stops, make an API call to osrm that returns route data that is then formatted
  const getMultiStopRoute = async (stops: Stop[]) => {
    try {
      const coordinates = stops
        .map((stop) =>
          stop.coords ? `${stop.coords.lng},${stop.coords.lat}` : ''
        )
        .join(';');

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_OSRM_URL || 'http://127.0.0.1:5001'}/route/v1/driving/${coordinates}?overview=full&geometries=geojson`
      );
      const data = await response.json();
      if (data.routes && data.routes.length > 0) {
        return data.routes[0].geometry.coordinates.map((coord: any) => [
          coord[1],
          coord[0],
        ]);
      }
      return null;
    } catch (error) {
      console.error('Error getting route:', error);
      return null;
    }
  };

  // Reusable route generation logic, calling the backend
  // optimizeRoute:
  // 1. Sets loading state.
  // 2. Sends formData to the backend /optimize_route endpoint.
  // 3. Updates formData with the reordered stops returned by the backend.
  // 4. Updates route state with the geometry returned by the backend.
  // 5. Switches to MapView.
  const optimizeRoute = async () => {
    setIsLoading(true);
    setLoadingMessage('Optimizing...');
    
    const timeoutId = setTimeout(() => {
      setLoadingMessage('Waking up server...');
    }, 15000); // 15 seconds

    try {
      let backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      if (!backendUrl.startsWith('http')) {
        backendUrl = `https://${backendUrl}`;
      }
      
      const response = await fetch(`${backendUrl}/optimize_route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (!response.ok) {
        console.error('Backend error:', data);
        return;
      }

      // Update stops (order may have changed)
      setFormData((prev) => ({
        ...prev,
        stops: data.optimizedStops,
      }));

      // Update map route
      setRoute(data.routeGeometry);

      setIsMapView(true);
    } catch (err) {
      console.error('Error calling backend:', err);
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
      setLoadingMessage('Optimizing...');
    }
  };

  // Form submission handler
  const handleSubmit = async (e: any) => {
    e.preventDefault();
    await optimizeRoute();
  };

  // Preset route loader
  const loadPresetRoute = () => {
    setFormData(presetRoute);
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-green-50 via-white to-green-50 flex flex-col">
      {/* Only show Navbar if not in MapView */}
      {!isMapView && <Navbar />}
      <div className="mt-16" />
      <div className="relative flex-1 flex flex-col justify-center items-center">
        {/* Decorative Leaves */}
        <img
          src="/images/leaf.png"
          alt="Leaf"
          style={{
            position: 'absolute',
            left: '5rem',
            top: '5vh',
            width: '6rem',
            transform: 'rotate(-26deg) scaleX(-1)',
            zIndex: 0,
          }}
          className="hidden md:block"
        />
        <img
          src="/images/leaf.png"
          alt="Leaf"
          style={{
            position: 'absolute',
            left: '5rem',
            top: '30vh',
            width: '5rem',
            transform: 'rotate(14deg)',
            zIndex: 0,
          }}
          className="hidden md:block"
        />
        <img
          src="/images/leaf.png"
          alt="Leaf"
          style={{
            position: 'absolute',
            left: '5rem',
            top: '55vh',
            width: '6rem',
            transform: 'rotate(-21deg) scaleX(-1)',
            zIndex: 0,
          }}
          className="hidden md:block"
        />
        <img
          src="/images/leaf.png"
          alt="Leaf"
          style={{
            position: 'absolute',
            right: '5rem',
            top: '10vh',
            width: '6rem',
            transform: 'rotate(24deg)',
            zIndex: 0,
          }}
          className="hidden md:block"
        />
        <img
          src="/images/leaf.png"
          alt="Leaf"
          style={{
            position: 'absolute',
            right: '5rem',
            top: '35vh',
            width: '5rem',
            transform: 'rotate(-16deg) scaleX(-1)',
            zIndex: 0,
          }}
          className="hidden md:block"
        />
        <img
          src="/images/leaf.png"
          alt="Leaf"
          style={{
            position: 'absolute',
            right: '5rem',
            top: '60vh',
            width: '6rem',
            transform: 'rotate(19deg)',
            zIndex: 0,
          }}
          className="hidden md:block"
        />
        {/* Main Content */}
        <div className="relative z-10 flex flex-col items-center justify-center w-full py-8 pb-24">
          {!isMapView ? (
            <div className="w-full max-w-4xl mx-auto flex flex-col items-center px-2 sm:px-4 md:px-8">
              <h1 className="text-[52px] poppins-bold text-center leading-tight mb-10 text-gray-900 animate-fade-in-down">
                <span className="pathos-green">Explore</span>{' '}
                <span className="text-black">Your New Route to</span>
                <br />
                <span className="pathos-green mt-2 inline-block">
                  Sustainability
                </span>
              </h1>
              <p className="text-gray-600 text-sm italic -mt-6 mb-8 poppins-regular">
                {/* *We currently only support routes within the state of New York */}
                *Backend is currently deactivated to reduce costs
              </p>
              <form
                onSubmit={handleSubmit}
                className="w-full flex flex-col items-center gap-8"
              >
                {/* Stops Section */}
                <div
                  className="w-full flex flex-col gap-4 relative overflow-visible"
                  style={{ minHeight: 60 * formData.stops.length }}
                >
                  {formData.stops.map((stop, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-2 w-full min-h-14 sm:min-h-16"
                    >
                      <div className="flex-grow relative">
                        {/* Timeline inside and between textboxes */}
                        <div className="absolute left-5 top-0 h-full w-8 flex flex-col items-center z-10 pointer-events-none">
                          {/* Vertical line above the circle (not for first) */}
                          {index !== 0 && (
                            <div
                              className="absolute"
                              style={{
                                left: '50%',
                                transform: 'translateX(-50%)',
                                top: '-22px',
                                height: 'calc(50% + 10px)',
                                width: '2px',
                                background: '#034626',
                                borderRadius: 2,
                              }}
                            />
                          )}
                          {/* Circle */}
                          <div
                            className={
                              stop.coords
                                ? 'w-4 h-4 rounded-full'
                                : 'w-4 h-4 rounded-full border-2 bg-white'
                            }
                            style={{
                              zIndex: 2,
                              left: '50%',
                              transform: 'translateX(-50%)',
                              position: 'absolute',
                              top: '50%',
                              marginTop: '-8px',
                              background: stop.coords ? '#034626' : 'white',
                              borderColor: !stop.coords ? '#034626' : undefined,
                            }}
                          ></div>
                          {/* Vertical line below the circle (not for last) */}
                          {index !== formData.stops.length - 1 && (
                            <div
                              className="absolute"
                              style={{
                                left: '50%',
                                transform: 'translateX(-50%)',
                                top: 'calc(50% + 14px)',
                                height: 'calc(50% + 10px)',
                                width: '2px',
                                background: '#034626',
                                borderRadius: 2,
                              }}
                            />
                          )}
                        </div>
                        {/* 
                          PlacesAutocomplete: 
                          Custom component that handles address search and selection.
                          Updates the specific stop's location and coordinates in formData.
                        */}
                        <PlacesAutocomplete
                          value={stop.location}
                          onChange={(value) => {
                            const newStops = [...formData.stops];
                            newStops[index].location = value;
                            newStops[index].coords = null;
                            setFormData((prev) => ({
                              ...prev,
                              stops: newStops,
                            }));
                          }}
                          onSelect={(place) => handleStopSelect(place, index)}
                          inputClassName="text-black text-base sm:text-lg md:text-xl pl-16 py-4"
                          placeholder={
                            index === 0
                              ? 'Enter start location'
                              : index === formData.stops.length - 1
                                ? 'Enter end location'
                                : `Stop ${index}`
                          }
                          onDropdownVisibilityChange={(visible) => {
                            setDropdownVisible((prev) => {
                              const arr = [...prev];
                              arr[index] = visible;
                              return arr;
                            });
                          }}
                          hasValidCoords={!!stop.coords}
                        />
                      </div>
                      {/* Remove button for intermediate stops */}
                      {index !== 0 && index !== formData.stops.length - 1 && (
                        <button
                          type="button"
                          onClick={() => removeStop(index)}
                          className="ml-2 text-gray-400 hover:text-red-500 text-2xl font-bold focus:outline-none min-w-[32px] min-h-[32px] flex items-center justify-center"
                          aria-label="Remove stop"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <div className="flex flex-col sm:flex-row gap-3 -mt-1 w-full">
                  <button
                    type="button"
                    onClick={addStop}
                    className="bg-[#034626] hover:bg-[#023219] text-white poppins-semibold text-xl py-1.5 px-4 rounded-xl transform transition-all hover:scale-105 w-full sm:w-auto"
                  >
                    + Add stop
                  </button>
                  <button
                    type="button"
                    onClick={loadPresetRoute}
                    className="border-2 border-[#034626] pathos-green poppins-semibold text-xl py-1.5 px-4 rounded-xl transform transition-all hover:scale-105 w-full sm:w-auto"
                  >
                    Load sample schools route
                  </button>
                </div>
                {/* 
                <div className="flex items-center w-full -mt-4 mb-4">
                  <input
                    id="maintainOrder"
                    type="checkbox"
                    name="maintainOrder"
                    checked={formData.maintainOrder}
                    onChange={handleInputChange}
                    className="mr-2 w-4 h-4 accent-[#034626] border-[#034626] rounded focus:ring-2 focus:ring-[#034626] transition-transform duration-150 hover:scale-110 focus:scale-110 cursor-pointer"
                  />
                  <label
                    htmlFor="maintainOrder"
                    className="text-gray-600 text-base text-[16px] cursor-pointer"
                  >
                    The stops are in the order they are currently operating
                  </label>
                </div>
                */}
                {/* Vehicle Inputs Hidden
                <div className="w-full flex flex-col gap-2 mt-10">
                  <h3 className="text-4xl text-center mb-2 text-gray-800 poppins-bold">
                    Tell Us About Your{' '}
                    <span className="pathos-green">Vehicle</span>
                  </h3>
                  <div className="grid grid-cols-3 gap-4 w-full mt-2">
                    <div className="flex flex-col">
                      <label className="block text-[18px] font-normal text-gray-800 mb-1">
                        Current Fuel Per Trip
                      </label>
                      <input
                        type="text"
                        name="currentFuel"
                        value={formData.currentFuel}
                        onChange={handleInputChange}
                        className="w-full px-4 py-2 border border-gray-400 rounded-md focus:outline-none focus:ring-2 focus:ring-[#034626] text-gray-700 placeholder-gray-600 text-[18px] poppins-regular"
                        placeholder="gal"
                      />
                    </div>
                    <div className="flex flex-col">
                      <label className="block text-[18px] font-normal text-gray-800 mb-1">
                        Trip Duration
                      </label>
                      <input
                        type="text"
                        name="time"
                        value={formData.time}
                        onChange={handleInputChange}
                        className="w-full px-4 py-2 border border-gray-400 rounded-md focus:outline-none focus:ring-2 focus:ring-[#034626] text-gray-700 placeholder-gray-600 text-[18px] poppins-regular"
                        placeholder="hh:mm"
                      />
                    </div>
                    <div className="flex flex-col">
                      <label className="block text-[18px] font-normal text-gray-800 mb-1">
                        Vehicle Numbe
                      </label>
                      <input
                        type="text"
                        name="vehicleNumber"
                        value={formData.vehicleNumber}
                        onChange={handleInputChange}
                        className="w-full px-4 py-2 border border-gray-400 rounded-md focus:outline-none focus:ring-2 focus:ring-[#034626] text-gray-700 placeholder-gray-600 text-[18px] poppins-regular"
                        placeholder=""
                      />
                    </div>
                  </div>
                </div>
                */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className={`w-full bg-[#034626] hover:bg-[#023219] text-white poppins-semibold text-xl py-2 px-4 rounded-xl transform transition-all hover:scale-105 -mt-1 flex justify-center items-center gap-2 ${isLoading ? 'opacity-75 cursor-not-allowed' : ''}`}
                >
                  {isLoading ? (
                    <>
                      <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div>
                      <span>{loadingMessage}</span>
                    </>
                  ) : (
                    'Optimize Route'
                  )}
                </button>
              </form>
            </div>
          ) : (
            <MapView
              formData={formData}
              route={route}
              startCoords={startCoords}
              endCoords={endCoords}
              onBack={() => setIsMapView(false)}
            />
          )}
        </div>
      </div>
      <div className="hidden md:block mt-32">
        <Footer />
      </div>
    </main>
  );
};

export default ExplorePage;
