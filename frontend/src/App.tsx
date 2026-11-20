import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { RootLayout } from './layouts/RootLayout';
import { HomePage } from './pages/HomePage';
import { Loader2 } from 'lucide-react';

import { NativeService } from './services/nativeService';

// Lazy-loaded routes for code-splitting
const WorkspacePage = lazy(() => import('./pages/WorkspacePage').then((m) => ({ default: m.WorkspacePage })));
const HistoryPage = lazy(() => import('./pages/HistoryPage').then((m) => ({ default: m.HistoryPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Fallback spinner for lazy components
const PageLoadingFallback: React.FC = () => (
  <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
    <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
  </div>
);

// Graceful Error Boundary to prevent blank white screens
interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('DocMorph UI caught unhandled render error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[calc(100vh-8rem)] flex-col items-center justify-center px-4 py-16 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-100 text-rose-600 shadow-sm">
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h1 className="mt-4 text-xl font-bold text-slate-900">Document Workspace Notice</h1>
          <p className="mt-2 max-w-md text-xs text-slate-600">
            {this.state.error?.message || 'An unexpected rendering error occurred while loading this view.'}
          </p>
          <div className="mt-6 flex gap-3">
            <button
              onClick={() => window.location.reload()}
              className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow hover:bg-indigo-700"
            >
              Reload Page
            </button>
            <a
              href="/"
              className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
            >
              Back to Home
            </a>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// Protected Route Guard (supports seamless account-free session)
const ProtectedRoute: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { isLoading } = useAuth();

  if (isLoading) {
    return <PageLoadingFallback />;
  }

  return children;
};

export const App: React.FC = () => {
  React.useEffect(() => {
    NativeService.initializeAppUI();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <ErrorBoundary>
            <Suspense fallback={<PageLoadingFallback />}>
              <Routes>
                <Route element={<RootLayout />}>
                  {/* Single Consolidated Home Screen */}
                  <Route path="/" element={<HomePage />} />
                  <Route path="/history" element={<HistoryPage />} />
                  <Route path="/home" element={<Navigate to="/" replace />} />
                  <Route path="/dashboard" element={<Navigate to="/" replace />} />
                  <Route path="/login" element={<Navigate to="/" replace />} />
                  <Route path="/signup" element={<Navigate to="/" replace />} />
                  <Route path="/features" element={<Navigate to="/" replace />} />
                  <Route path="/how-it-works" element={<Navigate to="/" replace />} />

                  {/* Document Workspace */}
                  <Route
                    path="/workspace/:documentId"
                    element={
                      <ProtectedRoute>
                        <WorkspacePage />
                      </ProtectedRoute>
                    }
                  />

                  {/* Fallback */}
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
