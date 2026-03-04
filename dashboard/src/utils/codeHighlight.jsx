import Prism from 'prismjs';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-r';
import 'prismjs/components/prism-bash';

// Map our language codes to Prism grammar names
const LANG_MAP = {
  cli: 'bash',
  python: 'python',
  r: 'r',
  stata: 'bash', // closest available grammar
};

export const highlightCode = (code, language) => {
  const prismLang = LANG_MAP[language] || 'bash';
  const grammar = Prism.languages[prismLang];

  if (!grammar) {
    return code;
  }

  const html = Prism.highlight(code, grammar, prismLang);
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
};
