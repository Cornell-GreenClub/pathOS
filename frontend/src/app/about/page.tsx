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
              Food transportation produces 18.2 million tonnes of CO<sub>2</sub> emissions annually. 
              K-12 schools are the largest source of institutional food waste, yet many organizations 
              lack the tools to rigorously determine the optimal stop ordering for their routes.
              <br />
              <br />
              pathOS is a student-led project at Cornell University driven by a shared goal: 
              quantify and optimize transportation emissions. What began as a 
              class project is now a platform ready to make a real-world impact by bridging 
              the data gap in Ithaca&apos;s Green New Deal.
            </p>
          </div>

          <div className="w-full md:w-1/2 p-4 flex items-center justify-center">
            <img
              src="/images/pathos-subteam.jpg"
              alt="pathOS Team"
              className="max-w-full h-auto transform transition-all duration-300 hover:scale-105"
            />
          </div>
        </section>

        {/* Section 2 */}
        <section className="flex flex-col md:flex-row justify-center p-[49px] pt-[97px]">
          <div className="w-full md:w-1/2 p-4 flex items-center justify-center">
            <img
              src="/images/pathos-graphic.png"
              alt="Optimization Logic"
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
              We’re building a web-based routing tool that optimizes fuel consumption for 
              transportation routes. While standard tools like Google Maps optimize point-to-point routing, 
              pathOS optimizes the order of the stops and accounts for real-world 
              factors like weight accumulation.
              <br />
              <br />
              Every component is purpose-built for institutional users looking to cut carbon 
              emissions and increase efficiency without impacting operations. Our goal is to reduce stakeholder emissions 
              by 10%, saving thousands of tonnes of CO<sub>2</sub> annually.
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
            routing using fundamental physics and metaheuristics.
          </p>
        </div>
      </section>

      {/* Section 3 — Icons */}
      <section className="flex flex-col md:flex-row justify-center items-center pt-[20px] pb-[180px] gap-x-1">
        <div className="w-1/3 flex flex-col items-center justify-center px-4">
          <img
            className="w-[75px] h-[75px]"
            src="/icons/backend.png"
            alt="Backend Icon"
          />
          <h3 className="poppins-semibold text-2xl text-gray-800 pt-[20px] pb-[10px] text-center">
            Simulated
            <br />
            Annealing
          </h3>
          <p className="poppins-regular text-lg text-gray-700 text-center">
            Utilizes Simulated Annealing to account 
            <br />
            for weight accumulation, achieving 
            <br />
            100% success on test routes.
          </p>
        </div>
        <div className="w-1/3 flex flex-col items-center justify-center px-4">
          <img
            className="w-[75px] h-[75px]"
            src="/icons/fuel.png"
            alt="Fuel Icon"
          />
          <h3 className="poppins-semibold text-2xl text-gray-800 pt-[20px] pb-[10px] text-center">
            Fuel Consumption 
            <br />
            Modeling
          </h3>
          <p className="poppins-regular text-lg text-gray-700 text-center">
            Predicts consumption using drag, grade, 
            <br />
            and friction with an average error 
            <br />
            of only 150 mL per trip.
          </p>
        </div>
        <div className="w-1/3 flex flex-col items-center justify-center px-4">
          <img
            className="w-[75px] h-[75px]"
            src="/icons/map.png"
            alt="Map Icon"
          />
          <h3 className="poppins-semibold text-2xl text-gray-800 pt-[20px] pb-[10px] text-center">
            Open Source
            <br />
            Routing Machine
          </h3>
          <p className="poppins-regular text-lg text-gray-700 text-center">
            Powered by AWS "Wake on Demand" 
            <br />
            architecture, slashing operating 
            <br />
            costs by 90%.
          </p>
        </div>
      </section>
      <Footer />
    </main>
  );
};

export default AboutPage;