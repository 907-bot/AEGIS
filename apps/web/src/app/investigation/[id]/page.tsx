import InvestigationClient from './InvestigationClient';

export const dynamicParams = false;

export async function generateStaticParams() {
  return [];
}

export default function InvestigationPage() {
  return <InvestigationClient />;
}
