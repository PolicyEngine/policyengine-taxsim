'use client';

import React, { useState, useEffect } from 'react';
import {
  IconExternalLink,
  IconClock,
  IconUser,
  IconTag,
  IconBrandGithub,
  IconInfoCircle,
} from '@tabler/icons-react';
import { fetchGitHubIssues, getIssuesByLabel, formatIssue } from '../utils/githubApi';
import { formatDate } from '../utils/formatters';
import { LABEL_COLORS } from '../constants';

const MODEL_DIFFERENCE_LABEL = 'model-difference';

const CONVENTIONS = [
  {
    id: 'ctc-split',
    title: 'Child Tax Credit output split (v22 / actc)',
    summary:
      'v22 reports the non-refundable CTC (capped at tax liability) for non-fully-refundable years, or the total CTC for fully-refundable years (2021 ARPA). The separate actc field reports the refundable (Additional) CTC.',
    detail:
      'For most years (2018–2020, 2022+), v22 = min(ctc, ctc_limiting_tax_liability). For 2021 under ARPA, the entire CTC is fully refundable so v22 = total CTC and actc equals v22.',
  },
  {
    id: 'state-eitc-bundling',
    title: 'State EITC output bundles working-family credits',
    summary:
      'The v39 state EITC field includes state-specific EITC match credits plus similar non-federal-style working-family credits: Minnesota Working Family Credit, Missouri Working Families Tax Credit (TY 2023+), and Washington Working Families Tax Credit (TY 2023+).',
    detail:
      'For states with split refundable/non-refundable EITCs (Maryland, Virginia), both components are summed. For Kansas, the single ks_total_eitc variable covers both.',
  },
  {
    id: 'filing-status-auto',
    title: 'Filing status auto-detection for single filers with dependents',
    summary:
      'Both PolicyEngine and TAXSIM treat mstat=1 (single) with at least one qualifying dependent as head-of-household for threshold and bracket purposes.',
    detail:
      'This affects standard deduction, tax brackets, and phase-out thresholds for credits like the CTC ARPA addition ($112,500 HoH threshold vs $75,000 single).',
  },
  {
    id: 'income-splitting',
    title: 'Spouse income splitting',
    summary:
      'For joint returns (mstat=2), household-level income inputs (capital gains, interest, dividends, pensions, transfers) are split 50/50 between the primary and secondary filers for person-level allocations.',
    detail:
      'Wage inputs (pwages, swages) are assigned to individuals as specified. Self-employment income (psemp, ssemp) and profession-specific inputs (pbusinc, pprofinc, sprofinc) are also assigned per-filer.',
  },
  {
    id: 'addl-medicare-tax',
    title: 'Additional Medicare Tax included in fiitax',
    summary:
      'TAXSIM reports the 0.9% Additional Medicare Tax on wages above $200k (single) / $250k (MFJ) as part of fiitax. PolicyEngine adds this to its income_tax base so the fiitax output matches TAXSIM.',
    detail: null,
  },
  {
    id: 'non-refundable-ordering',
    title: 'State non-refundable credit ordering follows form order',
    summary:
      'When multiple non-refundable state credits apply, they are subtracted from tax liability in the order specified by the state tax form (e.g., Delaware applies personal credits before the EITC per Form PIT-RES lines 26a → 33).',
    detail:
      'This can affect the reported amount of individual credits when the pre-credit tax liability is consumed by earlier-ordered credits.',
  },
];

