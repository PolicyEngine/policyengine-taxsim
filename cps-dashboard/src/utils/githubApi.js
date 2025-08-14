// GitHub API utility for fetching issues from PolicyEngine/policyengine-taxsim repository

const GITHUB_API_BASE = 'https://api.github.com';
const REPO_OWNER = 'PolicyEngine';
const REPO_NAME = 'policyengine-taxsim';

// Cache for GitHub issues to avoid repeated API calls
let issuesCache = null;
let cacheTimestamp = null;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

export const fetchGitHubIssues = async () => {
  // Check cache first
  if (issuesCache && cacheTimestamp && (Date.now() - cacheTimestamp) < CACHE_DURATION) {
    return issuesCache;
  }

  try {
    const response = await fetch(`${GITHUB_API_BASE}/repos/${REPO_OWNER}/${REPO_NAME}/issues?state=open&per_page=100`);
    
    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status} ${response.statusText}`);
    }

    const issues = await response.json();
    
    // Cache the results
    issuesCache = issues;
    cacheTimestamp = Date.now();
    
    return issues;
  } catch (error) {
    console.error('Error fetching GitHub issues:', error);
    return [];
  }
};

// Extract state codes from issue labels and title
export const extractStateFromIssue = (issue) => {
  const stateLabels = issue.labels
    .filter(label => label.name.length === 2 && /^[A-Z]{2}$/.test(label.name))
    .map(label => label.name);
  
  // Also check title for state codes
  const titleStateMatch = issue.title.match(/\b([A-Z]{2})\b/);
  if (titleStateMatch && !stateLabels.includes(titleStateMatch[1])) {
    stateLabels.push(titleStateMatch[1]);
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
