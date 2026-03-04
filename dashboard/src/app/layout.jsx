import './globals.css';
import Header from '@/components/Header';

const GA_ID = 'G-2YHG89FY0N';

export const metadata = {
  title: 'PolicyEngine TAXSIM — The next chapter of TAXSIM',
  description:
    'PolicyEngine TAXSIM — the next chapter of TAXSIM. Open-source tax calculator with drop-in TAXSIM-35 compatibility, powered by PolicyEngine\'s microsimulation engine.',
  openGraph: {
    title: 'PolicyEngine TAXSIM',
    description:
      'The next chapter of TAXSIM. Open-source, drop-in compatible tax calculator powered by PolicyEngine.',
    url: 'https://policyengine.org/us/taxsim',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'PolicyEngine TAXSIM',
    description:
      'The next chapter of TAXSIM. Open-source, drop-in compatible tax calculator powered by PolicyEngine.',
  },
  icons: {
    icon: '/policyengine.png',
    apple: '/policyengine.png',
  },
  alternates: {
    canonical: 'https://policyengine.org/us/taxsim',
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap"
          rel="stylesheet"
        />
        <script
          async
          src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${GA_ID}');
            `,
          }}
        />
        <script defer src="/_vercel/insights/script.js" />
      </head>
      <body>
        <Header />
        {children}
      </body>
    </html>
  );
}
