declare module 'pdfkit' {
  // Minimal ambient declaration so TypeScript build succeeds in production
  // Detailed types are available via @types/pdfkit during development, but
  // Render may install only dependencies. This file provides a safe fallback.
  const PDFDocument: any;
  export default PDFDocument;
}
