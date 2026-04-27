import Link from 'next/link';

export default function Footer() {
  return (
    <footer className="hidden md:block bg-white text-gray-600 py-12 shadow-[inset_0_8px_8px_-8px_rgba(0,0,0,0.5)]">
      <div className="max-w-6xl mx-auto px-4 grid grid-cols-1 md:grid-cols-4 gap-8 md:gap-0 py-8">
        <div>
          <h3 className="text-2xl mb-1">
            <span className="poppins-extrabold">
              <span className="pathos-green">path</span>
              <span className="text-black">OS</span>
            </span>
          </h3>
          <p className="text-base poppins-regular">
            Smarter transport, lower emissions, lasting impact
          </p>
        </div>
        <div>
          <h3 className="poppins-bold text-gray-800 text-lg font-bold">
            Quick Links
          </h3>
          <ul className="text-base poppins-regular space-y-2">
            <li>
              <Link href="/" className="hover:text-gray-800 transition-colors">
                Home
              </Link>
            </li>
            <li>
              <Link
                href="/explore"
                className="hover:text-gray-800 transition-colors"
              >
                Routes
              </Link>
            </li>
            <li>
              <Link
                href="/about"
                className="hover:text-gray-800 transition-colors"
              >
                About Us
              </Link>
            </li>
            <li>
              <Link
                href="/contact"
                className="hover:text-gray-800 transition-colors"
              >
                Contact Us
              </Link>
            </li>
          </ul>
        </div>
        <div>
          <h3 className="poppins-bold text-gray-800 text-lg font-bold">
            Socials
          </h3>
          <ul className="text-base poppins-regular space-y-2">
            <li>
              <a
                href="mailto:pathos.earth@gmail.com"
                className="hover:text-gray-800 transition-colors"
              >
                <img
                  src="/icons/mail.png"
                  alt="Email"
                  className="inline-block w-[32px] h-[32px] mr-2 align-text-bottom"
                />
                pathos.earth@gmail.com
              </a>
            </li>
            <li>
              <a
                href="https://www.instagram.com/joingreenclub"
                className="hover:text-gray-800 transition-colors"
                target="_blank"
                rel="noopener noreferrer"
              >
                <img
                  src="/icons/instagram.png"
                  alt="Instagram"
                  className="inline-block w-[32px] h-[32px] mr-2 align-text-bottom"
                />
                @joingreenclub
              </a>
            </li>
            <li>
              <a
                href="https://www.linkedin.com/company/cornellgreenclub/posts/?feedView=all"
                className="hover:text-gray-800 transition-colors"
                target="_blank"
                rel="noopener noreferrer"
              >
                <img
                  src="/icons/linkedin.png"
                  alt="LinkedIn"
                  className="inline-block w-[32px] h-[32px] mr-2 align-text-bottom"
                />
                Cornell GreenClub
              </a>
            </li>
          </ul>
        </div>
        <div>
          <img
            src="/images/project-of-the-year.png"
            alt="pathOS: Sustainability Project of the Year Award 2025"
            className="w-[200px] md:w-auto"
          />
        </div>
      </div>

    </footer>
  );
}
