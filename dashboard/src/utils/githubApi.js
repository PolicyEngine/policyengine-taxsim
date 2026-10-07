// GitHub API utility for fetching issues from PolicyEngine/policyengine-taxsim repository
import { GITHUB_CONFIG, STATE_TO_FIPS } from '../constants';

// Cache for GitHub issues to avoid repeated API calls
let issuesCache = null;
let cacheTimestamp = null;

export const fetchGitHubIssues = async () => {
  // Check cache first
  if (issuesCache && cacheTimestamp && (Date.now() - cacheTimestamp) < GITHUB_CONFIG.CACHE_DURATION) {
    return issuesCache;
  }

  try {
    // The API returns at most 100 issues per page, so read pages until a short one
    const issues = [];
    for (let page = 1; page <= GITHUB_CONFIG.MAX_ISSUE_PAGES; page += 1) {
      const response = await fetch(`${GITHUB_CONFIG.API_BASE}/repos/${GITHUB_CONFIG.REPO_OWNER}/${GITHUB_CONFIG.REPO_NAME}/issues?state=open&per_page=${GITHUB_CONFIG.ISSUES_PER_PAGE}&page=${page}`);

      if (!response.ok) {
        throw new Error(`GitHub API error: ${response.status} ${response.statusText}`);
      }

      const batch = await response.json();
      // The issues endpoint also lists pull requests
      issues.push(...batch.filter((item) => !item.pull_request));
      if (batch.length < GITHUB_CONFIG.ISSUES_PER_PAGE) {
        break;
      }
    }
    
    // Cache the results
    issuesCache = issues;
    cacheTimestamp = Date.now();
    
    return issues;
  } catch (error) {
    console.error('Error fetching GitHub issues:', error);
    return [];
  }
};

const isStateCode = (code) => Object.prototype.hasOwnProperty.call(STATE_TO_FIPS, code);

// Extract state codes from issue labels and title
export const extractStateFromIssue = (issue) => {
  const stateLabels = issue.labels
    .map(label => label.name)
    .filter(isStateCode);

  // Also check the title for a state code, skipping other capitals such as "IT-214" or "US"
  const titleState = (issue.title.match(/\b[A-Z]{2}\b/g) || []).find(isStateCode);
  if (titleState && !stateLabels.includes(titleState)) {
    stateLabels.push(titleState);
  }

  return stateLabels;
};

// Group issues by state
export const groupIssuesByState = (issues) => {
  const stateIssues = {};
  
  issues.forEach(issue => {
    const states = extractStateFromIssue(issue);
    
    if (states.length === 0) {
      // Issues without state labels go to 'N/A' category
      if (!stateIssues['N/A']) {
        stateIssues['N/A'] = [];
      }
      stateIssues['N/A'].push(issue);
    } else {
      // Add issue to each state it's associated with
      states.forEach(state => {
        if (!stateIssues[state]) {
          stateIssues[state] = [];
        }
        stateIssues[state].push(issue);
      });
    }
  });
  
  return stateIssues;
};

// Get issues for a specific state
export const getIssuesForState = (issues, stateCode) => {
  if (!stateCode) return [];
  
  return issues.filter(issue => {
    const states = extractStateFromIssue(issue);
    return states.includes(stateCode);
  });
};

// Format issue data for display
export const formatIssue = (issue) => {
  return {
    id: issue.id,
    number: issue.number,
    title: issue.title,
    body: issue.body,
    state: issue.state,
    created_at: issue.created_at,
    updated_at: issue.updated_at,
    html_url: issue.html_url,
    labels: issue.labels.map(label => label.name),
    assignee: issue.assignee?.login,
    author: issue.user?.login
  };
};
