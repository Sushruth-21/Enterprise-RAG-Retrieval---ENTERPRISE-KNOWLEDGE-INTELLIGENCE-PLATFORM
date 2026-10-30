import React, { Suspense, lazy, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig, AnimatePresence } from 'framer-motion';
import { AppLayout } from '@/components/layout/AppLayout';
import { Initial3DLoader } from '@/components/ui/Initial3DLoader';
import { useSettingsStore } from '@/stores/useSettingsStore';
import { Sparkles, Layers } from 'lucide-react';

// Route-level code-splitting for optimal first contentful paint (FCP)
const DashboardPage = lazy(() =>
  import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage }))
);
const WorkspacePage = lazy(() =>
  import('@/pages/WorkspacePage').then((m) => ({ default: m.WorkspacePage }))
);
const ChatPage = lazy(() =>
  import('@/pages/ChatPage').then((m) => ({ default: m.ChatPage }))
);
const BatchPage = lazy(() =>
  import('@/pages/BatchPage').then((m) => ({ default: m.BatchPage }))
);
const DocumentViewerPage = lazy(() =>
  import('@/pages/DocumentViewerPage').then((m) => ({ default: m.DocumentViewerPage }))
);
const SettingsPage = lazy(() =>
  import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage }))
);
const HealthPage = lazy(() =>
  import('@/pages/HealthPage').then((m) => ({ default: m.HealthPage }))
);
const LoginPage = lazy(() =>
  import('@/pages/LoginPage').then((m) => ({ default: m.LoginPage }))
);
const NotFoundPage = lazy(() =>
  import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage }))
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5,
    },
  },
});

const RouteLoadingFallback: React.FC = () => (
  <div className="h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center p-8 text-center space-y-3 bg-background">
    <div className="h-10 w-10 rounded-xl bg-surface-elevated border border-primary/30 flex items-center justify-center text-primary shadow-sm shadow-primary/20 animate-pulse">
      <Layers className="h-5 w-5" />
    </div>
    <div className="flex items-center gap-2 text-xs text-enterprise-muted font-mono">
      <Sparkles className="h-3.5 w-3.5 text-primary animate-spin" />
      <span>Loading knowledge environment...</span>
    </div>
  </div>
);

export const App: React.FC = () => {
  const { settings } = useSettingsStore();
  const [showInitialLoader, setShowInitialLoader] = useState(true);

  return (
    <QueryClientProvider client={queryClient}>
      {/* Precision 3D Graphical Loader (Only on First Initial Load and Refresh) */}
      <AnimatePresence mode="wait">
        {showInitialLoader && (
          <Initial3DLoader onComplete={() => setShowInitialLoader(false)} />
        )}
      </AnimatePresence>

      <MotionConfig reducedMotion={settings.reducedMotion ? 'always' : 'user'}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<AppLayout />}>
              <Route
                index
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <DashboardPage />
                  </Suspense>
                }
              />
              <Route
                path="workspace"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <WorkspacePage />
                  </Suspense>
                }
              />
              <Route
                path="chat"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <ChatPage />
                  </Suspense>
                }
              />
              <Route
                path="batch"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <BatchPage />
                  </Suspense>
                }
              />
              <Route
                path="document/:id"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <DocumentViewerPage />
                  </Suspense>
                }
              />
              <Route
                path="settings"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <SettingsPage />
                  </Suspense>
                }
              />
              <Route
                path="*"
                element={
                  <Suspense fallback={<RouteLoadingFallback />}>
                    <NotFoundPage />
                  </Suspense>
                }
              />
            </Route>

            {/* Standalone Enterprise Corporate Login & Password Reset Gateway */}
            <Route
              path="/login"
              element={
                <Suspense fallback={<RouteLoadingFallback />}>
                  <LoginPage />
                </Suspense>
              }
            />

            {/* Dedicated Diagnostic Page - Unlinked in frontend, accessible strictly via explicit /health URL */}
            <Route
              path="/health"
              element={
                <Suspense fallback={<RouteLoadingFallback />}>
                  <HealthPage />
                </Suspense>
              }
            />
          </Routes>
        </BrowserRouter>
      </MotionConfig>
    </QueryClientProvider>
  );
};

export default App;
