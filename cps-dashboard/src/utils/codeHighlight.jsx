import React from 'react';

const TOKEN_CLASS_MAP = {
  kw: 'code-keyword',
  fn: 'code-function',
  str: 'code-string',
  op: 'code-operator',
  var: 'code-variable',
};

function renderTokens(tokenizedLine, parts, keyRef) {
  const tokens = tokenizedLine.split(/(\x01\w+.*?\x02)/);
  tokens.forEach((t) => {
    const match = t.match(/^\x01(\w+)(.*)\x02$/);
    if (match) {
      const prefixLen = match[1].length;
      const className = TOKEN_CLASS_MAP[match[1]] || '';
      parts.push(<span key={keyRef.k++} className={className}>{t.slice(prefixLen + 1, -1)}</span>);
    } else {
      parts.push(<span key={keyRef.k++}>{t}</span>);
    }
  });
}

export const highlightCode = (code, language) => {
  const lines = code.split('\n');
  return lines.map((line, i) => {
    if (line.trimStart().startsWith('#')) {
      return <span key={i}><span className="code-comment">{line}</span>{'\n'}</span>;
    }

    const parts = [];
    const keyRef = { k: 0 };

    if (language === 'cli') {
      const match = line.match(/^(\S+)(.*)/);
      if (match && !line.startsWith('#')) {
        parts.push(<span key={keyRef.k++} className="code-function">{match[1]}</span>);
        const tokenized = match[2]
          .replace(/(-\w+)/g, (m) => `\x01op${m}\x02`)
          .replace(/"([^"]*)"/g, (_, s) => `\x01str"${s}"\x02`);
        renderTokens(tokenized, parts, keyRef);
      } else {
        parts.push(<span key={keyRef.k++}>{line}</span>);
      }
    } else if (language === 'python') {
      const tokenized = line
        .replace(/\b(import|from|as)\b/g, '\x01kw$1\x02')
        .replace(/"([^"]*)"/g, '\x01str"$1"\x02')
        .replace(/(\w+)\s*\(/g, '\x01fn$1\x02(');
      renderTokens(tokenized, parts, keyRef);
    } else if (language === 'r') {
      const tokenized = line
        .replace(/\b(library|setup_policyengine)\b/g, '\x01fn$1\x02')
        .replace(/"([^"]*)"/g, '\x01str"$1"\x02')
        .replace(/<-/g, '\x01op<-\x02')
        .replace(/(\w+)\s*\(/g, '\x01fn$1\x02(');
      renderTokens(tokenized, parts, keyRef);
    } else if (language === 'stata') {
      const tokenized = line
        .replace(/\b(shell|taxsimlocal35|set|gen|export|import|delimited)\b/g, '\x01kw$1\x02')
        .replace(/"([^"]*)"/g, '\x01str"$1"\x02')
        .replace(/,\s*(\w+)/g, ',\x01op $1\x02')
        .replace(/`([^']*)'/, '\x01var`$1\'\x02');
      renderTokens(tokenized, parts, keyRef);
    } else {
      // Fallback: no highlighting
      parts.push(<span key={keyRef.k++}>{line}</span>);
    }

    return <span key={i}>{parts}{'\n'}</span>;
  });
};
