import React, { useState, useEffect } from 'react';
import { FiExternalLink, FiClock, FiUser, FiTag, FiGithub } from 'react-icons/fi';
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
    <div className="github-issues-container">
      <div className="github-issues-header">
        <div className="flex items-center space-x-2">
          <FiGithub className="text-gray-600" />
          <h3 className="section-subtitle">GitHub Issues for {selectedState}</h3>
          <span className="issue-count-badge">
            {loading ? '...' : issues.length}
          </span>
        </div>
        <a
          href="https://github.com/PolicyEngine/policyengine-taxsim/issues"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary text-sm"
        >
          <FiExternalLink className="mr-1" />
          View All
        </a>
      </div>

      {loading && (
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <span>Loading issues...</span>
        </div>
      )}

      {error && (
        <div className="error-container">
          <span className="error-message">{error}</span>
        </div>
      )}

      {!loading && !error && issues.length === 0 && (
        <div className="no-issues-message">
          No open issues found for {selectedState}
        </div>
      )}

      {!loading && !error && issues.length > 0 && (
        <div className="issues-list">
          {issues.map((issue) => (
            <div key={issue.id} className="issue-card">
              <div className="issue-header">
                <div className="issue-title-container">
                  <a
                    href={issue.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="issue-title"
                  >
                    #{issue.number} {issue.title}
                    <FiExternalLink className="external-link-icon" />
                  </a>
                </div>
                <div className="issue-meta">
                  <span className="issue-author">
                    <FiUser className="meta-icon" />
                    {issue.author}
                  </span>
                  <span className="issue-date">
                    <FiClock className="meta-icon" />
                    {formatDate(issue.created_at)}
                  </span>
                </div>
              </div>

              {issue.labels.length > 0 && (
                <div className="issue-labels">
                  <FiTag className="label-icon" />
                  {issue.labels.map((label, index) => (
                    <span
                      key={index}
                      className="issue-label"
                      style={{ backgroundColor: getLabelColor(label) }}
                    >
                      {label}
                    </span>
                  ))}
                </div>
              )}

              {issue.body && (
                <div className="issue-body">
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
