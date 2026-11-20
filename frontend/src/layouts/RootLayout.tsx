import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { CompactHeader } from '../components/CompactHeader';
import { FloatingGlassNavigation } from '../components/FloatingGlassNavigation';

export const RootLayout: React.FC = () => {
  const location = useLocation();
  const isWorkspace = location.pathname.startsWith('/workspace');

  return (
    <div className={`w-full min-h-screen flex flex-col bg-surface text-on-surface selection:bg-primary-fixed selection:text-primary ${isWorkspace ? 'pb-0' : 'pb-32'}`}>
      {!isWorkspace && <CompactHeader />}
      <main className="flex-1 flex flex-col w-full">
        <Outlet />
      </main>
      {/* Floating Liquid Glass Navigation on main screens */}
      {!isWorkspace && <FloatingGlassNavigation />}
    </div>
  );
};
