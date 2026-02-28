import type { Metadata } from 'next';
import { Analytics } from "@vercel/analytics/next";
import localFont from 'next/font/local';
import './globals.css';
import BackendWakeup from './components/BackendWakeup';

const poppins = localFont({
  src: './fonts/Poppins/Poppins-Regular.ttf',
  variable: '--font-poppins-regular',
});

const poppinsBold = localFont({
  src: './fonts/Poppins/Poppins-Bold.ttf',
  variable: '--font-poppins-bold',
});

const poppinsMedium = localFont({
  src: './fonts/Poppins/Poppins-Medium.ttf',
  variable: '--font-poppins-medium',
});

const poppinsExtraBold = localFont({
  src: './fonts/Poppins/Poppins-ExtraBold.ttf',
  variable: '--font-poppins-extrabold',
});

const poppinsSemibold = localFont({
  src: './fonts/Poppins/Poppins-SemiBold.ttf',
  variable: '--font-poppins-semibold',
});

export const metadata: Metadata = {
  title: 'pathOS',
  description: 'Smarter routes, greener future',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      <html lang="en" suppressHydrationWarning>
        <body
          className={`${poppins.variable} ${poppinsBold.variable} ${poppinsMedium.variable} ${poppinsExtraBold.variable} ${poppinsSemibold.variable} antialiased`}
          suppressHydrationWarning
        >
          {children}
          <BackendWakeup />
          <Analytics />
        </body>
      </html>
    </>
  );
}
