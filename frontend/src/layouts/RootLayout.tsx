import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { Footer } from '../components/Footer';
import { FooterBar } from '../components/FooterBar';

export const RootLayout: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 pb-16">
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
      <FooterBar />
    </div>
  );
};


