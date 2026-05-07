import type { Metadata } from 'next';
import '../styles/globals.css';
import { Toaster } from 'react-hot-toast';

export const metadata: Metadata = {
  title: 'AEGIS — Autonomous Strategic Intelligence',
  description: 'Multi-agent AI platform for institutional-grade strategic intelligence',
  keywords: ['AI', 'intelligence', 'due diligence', 'competitive analysis'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: { background: '#1e293b', color: '#f1f5f9', border: '1px solid #334155' },
            duration: 4000,
          }}
        />
      </body>
    </html>
  );
}
