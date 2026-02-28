'use client';
import Link from 'next/link';
import { useState } from 'react';

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="bg-white shadow-md sticky top-0 z-50 border px-4 md:px-[22px]">
      <div className="w-full flex justify-between items-center p-2 md:p-4">
        {/* Logo */}
        <Link href="/" className="text-gray-800 text-2xl font-bold">
          <img
            className="w-auto h-12 md:h-[82px] object-contain"
            src="/images/logo.png"
            alt="pathOS Logo"
          />
        </Link>

        {/* Hamburger Icon for Mobile */}
        <div className="md:hidden">
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="text-gray-800 focus:outline-none"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              {isOpen ? (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              ) : (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 6h16M4 12h16M4 18h16"
                />
              )}
            </svg>
          </button>
        </div>

        {/* Navigation Links */}
        <div
          className={`${
            isOpen ? 'block' : 'hidden'
          } absolute top-full left-0 right-0 bg-white md:relative md:top-0 md:block md:bg-transparent poppins-regular text-xl`}
        >
          <ul className="flex flex-col md:flex-row md:space-x-[11px] p-4 md:p-0">
            <li>
              <Link
                href="/"
                className="block py-2 px-4 text-gray-700 hover:text-[#034626] transition-colors duration-300 relative after:content-[''] after:absolute after:w-full after:h-[2px] after:bg-[#034626] after:left-0 after:bottom-1 after:scale-x-0 hover:after:scale-x-100 after:transition-transform after:duration-300"
              >
                Home
              </Link>
            </li>
            <li>
              <Link
                href="/explore"
                className="block py-2 px-4 text-gray-700 hover:text-[#034626] transition-colors duration-300 relative after:content-[''] after:absolute after:w-full after:h-[2px] after:bg-[#034626] after:left-0 after:bottom-1 after:scale-x-0 hover:after:scale-x-100 after:transition-transform after:duration-300"
              >
                Explore
              </Link>
            </li>
            <li>
              <Link
                href="/about"
                className="block py-2 px-4 text-gray-700 hover:text-[#034626] transition-colors duration-300 relative after:content-[''] after:absolute after:w-full after:h-[2px] after:bg-[#034626] after:left-0 after:bottom-1 after:scale-x-0 hover:after:scale-x-100 after:transition-transform after:duration-300"
              >
                About Us
              </Link>
            </li>
            <li>
              <Link
                href="/contact"
                className="block py-2 px-4 text-gray-700 hover:text-[#034626] transition-colors duration-300 relative after:content-[''] after:absolute after:w-full after:h-[2px] after:bg-[#034626] after:left-0 after:bottom-1 after:scale-x-0 hover:after:scale-x-100 after:transition-transform after:duration-300"
              >
                Contact
              </Link>
            </li>
          </ul>
        </div>
      </div>
    </nav>
  );
}
