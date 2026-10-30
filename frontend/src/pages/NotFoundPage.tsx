import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { HelpCircle } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center p-8 text-center space-y-4">
      <HelpCircle className="h-12 w-12 text-primary opacity-60 animate-pulse-subtle" />
      <h1 className="text-3xl font-bold text-white">404 — Page Not Found</h1>
      <p className="text-sm text-enterprise-muted max-w-md">
        The requested enterprise knowledge view does not exist.
      </p>
      <Link to="/">
        <Button>Return to Dashboard</Button>
      </Link>
    </div>
  );
};
