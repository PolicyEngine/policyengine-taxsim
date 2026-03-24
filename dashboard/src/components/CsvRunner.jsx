'use client';

import React, { useState, useRef, useCallback } from 'react';
import { assetUrl } from '../utils/basePath';
import {
  IconUpload,
  IconDownload,
  IconX,
  IconLoader2,
  IconFileTypeCsv,
  IconAlertCircle,
  IconMail,
  IconCheck,
  IconDatabase,
} from '@tabler/icons-react';

const API_URL = process.env.NEXT_PUBLIC_TAXSIM_API_URL || '';

const SAMPLE_CSV = `taxsimid,year,state,mstat,depx,pwages,swages,page,sage
1,2024,5,2,2,80000,50000,40,38
2,2024,33,1,0,120000,0,35,0
3,2024,44,2,1,60000,40000,30,28`;

// Pre-built datasets available for download from /public
const SAMPLE_DATASETS = [
  {
    id: 'sample_3',
    label: '3 households',
    description: 'Minimal test file with 3 example households',
    file: null,  // uses inline SAMPLE_CSV
  },
  {
    id: 'sample_ecps_2024',
    label: 'Enhanced CPS 2024 (916 households)',
    description: 'Representative sample from the Enhanced Current Population Survey — diverse incomes, filing statuses, and all 50 states',
    file: 'sample_ecps_2024.csv',
  },
];

const fmt = (n) => Number(n).toLocaleString();

const KNOWN_COLUMNS = new Set([
  'taxsimid', 'year', 'state', 'mstat', 'page', 'sage',
  'dependent_exemption', 'depx', 'pwages', 'swages',
  'psemp', 'ssemp', 'dividends', 'intrec', 'stcg', 'ltcg',
  'otherprop', 'nonprop', 'pensions', 'gssi',
  'pui', 'sui', 'transfers', 'rentpaid', 'proptax',
  'otheritem', 'childcare', 'mortgage', 'scorp',
  'pbusinc', 'pprofinc', 'idtl',
]);

