import { Suspense } from 'react';
import InvestigationClient from './InvestigationClient';

export default function Page() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-slate-400">Loading...</div>}>
      <InvestigationClient />
    </Suspense>
  );
}