const ModelDifferences = () => {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    const loadIssues = async () => {
      setLoading(true);
      setError(null);
      try {
        const allIssues = await fetchGitHubIssues();
        const labeledIssues = getIssuesByLabel(allIssues, MODEL_DIFFERENCE_LABEL).map(
          formatIssue
        );
        setIssues(labeledIssues);
      } catch (err) {
        setError('Failed to load GitHub issues');
        console.error('Error loading model-difference issues:', err);
      } finally {
        setLoading(false);
      }
    };
    loadIssues();
  }, []);

  const getLabelColor = (label) => {
    return LABEL_COLORS[label.toLowerCase()] || '#0366d6';
  };

  return (
    <section className="space-y-6">
      {/* Intro */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
        <div className="flex items-start gap-3">
          <IconInfoCircle size={20} className="text-primary-500 mt-0.5" />
          <div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">
              How PolicyEngine and TAXSIM compare
            </h3>
            <p className="text-sm text-gray-600 leading-relaxed">
              PolicyEngine and TAXSIM implement the same underlying tax code
              but differ in a few documented conventions. This page covers the
              architectural choices that stay stable, and a live feed of open
              divergences being tracked on GitHub.
            </p>
          </div>
        </div>
      </div>

      {/* Conventions (static) */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-bold text-gray-900 mb-4">
          Output conventions
        </h3>
        <div className="space-y-3">
          {CONVENTIONS.map((conv) => {
            const isExpanded = expandedId === conv.id;
            return (
              <div
                key={conv.id}
                className="border border-gray-200 rounded-lg overflow-hidden"
              >
                <button
                  onClick={() => setExpandedId(isExpanded ? null : conv.id)}
                  className="w-full px-4 py-3 text-left hover:bg-gray-50 transition"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-gray-900">
                        {conv.title}
                      </h4>
                      <p className="text-sm text-gray-600 mt-1 leading-relaxed">
                        {conv.summary}
                      </p>
                    </div>
                    {conv.detail && (
                      <span className="text-xs text-primary-500 font-medium shrink-0 mt-0.5">
                        {isExpanded ? 'Hide' : 'More'}
                      </span>
                    )}
                  </div>
                </button>
                {isExpanded && conv.detail && (
                  <div className="px-4 pb-3 pt-0 text-sm text-gray-600 leading-relaxed border-t border-gray-100 bg-gray-50">
                    <p className="pt-3">{conv.detail}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Dynamic issues */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <IconBrandGithub size={18} className="text-gray-600" />
            <h3 className="text-lg font-bold text-gray-900">
              Known differences under investigation
            </h3>
            <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
              {loading ? '…' : issues.length}
            </span>
          </div>
          <a
            href={`https://github.com/PolicyEngine/policyengine-taxsim/issues?q=is%3Aissue+is%3Aopen+label%3A${MODEL_DIFFERENCE_LABEL}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-3 py-1.5 rounded-md border border-primary-500 text-primary-500 text-xs font-medium bg-white hover:bg-gray-50 transition"
          >
            <IconExternalLink size={12} className="mr-1" />
            View on GitHub
          </a>
        </div>
        <p className="text-sm text-gray-600 mb-4 leading-relaxed">
          Issues tagged{' '}
          <code className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 text-xs font-mono">
            {MODEL_DIFFERENCE_LABEL}
          </code>{' '}
          document current PolicyEngine vs. TAXSIM divergences and link to the
          statute or form instructions for each case. They disappear from this
          list when closed.
        </p>

        {loading && (
          <div className="flex items-center justify-center py-6 gap-2 text-gray-500">
            <div className="w-5 h-5 border-2 border-gray-200 border-t-primary-500 rounded-full animate-spin"></div>
            <span className="text-sm">Loading…</span>
          </div>
        )}

        {error && (
          <div className="py-4 px-4 bg-error/5 rounded-lg">
            <span className="text-sm text-error">{error}</span>
          </div>
        )}

        {!loading && !error && issues.length === 0 && (
          <div className="text-center py-6 text-sm text-gray-500">
            No open model-difference issues.
          </div>
        )}

        {!loading && !error && issues.length > 0 && (
          <div className="space-y-3">
            {issues.map((issue) => (
              <div
                key={issue.id}
                className="border border-gray-200 rounded-lg p-4 hover:shadow-sm transition"
              >
                <a
                  href={issue.html_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-primary-500 hover:text-primary-600 hover:underline"
                >
                  #{issue.number} {issue.title}
                  <IconExternalLink size={12} className="inline ml-1 opacity-50" />
                </a>
                <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
                  <span className="inline-flex items-center gap-1">
                    <IconUser size={12} />
                    {issue.author}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <IconClock size={12} />
                    {formatDate(issue.created_at)}
                  </span>
                </div>
                {issue.labels.length > 0 && (
                  <div className="flex items-center flex-wrap gap-1.5 mt-2">
                    <IconTag size={12} className="text-gray-400" />
                    {issue.labels.map((label, index) => (
                      <span
                        key={index}
                        className="px-2 py-0.5 rounded-full text-xs font-medium text-white"
                        style={{ backgroundColor: getLabelColor(label) }}
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                )}
                {issue.body && (
                  <div className="mt-2 text-xs text-gray-500 leading-relaxed">
                    {issue.body.length > 200
                      ? `${issue.body.substring(0, 200)}…`
                      : issue.body}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

export default ModelDifferences;
