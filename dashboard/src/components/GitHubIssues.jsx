'use client';

import React, { useState, useEffect } from 'react';
import { IconExternalLink, IconClock, IconUser, IconTag, IconBrandGithub } from '@tabler/icons-react';
import { fetchGitHubIssues, getIssuesForState, formatIssue } from '../utils/githubApi';
import { formatDate } from '../utils/formatters';
import { LABEL_COLORS } from '../constants';

const GitHubIssues = ({ selectedState }) => {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadIssues = async () => {
      if (!selectedState) {
        setIssues([]);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const allIssues = await fetchGitHubIssues();
        const stateIssues = getIssuesForState(allIssues, selectedState);
        const formattedIssues = stateIssues.map(formatIssue);
        setIssues(formattedIssues);
      } catch (err) {
        setError('Failed to load GitHub issues');
        console.error('Error loading issues:', err);
      } finally {
        setLoading(false);
      }
    };

    loadIssues();
  }, [selectedState]);


  const getLabelColor = (label) => {
    return LABEL_COLORS[label.toLowerCase()] || '#0366d6';
  };

  if (!selectedState) {
    return null;
  }

  return (
    <div className="px-6 py-6 border-t border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <IconBrandGithub size={18} className="text-gray-600" />
          <h3 className="text-base font-semibold text-secondary-900">GitHub Issues for {selectedState}</h3>
          <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
            {loading ? '...' : issues.length}
          </span>
        </div>
        <a
          href="https://github.com/PolicyEngine/policyengine-taxsim/issues"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center px-3 py-1.5 rounded-md border border-primary-500 text-primary-500 text-xs font-medium bg-white hover:bg-gray-50 transition"
        >
          <IconExternalLink size={12} className="mr-1" />
          View All
        </a>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-6 gap-2 text-gray-500">
          <div className="w-5 h-5 border-2 border-gray-200 border-t-primary-500 rounded-full animate-spin"></div>
          <span className="text-sm">Loading issues...</span>
        </div>
      )}

      {error && (
        <div className="py-4 px-4 bg-error/5 rounded-lg">
          <span className="text-sm text-error">{error}</span>
        </div>
      )}

      {!loading && !error && issues.length === 0 && (
        <div className="text-center py-6 text-sm text-gray-500">
          No open issues found for {selectedState}
        </div>
      )}

      {!loading && !error && issues.length > 0 && (
        <div className="space-y-3">
          {issues.map((issue) => (
            <div key={issue.id} className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition">
              <div>
                <div>
                  <a
                    href={issue.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-primary-500 hover:text-primary-600 hover:underline"
                  >
                    #{issue.number} {issue.title}
                    <IconExternalLink size={12} className="inline ml-1 opacity-50" />
                  </a>
                </div>
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
              </div>

              {issue.labels.length > 0 && (
                <div className="flex items-center gap-1.5 mt-2">
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
                    ? `${issue.body.substring(0, 200)}...`
                    : issue.body
                  }
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default GitHubIssues;
