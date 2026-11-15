import React from 'react';
import { FileText, Shield, Heart } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          <div className="md:col-span-2 space-y-4">
            <div className="flex items-center gap-2 text-brand-600">
              <FileText className="h-6 w-6" />
              <span className="text-lg font-bold text-slate-900 tracking-tight">DocMorph</span>
            </div>
            <p className="text-sm text-slate-600 max-w-md leading-relaxed">
              Every document, personalized. The intelligent document personalization SaaS engineered for students to update lab practical footers with vector-perfect accuracy and zero layout distortion.
            </p>
            <div className="flex items-center gap-2 text-xs text-slate-500 pt-2">
              <Shield className="h-4 w-4 text-emerald-600" />
              <span>Isolated private storage &bull; Deterministic redaction &bull; Read-only immutability</span>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-3">Product</h4>
            <ul className="space-y-2 text-sm text-slate-600">
              <li><Link to="/#features" className="hover:text-brand-600 transition-colors">Core Features</Link></li>
              <li><Link to="/#how-it-works" className="hover:text-brand-600 transition-colors">How It Works</Link></li>
              <li><Link to="/#supported-fields" className="hover:text-brand-600 transition-colors">Supported Fields</Link></li>
              <li><Link to="/dashboard" className="hover:text-brand-600 transition-colors">User Dashboard</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-3">Security & Privacy</h4>
            <ul className="space-y-2 text-sm text-slate-600">
              <li><Link to="/#privacy" className="hover:text-brand-600 transition-colors">Data Privacy Policy</Link></li>
              <li><Link to="/#faq" className="hover:text-brand-600 transition-colors">Frequently Asked Questions</Link></li>
              <li><span className="text-slate-400">Zero AI Training on User Files</span></li>
              <li><span className="text-slate-400">Encrypted in Transit & Rest</span></li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-4">
          <p>&copy; {new Date().getFullYear()} DocMorph SaaS. All rights reserved.</p>
          <p className="flex items-center gap-1">
            Engineered with <Heart className="h-3.5 w-3.5 text-rose-500 fill-rose-500" /> for Academic Integrity & Productivity
          </p>
        </div>
      </div>
    </footer>
  );
};