const CsvRunner = () => {
  const [inputCsv, setInputCsv] = useState('');
  const [outputCsv, setOutputCsv] = useState('');
  const [fileName, setFileName] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState('');
  const [rowCount, setRowCount] = useState(0);
  const [resultRows, setResultRows] = useState(0);
  const [idtl, setIdtl] = useState('0');
  const [progress, setProgress] = useState(null);
  const [email, setEmail] = useState('');
  const [emailSent, setEmailSent] = useState(false);
  const [emailSending, setEmailSending] = useState(false);
  const [subscribeToUpdates, setSubscribeToUpdates] = useState(true);
  const [warnings, setWarnings] = useState([]);
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const parseCsvRowCount = (csv) => {
    const lines = csv.trim().split('\n');
    return Math.max(0, lines.length - 1);
  };

  const handleFileContent = useCallback((content, name) => {
    setInputCsv(content);
    setFileName(name);
    setRowCount(parseCsvRowCount(content));
    setOutputCsv('');
    setError('');
    setProgress(null);
    setEmailSent(false);

    // Check for unrecognized columns immediately
    const header = content.trim().split('\n')[0];
    if (header) {
      const cols = header.split(',').map((c) => c.trim());
      const unknown = cols.filter((c) => !KNOWN_COLUMNS.has(c));
      if (unknown.length > 0) {
        setWarnings([
          `Unrecognized column${unknown.length > 1 ? 's' : ''}: ${unknown.join(', ')}. ` +
            'These will be ignored. See the documentation for valid input variables.',
        ]);
      } else {
        setWarnings([]);
      }
    }
  }, []);

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => handleFileContent(ev.target.result, file.name);
    reader.readAsText(file);
  };

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => handleFileContent(ev.target.result, file.name);
      reader.readAsText(file);
    },
    [handleFileContent]
  );

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const [loadingDataset, setLoadingDataset] = useState(null);

  const loadSampleDataset = async (dataset) => {
    if (dataset.file === null) {
      // Inline sample
      handleFileContent(SAMPLE_CSV, 'sample.csv');
      return;
    }
    setLoadingDataset(dataset.id);
    try {
      const res = await fetch(assetUrl(`/${dataset.file}`));
      if (!res.ok) throw new Error(`Failed to load ${dataset.file}`);
      const text = await res.text();
      handleFileContent(text, dataset.file);
    } catch (err) {
      setError(`Failed to load sample dataset: ${err.message}`);
    } finally {
      setLoadingDataset(null);
    }
  };

  const clearInput = () => {
    setInputCsv('');
    setOutputCsv('');
    setFileName('');
    setRowCount(0);
    setResultRows(0);
    setError('');
    setProgress(null);
    setEmailSent(false);
    setWarnings([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const runTaxsim = async () => {
    if (!inputCsv.trim()) return;
    if (!API_URL) {
      setError('API server URL is not configured (NEXT_PUBLIC_TAXSIM_API_URL).');
      return;
    }
    setIsRunning(true);
    setError('');
    setOutputCsv('');
    setWarnings([]);
    setProgress(null);

    try {
      const payload = JSON.stringify({
        csv: inputCsv,
        disable_salt: true,
        idtl: parseInt(idtl, 10),
      });

      // Try SSE streaming first for real-time progress, fall back to plain POST
      try {
        const res = await fetch(`${API_URL}/run/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
        });

        if (!res.ok) throw new Error('stream-fallback');

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop();

          for (const line of lines) {
            const match = line.match(/^data: (.+)$/m);
            if (!match) continue;
            const evt = JSON.parse(match[1]);

            if (evt.type === 'progress') {
              setProgress({
                chunks_done: evt.chunks_done,
                total_chunks: evt.total_chunks,
                rows_done: evt.rows_done,
                total_rows: evt.total_rows,
              });
            } else if (evt.type === 'result') {
              setOutputCsv(evt.csv);
              setResultRows(evt.rows_processed);
              if (evt.warnings) setWarnings(evt.warnings);
              setProgress(null);
            } else if (evt.type === 'error') {
              throw new Error(evt.error);
            }
          }
        }
      } catch (streamErr) {
        if (streamErr.message !== 'stream-fallback') throw streamErr;

        const res = await fetch(`${API_URL}/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || body.error || `Server error (${res.status})`);
        }

        const data = await res.json();
        if (data.error) throw new Error(data.error);
        setOutputCsv(data.csv);
        setResultRows(data.rows_processed);
        if (data.warnings) setWarnings(data.warnings);
      }
    } catch (err) {
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        setError(
          'Cannot reach the API server. The server may be starting up — please try again in a few seconds.'
        );
      } else {
        setError(err.message);
      }
    } finally {
      setIsRunning(false);
      setProgress(null);
    }
  };

  const sendViaEmail = async () => {
    if (!isValidEmail || !inputCsv.trim()) return;
    setEmailSending(true);
    setError('');

    try {
      const url = `${API_URL}/run/email`;
      // Fire-and-forget: don't await the response to avoid deadlocking
      // the single uvicorn worker (background task + stream = deadlock)
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          csv: inputCsv,
          email: email.trim(),
          filename: fileName || 'input.csv',
          disable_salt: true,
          idtl: parseInt(idtl, 10),
          subscribe: subscribeToUpdates,
        }),
      }).catch(() => {}); // Silently ignore email errors

      setEmailSent(true);
      setEmailSending(false);
      // Kick off the browser run immediately
      runTaxsim();
    } catch (err) {
      setError(err.message);
      setEmailSending(false);
    }
  };

  const downloadOutput = () => {
    if (!outputCsv) return;
    const blob = new Blob([outputCsv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName ? fileName.replace(/\.[^.]+$/, '_output.csv') : 'output.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const previewLines = (csv, max = 6) => {
    const lines = csv.trim().split('\n');
    const shown = lines.slice(0, max);
    const remaining = lines.length - max;
    return { shown, remaining: remaining > 0 ? remaining : 0 };
  };

  const progressPct = progress
    ? Math.round((progress.rows_done / progress.total_rows) * 100)
    : 0;

  const isValidEmail = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());

  return (
    <div className="max-w-4xl mx-auto">
      {/* Upload area */}
      {!inputCsv ? (
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
            isDragging
              ? 'border-primary-500 bg-primary-500/5'
              : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.txt"
            onChange={handleFileSelect}
            className="hidden"
          />
          <IconUpload size={40} className="mx-auto mb-4 text-gray-400" />
          <p className="text-lg font-medium text-secondary-900 mb-1">
            Drop a CSV file here or click to browse
          </p>
          <p className="text-sm text-gray-400">
            TAXSIM-format CSV with columns like taxsimid, year, state, mstat, pwages, etc.
          </p>

          {/* Sample datasets */}
          <div
            onClick={(e) => e.stopPropagation()}
            className="mt-6 pt-5 border-t border-gray-200"
          >
            <p className="text-sm font-medium text-gray-500 mb-3">Or try a sample dataset</p>
            <div className="flex flex-col sm:flex-row gap-2 justify-center">
              {SAMPLE_DATASETS.map((ds) => (
                <button
                  key={ds.id}
                  onClick={() => loadSampleDataset(ds)}
                  disabled={loadingDataset !== null}
                  className="group relative inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-white text-gray-700 border border-gray-200 hover:border-primary-400 hover:bg-primary-50 transition disabled:opacity-50"
                >
                  {loadingDataset === ds.id ? (
                    <IconLoader2 size={16} className="animate-spin text-primary-500" />
                  ) : (
                    <IconDatabase size={16} className="text-gray-400 group-hover:text-primary-500" />
                  )}
                  {ds.label}
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-secondary-900 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition pointer-events-none whitespace-nowrap z-10 max-w-xs text-center">
                    {ds.description}
                    <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-secondary-900" />
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Input file info */}
          <div className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3">
            <div className="flex items-center gap-3">
              <IconFileTypeCsv size={24} className="text-primary-500" />
              <div>
                <p className="font-medium text-secondary-900">{fileName}</p>
                <p className="text-sm text-gray-400">
                  {fmt(rowCount)} {rowCount === 1 ? 'household' : 'households'}
                </p>
              </div>
            </div>
            <button
              onClick={clearInput}
              className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-400 hover:text-gray-600 transition"
              title="Clear"
            >
              <IconX size={18} />
            </button>
          </div>

          {/* Warnings (e.g. unrecognized columns) */}
          {warnings.length > 0 && (
            <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
              <IconAlertCircle size={18} className="text-amber-500 flex-shrink-0" />
              <div className="text-sm text-amber-700">
                {warnings.map((w, i) => (
                  <p key={i}>{w}</p>
                ))}
              </div>
            </div>
          )}

          {/* Output detail options */}
          <div className="bg-gray-50 rounded-lg px-5 py-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium text-gray-700 min-w-[100px]">Output detail</span>
              <div className="flex flex-wrap gap-2">
                {[
                  { value: '0', label: 'Standard', tip: 'Key tax amounts: federal & state tax, FICA, marginal rates' },
                  { value: '2', label: 'Full', tip: 'All line items: AGI, taxable income, credits, deductions, AMT, and more (35+ columns)' },
                ].map(({ value, label, tip }) => (
                  <div key={value} className="relative group">
                    <button
                      onClick={() => setIdtl(value)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                        idtl === value
                          ? 'bg-primary-500 text-white'
                          : 'bg-white text-gray-500 hover:bg-gray-100 border border-gray-200'
                      }`}
                    >
                      {label}
                    </button>
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-secondary-900 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition pointer-events-none whitespace-nowrap z-10">
                      {tip}
                      <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-secondary-900" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Input preview */}
          <div className="bg-secondary-900 rounded-lg overflow-hidden">
            <div className="bg-secondary-800 px-4 py-2">
              <span className="text-gray-400 text-sm font-mono">Input preview</span>
            </div>
            <pre className="p-4 text-sm text-gray-100 font-mono overflow-x-auto leading-relaxed">
              {(() => {
                const { shown, remaining } = previewLines(inputCsv);
                return (
                  <>
                    {shown.join('\n')}
                    {remaining > 0 && (
                      <span className="text-gray-500">{'\n'}... {fmt(remaining)} more rows</span>
                    )}
                  </>
                );
              })()}
            </pre>
          </div>

          {/* Email — primary action */}
          <div className="border border-gray-200 rounded-xl px-6 py-5 space-y-4">
            <div className="text-center">
              <h3 className="text-base font-semibold text-secondary-900">
                Get your tax calculation results via email
              </h3>
              <p className="text-sm text-gray-500 mt-1">
                Enter your email and we&apos;ll send the results as a CSV attachment when processing completes.
              </p>
            </div>

            {emailSent ? (
              <div className="flex items-center justify-center gap-2 text-green-600 bg-green-50 rounded-lg px-4 py-3">
                <IconCheck size={18} />
                <span className="text-sm font-medium">
                  Results will be emailed to {email} when processing completes.
                </span>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2 max-w-md mx-auto">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                    className="flex-1 px-3 py-2.5 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                  <button
                    onClick={sendViaEmail}
                    disabled={!isValidEmail || emailSending || isRunning}
                    className={`inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-sm font-semibold transition ${
                      isValidEmail && !emailSending && !isRunning
                        ? 'bg-primary-500 text-white hover:bg-primary-600'
                        : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    }`}
                  >
                    {emailSending ? (
                      <IconLoader2 size={16} className="animate-spin" />
                    ) : (
                      <IconMail size={16} />
                    )}
                    Send results
                  </button>
                </div>

                <label className="flex items-center justify-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={subscribeToUpdates}
                    onChange={(e) => setSubscribeToUpdates(e.target.checked)}
                    className="rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                  />
                  <span className="text-xs text-gray-500">
                    Keep me updated on PolicyEngine models and tools
                  </span>
                </label>
              </>
            )}
          </div>

          {/* Or download directly */}
          <div className="flex items-center gap-3 justify-center">
            <div className="h-px bg-gray-200 flex-1" />
            <span className="text-xs text-gray-400 uppercase tracking-wide">or</span>
            <div className="h-px bg-gray-200 flex-1" />
          </div>

          <div className="flex justify-center">
            <button
              onClick={runTaxsim}
              disabled={isRunning}
              className={`inline-flex items-center gap-2 px-6 py-2.5 rounded-lg font-medium transition ${
                isRunning
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              {isRunning ? (
                <>
                  <IconLoader2 size={16} className="animate-spin" />
                  Processing {fmt(rowCount)} {rowCount === 1 ? 'household' : 'households'}...
                </>
              ) : (
                <>
                  <IconDownload size={16} />
                  Run and download in browser
                </>
              )}
            </button>
          </div>

          {/* Cold start / progress */}
          {isRunning && !progress && (
            <div className="flex items-center justify-center gap-2 text-sm text-gray-500 py-2">
              <IconLoader2 size={16} className="animate-spin" />
              <span>Connecting to server — first request may take up to a minute to start...</span>
            </div>
          )}
          {progress && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm text-gray-500">
                <span>
                  {fmt(progress.rows_done)} of {fmt(progress.total_rows)} households processed
                </span>
                <span>{progressPct}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-primary-500 h-full rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 text-center">
                Chunk {fmt(progress.chunks_done)} of {fmt(progress.total_chunks)}
              </p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
              <IconAlertCircle size={20} className="text-red-500 flex-shrink-0 mt-0.5" />
              <pre className="text-sm text-red-700 whitespace-pre-wrap font-mono">{error}</pre>
            </div>
          )}

          {/* Output */}
          {outputCsv && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-gray-500">
                  Results — {fmt(resultRows)} {resultRows === 1 ? 'household' : 'households'} processed
                </p>
                <button
                  onClick={downloadOutput}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition"
                >
                  <IconDownload size={16} />
                  Download CSV
                </button>
              </div>
              <div className="bg-secondary-900 rounded-lg overflow-hidden">
                <div className="bg-secondary-800 px-4 py-2">
                  <span className="text-gray-400 text-sm font-mono">Output preview</span>
                </div>
                <pre className="p-4 text-sm text-gray-100 font-mono overflow-x-auto leading-relaxed">
                  {(() => {
                    const { shown, remaining } = previewLines(outputCsv);
                    return (
                      <>
                        {shown.join('\n')}
                        {remaining > 0 && (
                          <span className="text-gray-500">{'\n'}... {fmt(remaining)} more rows</span>
                        )}
                      </>
                    );
                  })()}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CsvRunner;
