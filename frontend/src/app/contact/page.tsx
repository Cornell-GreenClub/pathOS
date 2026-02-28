'use client';

import { useState } from 'react';
import { Send, CheckCircle } from 'lucide-react';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';
import { Poppins } from 'next/font/google';

const poppins = Poppins({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
});

interface FormData {
  fullName: string;
  email: string;
  message: string;
}

const ContactInput = ({ 
  type, 
  name, 
  value, 
  onChange, 
  placeholder, 
  required
}: { 
  type: string;
  name: keyof FormData;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  placeholder: string;
  required?: boolean;
}) => {
  const isTextArea = type === 'textarea';
  const InputComponent = isTextArea ? 'textarea' : 'input';
  const inputId = `contact-${name}`;
  
  return (
    <div>
      <label htmlFor={inputId} className="sr-only">
        {placeholder}
      </label>
      <InputComponent
        id={inputId}
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        rows={isTextArea ? 4 : undefined}
        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#034626] text-gray-700 placeholder-gray-500 text-base poppins-regular bg-gray-50/50"
        style={isTextArea ? { resize: 'none', overflowY: 'auto' } : undefined}
      />
    </div>
  );
};

export default function ContactPage() {
  const [formData, setFormData] = useState<FormData>({
    fullName: '',
    email: '',
    message: '',
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState('');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitMessage('');

    // Uses the user-provided Google Apps Script Web App URL
    const scriptURL =
      'https://script.google.com/macros/s/AKfycbxghnUhgnHFf-SY6mJjQX3HhbXmnQravY-pTzKzwmcJF8rqtpX7Ftx0IhGiFPHVcvam/exec';

    try {
      const formDataToSend = new FormData();
      formDataToSend.append('name', formData.fullName);
      formDataToSend.append('email', formData.email);
      formDataToSend.append('message', formData.message);

      const response = await fetch(scriptURL, {
        method: 'POST',
        body: formDataToSend,
      });

      if (response.ok) {
        setSubmitMessage('Message sent successfully!');
        setFormData({ fullName: '', email: '', message: '' });
        setTimeout(() => {
          setSubmitMessage('');
        }, 5000);
      } else {
        setSubmitMessage('Failed to send message. Please try again.');
        console.error('Response Error:', response.status);
      }
    } catch (error) {
      console.error('Fetch Error!', error);
      setSubmitMessage('Failed to send message. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <main className={`min-h-screen bg-white ${poppins.className}`}>
        <Navbar />
        <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-green-50 p-2 md:p-6">
          <div className="max-w-7xl mx-auto grid md:grid-cols-2 gap-24 items-start mt-16 pb-16">
            <div className="w-full flex flex-col h-full mt-[20px]">
              <div>
                <div className="aspect-[3/2] w-full relative overflow-hidden rounded-lg transform hover:scale-105 transition-transform duration-300">
                  <img
                    src="/images/road.jpeg"
                    alt="Winding road through forest"
                    className="w-full h-full object-cover rounded-lg shadow-2xl"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-gray-900 via-transparent to-transparent opacity-60"></div>
                </div>
                <p className="mt-4 text-base text-gray-700 poppins-regular font-normal">
                  Have a question or want to get in touch? Just fill out the form or{' '}
                  <a href="mailto:[EMAIL_ADDRESS]" className="pathos-green pathos-green-hover underline poppins-regular">
                    email us.
                  </a>
                  {' '}We&apos;d love to hear from you!   
                </p>
              </div>
            </div>

            <div className="w-full flex flex-col">
              <h1 className="text-[52px] poppins-semibold mb-4 text-gray-900">Contact Us</h1>
              <form className="space-y-6" onSubmit={handleSubmit}>
                <ContactInput
                  type="text"
                  name="fullName"
                  value={formData.fullName}
                  onChange={handleChange}
                  placeholder="Name*"
                  required
                />
                <ContactInput
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="Email*"
                  required
                />
                <ContactInput
                  type="textarea"
                  name="message"
                  value={formData.message}
                  onChange={handleChange}
                  placeholder="Message*"
                  required
                />



                {(isSubmitting || submitMessage) ? (
                  <div
                    className={`w-full flex items-center gap-3 p-4 rounded-xl shadow-sm text-sm poppins-medium ${
                      isSubmitting
                        ? 'bg-gray-50 text-gray-800 border border-gray-200'
                        : submitMessage.includes('successfully')
                        ? 'bg-[#Ecfdf3] text-[#034626] border border-[#d1fadf]'
                        : 'bg-red-50 text-red-800 border border-red-200'
                    }`}
                  >
                    {isSubmitting ? (
                      <div className="animate-spin rounded-full h-5 w-5 border-2 border-gray-800 border-t-transparent flex-shrink-0"></div>
                    ) : submitMessage.includes('successfully') ? (
                      <CheckCircle className="h-5 w-5 flex-shrink-0" />
                    ) : (
                      <Send className="h-5 w-5 flex-shrink-0" />
                    )}
                    <span>{isSubmitting ? 'Submitting...' : submitMessage}</span>
                  </div>
                ) : (
                  <button
                    type="submit"
                    className="bg-[#034626] hover:bg-[#023219] text-white px-8 py-3 rounded-2xl text-base poppins-bold transform transition-all hover:scale-105 inline-flex items-center justify-center gap-2"
                  >
                    <span>Submit</span>
                    <Send className="h-4 w-4 ml-1" />
                  </button>
                )}
              </form>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}