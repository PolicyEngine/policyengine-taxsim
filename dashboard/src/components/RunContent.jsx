'use client';

import React from 'react';
import Link from 'next/link';
import {
  IconArrowRight,
  IconHome,
  IconBook,
  IconBrandGithub,
} from '@tabler/icons-react';
import CsvRunner from './CsvRunner';

const RunContent = () => {
  return (
    <div className="min-h-screen bg-white">
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-14">
          <div className="flex items-center gap-2 text-gray-900 font-semibold text-lg">
            Web Runner
          </div>
          <div className="flex items-center gap-1">
            <Link
              href="/"
              className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition"
            >
              <IconHome size={16} />
              Home
            </Link>
            <span className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium text-primary-600 bg-primary-50">
              Web Runner
            </span>
            <Link
              href="/documentation"
              className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition"
            >
              <IconBook size={16} />
              Documentation
            </Link>
            <a
              href="https://github.com/PolicyEngine/policyengine-taxsim"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition"
            >
              <IconBrandGithub size={16} />
              GitHub
            </a>
          </div>
        </div>
      </nav>

      <section className="py-16 px-6">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-3xl md:text-4xl font-bold text-secondary-900 text-center mb-4">
            Run the emulator in the web
          </h1>
          <p className="text-gray-500 text-center text-lg mb-10 max-w-2xl mx-auto">
            Upload a TAXSIM-format CSV and get results instantly — no installation required.
          </p>
          <CsvRunner />
          <div className="text-center mt-10">
            <Link
              href="/documentation"
              className="inline-flex items-center gap-1.5 text-primary-500 hover:text-primary-600 font-medium transition"
            >
              View input variable documentation
              <IconArrowRight size={16} />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default RunContent;
