import Navbar from '../components/Navbar';
import Footer from '../components/Footer';

const AboutPage = () => {
  return (
    <main className="min-h-screen bg-white m-0">
      <Navbar />
      <div className="max-w-full mx-auto bg-gradient-to-br from-green-50 via-white to-green-50 ">
        {/* Section 1 */}
        <section className="flex flex-col md:flex-row justify-center p-[49px] pt-[97px]">
          <div className="w-full md:w-1/2 pr-[90px]">
            <h1 className="poppins-bold text-5xl text-gray-900 leading-tight">
              Rethinking
              <span className="pathos-green"> Waste Transport</span>
            </h1>
            <p className="poppins-regular text-xl text-gray-700 pt-[30px]">
              pathOS is a student-led project driven by a shared goal: reducing
              waste emissions through smarter routing.
              <br />
              <br />
              Our interdisciplinary team comes together to build a tool that is
              easy to use, grounded in data, and tailored for institutional
              decision-making. What began as a class project is now a platform
              ready to make a real-world impact.
            </p>
          </div>

          <div className="w-full md:w-1/2 p-4 flex items-center justify-center">
            <img
              src="/images/pathos-subteam.jpg"
              alt="Temporary Image"
              className="max-w-full h-auto transform transition-all duration-300 hover:scale-105"
            />
          </div>
        </section>

        {/* Section 2 */}
        <section className="flex flex-col md:flex-row justify-center p-[49px] pt-[97px]">
          <div className="w-full md:w-1/2 p-4 flex items-center justify-center">
            <img
              src="/images/pathos-graphic.png"
              alt="Temporary Image"
              className="max-w-full h-auto transform transition-all duration-300 hover:scale-105"
            />
          </div>

          <div className="w-full md:w-1/2 p-[49px] pl-[90px]">
            <h1 className="poppins-bold text-5xl text-gray-900 leading-tight">
              Making
              <span className="pathos-green"> Impact </span>
              Actionable
            </h1>
            <p className="poppins-regular text-xl text-gray-700 pt-[30px]">
              We’re building a web-based routing tool that optimizes fuel
              consumption for waste transportation routes. Our custom back-end
              connects user inputs to an optimization model, generating
              emissions-reducing routes under real-world constraints.
              <br />
              <br />
              Every component is purpose-built for institutional users looking
              to cut carbon emissions without impacting operations.
            </p>
          </div>
        </section>
      </div>
      {/* Section 3 */}
      <section
        className="flex flex-col justify-center mt-[45px]"
        style={{
          background:
            'radial-gradient(ellipse 100% 100% at center, #D3F7E0 0%, rgba(255,255,255,0.8) 50%, rgba(255,255,255,1) 100%)',
          transform: 'scale(1.02)',
          top: '-1%',
        }}
      >
        <div className="flex items-center justify-center flex-col py-[90px]">
          <h1 className="poppins-bold text-5xl text-gray-900 leading-tight">
            System <span className="pathos-green">Architecture</span>
          </h1>
          <p className="poppins-regular text-xl text-gray-700 pt-[20px] text-center">
            A modular, data-driven platform for emissions-optimized <br />
            routing using live stakeholder inputs
          </p>
        </div>
      </section>

      {/* Section 3 — Icons (outside the gradient) */}
      <section className="flex flex-col md:flex-row justify-center items-center pt-[20px] pb-[180px] gap-x-1">
        <div className="w-1/3 flex flex-col items-center justify-center">
          <img
            className="w-[75px] h-[75px]"
            src="/icons/backend.png"
            alt="Backend Icon"
          />
          <h3 className="poppins-semibold text-2xl text-gray-800 pt-[20px] pb-[10px] text-center">
            Backend
            <br />
            Optimization
          </h3>
          <p className="poppins-regular text-lg text-gray-700 text-center">
            Flask handles requests, formats inputs,
            <br />
            and executes route solving
            <br />
            via Google OR-Tools
          </p>
        </div>
        <div className="w-1/3 flex flex-col items-center justify-center">
          <img
            className="w-[75px] h-[75px]"
            src="/icons/fuel.png"
            alt="Fuel Icon"
          />
          <h3 className="poppins-semibold text-2xl text-gray-800 pt-[20px] pb-[10px] text-center">
            Custom
            <br />
            Cost Modeling
          </h3>
          <p className="poppins-regular text-lg text-gray-700 text-center">
            Routing logic model accounts for fuel usage,
            <br />
            distance, brand route-specific
            <br />
            operational constraints
          </p>
        </div>
        <div className="w-1/3 flex flex-col items-center justify-center">
          <img
            className="w-[75px] h-[75px]"
            src="/icons/map.png"
            alt="Map Icon"
          />
          <h3 className="poppins-semibold text-2xl text-gray-800 pt-[20px] pb-[10px] text-center">
            Live-Updating
            <br />
            Map Interface
          </h3>
          <p className="poppins-regular text-lg text-gray-700 text-center">
            Results are visualized through a responsive
            <br />
            Next.js frontend with real-time
            <br />
            map updates
          </p>
        </div>
      </section>
      <Footer />
    </main>
  );
};

export default AboutPage;
