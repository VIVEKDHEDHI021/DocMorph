import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileText,
  Sparkles,
  ArrowRight,
  Shield,
  Layers,
  Zap,
  CheckCircle2,
  Lock,
  ChevronDown,
  ChevronUp,
  FileCheck,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, initializeAnonymousSession } = useAuth();
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const handleStartPersonalizing = async () => {
    if (!user) {
      await initializeAnonymousSession();
    }
    navigate('/dashboard');
  };

  const faqs = [
    {
      q: 'Does DocMorph convert my PDF into Microsoft Word?',
      a: 'No! DocMorph operates directly on native PDF streams using PyMuPDF vector redactions. Your document never leaves the PDF format, ensuring fonts, margins, formulas, and diagrams remain 100% intact.',
    },
    {
      q: 'Will other students or teachers be able to extract the old name?',
      a: 'No. Unlike basic editors that cover text with a white rectangle, DocMorph permanently removes the target characters from the content stream, making old values completely unextractable.',
    },
    {
      q: 'What happens if my replacement name is much longer than the original?',
      a: 'DocMorph calculates horizontal clearance before adjacent delimiters (like "|" or next field labels) and adaptively scales the font size down to 6.0pt. If the text cannot fit without collision, DocMorph alerts you rather than corrupting the layout.',
    },
    {
      q: 'Are my uploaded documents safe and private?',
      a: 'Yes. Documents are kept in private local storage behind strict ownership-authorization checks. Files are never indexed or exposed over static public routes.',
    },
    {
      q: 'Which fields can I personalize?',
      a: 'Currently, DocMorph detects and personalizes Student Name, Enrollment Number, Roll Number, and Student ID across all pages.',
    },
  ];

  return (
    <div className="space-y-24 pb-16">
      {/* HERO SECTION */}
      <section className="relative overflow-hidden pt-12 md:pt-20">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(45rem_50rem_at_top,theme(colors.brand.100),theme(colors.slate.50))] opacity-60" />
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center space-y-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50/80 px-4 py-1.5 text-xs font-semibold text-brand-700 shadow-sm backdrop-blur-sm">
            <Sparkles className="h-4 w-4 text-brand-600" />
            <span>Document Personalization SaaS &bull; Phase 4 Released</span>
          </div>

          <h1 className="mx-auto max-w-4xl text-4xl font-extrabold tracking-tight text-slate-900 sm:text-6xl sm:leading-tight">
            Every document,{' '}
            <span className="bg-gradient-to-r from-brand-600 via-indigo-600 to-indigo-800 bg-clip-text text-transparent">
              personalized.
            </span>
          </h1>

          <p className="mx-auto max-w-2xl text-lg text-slate-600 leading-relaxed">
            Upload shared academic practical lab manuals and personalize footer credentials — Student Name, Enrollment No, Roll No, and Student ID — without converting to Word or breaking vector diagrams.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-2">
            <button
              onClick={handleStartPersonalizing}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-7 py-3.5 text-base font-semibold text-white shadow-lg shadow-brand-500/25 hover:bg-brand-700 transition-all focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
            >
              Personalize Your PDF
              <ArrowRight className="h-4 w-4" />
            </button>
            <Link
              to="/signup"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-7 py-3.5 text-base font-semibold text-slate-700 shadow-sm hover:bg-slate-50 hover:text-slate-900 transition-all"
            >
              Create Free Account
            </Link>
          </div>

          {/* INTERACTIVE BEFORE & AFTER PREVIEW CARD */}
          <div className="pt-8 max-w-4xl mx-auto">
            <div className="rounded-2xl border border-slate-200 bg-white shadow-2xl p-6 sm:p-8 text-left">
              <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-6">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-rose-400" />
                  <div className="h-3 w-3 rounded-full bg-amber-400" />
                  <div className="h-3 w-3 rounded-full bg-emerald-400" />
                  <span className="ml-2 text-xs font-mono text-slate-500">practical_manual_CS301.pdf</span>
                </div>
                <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200/60">
                  Precision Vector Redaction
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Original Footer */}
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-2">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Original Source Footer</span>
                  <div className="p-3 rounded-lg bg-white border border-slate-200 font-mono text-xs text-slate-800 shadow-sm overflow-x-auto">
                    Student Name: <span className="text-rose-600 bg-rose-50 px-1 rounded font-bold">Rahul Patel</span> | Enrollment No: <span className="text-rose-600 bg-rose-50 px-1 rounded font-bold">2300012345</span> | Roll No: <span className="text-rose-600 bg-rose-50 px-1 rounded font-bold">25</span>
                  </div>
                  <p className="text-[11px] text-slate-500">Shared practical manual from class representative</p>
                </div>

                {/* Personalized Footer */}
                <div className="p-4 rounded-xl border border-brand-200 bg-brand-50/30 space-y-2">
                  <span className="text-xs font-bold text-brand-700 uppercase tracking-wider">Personalized Output (DocMorph)</span>
                  <div className="p-3 rounded-lg bg-white border border-brand-200 font-mono text-xs text-slate-900 shadow-sm overflow-x-auto">
                    Student Name: <span className="text-emerald-600 bg-emerald-50 px-1 rounded font-bold">Vivek Dhedhi</span> | Enrollment No: <span className="text-emerald-600 bg-emerald-50 px-1 rounded font-bold">2400015678</span> | Roll No: <span className="text-emerald-600 bg-emerald-50 px-1 rounded font-bold">42</span>
                  </div>
                  <p className="text-[11px] text-emerald-600 font-medium flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" />
                    Updated across all 5 pages &bull; 100% typography matched
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how-it-works" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center space-y-3 mb-16">
          <h2 className="text-xs font-bold uppercase tracking-wider text-brand-600">Workflow</h2>
          <h3 className="text-3xl font-extrabold text-slate-900 tracking-tight">How DocMorph Works</h3>
          <p className="text-slate-600 max-w-xl mx-auto text-sm">
            Four simple steps to transform generic practical files into verified, personalized submissions.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {[
            {
              step: '01',
              title: 'Upload PDF',
              desc: 'Drag & drop your lab manual. Fast validation verifies signature, page count, and encryption.',
            },
            {
              step: '02',
              title: 'Intelligent Detection',
              desc: 'Our engine identifies footer regions and extracts student fields with explainable confidence.',
            },
            {
              step: '03',
              title: 'Review & Personalize',
              desc: 'Confirm or correct values. Enter your personal credentials with automatic clearance calculation.',
            },
            {
              step: '04',
              title: 'Verify & Download',
              desc: 'Independent post-replacement audit confirms old values are purged. Download verified PDF.',
            },
          ].map((item) => (
            <div key={item.step} className="relative p-6 rounded-2xl border border-slate-200/80 bg-white shadow-sm space-y-3">
              <span className="text-3xl font-black text-brand-500/30">{item.step}</span>
              <h4 className="text-base font-bold text-slate-900">{item.title}</h4>
              <p className="text-xs text-slate-600 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* KEY FEATURES */}
      <section id="features" className="bg-slate-100/70 py-20 border-y border-slate-200/60">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 space-y-12">
          <div className="text-center space-y-3">
            <h2 className="text-xs font-bold uppercase tracking-wider text-brand-600">Engineering Quality</h2>
            <h3 className="text-3xl font-extrabold text-slate-900 tracking-tight">Engineered for Academic Precision</h3>
            <p className="text-slate-600 max-w-xl mx-auto text-sm">
              Built on PyMuPDF and Pydantic v2 to eliminate the formatting corruption caused by standard PDF-to-Word conversions.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-sm space-y-3">
              <div className="h-10 w-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
                <FileCheck className="h-5 w-5" />
              </div>
              <h4 className="text-base font-bold text-slate-900">True Vector Redaction</h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                Purges character glyphs permanently from the PDF content stream rather than covering with superficial white boxes.
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-sm space-y-3">
              <div className="h-10 w-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <Zap className="h-5 w-5" />
              </div>
              <h4 className="text-base font-bold text-slate-900">Adaptive Font Fitting</h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                Calculates horizontal clearance before neighboring delimiters ("|") and scales font down to 6.0pt, preventing text overlap.
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-sm space-y-3">
              <div className="h-10 w-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <Shield className="h-5 w-5" />
              </div>
              <h4 className="text-base font-bold text-slate-900">Read-Only Immutability</h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                Source PDFs remain strictly untouched with pre/post SHA-256 verification. Outputs are generated into isolated files.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* SUPPORTED FIELDS TABLE */}
      <section id="supported-fields" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center space-y-3 mb-12">
          <h2 className="text-xs font-bold uppercase tracking-wider text-brand-600">Supported Metadata</h2>
          <h3 className="text-3xl font-extrabold text-slate-900 tracking-tight">Recognized Student Fields</h3>
          <p className="text-slate-600 max-w-xl mx-auto text-sm">
            DocMorph recognizes student credentials across diverse formatting, abbreviation, and punctuation conventions.
          </p>
        </div>

        <div className="max-w-4xl mx-auto rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-700 uppercase">
                <tr>
                  <th className="px-6 py-4">Field Type</th>
                  <th className="px-6 py-4">Supported Variations</th>
                  <th className="px-6 py-4">Smart Filtering</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                <tr>
                  <td className="px-6 py-4 font-bold text-slate-900">Student Name</td>
                  <td className="px-6 py-4 text-slate-600">"Student Name", "Candidate Name", "Name of Student", "Learner Name", "Student:"</td>
                  <td className="px-6 py-4 text-slate-500">Excludes "File Name", "Faculty Name", "Algorithm Name"</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 font-bold text-slate-900">Enrollment Number</td>
                  <td className="px-6 py-4 text-slate-600">"Enrollment No", "Enrollment Number", "Enrolment No", "Enroll No", "Enrollment#"</td>
                  <td className="px-6 py-4 text-slate-500">Rejects generic non-enrollment numbers</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 font-bold text-slate-900">Roll Number</td>
                  <td className="px-6 py-4 text-slate-600">"Roll No", "Roll Number", "Roll No.", "Roll#", "Class Roll No"</td>
                  <td className="px-6 py-4 text-slate-500">Scoped strictly to footer numeric tokens</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 font-bold text-slate-900">Student ID</td>
                  <td className="px-6 py-4 text-slate-600">"Student ID", "StudentID", "Stud ID", "Student Identification Number"</td>
                  <td className="px-6 py-4 text-slate-500">Excludes "Document ID", "Section ID", "Tx ID"</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* PRIVACY & SECURITY */}
      <section id="privacy" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-900 to-indigo-950 p-8 sm:p-12 text-white">
          <div className="max-w-2xl space-y-4">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-400/30">
              <Lock className="h-3.5 w-3.5" />
              Enterprise-Grade Security Standards
            </div>
            <h3 className="text-3xl font-extrabold tracking-tight">Private, Isolated & Ephemeral</h3>
            <p className="text-slate-300 text-sm leading-relaxed">
              We never sell your data, train AI models on your coursework, or make files publicly accessible. Every upload is isolated in private local storage and accessible only by you.
            </p>
            <div className="pt-4 flex flex-wrap items-center gap-6 text-xs text-slate-400">
              <span className="flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Per-user document ownership</span>
              <span className="flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Path traversal defense</span>
              <span className="flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Zero cloud API dependencies</span>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ SECTION */}
      <section id="faq" className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <div className="text-center space-y-3 mb-12">
          <h2 className="text-xs font-bold uppercase tracking-wider text-brand-600">Help & Support</h2>
          <h3 className="text-3xl font-extrabold text-slate-900 tracking-tight">Frequently Asked Questions</h3>
        </div>

        <div className="space-y-4">
          {faqs.map((faq, idx) => (
            <div key={idx} className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
              <button
                onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                className="w-full flex items-center justify-between p-5 text-left text-sm font-bold text-slate-900 hover:text-brand-600 transition-colors"
              >
                <span>{faq.q}</span>
                {openFaq === idx ? (
                  <ChevronUp className="h-4 w-4 text-slate-400" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                )}
              </button>
              {openFaq === idx && (
                <div className="px-5 pb-5 text-xs text-slate-600 leading-relaxed border-t border-slate-100 pt-3">
                  {faq.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};

