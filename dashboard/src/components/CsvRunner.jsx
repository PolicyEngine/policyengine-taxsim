'use client';

import React, { useState, useRef, useCallback } from 'react';
import {
  IconUpload,
  IconDownload,
  IconX,
  IconLoader2,
  IconFileTypeCsv,
  IconAlertCircle,
} from '@tabler/icons-react';

// Modal deployment URL (set NEXT_PUBLIC_TAXSIM_API_URL to override)
const API_URL = process.env.NEXT_PUBLIC_TAXSIM_API_URL || 'http://localhost:8440';

const SAMPLE_CSV = `taxsimid,year,state,mstat,depx,pwages,swages,page,sage
1,2024,5,2,2,80000,50000,40,38
2,2024,33,1,0,120000,0,35,0
3,2024,44,2,1,60000,40000,30,28`;

const fmt = (n) => Number(n).toLocaleString();

const CsvRunner = () => {
  const [inputCsv, setInputCsv] = useState('');
  const [outputCsv, setOutputCsv] = useState('');
  const [fileName, setFileName] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState('');
  const [rowCount, setRowCount] = useState(0);
  const [resultRows, setResultRows] = useState(0);
  const [idtl, setIdtl] = useState('0');
  const [progress, setProgress] = useState(null); // { chunks_done, total_chunks, rows_done, total_rows }
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const parseCsvRowCount = (csv) => {
    const lines = csv.trim().split('\n');
    return Math.max(0, lines.length - 1); // subtract header
  };

  const handleFileContent = useCallback((content, name) => {
    setInputCsv(content);
    setFileName(name);
    setRowCount(parseCsvRowCount(content));
    setOutputCsv('');
    setError('');
    setProgress(null);
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

  const loadSample = () => {
    handleFileContent(SAMPLE_CSV, 'sample.csv');
  };

  const clearInput = () => {
    setInputCsv('');
    setOutputCsv('');
    setFileName('');
    setRowCount(0);
    setResultRows(0);
    setError('');
    setProgress(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const runTaxsim = async () => {
    if (!inputCsv.trim()) return;
    setIsRunning(true);
    setError('');
    setOutputCsv('');
    setProgress(null);

    try {
      const baseUrl = API_URL.includes('modal.run') ? API_URL : `${API_URL}/run`;
      const streamUrl = API_URL.includes('modal.run') ? API_URL : `${API_URL}/run/stream`;

      const payload = JSON.stringify({
        csv: inputCsv,
        disable_salt: true,
        assume_w2_wages: true,
        idtl: parseInt(idtl, 10),
      });

      // Try SSE streaming first for progress updates
      try {
        const res = await fetch(streamUrl, {
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
          buffer = lines.pop(); // keep incomplete chunk

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
              setProgress(null);
            } else if (evt.type === 'error') {
              throw new Error(evt.error);
            }
          }
        }
      } catch (streamErr) {
        // Fall back to regular POST if streaming not available
        if (streamErr.message !== 'stream-fallback') throw streamErr;

        const res = await fetch(baseUrl, {
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
      }
    } catch (err) {
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        setError(
          'Cannot reach the API server. Make sure it is running:\n\n  uvicorn policyengine_taxsim.api:local_app --port 8440'
        );
      } else {
        setError(err.message);
      }
    } finally {
      setIsRunning(false);
      setProgress(null);
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
          <button
            onClick={(e) => {
              e.stopPropagation();
              loadSample();
            }}
            className="mt-4 text-sm text-primary-500 hover:text-primary-600 underline"
          >
            Or try a sample file
          </button>
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

          {/* Options */}
          <div className="bg-gray-50 rounded-lg px-5 py-4 space-y-4">
            {/* Output detail level */}
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium text-gray-700 min-w-[100px]">Output detail</span>
              <div className="flex flex-wrap gap-2">
                {[
                  { value: '0', label: 'Standard', tip: '9 variables: federal & state tax, FICA, marginal rates' },
                  { value: '2', label: 'Full', tip: '35+ variables: AGI, taxable income, credits, deductions, AMT, and more' },
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

          {/* Run button */}
          <div className="flex justify-center">
            <button
              onClick={runTaxsim}
              disabled={isRunning}
              className={`inline-flex items-center gap-2 px-8 py-3 rounded-lg font-semibold text-white transition ${
                isRunning
                  ? 'bg-primary-400 cursor-not-allowed'
                  : 'bg-primary-500 hover:bg-primary-600'
              }`}
            >
              {isRunning ? (
                <>
                  <IconLoader2 size={18} className="animate-spin" />
                  Processing {fmt(rowCount)} {rowCount === 1 ? 'household' : 'households'}...
                </>
              ) : (
                <>Run the emulator</>
              )}
            </button>
          </div>

          {/* Progress bar */}
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
