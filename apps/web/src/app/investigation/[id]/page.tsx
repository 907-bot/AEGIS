export const dynamicParams = false;

export async function generateStaticParams() {
  return [];
}

import InvestigationClient from './InvestigationClient';

export default function Page() {
  return <InvestigationClient />;
}
