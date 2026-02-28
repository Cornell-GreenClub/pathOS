import Image from 'next/image';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Link from 'next/link';
import { FaLeaf, FaChartLine, FaCog } from 'react-icons/fa';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-white">
      <Navbar />
      <div className="max-w-screen-full mx-auto">
        {/* Hero Section */}
        <section className="mb-24 flex flex-col p-8 md:flex-row items-center justify-center min-h-[calc(100vh-8rem)] bg-gradient-to-t from-[#D3F7E0] to-white">
          <div className="md:w-1/2 p-4 md:p-12 text-left">
            <div>
              <h1 className="text-4xl md:text-7xl font-extrabold mb-8 animate-fade-in-down text-gray-900">
                <span className="poppins-semibold">
                  <span className="pathos-green">path</span>
                  <span className="text-[#6D6D6D]">OS</span>
                </span>
                <br />
                <div className="poppins-medium text-3xl md:text-6xl text-gray-900 mt-[5px]">
                  Smarter <span className="pathos-green">Routes,</span>
                  <br />
                  <span className="pathos-green">Greener</span> Future
                </div>
              </h1>
              <p className="text-xl text-gray-700 animate-fade-in-up">
                Driving change with data: Smarter transport, lower
                <br />
                emissions, lasting impact
              </p>
            </div>
            <div className="flex space-x-4 mt-8">
              <Link href="/explore">
                <button className="border border-2 border-[#034626] bg-[#034626] hover:bg-[#023219] hover:border-[#023219] text-white poppins-bold text-xl py-3 px-6 rounded-xl transform transition-all hover:scale-105">
                  Explore Routes
                </button>
              </Link>
              <Link href="/about">
                <button className="border border-2 border-[#034626] pathos-green hover:bg-[#034626] hover:text-white poppins-bold text-xl py-3 px-6 rounded-xl transform transition-all hover:scale-105">
                  About Us
                </button>
              </Link>
            </div>
          </div>

          <div className="md:w-1/2 p-4">
            <div className="relative overflow-hidden rounded-lg transform hover:scale-105 transition-transform duration-300">
              <img
                src="https://images.unsplash.com/photo-1465447142348-e9952c393450?w=800&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxzZWFyY2h8M3x8cm9hZHxlbnwwfHwwfHx8MA%3D%3D"
                alt="Ithaca Commons"
                className="w-[700px] h-[372px] object-cover object-center rounded-lg shadow-2xl"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-gray-900 via-transparent to-transparent opacity-60"></div>
            </div>
          </div>
        </section>

        {/* Container for "Get Started" and Stepper Section */}
        <div className="flex flex-col md:flex-row items-center justify-center px-8 md:px-16 lg:px-24 mt-8 pb-40 pt-12 bg-white text-black ">
          {/* "Get Started" section */}
          <div
            id="get-started"
            className="p-4 text-left md:w-auto flex justify-center"
          >
            <div>
              <img
                className="w-[480px] h-[550px] object-cover rounded-lg transform hover:scale-105 transition-transform duration-300"
                src="/images/image.png"
              ></img>
              <p
                style={{ fontFamily: 'Open Sans, sans-serif' }}
                className="mt-4"
              ></p>
            </div>
          </div>

          {/* Stepper Section */}
          <section className="w-full md:w-auto ml-16">
            <h1 className="poppins-bold text-left text-[48px] font-bold mb-8 text-gray-900">
              Explore Our <span className="pathos-green">Road</span> Network
            </h1>
            <div className="relative max-w-4xl mx-auto">
              {/* Vertical Line */}
              <div className="absolute left-[33px] top-[34px] h-[calc(100%-68px)] w-px bg-[#034626]"></div>

              {/* Step 1 */}
              <div>
                <div className="flex items-center mb-8 relative">
                  {/* Number 1 */}
                  <div className="w-[67px] h-[68px] flex-shrink-0 bg-[#034626] rounded-md flex items-center justify-center text-lg font-semibold">
                    <span className="text-3xl poppins-bold text-white">1</span>
                  </div>

                  {/* Horizontal line to text */}
                  <div className="h-px w-[39px] bg-[#034626] absolute left-[67px] top-1/2 transform -translate-y-1/2"></div>
                  {/* Step content */}
                  <div className="ml-24">
                    <h2 className="poppins-semibold text-3xl text-gray-800">
                      Visualize
                    </h2>
                    <p className="mt-2 text-xl poppins-medium text-gray-700">
                      Gain a comprehensive view of the transportation
                      infrastructure in your area
                    </p>
                  </div>
                </div>
              </div>

              {/* Step 2 */}
              <div>
                <div className="flex items-center mb-8 relative">
                  {/* Number 2 */}
                  <div className="w-[67px] h-[68px] flex-shrink-0 bg-[#034626] rounded-md flex items-center justify-center text-lg font-semibold">
                    <span className="text-3xl poppins-bold text-white">2</span>
                  </div>

                  {/* Horizontal line to text */}
                  <div className="h-px w-[39px] bg-[#034626] absolute left-[67px] top-1/2 transform -translate-y-1/2"></div>

                  {/* Step content */}
                  <div className="ml-24">
                    <h2 className="poppins-semibold text-3xl text-gray-800">
                      Analyze
                    </h2>
                    <p className="mt-2 text-xl poppins-medium text-gray-700">
                      Identify bottlenecks, alternative routes, and
                      opportunities for optimization
                    </p>
                  </div>
                </div>
              </div>

              {/* Step 3 */}
              <div>
                <div className="flex items-center mb-8 relative">
                  {/* Number 3 */}
                  <div className="w-[67px] h-[68px] flex-shrink-0 bg-[#034626] rounded-md flex items-center justify-center text-lg font-semibold">
                    <span className="text-3xl poppins-bold text-white">3</span>
                  </div>

                  {/* Horizontal line to text */}
                  <div className="h-px w-[39px] bg-[#034626] absolute left-[67px] top-1/2 transform -translate-y-1/2"></div>

                  {/* Step content */}
                  <div className="ml-24">
                    <h2 className="poppins-semibold text-3xl text-gray-800">
                      Optimize
                    </h2>
                    <p className="mt-2 text-xl poppins-medium text-gray-700">
                      Plan the most efficient, eco-friendly paths for your fleet
                      or personal commute
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Eco Section */}
        <section className="eco-section py-8">
          <div className="flex flex-col md:flex-row justify-between max-w-6xl mx-auto px-4 gap-12">
            <div className="bg-white p-6 rounded-xl shadow-[0_0_15px_rgba(0,0,0,.2)] transition-all duration-300 transform hover:-translate-y-2 w-full md:w-1/3">
              <FaChartLine className="text-[#034626] text-4xl mb-3 mx-auto" />
              <h2 className="poppins-semibold text-3xl mb-3 text-center text-gray-800">
                Data-Driven
              </h2>
              <p className="text-gray-700 text-center">
                Our platform uses spatial data and operational patterns to
                inform smarter route planning
              </p>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-[0_0_15px_rgba(0,0,0,0.2)] transition-all duration-300 transform hover:-translate-y-2 w-full md:w-1/3">
              <FaLeaf className="text-[#034626] text-4xl mb-3 mx-auto" />
              <h2 className="poppins-semibold text-3xl mb-3 text-center text-gray-800">
                Sustainable
              </h2>
              <p className="text-gray-700 text-center">
                Our platform minimizes fuel consumption and emissions through
                intelligent routing
              </p>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-[0_0_15px_rgba(0,0,0,0.2)] transition-all duration-300 transform hover:-translate-y-2 w-full md:w-1/3">
              <FaCog className="text-[#034626] text-4xl mb-3 mx-auto" />
              <h2 className="poppins-semibold text-3xl mb-3 text-center text-gray-800">
                Customizable
              </h2>
              <p className="text-gray-700 text-center">
                Our tools can be tailored to your workflow to ensure seamless
                integration
              </p>
            </div>
          </div>
        </section>

        {/* Contact Section */}
        <section className="py-24 relative overflow-hidden mt-12">
          <div
            className="absolute inset-0"
            style={{
              background:
                'radial-gradient(ellipse 100% 100% at center, #D3F7E0 0%, rgba(255,255,255,0.8) 50%, rgba(255,255,255,1) 100%)',
              transform: 'scale(1.02)',
              top: '-1%',
            }}
          ></div>
          <div className="max-w-4xl mx-auto text-center relative">
            <h2 className="text-5xl poppins-bold mb-4 text-gray-900">
              Start <span className="text-[#034626]">Optimizing</span> Your
              Routes Today
            </h2>
            <p className="mb-8 text-gray-600">
              Join the growing number of organizations using pathOS to reduce
              their carbon footprint
            </p>
            <Link href="/explore">
              <button className="bg-[#034626] hover:bg-[#023219] text-white poppins-bold py-3 px-8 rounded-2xl text-base transform transition-all duration-300 hover:scale-105">
                Get Started
              </button>
            </Link>
          </div>
        </section>

        {/* Footer */}
        <div className="mt-32">
          <Footer />
        </div>
      </div>
    </main>
  );
}

// Add these styles to your global.css
/*
@keyframes fade-in-down {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in-down {
  animation: fade-in-down 1s ease-out;
}

.animate-fade-in-up {
  animation: fade-in-up 1s ease-out;
}
*/
